"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { StatusPill } from "@/components/ui/StatusPill";
import { ApiError, api } from "@/lib/api";
import { formatBRL, formatShiftWindow } from "@/lib/format";
import { SPECIALTIES, specialtyName } from "@/lib/specialties";
import type { Shift } from "@/lib/types";

// Campo numérico opcional: "" vira undefined (deixa o backend usar o default).
const optionalInt = (min: number) =>
  z.preprocess(
    (v) => (v === "" || v === null || v === undefined ? undefined : v),
    z.coerce.number().int().min(min).optional(),
  );

const schema = z
  .object({
    specialty_id: z.coerce.number().int().min(1, "Selecione a especialidade"),
    starts_at: z.string().min(1, "Informe o início"),
    ends_at: z.string().min(1, "Informe o término"),
    rate_reais: z.coerce.number().positive("Valor deve ser maior que zero"),
    batch_size: optionalInt(1),
    batch_window_minutes: optionalInt(1),
    escalate_hours_before: optionalInt(0),
  })
  .refine((v) => new Date(v.ends_at) > new Date(v.starts_at), {
    message: "O término deve ser depois do início",
    path: ["ends_at"],
  });

// z.coerce/z.preprocess fazem input ≠ output: os campos chegam como string
// (input) e saem validados como number (output). RHF precisa dos dois tipos.
type FormInput = z.input<typeof schema>;
type FormOutput = z.output<typeof schema>;

export default function NovoPlantaoPage() {
  const [created, setCreated] = useState<Shift | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } = useForm<FormInput, any, FormOutput>({ resolver: zodResolver(schema) });

  const createMut = useMutation({
    mutationFn: (v: FormOutput) =>
      api<{ shift: Shift }>("/shifts", {
        method: "POST",
        body: {
          specialty_id: v.specialty_id,
          starts_at: new Date(v.starts_at).toISOString(),
          ends_at: new Date(v.ends_at).toISOString(),
          rate_cents: Math.round(v.rate_reais * 100),
          ...(v.batch_size ? { batch_size: v.batch_size } : {}),
          ...(v.batch_window_minutes
            ? { batch_window_minutes: v.batch_window_minutes }
            : {}),
          ...(v.escalate_hours_before !== undefined
            ? { escalate_hours_before: v.escalate_hours_before }
            : {}),
        },
      }),
    onSuccess: (r) => {
      setCreated(r.shift);
      toast.success("Plantão criado.");
    },
    onError: (e: unknown) =>
      toast.error(
        e instanceof ApiError ? e.message : "Não foi possível criar o plantão.",
      ),
  });

  const offerMut = useMutation({
    mutationFn: (shiftId: string) =>
      api<{ shift: Shift }>(`/shifts/${shiftId}/offer`, {
        method: "POST",
        body: {}, // sem doctor_ids → usa o ranking
      }),
    onSuccess: (r) => {
      setCreated(r.shift);
      toast.success("Ofertas enviadas para o primeiro lote de médicos.");
    },
    onError: (e: unknown) =>
      toast.error(
        e instanceof ApiError ? e.message : "Não foi possível disparar ofertas.",
      ),
  });

  // ---- Estado de sucesso: plantão criado, pronto pra ofertar ----------------
  if (created) {
    return (
      <div className="mx-auto max-w-xl">
        <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
          Plantão criado
        </h1>
        <div className="mt-5 rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] p-5 shadow-[var(--shadow-sm)]">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-display text-lg font-bold text-ink">
              {specialtyName(created.specialty_id)}
            </h2>
            <StatusPill status={created.status} />
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-y-3 text-sm">
            <dt className="text-muted">Horário</dt>
            <dd className="font-data text-right text-ink">
              {formatShiftWindow(created.starts_at, created.ends_at)}
            </dd>
            <dt className="text-muted">Valor</dt>
            <dd className="font-data text-right font-medium text-ink">
              {formatBRL(created.rate_cents)}
            </dd>
            <dt className="text-muted">Lote</dt>
            <dd className="font-data text-right text-ink">
              {created.batch_size} médicos · janela {created.batch_window_minutes}
              min
            </dd>
          </dl>

          {created.status === "open" ? (
            <p className="mt-4 text-sm text-muted">
              O plantão nasce <strong className="text-ink">aberto</strong>. Dispare
              as ofertas para o pipeline começar a chamar os médicos elegíveis.
            </p>
          ) : (
            <p className="mt-4 text-sm text-muted">
              Pipeline em andamento — o primeiro lote já recebeu a oferta.
            </p>
          )}
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          {created.status === "open" && (
            <Button
              onClick={() => offerMut.mutate(created.id)}
              loading={offerMut.isPending}
            >
              Disparar ofertas agora
            </Button>
          )}
          <Button
            variant="secondary"
            onClick={() => {
              setCreated(null);
              reset();
            }}
          >
            Criar outro
          </Button>
          <Link
            href="/plantoes"
            className="inline-flex h-11 items-center rounded-[var(--radius-sm)] px-4 text-sm font-medium text-ink transition-colors hover:bg-[var(--color-surface-2)]"
          >
            Ver plantões
          </Link>
        </div>
      </div>
    );
  }

  // ---- Formulário -----------------------------------------------------------
  return (
    <div className="mx-auto max-w-xl">
      <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
        Novo plantão
      </h1>
      <p className="mt-0.5 text-sm text-muted">
        Crie o plantão. Ele nasce aberto; você dispara as ofertas em seguida.
      </p>

      <form
        onSubmit={handleSubmit((v) => createMut.mutate(v))}
        noValidate
        className="mt-6 flex flex-col gap-5 rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] p-6 shadow-[var(--shadow-sm)]"
      >
        <Select
          label="Especialidade"
          defaultValue=""
          error={errors.specialty_id?.message}
          {...register("specialty_id")}
        >
          <option value="" disabled>
            Selecione…
          </option>
          {SPECIALTIES.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </Select>

        <div className="grid gap-5 sm:grid-cols-2">
          <Input
            label="Início"
            type="datetime-local"
            error={errors.starts_at?.message}
            {...register("starts_at")}
          />
          <Input
            label="Término"
            type="datetime-local"
            error={errors.ends_at?.message}
            {...register("ends_at")}
          />
        </div>

        <Input
          label="Valor (R$)"
          type="number"
          step="0.01"
          min="0"
          inputMode="decimal"
          placeholder="1500,00"
          error={errors.rate_reais?.message}
          {...register("rate_reais")}
        />

        <details className="rounded-[var(--radius-sm)] border border-rule bg-[var(--color-surface-sunk)] p-4">
          <summary className="cursor-pointer text-sm font-medium text-ink-2">
            Ajustes do pipeline (opcional)
          </summary>
          <div className="mt-4 grid gap-5 sm:grid-cols-3">
            <Input
              label="Médicos / lote"
              type="number"
              min="1"
              placeholder="3"
              hint="padrão: 3"
              error={errors.batch_size?.message}
              {...register("batch_size")}
            />
            <Input
              label="Janela (min)"
              type="number"
              min="1"
              placeholder="30"
              hint="padrão: 30"
              error={errors.batch_window_minutes?.message}
              {...register("batch_window_minutes")}
            />
            <Input
              label="Escalar (h antes)"
              type="number"
              min="0"
              placeholder="padrão"
              hint="risco se faltar"
              error={errors.escalate_hours_before?.message}
              {...register("escalate_hours_before")}
            />
          </div>
        </details>

        <Button type="submit" loading={isSubmitting || createMut.isPending}>
          Criar plantão
        </Button>
      </form>
    </div>
  );
}
