import type { ReactNode } from "react";

// Superfície near-white que salta do canvas azul (design.md §4): borda hairline
// + sombra tênue, sem padding embutido (a tela define a densidade).
export function Card({
  className = "",
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={`rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] shadow-[var(--shadow-sm)] ${className}`}
    >
      {children}
    </div>
  );
}
