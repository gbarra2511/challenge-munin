"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo } from "react";
import { ButtonLink } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusPill } from "@/components/ui/StatusPill";
import { ApiError, api } from "@/lib/api";
import { formatShiftWindow, msUntil } from "@/lib/format";
import { specialtyName } from "@/lib/specialties";
import { isFilled, isOpenish, statusColor, statusLabel } from "@/lib/status";
import type { Shift } from "@/lib/types";

const HOUR = 3_600_000;
const RISK_WINDOW_H = 12; // <12h sem aceite = em risco (PLANO §9)

// "em 5h" · "em 3d" · "em andamento" · "encerrado"
function relStart(iso: string): string {
  const ms = msUntil(iso);
  if (ms <= 0) return "em andamento";
  const h = ms / HOUR;
  if (h < 1) return `em ${Math.max(1, Math.round(ms / 60000))}min`;
  if (h < 48) return `em ${Math.round(h)}h`;
  return `em ${Math.round(h / 24)}d`;
}

function isAtRisk(s: Shift): boolean {
  if (s.status === "needs_attention") return true;
  if (!isOpenish(s.status)) return false;
  const ms = msUntil(s.starts_at);
  return ms > 0 && ms < RISK_WINDOW_H * HOUR;
}

const KPIS = [
  { key: "open", label: "Abertos" },
  { key: "offering", label: "Em oferta" },
  { key: "accepted", label: "Preenchidos" },
  { key: "needs_attention", label: "Em risco" },
] as const;

// Cores do empilhamento das barras (sem cancelled, que é ruído).
const BAR_STATUSES = [
  "needs_attention",
  "offering",
  "open",
  "accepted",
  "confirmed",
];

export default function DashboardPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["shifts"],
    queryFn: () => api<{ shifts: Shift[] }>("/shifts"),
    refetchInterval: 15_000,
  });

  const view = useMemo(() => {
    const shifts = data?.shifts ?? [];
    const counts: Record<string, number> = {
      open: 0,
      offering: 0,
      accepted: 0,
      needs_attention: 0,
    };
    for (const s of shifts) {
      if (isFilled(s.status)) counts.accepted += 1;
      else if (s.status in counts) counts[s.status] += 1;
    }

    const risk = shifts
      .filter(isAtRisk)
      .sort((a, b) => +new Date(a.starts_at) - +new Date(b.starts_at));

    // Próximos 7 dias a partir de hoje (00h local).
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    const days = Array.from({ length: 7 }, (_, i) => {
      const day = new Date(start);
      day.setDate(start.getDate() + i);
      const next = new Date(day);
      next.setDate(day.getDate() + 1);
      const inDay = shifts.filter((s) => {
        const t = +new Date(s.starts_at);
        return t >= +day && t < +next;
      });
      const byStatus: Record<string, number> = {};
      for (const s of inDay) byStatus[s.status] = (byStatus[s.status] ?? 0) + 1;
      return { day, total: inDay.length, byStatus };
    });
    const maxTotal = Math.max(1, ...days.map((d) => d.total));

    return { counts, risk, days, maxTotal };
  }, [data]);

  return (
    <div>
      <header className="mb-6">
        <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
          Dashboard
        </h1>
        <p className="mt-0.5 text-sm text-muted">
          Visão geral do hospital — atualiza a cada 15s.
        </p>
      </header>

      {isError && (
        <ErrorState
          message={
            error instanceof ApiError
              ? error.message
              : "Não foi possível carregar o dashboard."
          }
          onRetry={() => refetch()}
        />
      )}

      {isLoading && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      )}

      {data && (
        <>
          {/* KPIs */}
          <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {KPIS.map((k) => (
              <Card key={k.key} className="p-5">
                <div className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className="text-xs"
                    style={{ color: statusColor(k.key) }}
                  >
                    ●
                  </span>
                  <span className="text-sm text-muted">{k.label}</span>
                </div>
                <p className="font-display mt-2 text-4xl font-extrabold tabular-nums tracking-[-0.02em] text-ink">
                  {view.counts[k.key === "accepted" ? "accepted" : k.key]}
                </p>
              </Card>
            ))}
          </section>

          {/* Próximos 7 dias */}
          <Card className="mt-6 p-5">
            <h2 className="font-display text-lg font-bold text-ink">
              Próximos 7 dias
            </h2>
            <div className="mt-4 flex items-end justify-between gap-2">
              {view.days.map(({ day, total, byStatus }, i) => (
                <div key={i} className="flex flex-1 flex-col items-center gap-2">
                  <span className="font-data text-xs text-muted tabular-nums">
                    {total || ""}
                  </span>
                  <div
                    className="flex w-full max-w-10 flex-col-reverse overflow-hidden rounded-[var(--radius-xs)]"
                    style={{ height: 96 }}
                    title={`${total} plantão(ões)`}
                  >
                    {total === 0 ? (
                      <div className="h-1.5 w-full bg-[var(--color-surface-2)]" />
                    ) : (
                      BAR_STATUSES.filter((s) => byStatus[s]).map((s) => (
                        <div
                          key={s}
                          style={{
                            height: `${(byStatus[s] / view.maxTotal) * 96}px`,
                            background: statusColor(s),
                          }}
                          title={`${byStatus[s]} ${statusLabel(s)}`}
                        />
                      ))
                    )}
                  </div>
                  <span className="text-xs capitalize text-faint">
                    {day.toLocaleDateString("pt-BR", { weekday: "short" })}
                  </span>
                </div>
              ))}
            </div>
          </Card>

          {/* Plantões em risco */}
          <Card className="mt-6 p-5">
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-display text-lg font-bold text-ink">
                Plantões em risco
              </h2>
              {view.risk.length > 0 && (
                <span
                  className="font-data rounded-full px-2 py-0.5 text-xs font-medium text-ink"
                  style={{ background: "var(--status-needs-attention-soft)" }}
                >
                  {view.risk.length}
                </span>
              )}
            </div>

            {view.risk.length === 0 ? (
              <div className="mt-4">
                <EmptyState
                  glyph="✓"
                  title="Nada em risco agora"
                  description="Nenhum plantão escalado ou perto de começar sem aceite. Respira."
                />
              </div>
            ) : (
              <ul className="mt-4 divide-y divide-[var(--color-rule)]">
                {view.risk.map((s) => (
                  <li key={s.id}>
                    <Link
                      href={`/plantoes/${s.id}`}
                      className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-[var(--radius-sm)] px-2 py-3 transition-colors hover:bg-[var(--color-surface-2)]"
                    >
                      <span className="min-w-0 flex-1 font-medium text-ink">
                        {specialtyName(s.specialty_id)}
                      </span>
                      <span className="font-data text-sm text-muted">
                        {formatShiftWindow(s.starts_at, s.ends_at)}
                      </span>
                      <span
                        className="font-data text-sm font-medium"
                        style={{ color: "var(--status-needs-attention)" }}
                      >
                        {relStart(s.starts_at)}
                      </span>
                      <StatusPill status={s.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {data.shifts.length === 0 && (
            <Card className="mt-6 p-2">
              <EmptyState
                glyph="◧"
                title="Nenhum plantão ainda"
                description="Crie o primeiro plantão para o dashboard ganhar vida."
                action={
                  <ButtonLink href="/plantoes/novo">Criar plantão</ButtonLink>
                }
              />
            </Card>
          )}
        </>
      )}
    </div>
  );
}
