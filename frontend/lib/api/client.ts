import type { components } from "@/lib/api/schema";

type ErrorBody = components["schemas"]["ErrorBody"];

// Failed API call: HTTP status and the contract's stable error code (03a ErrorBody).
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly type: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function isErrorBody(body: unknown): body is ErrorBody {
  const error = (body as ErrorBody)?.error;
  return typeof error?.code === "string" && typeof error.message === "string";
}

type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
type Fetcher = (url: string, init: RequestInit) => Promise<Response>;

// Browser-side call on the console origin (/api/v1/... is rewritten to the backend, C6).
// Response and body types come from the generated schema at the call site (lib/api/queries.ts).
export async function api<T>(method: Method, path: string, body?: unknown, fetcher: Fetcher = fetch): Promise<T> {
  const init: RequestInit = { method, credentials: "same-origin" };
  if (body !== undefined) {
    init.headers = { "content-type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const response = await fetcher(path, init);
  if (response.status === 204) return undefined as T;
  const parsed: unknown = await response.json().catch(() => undefined);
  if (response.ok) return parsed as T;
  if (isErrorBody(parsed)) {
    throw new ApiError(response.status, parsed.error.code, parsed.error.type, parsed.error.message);
  }
  throw new ApiError(response.status, "unexpected_response", "api_error", `${method} ${path} returned ${response.status}`);
}

// Multipart upload with progress (fetch has no upload progress). Same origin and the same error
// contract as api(); 401 reaches the MutationCache like any other call. `onProgress` gets 0..1
// and is called only when the browser knows the total.
export function upload<T>(
  path: string,
  form: FormData,
  onProgress?: (fraction: number) => void,
  createXhr: () => XMLHttpRequest = () => new XMLHttpRequest(),
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = createXhr();
    xhr.open("POST", path);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) onProgress?.(event.loaded / event.total);
    };
    xhr.onload = () => {
      let parsed: unknown;
      try {
        parsed = xhr.responseText ? JSON.parse(xhr.responseText) : undefined;
      } catch {
        parsed = undefined;
      }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(parsed as T);
      if (isErrorBody(parsed)) {
        return reject(new ApiError(xhr.status, parsed.error.code, parsed.error.type, parsed.error.message));
      }
      reject(new ApiError(xhr.status, "unexpected_response", "api_error", `POST ${path} returned ${xhr.status}`));
    };
    xhr.onerror = () => reject(new ApiError(0, "network_error", "api_error", `POST ${path} did not complete`));
    xhr.onabort = () => reject(new ApiError(0, "network_error", "api_error", `POST ${path} was aborted`));
    xhr.send(form);
  });
}
