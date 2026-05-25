"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { ButtonLink } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Select } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusPill } from "@/components/ui/StatusPill";
import { ApiError, api } from "@/lib/api";
import { formatBRL, formatShiftWindow } from "@/lib/format";
import { specialtyName } from "@/lib/specialties";
import { SHIFT_STATUSES, statusLabel } from "@/lib/status";
import type { Shift } from "@/lib/types";

/** Agrupa shifts pelo dia (string "YYYY-MM-DD"). */
function groupByDay(shifts: Shift[]) {
  const map = new Map<string, Shift[]>();
  for (const s of shifts) {
    const key = s.starts_at.slice(0, 10); // "2026-05-25"
    const arr = map.get(key) ?? [];
    arr.push(s);
    map.set(key, arr);
  }
  return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
}

function formatDayLabel(isoDate: string): string {
  const d = new Date(isoDate + "T12:00:00"); // evita fuso off-by-one
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  const diff = Math.round(
    (d.getTime() - today.getTime()) / (1000 * 60 * 60 * 24),
  );
  const weekday = d.toLocaleDateString("pt-BR", { weekday: "long" });
  const dateStr = d.toLocaleDateString("pt-BR", {
    day: "numeric",
    month: "long",
  });

  if (diff === 0) return `Hoje — ${dateStr}`;
  if (diff === 1) return `Amanhã — ${dateStr}`;
  if (diff === -1) return `Ontem — ${dateStr}`;
  return `${weekday.charAt(0).toUpperCase() + weekday.slice(1)} — ${dateStr}`;
}

function isToday(isoDate: string): boolean {
  const today = new Date().toISOString().slice(0, 10);
  return isoDate === today;
}

function isPast(isoDate: string): boolean {
  const today = new Date().toISOString().slice(0, 10);
  return isoDate < today;
}

export default function PlantoesPage() {
  const [status, setStatus] = useState<string>("all");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["shifts"],
    queryFn: () => api<{ shifts: Shift[] }>("/shifts"),
    refetchInterval: 15_000,
  });

  const shifts = useMemo(() => {
    const all = data?.shifts ?? [];
    return status === "all" ? all : all.filter((s) => s.status === status);
  }, [data, status]);

  const grouped = useMemo(() => groupByDay(shifts), [shifts]);

  return (
    <div>
      <header className="mb-5 flex items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
            Plantões
          </h1>
          <p className="mt-0.5 text-sm text-muted">
            Todos os plantões do seu hospital.
          </p>
        </div>
        <ButtonLink href="/plantoes/novo" className="hidden sm:inline-flex">
          <span aria-hidden>＋</span> Novo plantão
        </ButtonLink>
      </header>

      {isLoading && (
        <div className="flex flex-col gap-2">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      )}

      {isError && (
        <ErrorState
          message={
            error instanceof ApiError
              ? error.message
              : "Não foi possível carregar os plantões."
          }
          onRetry={() => refetch()}
        />
      )}

      {data && data.shifts.length === 0 && (
        <EmptyState
          glyph="📋"
          title="Nenhum plantão ainda"
          description="Crie o primeiro plantão e dispare as ofertas para começar a preencher."
          action={<ButtonLink href="/plantoes/novo">Criar plantão</ButtonLink>}
        />
      )}

      {data && data.shifts.length > 0 && (
        <>
          <div className="mb-4 max-w-[16rem]">
            <Select
              label=""
              aria-label="Filtrar por status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="h-9 py-0"
            >
              <option value="all">Todos os status ({data.shifts.length})</option>
              {SHIFT_STATUSES.map((st) => (
                <option key={st} value={st}>
                  {statusLabel(st)}
                </option>
              ))}
            </Select>
          </div>

          {shifts.length === 0 ? (
            <p className="rounded-[var(--radius-md)] border border-dashed border-rule bg-[var(--color-surface)] px-4 py-8 text-center text-sm text-muted">
              Nenhum plantão com status &ldquo;{statusLabel(status)}&rdquo;.
            </p>
          ) : (
            <div className="flex flex-col gap-5">
              {grouped.map(([dayKey, dayShifts]) => {
                const today = isToday(dayKey);
                const past = isPast(dayKey);
                return (
                  <section key={dayKey}>
                    {/* Separador do dia */}
                    <div className="mb-2 flex items-center gap-3">
                      <h2
                        className={`shrink-0 text-xs font-semibold uppercase tracking-wider ${
                          today
                            ? "text-accent"
                            : past
                              ? "text-faint"
                              : "text-muted"
                        }`}
                      >
                        {formatDayLabel(dayKey)}
                      </h2>
                      <div className="h-px flex-1 bg-[var(--color-rule)]" />
                      <span className="font-data shrink-0 text-xs tabular-nums text-faint">
                        {dayShifts.length}
                      </span>
                    </div>

                    {/* Lista de plantões do dia */}
                    <ul
                      className={`divide-y divide-[var(--color-rule)] overflow-hidden rounded-[var(--radius-md)] border bg-[var(--color-surface)] shadow-[var(--shadow-sm)] ${
                        today
                          ? "border-[var(--color-accent)]/30"
                          : "border-rule"
                      }`}
                    >
                      {dayShifts.map((s) => (
                        <li key={s.id}>
                          <Link
                            href={`/plantoes/${s.id}`}
                            className="flex items-center justify-between gap-4 px-4 py-3.5 transition-colors hover:bg-[var(--color-surface-2)]"
                          >
                            <div className="min-w-0">
                              <p className="truncate font-medium text-ink">
                                {specialtyName(s.specialty_id)}
                              </p>
                              <p className="font-data mt-0.5 text-xs text-muted">
                                {formatShiftWindow(s.starts_at, s.ends_at)}
                              </p>
                            </div>
                            <div className="flex shrink-0 items-center gap-3 sm:gap-4">
                              <span className="font-data text-sm font-medium text-ink">
                                {formatBRL(s.rate_cents)}
                              </span>
                              <StatusPill status={s.status} />
                            </div>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </section>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
