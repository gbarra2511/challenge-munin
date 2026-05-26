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
import {
  STATUS_META,
  isFilled,
  isOpenish,
  statusColor,
  statusLabel,
  statusSoft,
} from "@/lib/status";
import type { Shift } from "@/lib/types";

const HOUR = 3_600_000;
const RISK_WINDOW_H = 12; // <12h sem aceite = em risco (PLANO §9)

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
  { key: "open", label: "Não ofertados" },
  { key: "offering", label: "Em oferta" },
  { key: "accepted", label: "Preenchidos" },
  { key: "needs_attention", label: "Em risco" },
] as const;

// Ordem de empilhamento + legenda (sem cancelled, que é ruído no overview).
const BAR_STATUSES = ["needs_attention", "offering", "open", "accepted", "confirmed"];

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

    const start = new Date();
    start.setHours(0, 0, 0, 0);
    const present = new Set<string>();
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
      let riskCount = 0;
      for (const s of inDay) {
        byStatus[s.status] = (byStatus[s.status] ?? 0) + 1;
        present.add(s.status);
        if (isAtRisk(s)) riskCount += 1;
      }
      return { day, total: inDay.length, byStatus, riskCount };
    });
    const maxTotal = Math.max(1, ...days.map((d) => d.total));
    const legend = BAR_STATUSES.filter((s) => present.has(s));

    return { counts, risk, days, maxTotal, legend };
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
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      )}

      {data && (
        <>
          {/* KPIs — glyph distinto por status (○ ● ✓ ▲), risco destacado */}
          <section className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
            {KPIS.map((k) => {
              // "Em risco" usa a regra ampla (mesma da lista): needs_attention
              // OU aberto/em oferta começando em <12h — "em risco de buraco"
              // (README). Os demais KPIs contam pelo status literal.
              const count =
                k.key === "needs_attention" ? view.risk.length : view.counts[k.key];
              const alert = k.key === "needs_attention" && count > 0;
              return (
                <Card
                  key={k.key}
                  className="p-5"
                  style={
                    alert
                      ? {
                          borderColor: statusColor(k.key),
                          background: statusSoft(k.key),
                        }
                      : undefined
                  }
                >
                  <div className="flex items-center gap-2">
                    <span
                      aria-hidden
                      className="text-base leading-none"
                      style={{ color: statusColor(k.key) }}
                    >
                      {STATUS_META[k.key].glyph}
                    </span>
                    <span className="text-sm text-muted">{k.label}</span>
                  </div>
                  <p
                    className="font-display mt-2 text-4xl font-extrabold tabular-nums tracking-[-0.02em]"
                    style={{ color: alert ? statusColor(k.key) : "var(--color-ink)" }}
                  >
                    {count}
                  </p>
                </Card>
              );
            })}
          </section>

          {/* Próximos 7 dias — colunas empilhadas por status */}
          <Card className="mt-6 p-5">
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
              <h2 className="font-display text-lg font-bold text-ink">
                Próximos 7 dias
              </h2>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                {view.legend.map((s) => (
                  <span
                    key={s}
                    className="flex items-center gap-1.5 text-xs text-muted"
                  >
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{ background: statusColor(s) }}
                    />
                    {statusLabel(s)}
                  </span>
                ))}
                {view.risk.length > 0 && (
                  <span className="flex items-center gap-1 text-xs text-muted">
                    <span style={{ color: "var(--status-needs-attention)" }}>
                      ▲
                    </span>
                    em risco
                  </span>
                )}
              </div>
            </div>

            {/* Colunas: altura = carga do dia, relativa ao pico da semana. */}
            <div className="mt-6 flex items-stretch gap-1.5 sm:gap-2.5">
              {view.days.map(({ day, total, byStatus, riskCount }, i) => {
                const today = i === 0;
                const heightPct = view.maxTotal
                  ? (total / view.maxTotal) * 100
                  : 0;
                const weekday = day
                  .toLocaleDateString("pt-BR", { weekday: "short" })
                  .replace(".", "");

                return (
                  <div key={i} className="flex flex-1 flex-col items-center">
                    {/* total acima da coluna; ▲ laranja sinaliza risco no dia */}
                    <div className="mb-1.5 flex items-center justify-center gap-1">
                      {riskCount > 0 && (
                        <span
                          aria-hidden
                          title={`${riskCount} em risco`}
                          className="text-[10px] leading-none"
                          style={{ color: "var(--status-needs-attention)" }}
                        >
                          ▲
                        </span>
                      )}
                      <span
                        className={`font-data text-xs tabular-nums ${
                          total ? "font-semibold text-ink" : "text-faint"
                        }`}
                      >
                        {total || "—"}
                      </span>
                    </div>

                    {/* área da coluna (altura fixa) com baseline */}
                    <div
                      className={`flex h-32 w-full items-end justify-center border-b-2 ${
                        today
                          ? "border-[var(--color-accent)]"
                          : "border-[var(--color-rule)]"
                      }`}
                    >
                      {total > 0 ? (
                        <div
                          className="flex w-full max-w-[2.5rem] flex-col-reverse overflow-hidden rounded-t-md transition-[filter] hover:brightness-105"
                          style={{ height: `${Math.max(6, heightPct)}%` }}
                        >
                          {BAR_STATUSES.filter((s) => byStatus[s]).map((s) => (
                            <div
                              key={s}
                              title={`${byStatus[s]} ${statusLabel(s)}`}
                              style={{
                                flex: byStatus[s],
                                background: statusColor(s),
                              }}
                            />
                          ))}
                        </div>
                      ) : (
                        <div className="h-1 w-full max-w-[2.5rem] rounded-full bg-[var(--color-surface-sunk)]" />
                      )}
                    </div>

                    {/* rótulo do dia */}
                    <div className="mt-2 text-center">
                      <div
                        className={`text-xs font-semibold capitalize ${
                          today ? "text-accent" : "text-ink-2"
                        }`}
                      >
                        {today ? "Hoje" : weekday}
                      </div>
                      <div className="font-data text-[11px] tabular-nums text-faint">
                        {day.getDate()}
                      </div>
                    </div>
                  </div>
                );
              })}
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
              <ul className="mt-3 divide-y divide-[var(--color-rule)]">
                {view.risk.map((s) => (
                  <li key={s.id}>
                    <Link
                      href={`/plantoes/${s.id}`}
                      className="flex items-center justify-between gap-4 rounded-[var(--radius-sm)] px-2 py-3 transition-colors hover:bg-[var(--color-surface-2)]"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium text-ink">
                          {specialtyName(s.specialty_id)}
                        </p>
                        <p className="font-data mt-0.5 text-xs text-muted">
                          {formatShiftWindow(s.starts_at, s.ends_at)} ·{" "}
                          <span style={{ color: "var(--status-needs-attention)" }}>
                            começa {relStart(s.starts_at)}
                          </span>
                        </p>
                      </div>
                      <StatusPill status={s.status} className="shrink-0" />
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
                action={<ButtonLink href="/plantoes/novo">Criar plantão</ButtonLink>}
              />
            </Card>
          )}
        </>
      )}
    </div>
  );
}
