"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError, api } from "@/lib/api";
import { formatBRL, formatShiftWindow } from "@/lib/format";
import { specialtyName } from "@/lib/specialties";
import type { SwapRequest } from "@/lib/types";

type Decision = { swap: SwapRequest; action: "approve" | "reject" };

export default function TrocasCoordPage() {
  const qc = useQueryClient();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [reason, setReason] = useState("");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["pending-swaps"],
    queryFn: () => api<{ swaps: SwapRequest[] }>("/swaps?status=pending"),
    refetchInterval: 15_000,
  });

  const decide = useMutation({
    mutationFn: ({ swap, action }: Decision) =>
      api<{ id: string }>(`/swaps/${swap.id}/${action}`, {
        method: "POST",
        body: { reason: reason.trim() || null },
      }),
    onSuccess: (_d, vars) => {
      toast.success(vars.action === "approve" ? "Troca aprovada." : "Troca recusada.");
      qc.invalidateQueries({ queryKey: ["pending-swaps"] });
      qc.invalidateQueries({ queryKey: ["shifts"] });
      setDecision(null);
      setReason("");
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Não foi possível concluir."),
  });

  const swaps = data?.swaps ?? [];

  return (
    <div>
      <header className="mb-6">
        <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
          Trocas de plantão
        </h1>
        <p className="mt-1 text-sm text-muted">
          Pedidos dos médicos para passar plantões a colegas. Aprovar transfere o
          plantão de forma atômica.
        </p>
      </header>

      {isLoading && (
        <div className="flex flex-col gap-3">
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-32 w-full" />
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
            title="Nenhum pedido pendente"
            description="Quando um médico solicitar uma troca, ela aparece aqui para aprovação."
          />
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {swaps.map((s) => (
              <div
                key={s.id}
                className="flex flex-col rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)]"
              >
                <div className="flex items-center justify-between gap-3">
                  <h2 className="font-display text-base font-bold text-ink">
                    {specialtyName(s.shift.specialty_id)}
                  </h2>
                  <span className="text-xs font-medium text-accent">
                    {s.shift.hospital_name}
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1 font-data text-sm text-ink">
                  <span>{formatShiftWindow(s.shift.starts_at, s.shift.ends_at)}</span>
                  <span className="font-medium">{formatBRL(s.shift.rate_cents)}</span>
                </div>
                <p className="mt-3 text-sm text-ink">
                  <span className="font-medium">{s.from_doctor.name}</span>
                  <span className="mx-1.5 text-muted" aria-hidden>
                    →
                  </span>
                  <span className="font-medium">{s.to_doctor.name}</span>
                </p>
                <div className="mt-4 flex gap-2 border-t border-rule pt-3">
                  <Button
                    variant="primary"
                    fullWidth
                    onClick={() => {
                      setReason("");
                      setDecision({ swap: s, action: "approve" });
                    }}
                  >
                    Aprovar
                  </Button>
                  <Button
                    variant="secondary"
                    fullWidth
                    onClick={() => {
                      setReason("");
                      setDecision({ swap: s, action: "reject" });
                    }}
                  >
                    Recusar
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ))}

      {decision && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-[2px]"
          onClick={(e) => e.target === e.currentTarget && setDecision(null)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="decision-title"
        >
          <div className="mx-4 w-full max-w-md rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] p-6 shadow-lg">
            <h2 id="decision-title" className="font-display text-lg font-bold text-ink">
              {decision.action === "approve" ? "Aprovar troca" : "Recusar troca"}
            </h2>
            <p className="mt-1 text-sm text-muted">
              {decision.swap.from_doctor.name} → {decision.swap.to_doctor.name} ·{" "}
              {specialtyName(decision.swap.shift.specialty_id)}
            </p>
            <label className="mt-4 block text-sm font-medium text-ink-2">
              Motivo {decision.action === "approve" ? "(opcional)" : "(recomendado)"}
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={3}
                maxLength={500}
                placeholder={
                  decision.action === "approve"
                    ? "Ex.: cobertura garantida."
                    : "Ex.: colega não tem o perfil para este plantão."
                }
                className="mt-1.5 w-full rounded-[var(--radius-sm)] border border-[var(--color-rule-strong)] bg-[var(--color-surface)] px-3 py-2 text-sm text-ink outline-none focus:border-[var(--color-accent)] focus-visible:ring-2 focus-visible:ring-[var(--color-focus)]"
              />
            </label>
            <p className="mt-1 text-xs text-faint">
              O motivo é enviado ao médico (in-app e WhatsApp).
            </p>
            <div className="mt-5 flex justify-end gap-3">
              <Button
                variant="secondary"
                onClick={() => setDecision(null)}
                disabled={decide.isPending}
              >
                Voltar
              </Button>
              <Button
                variant={decision.action === "approve" ? "primary" : "danger"}
                onClick={() => decide.mutate(decision)}
                loading={decide.isPending}
              >
                {decision.action === "approve" ? "Aprovar troca" : "Recusar troca"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
