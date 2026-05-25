"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { ButtonLink } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Select } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError, api } from "@/lib/api";
import { specialtyName, SPECIALTIES } from "@/lib/specialties";
import type { DoctorListItem, DoctorStats } from "@/lib/types";

export default function MedicosPage() {
  const [search, setSearch] = useState("");
  const [specFilter, setSpecFilter] = useState<string>("all");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["doctors"],
    queryFn: () => api<{ doctors: DoctorListItem[] }>("/doctors"),
  });

  const filtered = useMemo(() => {
    let list = data?.doctors ?? [];
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((d) => d.name.toLowerCase().includes(q));
    }
    if (specFilter !== "all") {
      const sid = parseInt(specFilter);
      list = list.filter((d) => d.specialty_ids.includes(sid));
    }
    return list;
  }, [data, search, specFilter]);

  return (
    <div>
      <header className="mb-5 flex items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
            Médicos
          </h1>
          <p className="mt-0.5 text-sm text-muted">
            Gerencie os médicos do seu hospital.
          </p>
        </div>
        <ButtonLink href="/medicos/novo">Cadastrar médico</ButtonLink>
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
              : "Não foi possível carregar os médicos."
          }
          onRetry={() => refetch()}
        />
      )}

      {data && data.doctors.length === 0 && (
        <EmptyState
          glyph="⊕"
          title="Nenhum médico cadastrado"
          description="Cadastre o primeiro médico para começar."
        />
      )}

      {data && data.doctors.length > 0 && (
        <>
          {/* Filtros */}
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <input
              type="text"
              placeholder="Buscar por nome…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9 w-56 rounded-[var(--radius-sm)] border border-rule bg-[var(--color-surface)] px-3 text-sm text-ink placeholder:text-faint outline-none focus:border-[var(--color-accent)] transition-colors"
            />
            <div className="w-48">
              <Select
                label=""
                aria-label="Filtrar por especialidade"
                value={specFilter}
                onChange={(e) => setSpecFilter(e.target.value)}
                className="h-9 py-0"
              >
                <option value="all">
                  Todas as especialidades
                </option>
                {SPECIALTIES.map((s) => (
                  <option key={s.id} value={String(s.id)}>
                    {s.name}
                  </option>
                ))}
              </Select>
            </div>
            <span className="text-xs text-faint">
              {filtered.length} médico{filtered.length !== 1 ? "s" : ""}
            </span>
          </div>

          {filtered.length === 0 ? (
            <p className="rounded-[var(--radius-md)] border border-dashed border-rule bg-[var(--color-surface)] px-4 py-8 text-center text-sm text-muted">
              Nenhum médico encontrado.
            </p>
          ) : (
            <div className="overflow-hidden rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] shadow-[var(--shadow-sm)]">
              {/* Header da tabela (desktop) */}
              <div className="hidden border-b border-rule bg-[var(--color-surface-sunk)]/40 px-4 py-2.5 sm:grid sm:grid-cols-[1fr_auto_auto]">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted">
                  Nome
                </span>
                <span className="w-48 text-xs font-semibold uppercase tracking-wider text-muted">
                  Especialidades
                </span>
                <span className="w-24 text-right text-xs font-semibold uppercase tracking-wider text-muted">
                  Plantões
                </span>
              </div>

              <ul className="divide-y divide-[var(--color-rule)]">
                {filtered.map((d) => (
                  <li key={d.id}>
                    <Link
                      href={`/medicos/${d.id}`}
                      className="flex flex-col gap-1 px-4 py-3.5 transition-colors hover:bg-[var(--color-surface-2)] sm:grid sm:grid-cols-[1fr_auto_auto] sm:items-center sm:gap-4"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium text-ink">
                          {d.name}
                        </p>
                        {d.phone && (
                          <p className="mt-0.5 text-xs text-muted">{d.phone}</p>
                        )}
                      </div>
                      <div className="flex w-48 flex-wrap gap-1">
                        {d.specialty_ids.map((sid) => (
                          <span
                            key={sid}
                            className="inline-block rounded-full bg-[var(--color-accent-soft)] px-2 py-0.5 text-[10px] font-medium text-accent"
                          >
                            {specialtyName(sid)}
                          </span>
                        ))}
                      </div>
                      <span className="w-24 text-right text-sm text-muted">
                        →
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
