// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it } from "vitest";

import { SessionProvider } from "@/components/session-provider";
import { WriteGate } from "@/components/write-gate";
import { Button } from "@/components/ui/button";
import type { Session } from "@/lib/access";
import messages from "@/messages/en.json";

function renderGate(session: Session) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <SessionProvider session={session}>
        <WriteGate>
          <Button>Create</Button>
        </WriteGate>
      </SessionProvider>
    </NextIntlClientProvider>,
  );
}

afterEach(cleanup);

describe("test_10a_6_write_gate", () => {
  it("leaves the button active in edit mode", () => {
    renderGate({ role: "admin", access: "edit" });
    const button = screen.getByRole("button", { name: "Create" });
    expect(button.hasAttribute("disabled")).toBe(false);
  });

  it("disables the button and explains why in read mode", () => {
    renderGate({ role: "admin", access: "read" });
    const button = screen.getByRole("button", { name: "Create" });
    expect(button.hasAttribute("disabled")).toBe(true);
    expect(button.getAttribute("aria-describedby")).toBeTruthy();
    const hint = document.getElementById(button.getAttribute("aria-describedby")!);
    expect(hint?.textContent).toBe(messages.Access.readOnlyHint);
  });
});
