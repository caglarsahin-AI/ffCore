// @vitest-environment jsdom
import { QueryClient } from "@tanstack/react-query";
import { act, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PortalTab } from "@/components/agent-wizard/portal-tab";
import type { Agent } from "@/lib/api/agents-queries";

import { renderAs } from "./eval-support";

// 11-2 (K-11-0005 S2, S3): the console's Portal tab. Agent level, outside the version fieldset,
// its own save (PATCH, analyst + edit); read access sees the values without controls; the preview
// shows the derived light and dark tones and says when they differ from the picked colour.

const P = "/api/v1/projects/p1";
const AGENT = {
  id: "a1", project_id: "p1", key: "asistan", name: "Asistan", description: "", status: "published", kind: "native",
  current_version_id: "v1", latest_version: 1, created_at: "2026-11-20T10:00:00Z", updated_at: "2026-11-20T10:00:00Z",
  portal_config: { welcome: "Merhaba.", examples: ["Fesih süresi?"], accent: "#ffff00" },
} as Agent;

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}
const client = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("test_11_3_portal_tab", () => {
  it("saves the portal settings with PATCH, on a published agent too", async () => {
    const fetchMock = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => json({ ...AGENT, portal_config: JSON.parse(String(init?.body)).portal_config }));
    vi.stubGlobal("fetch", fetchMock);
    renderAs("analyst", "edit", <PortalTab projectId="p1" agent={AGENT} />, client());
    fireEvent.change(screen.getByTestId("portal-welcome"), { target: { value: "Sözleşmeler hakkında sorun." } });
    fireEvent.change(screen.getByTestId("portal-example-2"), { target: { value: "Cezai şart var mı?" } });
    fireEvent.change(screen.getByTestId("portal-accent"), { target: { value: "#0F766E" } });
    await act(async () => {
      fireEvent.click(screen.getByTestId("portal-save"));
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe(`${P}/agents/a1`);
    expect(init?.method).toBe("PATCH");
    expect(JSON.parse(String(init?.body))).toEqual({
      portal_config: { welcome: "Sözleşmeler hakkında sorun.", examples: ["Fesih süresi?", "Cezai şart var mı?"], accent: "#0F766E" },
    });
    expect(await screen.findByTestId("portal-saved")).toBeTruthy();
  });

  it("offers three example fields at most and drops empty ones on save", async () => {
    const fetchMock = vi.fn(async (...args: [RequestInfo | URL, RequestInit?]) => json({ ...AGENT, url: String(args[0]) }));
    vi.stubGlobal("fetch", fetchMock);
    renderAs("analyst", "edit", <PortalTab projectId="p1" agent={{ ...AGENT, portal_config: null }} />, client());
    expect(screen.getAllByTestId(/^portal-example-\d$/)).toHaveLength(3);
    fireEvent.change(screen.getByTestId("portal-example-1"), { target: { value: "Fesih süresi?" } });
    await act(async () => {
      fireEvent.click(screen.getByTestId("portal-save"));
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      portal_config: { welcome: null, examples: ["Fesih süresi?"], accent: null },
    });
  });

  it("refuses an accent that is not #rrggbb before sending", async () => {
    const fetchMock = vi.fn(async () => json(AGENT));
    vi.stubGlobal("fetch", fetchMock);
    renderAs("analyst", "edit", <PortalTab projectId="p1" agent={AGENT} />, client());
    fireEvent.change(screen.getByTestId("portal-accent"), { target: { value: "teal" } });
    expect(screen.getByTestId("portal-accent-error")).toBeTruthy();
    expect((screen.getByTestId("portal-save") as HTMLButtonElement).disabled).toBe(true);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("previews both themes and says the tone was adjusted for contrast", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderAs("analyst", "edit", <PortalTab projectId="p1" agent={AGENT} />, client());
    expect(screen.getByTestId("portal-preview-light")).toBeTruthy();
    expect(screen.getByTestId("portal-preview-dark")).toBeTruthy();
    expect(screen.getByTestId("portal-adjusted")).toBeTruthy();
  });

  it("shows the settings read-only in read access, without a save", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderAs("analyst", "read", <PortalTab projectId="p1" agent={AGENT} />, client());
    expect((screen.getByTestId("portal-welcome") as HTMLTextAreaElement).value).toBe("Merhaba.");
    expect((screen.getByTestId("portal-welcome") as HTMLTextAreaElement).disabled).toBe(true);
    const save = screen.getByTestId("portal-save") as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    expect(save.closest("[data-read-only]")).not.toBeNull();
  });
});
