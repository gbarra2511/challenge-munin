"use client";
import { useQuery } from "@tanstack/react-query";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusPill } from "@/components/ui/StatusPill";
import { ApiError, api } from "@/lib/api";
import { formatBRL, formatShiftWindow } from "@/lib/format";
import { specialtyName } from "@/lib/specialties";
import type { Assignment } from "@/lib/types";

export default function AgendaPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["assignments"],
    queryFn: () => api<{ assignments: Assignment[] }>("/me/assignments"),
  });

  return (
    <div>
      <header className="mb-5">
        <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
          Agenda
        </h1>
        <p className="mt-0.5 text-sm text-muted">
          Os plantões que você aceitou.
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

      {data && data.assignments.length === 0 && (
        <EmptyState
          glyph="📅"
          title="Sua agenda está livre"
          description="Os plantões que você aceitar nas Ofertas aparecem aqui."
        />
      )}

      {data && data.assignments.length > 0 && (
        <ul className="flex flex-col gap-3">
          {data.assignments.map((a) => (
            <li
              key={a.id}
              className="rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)]"
            >
              <div className="flex items-center justify-between gap-3">
                <h2 className="font-display text-lg font-bold text-ink">
                  {specialtyName(a.shift.specialty_id)}
                </h2>
                <StatusPill status={a.shift.status} />
              </div>
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
      )}
    </div>
  );
}
