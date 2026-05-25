"use client";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError, api } from "@/lib/api";
import { specialtyName } from "@/lib/specialties";
import type { DoctorListItem, DoctorStats, Unavailability } from "@/lib/types";

export default function MedicoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { data: doctorData, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["doctor", id],
    queryFn: () => api<{ doctor: DoctorListItem }>(`/doctors/${id}`),
  });

  const { data: statsData } = useQuery({
    queryKey: ["doctor-stats", id],
    queryFn: () => api<{ stats: DoctorStats }>(`/doctors/${id}/stats`),
  });

  const { data: unavailData, refetch: refetchUnavail } = useQuery({
    queryKey: ["doctor-unavail", id],
    queryFn: () =>
      api<{ unavailabilities: Unavailability[] }>(
        `/doctors/${id}/unavailabilities`,
      ),
  });

  const deactivateMut = useMutation({
    mutationFn: () => api(`/doctors/${id}/deactivate`, { method: "POST" }),
    onSuccess: () => {
      toast.success("Médico desativado.");
      qc.invalidateQueries({ queryKey: ["doctors"] });
      refetch();
    },
    onError: (e: unknown) =>
      toast.error(
        e instanceof ApiError ? e.message : "Erro ao desativar.",
      ),
  });

  const activateMut = useMutation({
    mutationFn: () => api(`/doctors/${id}/activate`, { method: "POST" }),
    onSuccess: () => {
      toast.success("Médico reativado.");
      qc.invalidateQueries({ queryKey: ["doctors"] });
      refetch();
    },
    onError: (e: unknown) =>
      toast.error(
        e instanceof ApiError ? e.message : "Erro ao ativar.",
      ),
  });

  const deleteUnavailMut = useMutation({
    mutationFn: (unavailId: string) =>
      api(`/doctors/${id}/unavailabilities/${unavailId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      toast.success("Indisponibilidade removida.");
      refetchUnavail();
    },
  });

  const doctor = doctorData?.doctor;
  const stats = statsData?.stats;
  const unavailabilities = unavailData?.unavailabilities ?? [];

  return (
    <div>
      <header className="mb-6">
        <div className="flex items-center gap-3">
          <Link
            href="/medicos"
            className="text-sm text-muted hover:text-ink transition-colors"
          >
            ← Médicos
          </Link>
        </div>
        {isLoading && <Skeleton className="mt-3 h-8 w-48" />}
        {doctor && (
          <div className="mt-3 flex items-center justify-between gap-3">
            <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
              {doctor.name}
            </h1>
            <div className="flex gap-2">
              <button
                onClick={() => activateMut.mutate()}
                className="h-8 rounded-[var(--radius-sm)] border border-rule px-3 text-xs font-medium text-muted hover:bg-[var(--color-surface-2)] hover:text-ink transition-colors"
              >
                Ativar
              </button>
              <button
                onClick={() => deactivateMut.mutate()}
                className="h-8 rounded-[var(--radius-sm)] border border-[var(--status-cancelled)] px-3 text-xs font-medium text-[var(--status-cancelled)] hover:bg-[var(--status-cancelled-soft)] transition-colors"
              >
                Desativar
              </button>
            </div>
          </div>
        )}
      </header>

      {isError && (
        <ErrorState
          message={
            error instanceof ApiError
              ? error.message
              : "Erro ao carregar médico."
          }
          onRetry={() => refetch()}
        />
      )}

      {doctor && (
        <div className="grid gap-5 md:grid-cols-[1fr_280px]">
          {/* Coluna principal */}
          <div className="flex flex-col gap-5">
            {/* Dados */}
            <Card className="p-5">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
                Dados
              </h2>
              <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-xs text-faint">Telefone</dt>
                  <dd className="font-medium text-ink">
                    {doctor.phone || "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-faint">Hospitais</dt>
                  <dd className="font-medium text-ink">
                    {doctor.hospital_ids.length}
                  </dd>
                </div>
              </dl>
              <div className="mt-3">
                <span className="text-xs text-faint">Especialidades</span>
                <div className="mt-1 flex flex-wrap gap-1">
                  {doctor.specialty_ids.map((sid) => (
                    <span
                      key={sid}
                      className="inline-block rounded-full bg-[var(--color-accent-soft)] px-2.5 py-0.5 text-xs font-medium text-accent"
                    >
                      {specialtyName(sid)}
                    </span>
                  ))}
                </div>
              </div>
            </Card>

            {/* Indisponibilidades */}
            <Card className="p-5">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
                Indisponibilidades
              </h2>
              {unavailabilities.length === 0 ? (
                <p className="mt-3 text-sm text-faint">
                  Nenhuma indisponibilidade registrada.
                </p>
              ) : (
                <ul className="mt-4 divide-y divide-[var(--color-rule)]">
                  {unavailabilities.map((u) => {
                    const start = new Date(u.starts_at);
                    const end = new Date(u.ends_at);
                    
                    const formatDt = (d: Date) => 
                      d.toLocaleDateString("pt-BR", { day: "numeric", month: "short" }) +
                      ", " +
                      d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

                    return (
                      <li
                        key={u.id}
                        className="flex items-center justify-between py-3"
                      >
                        <div>
                          <p className="font-data text-sm font-medium text-ink">
                            {formatDt(start)} <span className="text-muted font-normal mx-1">até</span> {formatDt(end)}
                          </p>
                          {u.reason && (
                            <p className="mt-0.5 text-xs text-muted">
                              {u.reason}
                            </p>
                          )}
                        </div>
                        <button
                          onClick={() => deleteUnavailMut.mutate(u.id)}
                          className="shrink-0 text-xs font-medium text-muted hover:text-[var(--status-cancelled)] transition-colors"
                        >
                          Remover
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Card>
          </div>

          {/* Sidebar: métricas */}
          <div className="flex flex-col gap-4">
            {stats ? (
              <>
                <Card className="p-4 text-center">
                  <p className="text-xs text-faint">Taxa de aceite</p>
                  <p className="font-display mt-1 text-3xl font-extrabold text-ink">
                    {stats.acceptance_rate !== null
                      ? `${Math.round(stats.acceptance_rate * 100)}%`
                      : "—"}
                  </p>
                </Card>
                <Card className="p-4 text-center">
                  <p className="text-xs text-faint">Tempo médio de resposta</p>
                  <p className="font-display mt-1 text-3xl font-extrabold text-ink">
                    {stats.avg_response_min !== null
                      ? `${stats.avg_response_min}min`
                      : "—"}
                  </p>
                </Card>
                <Card className="p-4 text-center">
                  <p className="text-xs text-faint">Plantões ativos</p>
                  <p className="font-display mt-1 text-3xl font-extrabold text-accent">
                    {stats.total_assignments}
                  </p>
                </Card>
                <Card className="p-4 text-center">
                  <p className="text-xs text-faint">Total de ofertas</p>
                  <p className="font-display mt-1 text-3xl font-extrabold text-ink">
                    {stats.total_offers}
                  </p>
                  <div className="mt-2 flex justify-center gap-3 text-xs text-muted">
                    <span className="text-[var(--status-accepted)]">
                      ✓ {stats.accepted}
                    </span>
                    <span className="text-[var(--status-cancelled)]">
                      ✕ {stats.declined}
                    </span>
                    <span className="text-[var(--status-needs-attention)]">
                      ⏱ {stats.expired}
                    </span>
                  </div>
                </Card>
              </>
            ) : (
              [0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-24" />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
