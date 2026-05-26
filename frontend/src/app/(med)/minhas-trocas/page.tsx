"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError, api } from "@/lib/api";
import { formatBRL, formatShiftWindow } from "@/lib/format";
import { specialtyName } from "@/lib/specialties";
import type { SwapRequest, SwapStatus } from "@/lib/types";

const SWAP_META: Record<SwapStatus, { label: string; cls: string }> = {
  pending: { label: "Aguardando coordenação", cls: "text-[var(--status-offering)]" },
  approved: { label: "Aprovada", cls: "text-[var(--status-accepted)]" },
  rejected: { label: "Recusada", cls: "text-[var(--status-needs-attention)]" },
  cancelled: { label: "Cancelada", cls: "text-faint" },
};

export default function MinhasTrocasPage() {
  const qc = useQueryClient();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["my-swaps"],
    queryFn: () => api<{ swaps: SwapRequest[] }>("/me/swaps"),
    refetchInterval: 20_000,
  });

  const cancel = useMutation({
    mutationFn: (id: string) => api<void>(`/swaps/${id}/cancel`, { method: "POST" }),
    onSuccess: () => {
      toast.success("Pedido de troca cancelado.");
      qc.invalidateQueries({ queryKey: ["my-swaps"] });
      qc.invalidateQueries({ queryKey: ["assignments"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Não foi possível cancelar."),
  });

  const swaps = data?.swaps ?? [];

  return (
    <div>
      <header className="mb-5">
        <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
          Minhas trocas
        </h1>
        <p className="mt-0.5 text-sm text-muted">
          Pedidos para passar seus plantões a colegas.
        </p>
      </header>

      {isLoading && (
        <div className="flex flex-col gap-3">
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      )}

      {isError && (
        <ErrorState
          message={
            error instanceof ApiError ? error.message : "Não foi possível carregar."
          }
          onRetry={() => refetch()}
        />
      )}

      {data &&
        (swaps.length === 0 ? (
          <EmptyState
            glyph="⇄"
            title="Nenhuma troca solicitada"
            description="Use o botão 'Pedir troca' na Agenda para passar um plantão a um colega."
          />
        ) : (
          <div className="flex flex-col gap-3">
            {swaps.map((s) => {
              const meta = SWAP_META[s.status];
              return (
                <div
                  key={s.id}
                  className="rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)]"
                >
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="font-display text-base font-bold text-ink">
                      {specialtyName(s.shift.specialty_id)}
                    </h2>
                    <span className={`text-xs font-semibold ${meta.cls}`}>
                      {meta.label}
                    </span>
                  </div>
                  <p className="mt-1 text-xs font-medium text-accent">
                    {s.shift.hospital_name}
                  </p>
                  <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1 font-data text-sm text-ink">
                    <span>{formatShiftWindow(s.shift.starts_at, s.shift.ends_at)}</span>
                    <span className="font-medium">{formatBRL(s.shift.rate_cents)}</span>
                  </div>
                  <p className="mt-2 text-sm text-muted">
                    Para <span className="font-medium text-ink">{s.to_doctor.name}</span>
                  </p>
                  {s.status === "rejected" && s.reason && (
                    <p className="mt-1 text-sm text-[var(--status-needs-attention)]">
                      Motivo: {s.reason}
                    </p>
                  )}
                  {s.status === "pending" && (
                    <div className="mt-3 border-t border-rule pt-3">
                      <Button
                        variant="secondary"
                        onClick={() => cancel.mutate(s.id)}
                        loading={cancel.isPending && cancel.variables === s.id}
                      >
                        Cancelar pedido
                      </Button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
    </div>
  );
}
