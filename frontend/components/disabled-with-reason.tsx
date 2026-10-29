"use client";

import { cloneElement, useId } from "react";

type Gated = React.ReactElement<{ disabled?: boolean; "aria-describedby"?: string }>;

// A control the user's role cannot use: visible, disabled, with the reason on hover and for screen
// readers (like WriteGate for read mode). `needs` names the missing permission for tests:
// superadmin (FOLLOWUP-79) or a project role. The API still enforces it.
export function DisabledWithReason({
  reason,
  needs,
  children,
}: {
  reason: string;
  needs: "superadmin" | "admin";
  children: Gated;
}) {
  const hintId = useId();
  const marker = needs === "superadmin" ? { "data-needs-superadmin": "" } : { "data-needs-role": needs };
  return (
    <span className="inline-flex" title={reason} {...marker}>
      {cloneElement(children, { disabled: true, "aria-describedby": hintId })}
      <span id={hintId} className="sr-only">
        {reason}
      </span>
    </span>
  );
}
