"""Test only (package 16-2): a fake Confluence and Jira, Server/Data Center and Cloud.

Stdlib only; never part of an installation; no real Atlassian address is contacted anywhere in
the tests: this server is the source. It serves the subset FFCore's drivers call, from synthetic
data loaded with `POST /_state`, and records every request so a test can prove what the sync
asked for (`GET /_requests`; a gold run must leave it empty, a delta run must ask only for the
changed page).

Confluence (DC paths; Cloud adds the `/wiki` prefix):
  GET /rest/api/content/search?cql=&expand=&limit=&start=    pages with body.storage (DC)
  GET /rest/api/search?cql=&limit=&start=                    totalSize, results (count; Cloud listing)
  GET /api/v2/pages/{id}?body-format=storage                 Cloud page with body (under /wiki)
  GET /api/v2/pages/{id}/attachments?cursor=                 Cloud attachments (under /wiki)
  GET /rest/api/content/{id}/child/attachment                DC attachments (all versions)
  GET /rest/api/content/{id}/restriction/byOperation/read    page read restrictions
  GET /download/attachments/{id}/{name}                      attachment bytes
Jira:
  GET /rest/api/2/search?jql=&startAt=&maxResults=&fields=   DC (startAt), total
  GET /rest/api/2/search/jql?jql=&nextPageToken=&maxResults=  Cloud (token, no total)
  GET /rest/api/2/issue/{key}; POST /rest/api/2/issue; POST /rest/api/2/issue/{key}/comment
  GET /secure/attachment/{id}/{name}
Links (`_links.next`, `_links.download`, `downloadLink`) are relative to the API base, as
Confluence returns them: `/rest/...` under the DC base or the Cloud `/wiki` base.
Control: GET /_requests, POST /_reset (requests only), POST /_state (data and credentials),
POST /_fault {"cut_listing_after": n, "rate_limit": n, "retry_after": s}, GET /healthz.

Query support is exactly what the drivers send: CQL `type=page`, `space = K`, `space in (A,B)`,
`lastmodified >= now("-Nm")`; JQL `project in (A,B)`, `project = K`, `updated >= "-Nm"`,
`ORDER BY updated ASC`, an outer `(…) AND` wrapper. Anything else is 400 (a driver that sends
another query must fail the test, not get a guess).
"""

import base64
import json
import re
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlsplit

