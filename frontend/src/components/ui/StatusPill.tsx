// O componente mais importante do app (design.md §2). Modelo Linear:
// fundo soft + texto --color-ink legível + ponto/ícone na cor de status
// (neon onde for o caso). Cor NUNCA carrega significado sozinha — sempre há
// glyph + label (acessibilidade + daltonismo). O ponto `offering` pulsa.
import { STATUS_META, statusKey } from "@/lib/status";

export function StatusPill({
  status,
  className = "",
}: {
  status: string;
  className?: string;
}) {
  const s = STATUS_META[status] ?? { label: status, glyph: "•" };
  const key = statusKey(status);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm font-medium text-ink ${className}`}
      style={{ background: `var(--status-${key}-soft)` }}
    >
      <span
        aria-hidden
        className={`text-[0.7em] leading-none ${s.pulse ? "animate-status-pulse" : ""}`}
        style={{ color: `var(--status-${key})` }}
      >
        {s.glyph}
      </span>
      <span className={s.strike ? "line-through" : ""}>{s.label}</span>
    </span>
  );
}
