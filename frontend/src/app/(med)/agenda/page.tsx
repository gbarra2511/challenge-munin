"use client";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Select } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusPill } from "@/components/ui/StatusPill";
import { ApiError, api } from "@/lib/api";
import { formatBRL, formatShiftWindow } from "@/lib/format";
import { specialtyName } from "@/lib/specialties";
import type { Assignment } from "@/lib/types";

function groupByDay(items: Assignment[]) {
  const map = new Map<string, Assignment[]>();
  for (const a of items) {
    const key = a.shift.starts_at.slice(0, 10);
    const arr = map.get(key) ?? [];
    arr.push(a);
    map.set(key, arr);
  }
  return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
}

function formatDayLabel(iso: string): string {
  const d = new Date(iso + "T12:00:00");
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  const diff = Math.round(
    (d.getTime() - today.getTime()) / (1000 * 60 * 60 * 24),
  );
  const dateStr = d.toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  if (diff === 0) return `Hoje — ${d.toLocaleDateString("pt-BR", { day: "numeric", month: "long" })}`;
  if (diff === 1) return `Amanhã — ${d.toLocaleDateString("pt-BR", { day: "numeric", month: "long" })}`;
  return dateStr.charAt(0).toUpperCase() + dateStr.slice(1);
}

export default function AgendaPage() {
  const [hospitalFilter, setHospitalFilter] = useState("all");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["assignments"],
    queryFn: () => api<{ assignments: Assignment[] }>("/me/assignments"),
  });

  const hospitals = useMemo(() => {
    const set = new Map<string, string>();
    for (const a of data?.assignments ?? []) {
      if (a.shift.hospital_name) {
        set.set(a.shift.hospital_id ?? "", a.shift.hospital_name);
      }
    }
    return Array.from(set.entries());
  }, [data]);

  const filtered = useMemo(() => {
    const all = data?.assignments ?? [];
    if (hospitalFilter === "all") return all;
    return all.filter((a) => (a.shift.hospital_id ?? "") === hospitalFilter);
  }, [data, hospitalFilter]);

  const grouped = useMemo(() => groupByDay(filtered), [filtered]);
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div>
      <header className="mb-5">
        <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
          Agenda
        </h1>
        <p className="mt-0.5 text-sm text-muted">
          Seus plantões aceitos, organizados por dia.
        </p>
      </header>

      {isLoading && (
        <div className="flex flex-col gap-3">
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      )}

      {isError && (
        <ErrorState
          message={
            error instanceof ApiError
              ? error.message
              : "Não foi possível carregar sua agenda."
          }
          onRetry={() => refetch()}
        />
      )}

      {data && (
        <>
          {hospitals.length > 1 && (
            <div className="mb-4 max-w-[16rem]">
              <Select
                label=""
                aria-label="Filtrar por hospital"
                value={hospitalFilter}
                onChange={(e) => setHospitalFilter(e.target.value)}
                className="h-9 py-0"
              >
                <option value="all">Todos os hospitais</option>
                {hospitals.map(([hid, name]) => (
                  <option key={hid} value={hid}>
                    {name}
                  </option>
                ))}
              </Select>
            </div>
          )}

          {filtered.length === 0 ? (
            <EmptyState
              glyph="📅"
              title={
                hospitalFilter !== "all"
                  ? "Nenhum plantão nesse hospital"
                  : "Sua agenda está livre"
              }
              description="Os plantões que você aceitar nas Ofertas aparecem aqui."
            />
          ) : (
            <div className="flex flex-col gap-5">
              {grouped.map(([dayKey, dayAssignments]) => {
                const isToday = dayKey === today;
                return (
                  <section key={dayKey}>
                    <div className="mb-2 flex items-center gap-3">
                      <h2
                        className={`shrink-0 text-xs font-semibold uppercase tracking-wider ${
                          isToday ? "text-accent" : "text-muted"
                        }`}
                      >
                        {formatDayLabel(dayKey)}
                      </h2>
                      <div className="h-px flex-1 bg-[var(--color-rule)]" />
                    </div>

                    <div className="flex flex-col gap-3">
                      {dayAssignments.map((a) => (
                        <div
                          key={a.id}
                          className={`rounded-[var(--radius-md)] border bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)] ${
                            isToday
                              ? "border-[var(--color-accent)]/30"
                              : "border-rule"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <h3 className="font-display text-lg font-bold text-ink">
                              {specialtyName(a.shift.specialty_id)}
                            </h3>
                            <StatusPill status={a.shift.status} />
                          </div>
                          {a.shift.hospital_name && (
                            <p className="mt-1 text-xs font-medium text-accent">
                              {a.shift.hospital_name}
                            </p>
                          )}
                          <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1">
                            <span className="font-data text-sm text-ink">
                              {formatShiftWindow(
                                a.shift.starts_at,
                                a.shift.ends_at,
                              )}
                            </span>
                            <span className="font-data text-sm font-medium text-ink">
                              {formatBRL(a.shift.rate_cents)}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
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
