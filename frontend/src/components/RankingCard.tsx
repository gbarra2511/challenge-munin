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

export function RankingCard({ entries }: { entries: ShiftRankingEntry[] }) {
  if (entries.length === 0) {
    return (
      <p className="mt-3 text-sm text-muted">
        Nenhum médico elegível agora — o ranking considera especialidade,
        afiliação ativa ao hospital e disponibilidade na janela do plantão.
      </p>
    );
  }

  return (
    <ol className="mt-4 flex flex-col gap-3.5">
      {entries.map((e, i) => (
        <li key={e.doctor.id} className="flex gap-3">
          <span className="font-data mt-0.5 w-5 shrink-0 text-right text-sm font-medium text-faint">
            {i + 1}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate font-medium text-ink">
                {e.doctor.name}
              </span>
              {e.already_offered && (
                <span className="shrink-0 rounded-full border border-rule px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted">
                  já ofertado
                </span>
              )}
              <span
                className="font-data ml-auto shrink-0 text-sm font-semibold text-ink"
                title="Score 0–100"
              >
                {Math.round(e.score)}
              </span>
            </div>
            <div
              className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-rule)]"
              role="presentation"
            >
              <div
                className="h-full rounded-full bg-accent"
                style={{ width: `${Math.max(2, Math.min(100, e.score))}%` }}
              />
            </div>
            <p className="mt-1.5 text-xs text-muted">
              {reasonsFor(e).join(" · ")}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
