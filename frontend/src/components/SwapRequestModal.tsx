"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { ApiError, api } from "@/lib/api";
import type { SwapCandidate } from "@/lib/types";

interface Props {
  assignmentId: string;
  shiftLabel: string;
  open: boolean;
  onClose: () => void;
}

// Modal: o médico escolhe um colega elegível para assumir o plantão e envia o
// pedido à coordenação. Candidatos vêm ranqueados (especialista primeiro).
export function SwapRequestModal({ assignmentId, shiftLabel, open, onClose }: Props) {
  const qc = useQueryClient();
  const [toDoctorId, setToDoctorId] = useState("");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["swap-candidates", assignmentId],
    queryFn: () =>
      api<{ candidates: SwapCandidate[] }>(`/me/assignments/${assignmentId}/swap-candidates`),
    enabled: open,
  });

  const submit = useMutation({
    mutationFn: () =>
      api<{ id: string }>("/swaps", {
        method: "POST",
        body: { assignment_id: assignmentId, to_doctor_id: toDoctorId },
      }),
    onSuccess: () => {
      toast.success("Pedido de troca enviado à coordenação.");
      qc.invalidateQueries({ queryKey: ["assignments"] });
      qc.invalidateQueries({ queryKey: ["my-swaps"] });
      setToDoctorId("");
      onClose();
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Não foi possível enviar o pedido."),
  });

  if (!open) return null;
  const candidates = data?.candidates ?? [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-[2px]"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      role="dialog"
      aria-modal="true"
      aria-labelledby="swap-title"
    >
      <div className="mx-4 w-full max-w-md rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] p-6 shadow-lg">
        <h2 id="swap-title" className="font-display text-lg font-bold text-ink">
          Pedir troca de plantão
        </h2>
        <p className="mt-1 text-sm text-muted">{shiftLabel}</p>

        <div className="mt-4">
          {isLoading && <p className="text-sm text-muted">Carregando colegas elegíveis…</p>}
          {isError && (
            <p className="text-sm text-[var(--status-needs-attention)]">
              Não foi possível carregar os candidatos.
            </p>
          )}
          {data && candidates.length === 0 && (
            <p className="text-sm text-muted">
              Nenhum colega elegível e disponível para este plantão.
            </p>
          )}
          {data && candidates.length > 0 && (
            <Select
              label="Passar o plantão para"
              value={toDoctorId}
              onChange={(e) => setToDoctorId(e.target.value)}
            >
              <option value="">Selecione um colega…</option>
              {candidates.map((c) => (
                <option key={c.doctor.id} value={c.doctor.id}>
                  {c.doctor.name}
                  {c.is_specialist ? "" : " (fora da especialidade)"}
                </option>
              ))}
            </Select>
          )}
        </div>

        <div className="mt-5 flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose} disabled={submit.isPending}>
            Voltar
          </Button>
          <Button
            variant="primary"
            onClick={() => submit.mutate()}
            loading={submit.isPending}
            disabled={!toDoctorId}
          >
            Enviar pedido
          </Button>
        </div>
      </div>
    </div>
  );
}
