// @vitest-environment jsdom
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ApiKeysPage from "@/app/(console)/api-keys/page";

import { P, apiKey, renderGov, stubApi } from "./gov-support";

// 10c-2 D3: API keys (03c). An admin lists every key of the project, creates one with explicit
// scopes (no scope is preselected), sees the raw key exactly once, and revokes a key after a
// confirmation. impersonate needs allowed networks (backend rule, checked before sending).

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function fill(id: string, value: string) {
  fireEvent.change(screen.getByLabelText(id, { exact: false }), { target: { value } });
}

describe("test_10c2_1_api_keys", () => {
  it("lists every key of the project for an admin, revoked ones marked", async () => {
    const calls = stubApi({ [`GET ${P}/api-keys`]: { data: [apiKey(), apiKey({ id: "k2", name: "old", key_prefix: "ffk_zz99", revoked_at: "2026-11-17T09:00:00Z" })] } });
    renderGov("admin", "edit", <ApiKeysPage />);
    const table = await screen.findByTestId("api-keys-table");
    expect(calls[0].search.get("all")).toBe("true");
    expect(within(table).getByText("ffk_ab12")).toBeTruthy();
    expect(within(screen.getByTestId("api-key-k2")).getByText(/revoked/i)).toBeTruthy();
    expect(within(screen.getByTestId("api-key-k2")).queryByTestId("api-key-revoke")).toBeNull();
  });

  it("creates a key with the chosen scopes and shows the raw key once", async () => {
    const calls = stubApi({
      [`GET ${P}/api-keys`]: { data: [] },
      [`POST ${P}/api-keys`]: apiKey({ id: "k9", name: "ci-bot", key: "ffk_ab12_SECRET_VALUE" }),
    });
    renderGov("admin", "edit", <ApiKeysPage />);
    await screen.findByTestId("empty-state");
    fireEvent.click(screen.getByTestId("api-key-add"));
    for (const box of within(screen.getByTestId("api-key-scopes")).getAllByRole("checkbox")) expect((box as HTMLInputElement).checked).toBe(false);
    fill("Name", "ci-bot");
    fireEvent.click(within(screen.getByTestId("api-key-scopes")).getByLabelText(/agents/i));
    fireEvent.submit(screen.getByTestId("api-key-form"));
    const created = await screen.findByTestId("api-key-created");
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ name: "ci-bot", scopes: ["agents"], acl_role: "analyst", allowed_cidrs: [], expires_at: null });
    expect(within(created).getByTestId("api-key-created-value").textContent).toBe("ffk_ab12_SECRET_VALUE");
    expect(within(created).getByTestId("api-key-copy")).toBeTruthy();
    fireEvent.click(within(created).getByTestId("api-key-created-done"));
    await waitFor(() => expect(screen.queryByTestId("api-key-created")).toBeNull());
    expect(document.body.textContent).not.toContain("SECRET_VALUE");
  });

  it("does not send a key without a scope, or impersonate without allowed networks", async () => {
    const calls = stubApi({ [`GET ${P}/api-keys`]: { data: [] } });
    renderGov("admin", "edit", <ApiKeysPage />);
    await screen.findByTestId("empty-state");
    fireEvent.click(screen.getByTestId("api-key-add"));
    fill("Name", "obo");
    fireEvent.submit(screen.getByTestId("api-key-form"));
    expect(await screen.findByText(/at least one scope/i)).toBeTruthy();
    fireEvent.click(within(screen.getByTestId("api-key-scopes")).getByLabelText(/impersonate/i));
    fireEvent.submit(screen.getByTestId("api-key-form"));
    expect(await screen.findByText(/needs allowed networks/i)).toBeTruthy();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("revokes a key only after confirmation", async () => {
    const calls = stubApi({ [`GET ${P}/api-keys`]: { data: [apiKey()] }, [`POST ${P}/api-keys/k1/revoke`]: apiKey({ revoked_at: "2026-11-17T10:00:00Z" }) });
    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    renderGov("admin", "edit", <ApiKeysPage />);
    const row = await screen.findByTestId("api-key-k1");
    fireEvent.click(within(row).getByTestId("api-key-revoke"));
    expect(calls.some((c) => c.method === "POST")).toBe(false);
    fireEvent.click(within(row).getByTestId("api-key-revoke"));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === `${P}/api-keys/k1/revoke`)).toBe(true));
    expect(confirm).toHaveBeenCalledTimes(2);
  });
});
