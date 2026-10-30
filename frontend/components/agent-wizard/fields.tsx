"use client";

import { FieldShell } from "@/components/form-parts";
import { Input } from "@/components/ui/input";

// Optional whole number: empty means "use the contract default" (the field is not sent), so the
// wizard never invents a value the backend did not choose (ARCH-10).
export function NumberField({
  id,
  label,
  hint,
  value,
  onChange,
  min,
  max,
  step,
  disabled,
}: {
  id: string;
  label: string;
  hint?: string;
  value: number | null | undefined;
  onChange: (value: number | null) => void;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
}) {
  return (
    <FieldShell id={id} label={label} hint={hint}>
      {(a11y) => (
        <Input
          {...a11y}
          type="number"
          inputMode="decimal"
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        />
      )}
    </FieldShell>
  );
}

// Drops keys whose value is null so the backend applies its own default for them.
export function withoutNulls<T extends Record<string, unknown>>(value: T): Partial<T> {
  return Object.fromEntries(Object.entries(value).filter(([, v]) => v !== null && v !== undefined)) as Partial<T>;
}
