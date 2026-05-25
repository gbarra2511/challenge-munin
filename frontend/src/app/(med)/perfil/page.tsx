"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError, api } from "@/lib/api";
import type { DoctorProfile, Unavailability } from "@/lib/types";

export default function PerfilPage() {
  const qc = useQueryClient();

  const {
    data: profileData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["me-profile"],
    queryFn: () => api<{ profile: DoctorProfile }>("/me/profile"),
  });

  const { data: unavailData, refetch: refetchUnavail } = useQuery({
    queryKey: ["me-unavail"],
    queryFn: () =>
      api<{ unavailabilities: Unavailability[] }>("/me/unavailabilities"),
  });

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");

  const [unavailStart, setUnavailStart] = useState("");
  const [unavailEnd, setUnavailEnd] = useState("");
  const [unavailReason, setUnavailReason] = useState("");
  const [repeatWeeks, setRepeatWeeks] = useState(0);

  const profile = profileData?.profile;
  const unavailabilities = unavailData?.unavailabilities ?? [];

  const updateMut = useMutation({
    mutationFn: (body: { name?: string; phone?: string }) =>
      api("/me/profile", {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      toast.success("Perfil atualizado.");
      setEditing(false);
      refetch();
    },
    onError: (e: unknown) =>
      toast.error(e instanceof ApiError ? e.message : "Erro ao atualizar."),
  });

  const createUnavailMut = useMutation({
    mutationFn: () =>
      api("/me/unavailabilities", {
        method: "POST",
        body: JSON.stringify({
          starts_at: new Date(unavailStart).toISOString(),
          ends_at: new Date(unavailEnd).toISOString(),
          reason: unavailReason || null,
          repeat_weeks: repeatWeeks,
        }),
      }),
    onSuccess: () => {
      toast.success("Indisponibilidade registrada.");
      setUnavailStart("");
      setUnavailEnd("");
      setUnavailReason("");
      setRepeatWeeks(0);
      refetchUnavail();
    },
    onError: (e: unknown) =>
      toast.error(e instanceof ApiError ? e.message : "Erro ao registrar."),
  });

  const deleteUnavailMut = useMutation({
    mutationFn: (id: string) =>
      api(`/me/unavailabilities/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("Indisponibilidade removida.");
      refetchUnavail();
    },
  });

  const startEditing = () => {
    if (profile) {
      setName(profile.name);
      setPhone(profile.phone ?? "");
      setEditing(true);
    }
  };

  return (
    <div>
      <header className="mb-5">
        <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
          Meu Perfil
        </h1>
        <p className="mt-0.5 text-sm text-muted">
          Seus dados e indisponibilidades.
        </p>
      </header>

      {isLoading && (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      )}

      {isError && (
        <ErrorState
          message={
            error instanceof ApiError
              ? error.message
              : "Erro ao carregar perfil."
          }
          onRetry={() => refetch()}
        />
      )}

      {profile && (
        <div className="flex flex-col gap-5">
          {/* Dados pessoais */}
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
                Dados pessoais
              </h2>
              {!editing && (
                <button
                  onClick={startEditing}
                  className="text-xs font-medium text-accent hover:underline"
                >
                  Editar
                </button>
              )}
            </div>

            {editing ? (
              <div className="mt-3 flex flex-col gap-3">
                <Input
                  label="Nome"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
                <Input
                  label="Telefone"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
                <div className="flex gap-2">
                  <Button
                    onClick={() => updateMut.mutate({ name, phone })}
                    disabled={updateMut.isPending}
                  >
                    {updateMut.isPending ? "Salvando…" : "Salvar"}
                  </Button>
                  <Button variant="ghost" onClick={() => setEditing(false)}>
                    Cancelar
                  </Button>
                </div>
              </div>
            ) : (
              <dl className="mt-3 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs text-faint">Nome</dt>
                  <dd className="font-medium text-ink">{profile.name}</dd>
                </div>
                <div>
                  <dt className="text-xs text-faint">Email</dt>
                  <dd className="font-medium text-ink">
                    {profile.email ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-faint">Telefone</dt>
                  <dd className="font-medium text-ink">
                    {profile.phone || "—"}
                  </dd>
                </div>
              </dl>
            )}
          </Card>

          {/* Especialidades e Hospitais */}
          <Card className="p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
              Vínculos
            </h2>
            <div className="mt-3">
              <p className="text-xs text-faint">Especialidades</p>
              <div className="mt-1 flex flex-wrap gap-1">
                {profile.specialties.map((s) => (
                  <span
                    key={s.id}
                    className="inline-block rounded-full bg-[var(--color-accent-soft)] px-2.5 py-0.5 text-xs font-medium text-accent"
                  >
                    {s.name}
                  </span>
                ))}
              </div>
            </div>
            <div className="mt-4">
              <p className="text-xs text-faint">Hospitais</p>
              <ul className="mt-1 flex flex-col gap-1.5">
                {profile.hospitals.map((h) => (
                  <li
                    key={h.id}
                    className="flex items-center gap-2 text-sm"
                  >
                    <span
                      className={`h-2 w-2 rounded-full ${
                        h.status === "active"
                          ? "bg-[var(--status-accepted)]"
                          : "bg-[var(--status-cancelled)]"
                      }`}
                    />
                    <span className="text-ink">{h.name}</span>
                    <span className="text-xs text-faint">
                      ({h.status === "active" ? "ativo" : "inativo"})
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </Card>

          {/* Indisponibilidades */}
          <Card className="p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
              Indisponibilidades
            </h2>

            {/* Formulário */}
            <div className="mt-3 rounded-[var(--radius-sm)] border border-dashed border-rule p-3">
              <p className="mb-2 text-xs font-medium text-muted">
                Marcar indisponível
              </p>
              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <Input
                    label="Início"
                    type="datetime-local"
                    value={unavailStart}
                    onChange={(e) => setUnavailStart(e.target.value)}
                  />
                  <Input
                    label="Fim"
                    type="datetime-local"
                    value={unavailEnd}
                    onChange={(e) => setUnavailEnd(e.target.value)}
                  />
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <Input
                    label="Motivo (opcional)"
                    value={unavailReason}
                    onChange={(e) => setUnavailReason(e.target.value)}
                  />
                  <div>
                    <label className="text-xs font-medium text-faint">
                      Repetir semanalmente
                    </label>
                    <div className="relative mt-1">
                      <select
                        value={repeatWeeks}
                        onChange={(e) => setRepeatWeeks(Number(e.target.value))}
                        className="w-full h-9 appearance-none rounded-[var(--radius-sm)] border border-rule bg-[var(--color-surface)] px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-focus)]"
                      >
                        <option value={0}>Não repetir</option>
                        <option value={1}>Por 1 semana adicional</option>
                        <option value={2}>Por 2 semanas adicionais</option>
                        <option value={3}>Por 3 semanas adicionais</option>
                        <option value={4}>Por 4 semanas adicionais</option>
                        <option value={12}>Por 12 semanas (3 meses)</option>
                      </select>
                      <span
                        aria-hidden
                        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted"
                      >
                        ▾
                      </span>
                    </div>
                  </div>
                </div>
              </div>
              <Button
                className="mt-3"
                onClick={() => createUnavailMut.mutate()}
                disabled={
                  !unavailStart || !unavailEnd || createUnavailMut.isPending
                }
              >
                {createUnavailMut.isPending ? "Salvando…" : "Adicionar"}
              </Button>
            </div>

            {/* Lista */}
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
      )}
    </div>
  );
}
