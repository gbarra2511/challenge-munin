// Loading = skeleton com a forma do conteúdo (design.md §7). Nunca spinner
// gigante centrado. Compõe-se nas telas para imitar o layout que vai chegar.
export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={`animate-pulse rounded-[var(--radius-sm)] bg-[var(--color-surface-2)] ${className}`}
    />
  );
}
