"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusPill } from "@/components/ui/StatusPill";
import { ApiError, api } from "@/lib/api";
import { formatBRL, formatShiftWindow } from "@/lib/format";
import { specialtyName } from "@/lib/specialties";
import { type AuditEvent, describeEvent } from "@/lib/timeline";
import type { Shift } from "@/lib/types";

interface DoctorLite {
  id: string;
  name: string;
}

export default function PlantaoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

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
  // Mapa id → nome para humanizar a timeline.
  const doctorsQ = useQuery({
    queryKey: ["doctors"],
    queryFn: () => api<{ doctors: DoctorLite[] }>("/doctors"),
    staleTime: 5 * 60_000,
  });

  const doctorName = useMemo(() => {
    const map = new Map((doctorsQ.data?.doctors ?? []).map((d) => [d.id, d.name]));
    return (did: string) => map.get(did) ?? `Dr. ${did.slice(0, 6)}`;
  }, [doctorsQ.data]);

  const timeline = useMemo(
    () => (auditQ.data?.events ?? []).map((e) => describeEvent(e, doctorName)),
    [auditQ.data, doctorName],
  );

  const offerMut = useMutation({
    mutationFn: () =>
      api<{ shift: Shift }>(`/shifts/${id}/offer`, { method: "POST", body: {} }),
    onSuccess: () => {
      toast.success("Ofertas enviadas para o primeiro lote.");
      qc.invalidateQueries({ queryKey: ["shift", id] });
    },
    onError: (e: unknown) =>
      toast.error(
        e instanceof ApiError ? e.message : "Não foi possível disparar ofertas.",
      ),
  });

  if (shiftQ.isError) {
    const notFound =
      shiftQ.error instanceof ApiError && shiftQ.error.status === 404;
    return (
      <div className="mx-auto max-w-2xl">
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

  return (
    <div className="mx-auto max-w-2xl">
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

          {/* Resumo */}
          <Card className="mt-5 p-5">
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
                {shift.current_batch || "—"} · {shift.batch_size}/lote · janela{" "}
                {shift.batch_window_minutes}min
              </dd>
              <dt className="text-muted">Escala em risco</dt>
              <dd className="font-data text-right text-ink">
                {shift.escalate_hours_before}h antes
              </dd>
            </dl>

            {shift.status === "open" && (
              <Button
                className="mt-5"
                onClick={() => offerMut.mutate()}
                loading={offerMut.isPending}
              >
                Disparar ofertas agora
              </Button>
            )}
            {shift.status === "needs_attention" && (
              <p className="mt-5 rounded-[var(--radius-sm)] bg-[var(--status-needs-attention-soft)] px-3 py-2 text-sm text-ink">
                Em risco. Ampliar o pool / cancelar dependem de endpoints ainda
                não implementados no backend.
              </p>
            )}
          </Card>

          {/* Timeline (do audit log) */}
          <Card className="mt-6 p-5">
            <h2 className="font-display text-lg font-bold text-ink">Timeline</h2>
            {auditQ.isLoading ? (
              <Skeleton className="mt-4 h-32 w-full" />
            ) : timeline.length === 0 ? (
              <p className="mt-3 text-sm text-muted">
                Sem eventos ainda. A timeline começa quando você dispara as
                ofertas.
              </p>
            ) : (
              <ol className="mt-4 ml-1 border-l border-rule">
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
        </>
      )}
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
