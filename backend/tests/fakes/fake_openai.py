"""Fake OpenAI-compatible provider for package 01 integration tests (compose service `fake-llm`).

Stdlib only, so it runs in the backend image without extra packages. Behaviour is chosen by the
upstream model id LiteLLM sends (the part after "openai/"):

- `fail-*`  answers 500 (a provider that is down)
- `empty-*` answers with empty content
- `slow-*`  streams 20 chunks, 0.25 s apart (a long stream during a catalog change)
- `tool-*`  with `tools` in the request: one call of the first tool, its required arguments
            filled with sample values (TOOL_SAMPLES, else by type); once the last message is a
            tool result: "hello " + the result's first 50 characters; without tools: "hello"
            (plan/18 F3/F4/F11, 10b-poc-2; K-SEN-0025)
- anything else answers "hello" (streamed with a final usage chunk when asked)

Every request body is recorded; GET /_requests returns them, POST /_reset clears them. Values
here are fake; nothing leaves the compose network.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_requests: list[dict] = []
_lock = threading.Lock()
USAGE = {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}
# Sample values for well-known argument names of the scenario tools; others go by type.
TOOL_SAMPLES = {
    "ticket_id": "tkt-001",
    "body": "hello",
    "sql": "SELECT code FROM departments LIMIT 1",
    "reason": "fake",
    "query": "hello",
}
TYPE_SAMPLES = {
    "string": "hello",
    "integer": 1,
    "number": 1,
    "boolean": True,
    "array": [],
    "object": {},
}


def _tool_call(tools: list[dict]) -> dict:
    """One call of the first tool, required arguments only."""
    function = tools[0]["function"]
    schema = function.get("parameters") or {}
    properties = schema.get("properties") or {}
    arguments = {
        name: TOOL_SAMPLES.get(
            name, TYPE_SAMPLES.get(properties.get(name, {}).get("type"), "hello")
        )
        for name in schema.get("required") or []
    }
    return {
        "id": "call_fake_1",
        "type": "function",
        "function": {"name": function["name"], "arguments": json.dumps(arguments)},
    }


def _tool_turn(body: dict) -> tuple[str, dict | None]:
    """`tool-*` model: (text, tool_call) for this request."""
    messages = body.get("messages") or []
    if messages and messages[-1].get("role") == "tool":
        return "hello " + str(messages[-1].get("content") or "")[:50], None
    if body.get("tools"):
        return "", _tool_call(body["tools"])
    return "hello", None


def _chunk(model: str, delta: dict, finish: str | None = None, usage: dict | None = None) -> bytes:
    body = {
        "id": "fake",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    if usage is not None:
        body["usage"] = usage
    return f"data: {json.dumps(body)}\n\n".encode()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _json(self, status: int, body: object) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/_requests":
            with _lock:
                self._json(200, list(_requests))
        elif self.path.endswith("/models"):
            self._json(200, {"object": "list", "data": []})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/_reset":
            with _lock:
                _requests.clear()
            self._json(200, {"ok": True})
            return
        if not self.path.endswith("/chat/completions"):
            self._json(404, {"error": "not found"})
            return
        with _lock:
            _requests.append(body)
        model = str(body.get("model", ""))
        if model.startswith("fail"):
            self._json(500, {"error": {"message": "fake provider is down", "type": "server_error"}})
            return
        text, call = "" if model.startswith("empty") else "hello", None
        if model.startswith("tool"):
            text, call = _tool_turn(body)
        if body.get("stream"):
            self._stream(model, text, slow=model.startswith("slow"), call=call)
            return
        message = {"role": "assistant", "content": text}
        if call is not None:
            message = {"role": "assistant", "content": None, "tool_calls": [call]}
        self._json(
            200,
            {
                "id": "fake",
                "object": "chat.completion",
                "created": 0,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": message,
                        "finish_reason": "tool_calls" if call else "stop",
                    }
                ],
                "usage": USAGE,
            },
        )

    def _stream(self, model: str, text: str, slow: bool, call: dict | None = None) -> None:
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()
        pieces = [f"t{i} " for i in range(20)] if slow else ([text] if text else [])
        for piece in pieces:
            self._write(_chunk(model, {"content": piece}))
            if slow:
                time.sleep(0.25)
        if call is not None:
            self._write(_chunk(model, {"role": "assistant", "tool_calls": [{"index": 0, **call}]}))
        self._write(_chunk(model, {}, finish="tool_calls" if call else "stop"))
        self._write(_chunk(model, {}, usage=USAGE))
        self._write(b"data: [DONE]\n\n")
        self.wfile.write(b"0\r\n\r\n")

    def _write(self, data: bytes) -> None:
        self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
        self.wfile.flush()

    def log_message(self, *args) -> None:
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9999), Handler).serve_forever()
