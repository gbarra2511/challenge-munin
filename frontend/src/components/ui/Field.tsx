import { forwardRef } from "react";

const fieldBase =
  "h-11 rounded-[var(--radius-sm)] border bg-[var(--color-surface-sunk)] px-3 text-ink " +
  "placeholder:text-[var(--color-faint)] " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-focus)] " +
  "disabled:opacity-50";

function ring(error?: string) {
  return error
    ? "border-[var(--color-danger)]"
    : "border-[var(--color-rule-strong)]";
}

function FieldMsg({ error, hint }: { error?: string; hint?: string }) {
  if (error)
    return (
      <p className="text-xs" style={{ color: "var(--color-danger)" }}>
        {error}
      </p>
    );
  if (hint) return <p className="text-xs text-muted">{hint}</p>;
  return null;
}

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, hint, id, name, className = "", ...rest },
  ref,
) {
  const inputId = id ?? name;
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={inputId} className="text-sm font-medium text-ink-2">
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={inputId}
        name={name}
        aria-invalid={!!error}
        className={`${fieldBase} ${ring(error)} ${className}`}
        {...rest}
      />
      <FieldMsg error={error} hint={hint} />
    </div>
  );
});

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  error?: string;
  hint?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, error, hint, id, name, className = "", children, ...rest },
  ref,
) {
  const selectId = id ?? name;
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={selectId} className="text-sm font-medium text-ink-2">
          {label}
        </label>
      )}
      <div className="relative">
        <select
          ref={ref}
          id={selectId}
          name={name}
          aria-invalid={!!error}
          className={`${fieldBase} ${ring(error)} w-full appearance-none pr-8 ${className}`}
          {...rest}
        >
          {children}
        </select>
        <span
          aria-hidden
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted"
        >
          ▾
        </span>
      </div>
      <FieldMsg error={error} hint={hint} />
    </div>
  );
});