LOCK = threading.Lock()
STATE: dict = {}
REQUESTS: list[dict] = []
FAULT: dict = {}


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_when(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class QueryError(ValueError):
    pass


def _minutes(clause: str, field: str) -> int | None:
    match = re.search(field + r'\s*>=\s*(?:now\()?"-(\d+)m"\)?', clause, re.I)
    return int(match.group(1)) if match else None


def _keys(clause: str, field: str) -> set[str] | None:
    many = re.search(field + r"\s+in\s*\(([^)]*)\)", clause, re.I)
    if many:
        return {k.strip().strip('"') for k in many.group(1).split(",") if k.strip()}
    one = re.search(field + r'\s*=\s*"?([A-Za-z0-9_~-]+)"?', clause, re.I)
    return {one.group(1)} if one else None


def _check_cql(cql: str) -> None:
    rest = re.sub(r'lastmodified\s*>=\s*now\("-\d+m"\)', "", cql, flags=re.I)
    rest = re.sub(r"space\s+in\s*\([^)]*\)|space\s*=\s*\"?[A-Za-z0-9_~-]+\"?", "", rest, flags=re.I)
    rest = re.sub(r"type\s*=\s*page", "", rest, flags=re.I)
    if re.sub(r"\b(and)\b|[\s()]", "", rest, flags=re.I):
        raise QueryError(f"unsupported CQL: {cql}")


def _check_jql(jql: str) -> None:
    rest = re.sub(r"order\s+by\s+updated\s+asc\s*$", "", jql.strip(), flags=re.I)
    rest = re.sub(r'updated\s*>=\s*"-\d+m"', "", rest, flags=re.I)
    rest = re.sub(r"project\s+in\s*\([^)]*\)|project\s*=\s*\"?[A-Za-z0-9_-]+\"?", "", rest, flags=re.I)
    if re.sub(r"\b(and)\b|[\s()]", "", rest, flags=re.I):
        raise QueryError(f"unsupported JQL: {jql}")


def _pages(cql: str) -> list[dict]:
    _check_cql(cql)
    confluence = STATE.get("confluence", {})
    permitted = {k for k, v in confluence.get("spaces", {}).items() if v.get("permitted", True)}
    spaces = _keys(cql, "space")
    minutes = _minutes(cql, "lastmodified")
    since = _now() - timedelta(minutes=minutes) if minutes is not None else None
    out = []
    for page in sorted(confluence.get("pages", []), key=lambda p: p["id"]):
        if page["space"] not in permitted or (spaces is not None and page["space"] not in spaces):
            continue
        if since is not None and _parse_when(page["when"]) < since:
            continue
        out.append(page)
    return out


def _issues(jql: str) -> list[dict]:
    _check_jql(jql)
    jira = STATE.get("jira", {})
    permitted = {k for k, v in jira.get("projects", {}).items() if v.get("permitted", True)}
    projects = _keys(jql, "project")
    minutes = _minutes(jql, "updated")
    since = _now() - timedelta(minutes=minutes) if minutes is not None else None
    out = []
    for issue in jira.get("issues", []):
        project = issue["key"].split("-")[0]
        if project not in permitted or (projects is not None and project not in projects):
            continue
        if since is not None and _parse_when(issue["fields"]["updated"]) < since:
            continue
        out.append(issue)
    return sorted(out, key=lambda i: i["fields"]["updated"])


def _page_json(page: dict, base: str, *, body: bool) -> dict:
    data = {
        "id": page["id"],
        "type": "page",
        "status": page.get("status", "current"),
        "title": page["title"],
        "space": {"key": page["space"]},
        "version": {"number": page.get("version", 1), "when": page["when"]},
        "ancestors": [{"id": a["id"], "title": a["title"]} for a in page.get("ancestors", [])],
        "metadata": {"labels": {"results": [{"name": n} for n in page.get("labels", [])]}},
        "_links": {"webui": f"/spaces/{page['space']}/pages/{page['id']}"},
    }
    if body:
        data["body"] = {"storage": {"value": page["body"], "representation": "storage"}}
    return data


def _attachment_json(page: dict, att: dict, prefix: str) -> dict:
    name = att["title"]
    return {
        "id": f"att-{page['id']}-{name}",
        "title": name,
        "extensions": {"fileSize": att.get("size", len(_content(att))), "mediaType": att.get("mediaType")},
        "version": {"number": att.get("version", 1), "when": att.get("when", page["when"])},
        "_links": {"download": f"/download/attachments/{page['id']}/{quote(name)}"},
    }


def _content(att: dict) -> bytes:
    if "content_b64" in att:
        return base64.b64decode(att["content_b64"])
    return att.get("content", "").encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "fake-atlassian/1"

    def log_message(self, *args) -> None:  # quiet: the tests read /_requests
        return

    # -- helpers -------------------------------------------------------------------------

    def _send(self, status: int, payload=None, *, raw: bytes | None = None, headers=None) -> None:
        body = raw if raw is not None else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/octet-stream" if raw is not None else "application/json")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        expected = STATE.get("auth")
        if not expected:
            return True
        return self.headers.get("Authorization") in expected

    def _record(self, url) -> None:
        with LOCK:
            REQUESTS.append(
                {"method": self.command, "path": url.path, "query": parse_qs(url.query)}
            )

    def _fault(self) -> bool:
        with LOCK:
            remaining = FAULT.get("rate_limit", 0)
            if remaining:
                FAULT["rate_limit"] = remaining - 1
        if remaining:
            self._send(429, {"message": "rate limited"}, headers={"Retry-After": str(FAULT.get("retry_after", 1))})
            return True
        return False

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    # -- control -----------------------------------------------------------------------

    def _control(self, url) -> bool:
        global STATE
        if url.path == "/healthz":
            self._send(200, {"status": "ok"})
        elif url.path == "/_requests":
            with LOCK:
                self._send(200, {"requests": list(REQUESTS)})
        elif url.path == "/_reset" and self.command == "POST":
            with LOCK:
                REQUESTS.clear()
                FAULT.clear()
            self._send(200, {"ok": True})
        elif url.path == "/_state" and self.command == "POST":
            data = self._body()
            with LOCK:
                STATE = data
                STATE.setdefault("writes", [])
                REQUESTS.clear()
                FAULT.clear()
            self._send(200, {"ok": True})
        elif url.path == "/_state" and self.command == "GET":
            with LOCK:
                self._send(200, STATE)
        elif url.path == "/_fault" and self.command == "POST":
            data = self._body()
            with LOCK:
                FAULT.clear()
                FAULT.update(data)
            self._send(200, {"ok": True})
        else:
            return False
        return True

    # -- routes --------------------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        self._route()

    def do_POST(self) -> None:  # noqa: N802
        self._route()

    def _route(self) -> None:
        url = urlsplit(self.path)
        if self._control(url):
            return
        self._record(url)
        if not self._authorized():
            self._send(401, {"message": "unauthorized"})
            return
        if self._fault():
            return
        path, prefix = url.path, ""
        if path.startswith("/wiki/"):
            path, prefix = path[len("/wiki"):], "/wiki"
        query = {k: v[-1] for k, v in parse_qs(url.query).items()}
        try:
            self._dispatch(path, prefix, query)
        except QueryError as exc:
            self._send(400, {"message": str(exc)})

    def _listing_cut(self, start: int) -> bool:
        cut = FAULT.get("cut_listing_after")
        if cut is not None and start >= cut:
            # The connection drops in the middle of a listing (a proxy, a restart).
            self.close_connection = True
            self.connection.shutdown(2)
            return True
        return False

    def _dispatch(self, path: str, prefix: str, q: dict) -> None:
        base = f"http://{self.headers.get('Host')}{prefix}"
        if path == "/rest/api/content/search":
            pages = _pages(q.get("cql", ""))
            start, limit = int(q.get("start", 0)), min(int(q.get("limit", 25)), 50)
            if self._listing_cut(start):
                return
            chunk = pages[start : start + limit]
            body = "body.storage" in q.get("expand", "")
            payload = {"results": [_page_json(p, base, body=body) for p in chunk], "start": start, "limit": limit, "size": len(chunk), "_links": {}}
            if start + limit < len(pages):
                payload["_links"]["next"] = f"/rest/api/content/search?cql={quote(q.get('cql', ''))}&expand={quote(q.get('expand', ''))}&limit={limit}&start={start + limit}"
            self._send(200, payload)
        elif path == "/rest/api/search":
            pages = _pages(q.get("cql", ""))
            start, limit = int(q.get("start", 0)), min(int(q.get("limit", 25)), 50)
            if limit > 1 and self._listing_cut(start):
                return
            chunk = pages[start : start + limit]
            payload = {
                "results": [{"content": _page_json(p, base, body=False)} for p in chunk],
                "totalSize": len(pages),
                "start": start,
                "limit": limit,
                "size": len(chunk),
                "_links": {},
            }
            if start + limit < len(pages):
                payload["_links"]["next"] = f"/rest/api/search?cql={quote(q.get('cql', ''))}&limit={limit}&start={start + limit}"
            self._send(200, payload)
        elif m := re.fullmatch(r"/api/v2/pages/([^/]+)", path):
            page = self._page(m.group(1))
            if page is None:
                return
            data = _page_json(page, base, body=False)
            data["spaceId"] = page["space"]
            data["parentId"] = page["ancestors"][-1]["id"] if page.get("ancestors") else None
            data["body"] = {"storage": {"value": page["body"], "representation": "storage"}}
            self._send(200, data)
        elif m := re.fullmatch(r"/api/v2/pages/([^/]+)/attachments", path):
            page = self._page(m.group(1))
            if page is None:
                return
            results = []
            for att in page.get("attachments", []):
                item = _attachment_json(page, att, prefix)
                results.append({"id": item["id"], "title": item["title"], "fileSize": item["extensions"]["fileSize"], "mediaType": att.get("mediaType"), "version": item["version"], "downloadLink": item["_links"]["download"]})
            self._send(200, {"results": results, "_links": {}})
        elif m := re.fullmatch(r"/rest/api/content/([^/]+)/child/attachment", path):
            page = self._page(m.group(1))
            if page is None:
                return
            results = [_attachment_json(page, a, prefix) for a in page.get("attachments", [])]
            self._send(200, {"results": results, "size": len(results), "_links": {}})
        elif m := re.fullmatch(r"/rest/api/content/([^/]+)/restriction/byOperation/read", path):
            page = self._page(m.group(1))
            if page is None:
                return
            restriction = page.get("restrictions", {})
            self._send(200, {
                "operation": "read",
                "restrictions": {
                    "group": {"results": [{"type": "group", "name": g} for g in restriction.get("groups", [])]},
                    "user": {"results": [{"type": "known", "username": u, "accountId": u} for u in restriction.get("users", [])]},
                },
            })
        elif m := re.fullmatch(r"/download/attachments/([^/]+)/(.+)", path):
            page = self._page(m.group(1))
            if page is None:
                return
            name = unquote(m.group(2))
            att = next((a for a in page.get("attachments", []) if a["title"] == name), None)
            if att is None or att.get("gone"):
                self._send(404, {"message": "attachment not found"})
                return
            self._send(200, raw=_content(att))
        elif path in ("/rest/api/2/search", "/rest/api/2/search/jql"):
            self._jira_search(path, q)
        elif m := re.fullmatch(r"/rest/api/2/issue/([A-Z][A-Z0-9]*-\d+)", path):
            issue = next((i for i in STATE.get("jira", {}).get("issues", []) if i["key"] == m.group(1)), None)
            if issue is None:
                self._send(404, {"errorMessages": ["Issue does not exist"]})
            else:
                self._send(200, {"key": issue["key"], "fields": issue["fields"]})
        elif path == "/rest/api/2/issue" and self.command == "POST":
            data = self._body()
            with LOCK:
                STATE["writes"].append({"kind": "issue", "body": data})
            self._send(201, {"id": "90001", "key": f"{data['fields']['project']['key']}-9001"})
        elif m := re.fullmatch(r"/rest/api/2/issue/([A-Z][A-Z0-9]*-\d+)/comment", path):
            data = self._body()
            with LOCK:
                STATE["writes"].append({"kind": "comment", "issue": m.group(1), "body": data})
            self._send(201, {"id": "80001", "created": _now().isoformat()})
        elif m := re.fullmatch(r"/secure/attachment/([^/]+)/(.+)", path):
            name = unquote(m.group(2))
            for issue in STATE.get("jira", {}).get("issues", []):
                for att in issue.get("attachments_data", []):
                    if att["id"] == m.group(1) and att["filename"] == name:
                        self._send(200, raw=_content(att))
                        return
            self._send(404, {"errorMessages": ["attachment not found"]})
        else:
            self._send(404, {"message": f"no route {path}"})

    def _page(self, page_id: str) -> dict | None:
        confluence = STATE.get("confluence", {})
        permitted = {k for k, v in confluence.get("spaces", {}).items() if v.get("permitted", True)}
        page = next((p for p in confluence.get("pages", []) if p["id"] == page_id), None)
        if page is None or page["space"] not in permitted:
            self._send(404, {"message": "page not found"})
            return None
        return page

    def _jira_search(self, path: str, q: dict) -> None:
        issues = _issues(q.get("jql", ""))
        limit = min(int(q.get("maxResults", 50)), 100)
        fields = q.get("fields", "*all")
        if path.endswith("/jql"):
            start = int(q.get("nextPageToken") or 0)
        else:
            start = int(q.get("startAt", 0))
        if limit > 0 and self._listing_cut(start):
            return
        chunk = issues[start : start + limit] if limit else []

        def view(issue):
            if fields == "key":
                return {"key": issue["key"]}
            return {"key": issue["key"], "fields": issue["fields"]}

        if path.endswith("/jql"):
            payload = {"issues": [view(i) for i in chunk]}
            if start + limit < len(issues):
                payload["nextPageToken"] = str(start + limit)
        else:
            payload = {"startAt": start, "maxResults": limit, "total": len(issues), "issues": [view(i) for i in chunk]}
        self._send(200, payload)


def serve(port: int = 0) -> ThreadingHTTPServer:
    """In the test process on loopback only (unit and integration tests start it in a thread)."""
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
