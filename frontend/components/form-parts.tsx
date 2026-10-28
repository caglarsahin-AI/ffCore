"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const SELECT = "rounded-md border border-input bg-background px-2 py-1.5 text-foreground disabled:opacity-50";
const CHECK = "size-4 accent-primary disabled:opacity-50";

// Label, hint and error of one control, wired with aria-describedby (same shape as ProjectForm).
export function FieldShell({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: (a11y: { id: string; "aria-invalid": boolean; "aria-describedby"?: string }) => React.ReactNode;
}) {
  const describedBy = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ") || undefined;
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>
      {children({ id, "aria-invalid": Boolean(error), "aria-describedby": describedBy })}
      {hint && (
        <p id={`${id}-hint`} className="text-sm text-muted-foreground">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

export function TextField({
  id,
  label,
  hint,
  error,
  value,
  onChange,
  type = "text",
  disabled,
  placeholder,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "password" | "number";
  disabled?: boolean;
  placeholder?: string;
}) {
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      {(a11y) => (
        <Input
          {...a11y}
          name={id}
          type={type}
          value={value}
          disabled={disabled}
          placeholder={placeholder}
          autoComplete={type === "password" ? "new-password" : "off"}
          step={type === "number" ? "any" : undefined}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </FieldShell>
  );
}

// A group of checkboxes for a set of values; the legend is the group's accessible name.
export function CheckGroup<T extends string>({
  id,
  legend,
  options,
  selected,
  onChange,
  error,
  hint,
}: {
  id: string;
  legend: string;
  options: { value: T; label: string; disabled?: boolean; title?: string }[];
  selected: T[];
  onChange: (next: T[]) => void;
  error?: string;
  hint?: string;
}) {
  const describedBy = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ") || undefined;
  return (
    <fieldset className="flex flex-col gap-2" aria-describedby={describedBy} aria-invalid={Boolean(error)} data-testid={id}>
      <legend className="mb-2 text-sm leading-none font-medium">{legend}</legend>
      <div className="flex flex-wrap gap-x-5 gap-y-2">
        {options.map((option) => (
          <label key={option.value} className="flex items-center gap-2 text-sm" title={option.title}>
            <input
              type="checkbox"
              className={CHECK}
              checked={selected.includes(option.value)}
              disabled={option.disabled}
              onChange={(e) =>
                onChange(e.target.checked ? [...selected, option.value] : selected.filter((v) => v !== option.value))
              }
            />
            {option.label}
          </label>
        ))}
      </div>
      {hint && (
        <p id={`${id}-hint`} className="text-sm text-muted-foreground">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </fieldset>
  );
}

export function CheckField({
  id,
  label,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label htmlFor={id} className="flex items-center gap-2 text-sm">
      <input id={id} type="checkbox" className={CHECK} checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}
