"""OpenAPI document -> MCP tool definitions, and tool arguments -> one upstream request (05b).

Rules (plan/05 A3, K-05B-0002):
- operationId is the tool name; parameters and the JSON request body form input_schema
  (`body` holds the request body); description is the operation's description or summary.
- Only local references (`#/...`) are resolved; an external reference, a reference cycle, a
  header or cookie parameter, a non-JSON body or an unusable name makes the operation not
  exposable, with the reason (never dropped silently, ARCH-06).
- Arguments are checked against the operation's parameters before anything is sent: unknown
  names, missing required values, null and nested values for path/query parameters are
  refused. Path values are percent-encoded whole (a value cannot add path segments).
"""

import copy
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import yaml

MAX_SPEC_CHARS = 1_000_000
METHODS = ("get", "post", "put", "patch", "delete")
# MCP tool names (the SDK's limit) and FFCore's C7 `<tool_key>__<action>` both fit this.
TOOL_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
BODY = "body"
_MAX_REF_DEPTH = 32


class SpecError(ValueError):
    """The document cannot be used: spec_invalid, spec_too_large, spec_version_unsupported."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ArgumentsError(ValueError):
    """The arguments do not fit the operation (invalid_arguments); nothing is sent."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.code = "invalid_arguments"


class _Unpublishable(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class UpstreamRequest:
    method: str
    path: str
    params: dict[str, Any] = field(default_factory=dict)
    json: Any = None


def load_spec(text: str) -> dict:
    """A YAML or JSON OpenAPI 3 document as a dict (JSON is YAML; safe_load only)."""
    if len(text) > MAX_SPEC_CHARS:
        raise SpecError("spec_too_large", f"The document is larger than {MAX_SPEC_CHARS} chars.")
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError:
        raise SpecError("spec_invalid", "The document is not valid YAML or JSON.") from None
    if not isinstance(doc, dict):
        raise SpecError("spec_invalid", "The document is not an OpenAPI object.")
    version = doc.get("openapi")
    if version is None:
        if "swagger" in doc:
            raise SpecError("spec_version_unsupported", "Only OpenAPI 3 documents are accepted.")
        raise SpecError("spec_invalid", "The document has no `openapi` version.")
    if not str(version).startswith("3."):
        raise SpecError("spec_version_unsupported", "Only OpenAPI 3 documents are accepted.")
    if not isinstance(doc.get("paths"), dict):
        raise SpecError("spec_invalid", "The document has no `paths` object.")
    return doc


class _Resolver:
    def __init__(self, doc: dict) -> None:
        self.doc = doc

    def _target(self, ref: str) -> Any:
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise _Unpublishable("external_ref")
        node: Any = self.doc
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(node, dict) or part not in node:
                raise _Unpublishable("ref_not_found")
            node = node[part]
        return node

    def resolve(self, node: Any, seen: tuple[str, ...] = ()) -> Any:
        """A copy of `node` with every local $ref replaced; a cycle is refused."""
        if len(seen) > _MAX_REF_DEPTH:
            raise _Unpublishable("ref_cycle")
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                if ref in seen:
                    raise _Unpublishable("ref_cycle")
                return self.resolve(self._target(ref), (*seen, ref))
            return {k: self.resolve(v, seen) for k, v in node.items()}
        if isinstance(node, list):
            return [self.resolve(v, seen) for v in node]
        return copy.deepcopy(node)


def _schema_of(parameter: dict) -> dict:
    schema = dict(parameter.get("schema") or {"type": "string"})
    if parameter.get("description") and "description" not in schema:
        schema["description"] = parameter["description"]
    return schema


def _operation(resolver: _Resolver, path: str, method: str, item: dict, op: dict) -> dict:
    name = op.get("operationId")
    entry = {
        "name": name or f"{method}:{path}",
        "method": method.upper(),
        "path": path,
        "description": op.get("description") or op.get("summary"),
        "input_schema": {"type": "object", "properties": {}},
        "exposable": False,
        "reason": None,
        "alias": None,
        "alias_description": None,
    }
    try:
        if not name:
            raise _Unpublishable("operation_id_missing")
        if not TOOL_NAME.fullmatch(name):
            raise _Unpublishable("operation_name_invalid")
        params: dict[tuple[str, str], dict] = {}
        for raw in [*(item.get("parameters") or []), *(op.get("parameters") or [])]:
            parameter = resolver.resolve(raw)
            params[(parameter.get("name"), parameter.get("in"))] = parameter
        properties: dict[str, Any] = {}
        required: list[str] = []
        locations: dict[str, str] = {}
        for (pname, where), parameter in params.items():
            if where not in ("path", "query"):
                raise _Unpublishable("parameter_location_unsupported")
            if not isinstance(pname, str) or pname == BODY or pname in properties:
                raise _Unpublishable("parameter_name_conflict")
            properties[pname] = _schema_of(parameter)
            locations[pname] = where
            if where == "path" or parameter.get("required"):
                required.append(pname)
        body = op.get("requestBody")
        if body is not None:
            body = resolver.resolve(body)
            content = body.get("content") or {}
            if "application/json" not in content:
                raise _Unpublishable("request_body_unsupported")
            properties[BODY] = resolver.resolve(content["application/json"].get("schema") or {})
            if body.get("required"):
                required.append(BODY)
        schema: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        entry["input_schema"] = schema
        entry["locations"] = locations
        entry["exposable"] = True
    except _Unpublishable as exc:
        entry["reason"] = exc.reason
    return entry


def catalog(doc: dict) -> list[dict]:
    """Every operation of the document, publishable or not (with its reason)."""
    resolver = _Resolver(doc)
    found = []
    for path, item in doc["paths"].items():
        if not isinstance(item, dict):
            continue
        for method in METHODS:
            op = item.get(method)
            if isinstance(op, dict):
                found.append(_operation(resolver, path, method, item, op))
    names = [op["name"] for op in found]
    for op in found:
        if op["exposable"] and names.count(op["name"]) > 1:
            op["exposable"], op["reason"] = False, "operation_id_duplicate"
    return found


def _scalar(name: str, value: Any) -> Any:
    if value is None or isinstance(value, dict):
        raise ArgumentsError(f"{name} must be a plain value")
    if isinstance(value, list):
        if any(v is None or isinstance(v, dict | list) for v in value):
            raise ArgumentsError(f"{name} must hold plain values")
        return [str(v).lower() if isinstance(v, bool) else v for v in value]
    return str(value).lower() if isinstance(value, bool) else value


def build_request(op: dict, arguments: dict[str, Any]) -> UpstreamRequest:
    """The upstream request for `arguments`; the caller joins `path` to the registered base URL."""
    if not isinstance(arguments, dict):
        raise ArgumentsError("arguments must be an object")
    schema = op["input_schema"]
    properties = schema.get("properties", {})
    unknown = set(arguments) - set(properties)
    if unknown:
        raise ArgumentsError("unknown arguments")
    missing = [n for n in schema.get("required", []) if arguments.get(n) is None]
    if missing:
        raise ArgumentsError("missing required arguments")
    locations = op.get("locations", {})
    path, params = op["path"], {}
    for name, value in arguments.items():
        where = locations.get(name)
        if where == "path":
            path = path.replace("{" + name + "}", quote(str(_scalar(name, value)), safe=""))
        elif where == "query":
            if value is not None:
                params[name] = _scalar(name, value)
    if "{" in path:
        raise ArgumentsError("missing path arguments")
    body = arguments.get(BODY) if BODY in properties else None
    return UpstreamRequest(op["method"], path, params, body)
