// @vitest-environment jsdom
import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GateFailure } from "@/components/eval/gate-failure";
import { ApiError } from "@/lib/api/client";

import { renderAs } from "./eval-support";

afterEach(cleanup);

const refused = new ApiError(409, "eval_gate_failed", "conflict_error", "The exam gate refuses version 2: sozlesme=not_passed, sql-set=brand_new.");

describe("test_10c1_8_gate_failure", () => {
  it("lists each suite with its reason explained; an unknown reason is shown as written", () => {
    renderAs("analyst", "edit", <GateFailure projectId="p1" error={refused} pending={false} onForce={vi.fn()} />);
    expect(screen.getByTestId("gate-suite-sozlesme").textContent).toMatch(/did not reach the pass threshold/i);
    expect(screen.getByTestId("gate-suite-sql-set").textContent).toContain("brand_new");
  });

  it("shows the raw message when it is not in the expected shape", () => {
    const other = new ApiError(409, "eval_gate_failed", "conflict_error", "Gate said no.");
    renderAs("analyst", "edit", <GateFailure projectId="p1" error={other} pending={false} onForce={vi.fn()} />);
    expect(screen.getByTestId("gate-raw").textContent).toContain("Gate said no.");
  });

  it("gives force only to an admin, never without a reason", () => {
    const onForce = vi.fn();
    renderAs("admin", "edit", <GateFailure projectId="p1" error={refused} pending={false} onForce={onForce} />);
    const button = screen.getByTestId("gate-force") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/reason/i), { target: { value: "   " } });
    expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/reason/i), { target: { value: "  Hotfix approved by CAB  " } });
    expect(button.disabled).toBe(false);
    fireEvent.click(button);
    expect(onForce).toHaveBeenCalledWith("Hotfix approved by CAB");
  });

  it("shows force disabled with the reason to an analyst and to a read-only admin", () => {
    renderAs("analyst", "edit", <GateFailure projectId="p1" error={refused} pending={false} onForce={vi.fn()} />);
    const analyst = screen.getByTestId("gate-force") as HTMLButtonElement;
    expect(analyst.disabled).toBe(true);
    expect(analyst.closest("[data-needs-role='admin']")).not.toBeNull();
    cleanup();
    renderAs("admin", "read", <GateFailure projectId="p1" error={refused} pending={false} onForce={vi.fn()} />);
    const reader = screen.getByTestId("gate-force") as HTMLButtonElement;
    expect(reader.disabled).toBe(true);
    expect(reader.closest("[data-read-only]")).not.toBeNull();
  });
});
