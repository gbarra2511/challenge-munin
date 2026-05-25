"use client";
import Link from "next/link";
import { forwardRef } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
  fullWidth?: boolean;
}

// Estados: default · hover · :focus-visible · :active · disabled · loading.
// Foco aparece instantâneo (nunca anima, design.md §5). Altura 44px = alvo de
// toque do fluxo do médico. Anima só transform/box-shadow/background.
const base =
  "inline-flex h-11 items-center justify-center gap-2 rounded-[var(--radius-sm)] px-4 " +
  "text-sm font-medium transition-[transform,background-color,border-color,box-shadow] " +
  "duration-[120ms] [transition-timing-function:var(--ease-out)] " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-focus)] " +
  "focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-paper)] " +
  "active:translate-y-px disabled:pointer-events-none disabled:opacity-50";

const variants: Record<Variant, string> = {
  primary:
    "bg-[var(--color-accent)] text-[var(--color-accent-ink)] shadow-[var(--shadow-sm)] hover:bg-[var(--color-accent-hover)]",
  secondary:
    "border border-[var(--color-rule-strong)] bg-[var(--color-surface)] text-ink hover:bg-[var(--color-surface-2)]",
  ghost: "bg-transparent text-ink hover:bg-[var(--color-surface-2)]",
  danger:
    "bg-[var(--color-danger)] text-white shadow-[var(--shadow-sm)] hover:opacity-90",
};

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  {
    variant = "primary",
    loading = false,
    fullWidth,
    className = "",
    children,
    disabled,
    ...rest
  },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`${base} ${variants[variant]} ${fullWidth ? "w-full" : ""} ${className}`}
      {...rest}
    >
      {loading && (
        <span
          aria-hidden
          className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent opacity-80"
        />
      )}
      {children}
    </button>
  );
});

// Link com a mesma roupa de botão (para CTAs que navegam).
export function ButtonLink({
  href,
  variant = "primary",
  fullWidth,
  className = "",
  children,
}: {
  href: string;
  variant?: Variant;
  fullWidth?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={`${base} ${variants[variant]} ${fullWidth ? "w-full" : ""} ${className}`}
    >
      {children}
    </Link>
  );
}
