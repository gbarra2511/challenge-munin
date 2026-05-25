// O componente mais importante do app (design.md §2). Modelo Linear:
// fundo soft + texto --color-ink legível + ponto/ícone na cor de status
// (neon onde for o caso). Cor NUNCA carrega significado sozinha — sempre há
// glyph + label (acessibilidade + daltonismo). O ponto `offering` pulsa.

const MAP: Record<
  string,
  { label: string; glyph: string; pulse?: boolean; strike?: boolean }
> = {
  open: { label: "Aberto", glyph: "○" },
  offering: { label: "Em oferta", glyph: "●", pulse: true },
  accepted: { label: "Preenchido", glyph: "✓" },
  confirmed: { label: "Confirmado", glyph: "✓✓" },
  needs_attention: { label: "Em risco", glyph: "▲" },
  cancelled: { label: "Cancelado", glyph: "⊘", strike: true },
};

export function StatusPill({
  status,
  className = "",
}: {
  status: string;
  className?: string;
}) {
  const s = MAP[status] ?? { label: status, glyph: "•" };
  const key = status.replace(/_/g, "-"); // needs_attention -> needs-attention
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
