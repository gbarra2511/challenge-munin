"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusPill } from "@/components/ui/StatusPill";
import { ApiError, api } from "@/lib/api";
import { formatBRL, formatShiftWindow } from "@/lib/format";
import { specialtyName } from "@/lib/specialties";
import { statusColor, statusLabel } from "@/lib/status";
import { type AuditEvent, describeEvent } from "@/lib/timeline";
import type { Shift, ShiftOfferDetail, ShiftRankingEntry } from "@/lib/types";
import { RankingCard } from "@/components/RankingCard";
import { RankingHeuristic } from "@/components/RankingHeuristic";

interface DoctorLite {
  id: string;
  name: string;
}

export default function PlantaoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [cancelOpen, setCancelOpen] = useState(false);
  // Override manual do 1º lote. null = a coordenadora ainda não mexeu → usamos
  // a pré-seleção derivada do ranking (sem efeito; ver `effectiveSelected`).
  const [selected, setSelected] = useState<Set<string> | null>(null);

  // ---- Queries ----
  const shiftQ = useQuery({
    queryKey: ["shift", id],
    queryFn: () => api<{ shift: Shift }>(`/shifts/${id}`),
    refetchInterval: 15_000,
  });
  const auditQ = useQuery({
    queryKey: ["shift", id, "audit"],
    queryFn: () => api<{ events: AuditEvent[] }>(`/shifts/${id}/audit`),
    refetchInterval: 15_000,
  });
  const doctorsQ = useQuery({
    queryKey: ["doctors"],
    queryFn: () => api<{ doctors: DoctorLite[] }>("/doctors"),
    staleTime: 5 * 60_000,
  });
  const offersQ = useQuery({
    queryKey: ["shift", id, "offers"],
    queryFn: () => api<{ offers: ShiftOfferDetail[] }>(`/shifts/${id}/offers`),
    refetchInterval: 15_000,
    // Só busca quando o shift não está mais em 'open' (já teve ofertas)
    enabled: !!shiftQ.data && shiftQ.data.shift.status !== "open",
  });
  // Ranking explicável: útil enquanto o plantão ainda está sendo preenchido.
  const rankingActive = !!shiftQ.data &&
    ["open", "offering", "needs_attention"].includes(shiftQ.data.shift.status);
  const rankingQ = useQuery({
    queryKey: ["shift", id, "ranking"],
    queryFn: () => api<{ ranking: ShiftRankingEntry[] }>(`/shifts/${id}/ranking`),
    refetchInterval: 30_000,
    enabled: rankingActive,
  });

  // Pré-seleção: os `batch_size` melhores do ranking (derivada, não estado).
  const defaultSelection = useMemo(() => {
    const s = shiftQ.data?.shift;
    const ranking = rankingQ.data?.ranking;
    if (!s || s.status !== "open" || !ranking) return new Set<string>();
    const n = s.batch_size || 3;
    return new Set(ranking.slice(0, n).map((r) => r.doctor.id));
  }, [shiftQ.data, rankingQ.data]);
  // O que de fato vale: override do usuário, ou a pré-seleção do ranking.
  const effectiveSelected = selected ?? defaultSelection;
  const toggleDoctor = (docId: string) =>
    setSelected((prev) => {
      const next = new Set(prev ?? defaultSelection);
      if (next.has(docId)) next.delete(docId);
      else next.add(docId);
      return next;
    });

  // ---- Derived ----
  const doctorName = useMemo(() => {
    const map = new Map(
      (doctorsQ.data?.doctors ?? []).map((d) => [d.id, d.name]),
    );
    return (did: string) => map.get(did) ?? `Dr. ${did.slice(0, 6)}`;
  }, [doctorsQ.data]);

  const timeline = useMemo(
    () => (auditQ.data?.events ?? []).map((e) => describeEvent(e, doctorName)),
    [auditQ.data, doctorName],
  );

  const offersByBatch = useMemo(() => {
    const offers = offersQ.data?.offers ?? [];
    const map = new Map<number, ShiftOfferDetail[]>();
    for (const o of offers) {
      const arr = map.get(o.batch_number) ?? [];
      arr.push(o);
      map.set(o.batch_number, arr);
    }
    return Array.from(map.entries()).sort((a, b) => a[0] - b[0]);
  }, [offersQ.data]);

  // ---- Mutations ----
  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["shift", id] });
    qc.invalidateQueries({ queryKey: ["shifts"] });
  };

  const offerMut = useMutation({
    mutationFn: (doctorIds: string[]) =>
      api<{ shift: Shift }>(`/shifts/${id}/offer`, {
        method: "POST",
        // doctor_ids = override manual; vazio cairia no ranking automático.
        body: doctorIds.length ? { doctor_ids: doctorIds } : {},
      }),
    onSuccess: () => {
      toast.success("Ofertas enviadas para o primeiro lote.");
      invalidateAll();
    },
    onError: (e: unknown) =>
      toast.error(
        e instanceof ApiError ? e.message : "Não foi possível disparar ofertas.",
      ),
  });

  const cancelMut = useMutation({
    mutationFn: () =>
      api<{ shift: Shift }>(`/shifts/${id}/cancel`, { method: "POST" }),
    onSuccess: () => {
      toast.success("Plantão cancelado.");
      setCancelOpen(false);
      invalidateAll();
    },
    onError: (e: unknown) => {
      setCancelOpen(false);
      toast.error(
        e instanceof ApiError ? e.message : "Não foi possível cancelar.",
      );
    },
  });

  const expandMut = useMutation({
    mutationFn: () =>
      api<{ shift: Shift; new_offers: number }>(`/shifts/${id}/expand-pool`, {
        method: "POST",
      }),
    onSuccess: (r) => {
      toast.success(`Pool ampliado — ${r.new_offers} novas ofertas enviadas.`);
      invalidateAll();
    },
    onError: (e: unknown) =>
      toast.error(
        e instanceof ApiError ? e.message : "Não foi possível ampliar o pool.",
      ),
  });

  // ---- Error state ----
  if (shiftQ.isError) {
    const notFound =
      shiftQ.error instanceof ApiError && shiftQ.error.status === 404;
    return (
      <div className="mx-auto max-w-4xl">
        <BackLink />
        <div className="mt-4">
          <ErrorState
            message={
              notFound
                ? "Plantão não encontrado (ou de outro hospital)."
                : shiftQ.error instanceof ApiError
                  ? shiftQ.error.message
                  : "Não foi possível carregar o plantão."
            }
            onRetry={notFound ? undefined : () => shiftQ.refetch()}
          />
        </div>
      </div>
    );
  }

  const shift = shiftQ.data?.shift;
  const canCancel =
    shift?.status === "offering" ||
    shift?.status === "needs_attention" ||
    shift?.status === "accepted";

  return (
    <div className="mx-auto max-w-4xl">
      <BackLink />

      {shiftQ.isLoading || !shift ? (
        <div className="mt-4 flex flex-col gap-4">
          <Skeleton className="h-8 w-56" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <>
          <header className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
                {specialtyName(shift.specialty_id)}
              </h1>
              <p className="font-data mt-0.5 text-xs text-faint">
                Plantão #{shift.id.slice(0, 8)}
              </p>
            </div>
            <StatusPill status={shift.status} />
          </header>

          {/* Grid: conteúdo principal + sidebar de ofertas */}
          <div className="mt-5 grid grid-cols-1 gap-6 md:grid-cols-[1fr_320px]">
            {/* Coluna principal */}
            <div className="flex flex-col gap-6">
              {/* Resumo */}
              <Card className="p-5">
                <dl className="grid grid-cols-2 gap-y-3 text-sm">
                  <dt className="text-muted">Horário</dt>
                  <dd className="font-data text-right text-ink">
                    {formatShiftWindow(shift.starts_at, shift.ends_at)}
                  </dd>
                  <dt className="text-muted">Valor</dt>
                  <dd className="font-data text-right font-medium text-ink">
                    {formatBRL(shift.rate_cents)}
                  </dd>
                  <dt className="text-muted">Lote atual</dt>
                  <dd className="font-data text-right text-ink">
                    {shift.current_batch || "—"} · {shift.batch_size}/lote ·
                    janela {shift.batch_window_minutes}min
                  </dd>
                  <dt className="text-muted">Escala em risco</dt>
                  <dd className="font-data text-right text-ink">
                    {shift.escalate_hours_before}h antes
                  </dd>
                </dl>

                {/* Ações (disparar ofertas vive no card de ranking abaixo,
                    junto da seleção de médicos). */}
                {(canCancel || shift.status === "needs_attention") && (
                <div className="mt-5 flex flex-wrap gap-3">
                  {shift.status === "needs_attention" && (
                    <Button
                      id="btn-expand"
                      variant="secondary"
                      onClick={() => expandMut.mutate()}
                      loading={expandMut.isPending}
                    >
                      Ampliar pool de médicos
                    </Button>
                  )}
                  {canCancel && (
                    <Button
                      id="btn-cancel"
                      variant="danger"
                      onClick={() => setCancelOpen(true)}
                    >
                      Cancelar plantão
                    </Button>
                  )}
                </div>
                )}
              </Card>

              {/* Ranking explicável + override do 1º lote (bônus Tier 1) */}
              {rankingActive && (
                <Card className="p-5">
                  <div className="flex items-baseline justify-between gap-2">
                    <h2 className="font-display text-lg font-bold text-ink">
                      Ranking de médicos
                    </h2>
                    <span className="text-xs text-faint">
                      aceite · recência · carga · resposta
                    </span>
                  </div>
                  {shift.status === "open" && (
                    <p className="mt-1 text-sm text-muted">
                      Marque quem recebe o 1º lote. Pré-selecionei os{" "}
                      {shift.batch_size} melhores — ajuste se quiser.
                    </p>
                  )}
                  <RankingHeuristic />
                  {rankingQ.isLoading ? (
                    <Skeleton className="mt-4 h-32 w-full" />
                  ) : rankingQ.isError ? (
                    <p className="mt-3 text-sm text-muted">
                      Não foi possível carregar o ranking.
                    </p>
                  ) : (
                    <RankingCard
                      entries={rankingQ.data?.ranking ?? []}
                      batchSize={shift.batch_size}
                      selectable={shift.status === "open"}
                      selectedIds={effectiveSelected}
                      onToggle={toggleDoctor}
                    />
                  )}
                  {shift.status === "open" &&
                    !rankingQ.isLoading &&
                    !rankingQ.isError &&
                    (rankingQ.data?.ranking?.length ?? 0) > 0 && (
                      <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-rule pt-4">
                        <Button
                          id="btn-offer"
                          onClick={() => offerMut.mutate([...effectiveSelected])}
                          loading={offerMut.isPending}
                          disabled={effectiveSelected.size === 0}
                        >
                          Disparar ofertas ({effectiveSelected.size})
                        </Button>
                        <span className="flex-1 text-xs text-muted">
                          O 1º lote vai para os médicos marcados. Os demais
                          entram nos próximos lotes se ninguém aceitar.
                        </span>
                      </div>
                    )}
                </Card>
              )}

              {/* Timeline (do audit log) */}
              <Card className="p-5">
                <h2 className="font-display text-lg font-bold text-ink">
                  Timeline
                </h2>
                {auditQ.isLoading ? (
                  <Skeleton className="mt-4 h-32 w-full" />
                ) : timeline.length === 0 ? (
                  <p className="mt-3 text-sm text-muted">
                    Sem eventos ainda. A timeline começa quando você dispara as
                    ofertas.
                  </p>
                ) : (
                  <ol className="ml-1 mt-4 border-l border-rule">
                    {timeline.map((it) => (
                      <li key={it.id} className="relative py-2 pl-5 last:pb-0">
                        <span
                          aria-hidden
                          className="absolute top-3 h-2.5 w-2.5 rounded-full ring-2 ring-[var(--color-surface)]"
                          style={{ left: "-5px", background: it.color }}
                        />
                        <p className="text-sm text-ink">{it.text}</p>
                        <time className="font-data text-xs text-faint">
                          {it.time}
                        </time>
                      </li>
                    ))}
                  </ol>
                )}
              </Card>
            </div>

            {/* Sidebar: ofertas do plantão */}
            <div>
              <Card className="p-5">
                <h2 className="font-display text-lg font-bold text-ink">
                  Ofertas
                </h2>
                {shift.status === "open" ? (
                  <p className="mt-3 text-sm text-muted">
                    Nenhuma oferta enviada ainda. Dispare as ofertas para começar.
                  </p>
                ) : offersQ.isLoading ? (
                  <Skeleton className="mt-4 h-32 w-full" />
                ) : offersByBatch.length === 0 ? (
                  <p className="mt-3 text-sm text-muted">
                    Nenhuma oferta registrada.
                  </p>
                ) : (
                  <div className="mt-4 flex flex-col gap-4">
                    {offersByBatch.map(([batch, offers]) => (
                      <div key={batch}>
                        <h3 className="text-xs font-medium uppercase tracking-wider text-muted">
                          Lote {batch}
                        </h3>
                        <ul className="mt-2 flex flex-col gap-1.5">
                          {offers.map((o) => (
                            <li
                              key={o.id}
                              className="flex items-center gap-2 text-sm"
                            >
                              <span
                                aria-hidden
                                className="h-2 w-2 shrink-0 rounded-full"
                                style={{
                                  background: statusColor(o.status),
                                }}
                              />
                              <span className="min-w-0 truncate text-ink">
                                {o.doctor.name}
                              </span>
                              <span className="ml-auto shrink-0 text-xs text-muted">
                                {statusLabel(o.status)}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>
          </div>
        </>
      )}

      {/* Modal de confirmação de cancelamento */}
      <ConfirmDialog
        open={cancelOpen}
        title="Cancelar plantão?"
        description="Ofertas pendentes serão canceladas e médicos notificados. Esta ação não pode ser desfeita."
        confirmLabel="Sim, cancelar"
        confirmVariant="danger"
        loading={cancelMut.isPending}
        onConfirm={() => cancelMut.mutate()}
        onCancel={() => setCancelOpen(false)}
      />
    </div>
  );
}

function BackLink() {
  return (
    <Link
      href="/plantoes"
      className="inline-flex items-center gap-1 text-sm text-muted transition-colors hover:text-ink"
    >
      ← Plantões
    </Link>
  );
}
