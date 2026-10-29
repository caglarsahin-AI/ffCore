import { describe, expect, it } from "vitest";

import { ApiError, upload } from "@/lib/api/client";

// Minimal XMLHttpRequest stand-in: records the request and lets the test drive progress and the
// response the way the browser would.
class FakeXhr {
  method = "";
  url = "";
  body: unknown = null;
  withCredentials = false;
  status = 0;
  responseText = "";
  upload: { onprogress: ((event: { lengthComputable: boolean; loaded: number; total: number }) => void) | null } = {
    onprogress: null,
  };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }
  send(body: unknown) {
    this.body = body;
  }
  respond(status: number, body: unknown) {
    this.status = status;
    this.responseText = body === undefined ? "" : JSON.stringify(body);
    this.onload?.();
  }
}

function setup() {
  const xhr = new FakeXhr();
  return { xhr, factory: () => xhr as unknown as XMLHttpRequest };
}

const form = () => {
  const data = new FormData();
  data.append("files", new Blob(["x"]), "a.pdf");
  return data;
};

describe("test_10bp1_13_upload_client", () => {
  it("posts the form on the console origin and reports progress as a fraction", async () => {
    const { xhr, factory } = setup();
    const seen: number[] = [];
    const body = form();
    const pending = upload<{ data: unknown[] }>("/api/v1/x/documents", body, (fraction) => seen.push(fraction), factory);
    expect(xhr.method).toBe("POST");
    expect(xhr.url).toBe("/api/v1/x/documents");
    expect(xhr.body).toBe(body);
    expect(xhr.withCredentials).toBe(false); // same origin: the cookie goes without CORS credentials
    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 200 });
    xhr.upload.onprogress?.({ lengthComputable: false, loaded: 0, total: 0 });
    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 200, total: 200 });
    xhr.respond(202, { data: [] });
    await expect(pending).resolves.toEqual({ data: [] });
    expect(seen).toEqual([0.25, 1]);
  });

  it.each([
    [413, "request_too_large"],
    [422, "acl_conflict"],
    [401, "unauthenticated"],
    [403, "read_only_access"],
  ])("turns a %i error body into an ApiError with code %s", async (status, code) => {
    const { xhr, factory } = setup();
    const pending = upload("/api/v1/x", form(), undefined, factory);
    xhr.respond(status, { error: { code, type: "invalid_request_error", message: "backend text" } });
    const error = await pending.catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status, code, message: "backend text" });
  });

  it("fails loudly on a body that is not the error contract and on a network error", async () => {
    const first = setup();
    const pending = upload("/api/v1/x", form(), undefined, first.factory);
    first.xhr.status = 502;
    first.xhr.responseText = "<html>bad gateway</html>";
    first.xhr.onload?.();
    await expect(pending).rejects.toMatchObject({ status: 502, code: "unexpected_response" });

    const second = setup();
    const failing = upload("/api/v1/x", form(), undefined, second.factory);
    second.xhr.onerror?.();
    await expect(failing).rejects.toMatchObject({ status: 0, code: "network_error" });
  });
});
