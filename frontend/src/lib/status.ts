// Meta única do sistema de status (design.md §2). Fonte de verdade para
// StatusPill, chips do calendário e barras do dashboard — todos consistentes.
import type { ShiftStatus } from "@/lib/types";

export const SHIFT_STATUSES: ShiftStatus[] = [
  "open",
  "offering",
  "accepted",
  "confirmed",
  "needs_attention",
  "cancelled",
];

export const STATUS_META: Record<
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

// needs_attention -> needs-attention (os tokens usam hífen)
export const statusKey = (s: string) => s.replace(/_/g, "-");
export const statusLabel = (s: string) => STATUS_META[s]?.label ?? s;
export const statusColor = (s: string) => `var(--status-${statusKey(s)})`;
export const statusSoft = (s: string) => `var(--status-${statusKey(s)}-soft)`;

// "Preenchido" agrega accepted + confirmed para os KPIs.
export const isFilled = (s: string) => s === "accepted" || s === "confirmed";
export const isOpenish = (s: string) =>
  s === "open" || s === "offering" || s === "needs_attention";
