"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ButtonLink } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusPill } from "@/components/ui/StatusPill";
import { ApiError, api } from "@/lib/api";
import { formatBRL, formatShiftWindow } from "@/lib/format";
import { specialtyName } from "@/lib/specialties";
import type { Shift } from "@/lib/types";

export default function PlantoesPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["shifts"],
    queryFn: () => api<{ shifts: Shift[] }>("/shifts"),
    refetchInterval: 15_000,
  });

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
        <Link
          href="/plantoes/novo"
          className="hidden h-10 items-center gap-2 rounded-[var(--radius-sm)] bg-[var(--color-accent)] px-3 text-sm font-medium text-[var(--color-accent-ink)] shadow-[var(--shadow-sm)] transition-colors hover:bg-[var(--color-accent-hover)] sm:inline-flex"
        >
          <span aria-hidden>＋</span> Novo plantão
        </Link>
      </header>

      {isLoading && (
        <div className="flex flex-col gap-2">
          {[0, 1, 2].map((i) => (
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
          glyph="≣"
          title="Nenhum plantão ainda"
          description="Crie o primeiro plantão e dispare as ofertas para começar a preencher."
          action={<ButtonLink href="/plantoes/novo">Criar plantão</ButtonLink>}
        />
      )}

      {data && data.shifts.length > 0 && (
        <ul className="divide-y divide-[var(--color-rule)] overflow-hidden rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)]">
          {data.shifts.map((s) => (
            <li key={s.id}>
              <Link
                href={`/plantoes/${s.id}`}
                className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 transition-colors hover:bg-[var(--color-surface-2)]"
              >
                <span className="min-w-0 flex-1 font-medium text-ink">
                  {specialtyName(s.specialty_id)}
                </span>
                <span className="font-data text-sm text-muted">
                  {formatShiftWindow(s.starts_at, s.ends_at)}
                </span>
                <span className="font-data text-sm font-medium text-ink">
                  {formatBRL(s.rate_cents)}
                </span>
                <StatusPill status={s.status} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
