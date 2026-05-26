import type { ReactNode } from "react";

// Estado vazio com voz humana e (quando faz sentido) um CTA — escola Notion.
export function EmptyState({
  title,
  description,
  action,
  glyph,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  glyph?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[var(--radius-md)] border border-dashed border-[var(--color-rule-strong)] bg-[var(--color-surface)] px-6 py-14 text-center">
      {glyph && (
        <span aria-hidden className="mb-3 text-3xl text-[var(--color-faint)]">
          {glyph}
        </span>
      )}
      <p className="font-display text-lg font-bold text-ink">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-pretty text-sm text-muted">
          {description}
        </p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
