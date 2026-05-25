"use client";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusPill } from "@/components/ui/StatusPill";
import { ApiError, api } from "@/lib/api";
import { formatBRL, formatShiftWindow } from "@/lib/format";
import { specialtyName } from "@/lib/specialties";
import type { Assignment } from "@/lib/types";

const STATUS_OPTIONS = [
  { value: "all", label: "Todos" },
  { value: "active", label: "Ativo" },
  { value: "cancelled", label: "Cancelado" },
] as const;

export default function HistoricoPage() {
  const [statusFilter, setStatusFilter] = useState("all");
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
    let list = data?.assignments ?? [];
    if (statusFilter !== "all") {
      list = list.filter((a) => a.status === statusFilter);
    }
    if (hospitalFilter !== "all") {
      list = list.filter((a) => (a.shift.hospital_id ?? "") === hospitalFilter);
    }
    return list;
  }, [data, statusFilter, hospitalFilter]);

  return (
    <div>
      <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
            Histórico
          </h1>
          <p className="mt-0.5 text-sm text-muted">
            Todos os seus plantões aceitos.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {hospitals.length > 1 && (
            <div className="relative">
              <select
                id="hospital-filter"
                value={hospitalFilter}
                onChange={(e) => setHospitalFilter(e.target.value)}
                className="h-9 appearance-none rounded-[var(--radius-sm)] border border-rule bg-[var(--color-surface)] px-3 pr-8 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-[var(--color-focus)]"
              >
                <option value="all">Todos os hospitais</option>
                {hospitals.map(([hid, name]) => (
                  <option key={hid} value={hid}>
                    {name}
                  </option>
                ))}
              </select>
              <span
                aria-hidden
                className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted"
              >
                ▾
              </span>
            </div>
          )}
          <div className="relative">
            <select
              id="historico-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-9 appearance-none rounded-[var(--radius-sm)] border border-rule bg-[var(--color-surface)] px-3 pr-8 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-[var(--color-focus)]"
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <span
              aria-hidden
              className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted"
            >
              ▾
            </span>
          </div>
        </div>
      </header>

      {isLoading && (
        <div className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      )}

      {isError && (
        <ErrorState
          message={
            error instanceof ApiError
              ? error.message
              : "Não foi possível carregar seu histórico."
          }
          onRetry={() => refetch()}
        />
      )}

      {data && filtered.length === 0 && (
        <EmptyState
          glyph="📋"
          title={
            statusFilter === "all"
              ? "Nenhum plantão no histórico"
              : "Nenhum resultado"
          }
          description={
            statusFilter === "all"
              ? "Os plantões que você aceitar nas Ofertas aparecem aqui."
              : "Tente outro filtro."
          }
        />
      )}

      {data && filtered.length > 0 && (
        <>
          {/* Desktop: tabela */}
          <div className="hidden md:block">
            <div className="overflow-x-auto rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] shadow-[var(--shadow-sm)]">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-rule text-left text-xs font-medium uppercase tracking-wider text-muted">
                    <th className="px-4 py-3">Especialidade</th>
                    <th className="px-4 py-3">Hospital</th>
                    <th className="px-4 py-3">Horário</th>
                    <th className="px-4 py-3 text-right">Valor</th>
                    <th className="px-4 py-3 text-right">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((a) => (
                    <tr
                      key={a.id}
                      className="border-b border-rule last:border-0"
                    >
                      <td className="px-4 py-3 font-medium text-ink">
                        {specialtyName(a.shift.specialty_id)}
                      </td>
                      <td className="px-4 py-3 text-muted">
                        {a.shift.hospital_name ?? "—"}
                      </td>
                      <td className="font-data px-4 py-3 text-ink">
                        {formatShiftWindow(a.shift.starts_at, a.shift.ends_at)}
                      </td>
                      <td className="font-data px-4 py-3 text-right font-medium text-ink">
                        {formatBRL(a.shift.rate_cents)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <StatusPill status={a.shift.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Mobile: cards */}
          <ul className="flex flex-col gap-3 md:hidden">
            {filtered.map((a) => (
              <li
                key={a.id}
                className="rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)]"
              >
                <div className="flex items-center justify-between gap-3">
                  <h2 className="font-display text-base font-bold text-ink">
                    {specialtyName(a.shift.specialty_id)}
                  </h2>
                  <StatusPill status={a.shift.status} />
                </div>
                {a.shift.hospital_name && (
                  <p className="mt-1 text-sm text-muted">
                    {a.shift.hospital_name}
                  </p>
                )}
                <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1">
                  <span className="font-data text-sm text-ink">
                    {formatShiftWindow(a.shift.starts_at, a.shift.ends_at)}
                  </span>
                  <span className="font-data text-sm font-medium text-ink">
                    {formatBRL(a.shift.rate_cents)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
