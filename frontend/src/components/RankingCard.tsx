"use client";
import type { ShiftRankingEntry } from "@/lib/types";

// Traduz o breakdown numérico do ranking em motivos legíveis (PLANO §13:
// "ranqueou 1º: aceitou 8/10 · 6 dias sem plantão"). A direção de cada
// fator espelha a heurística do backend (services/ranking.py).
function reasonsFor(e: ShiftRankingEntry): string[] {
  const b = e.breakdown;
  const out: string[] = [];

  if (b.acceptance_rate != null) {
    out.push(`aceita ${Math.round(b.acceptance_rate * 100)}% das ofertas`);
  } else {
    out.push("sem histórico de ofertas");
  }

  if (b.days_since_last == null) {
    out.push("nunca pegou plantão");
  } else if (b.days_since_last > 0) {
    out.push(`${b.days_since_last}d sem plantão`);
  }

  if (b.weekly_load > 0) {
    out.push(`${b.weekly_load} plantão${b.weekly_load > 1 ? "es" : ""} esta semana`);
  }

  if (b.avg_response_min != null) {
    out.push(`responde em ~${b.avg_response_min}min`);
  }

  return out;
}

// Sub-scores ponderados (0–100) — surgem no hover do score. Deixa a heurística
// auditável: dá pra ver QUAL fator puxou o número pra cima ou pra baixo.
function scoreTitle(e: ShiftRankingEntry): string {
  const s = e.breakdown.scores;
  return [
    `Score ${Math.round(e.score)}/100 — composição:`,
    `aceite ${Math.round(s.acceptance)} (40%)`,
    `recência ${Math.round(s.recency)} (25%)`,
    `carga ${Math.round(s.load)} (20%)`,
    `resposta ${Math.round(s.response)} (15%)`,
  ].join("\n");
}

export function RankingCard({
  entries,
  batchSize,
  selectable = false,
  selectedIds,
  onToggle,
}: {
  entries: ShiftRankingEntry[];
  /** Tamanho do lote do plantão — divide a lista em "Lote 1, 2, …". */
  batchSize?: number;
  /** Liga o modo seleção (override manual do 1º lote). */
  selectable?: boolean;
  selectedIds?: Set<string>;
  onToggle?: (doctorId: string) => void;
}) {
  if (entries.length === 0) {
    return (
      <p className="mt-3 text-sm text-muted">
        Nenhum médico elegível agora — o ranking considera especialidade,
        afiliação ativa ao hospital e disponibilidade na janela do plantão.
      </p>
    );
  }

  const size = batchSize && batchSize > 0 ? batchSize : 0;

  return (
    <ol className="mt-4 flex flex-col gap-1">
      {entries.map((e, i) => {
        const isLeader = i === 0;
        const lote = size ? Math.floor(i / size) + 1 : 0;
        const firstOfLote = size > 0 && i % size === 0;
        const selected = selectedIds?.has(e.doctor.id) ?? false;

        const row = (
          <>
            <span className="font-data mt-0.5 w-5 shrink-0 text-right text-sm font-medium text-faint">
              {i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate font-medium text-ink">
                  {e.doctor.name}
                </span>
                {!e.is_specialist && (
                  <span
                    className="shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] uppercase tracking-wide"
                    style={{
                      color: "var(--color-warning)",
                      borderColor: "var(--color-warning)",
                    }}
                    title="Fora da especialidade do plantão — só ofertado se faltarem especialistas"
                  >
                    fora da especialidade
                  </span>
                )}
                {e.already_offered && (
                  <span className="shrink-0 rounded-full border border-rule px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted">
                    já ofertado
                  </span>
                )}
                <span
                  className="font-data ml-auto shrink-0 cursor-help text-sm font-semibold text-ink"
                  title={scoreTitle(e)}
                >
                  {Math.round(e.score)}
                </span>
              </div>
              <div
                className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-rule)]"
                role="presentation"
              >
                {/* Accent cheio só no líder (cirúrgico, design.md §2); os demais
                    em índigo esmaecido — hue mantido, peso reduzido. */}
                <div
                  className="h-full rounded-full bg-accent"
                  style={{
                    width: `${Math.max(2, Math.min(100, e.score))}%`,
                    opacity: isLeader ? 1 : 0.4,
                  }}
                />
              </div>
              <p className="mt-1.5 text-xs text-muted">
                {reasonsFor(e).join(" · ")}
              </p>
            </div>
          </>
        );

        return (
          <li key={e.doctor.id}>
            {/* Cabeçalho de lote: conecta o ranking ao pipeline de batches. */}
            {firstOfLote && (
              <p className="mb-1 mt-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-faint first:mt-0">
                Lote {lote}
                <span className="font-normal normal-case tracking-normal text-faint">
                  {lote === 1 ? "· recebe a oferta agora" : "· se o lote anterior expirar"}
                </span>
                <span className="h-px flex-1 bg-[var(--color-rule)]" />
              </p>
            )}

            {selectable ? (
              <label
                className={`flex cursor-pointer gap-3 rounded-[var(--radius-sm)] px-2 py-1.5 transition-colors hover:bg-[var(--color-surface-2)] ${
                  selected ? "bg-[var(--color-accent-soft)]/40" : ""
                }`}
              >
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 shrink-0 accent-[var(--color-accent)]"
                  checked={selected}
                  onChange={() => onToggle?.(e.doctor.id)}
                  aria-label={`Incluir ${e.doctor.name} no lote de ofertas`}
                />
                {row}
              </label>
            ) : (
              <div className="flex gap-3 px-2 py-1.5">{row}</div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
