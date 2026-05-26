"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { OfferCard } from "@/components/OfferCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { Moon } from "@/components/ui/Icon";
import { ErrorState } from "@/components/ui/ErrorState";
import { Select } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError, api } from "@/lib/api";
import type { AcceptResult, Offer } from "@/lib/types";

export default function OfertasPage() {
  const qc = useQueryClient();
  const [hospitalFilter, setHospitalFilter] = useState("all");

  // Lista crítica: refetch a cada 15s (design.md §7 — tempo real sem WebSocket).
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["offers", "pending"],
    queryFn: () => api<{ offers: Offer[] }>("/me/offers?status=pending"),
    refetchInterval: 15_000,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["offers"] });
    qc.invalidateQueries({ queryKey: ["assignments"] });
  };

  const hospitals = useMemo(() => {
    const set = new Map<string, string>();
    for (const o of data?.offers ?? []) {
      if (o.shift.hospital_name) {
        set.set(o.shift.hospital_id ?? "", o.shift.hospital_name);
      }
    }
    return Array.from(set.entries());
  }, [data]);

  const filtered = useMemo(() => {
    const all = data?.offers ?? [];
    if (hospitalFilter === "all") return all;
    return all.filter((o) => (o.shift.hospital_id ?? "") === hospitalFilter);
  }, [data, hospitalFilter]);

  const acceptMut = useMutation({
    mutationFn: (offerId: string) =>
      api<AcceptResult>(`/offers/${offerId}/accept`, { method: "POST" }),
    onSuccess: () => {
      toast.success("Confirmado. O plantão é seu.");
      invalidate();
    },
    onError: (e: unknown) => {
      // Mensagens calmas, sem culpa (design.md §7).
      if (e instanceof ApiError && e.status === 409)
        toast("Esse plantão acabou de ser preenchido.");
      else if (e instanceof ApiError && e.status === 410)
        toast("Essa oferta expirou.");
      else
        toast.error(
          e instanceof ApiError ? e.message : "Não foi possível aceitar.",
        );
      invalidate();
    },
  });

  const declineMut = useMutation({
    mutationFn: (offerId: string) =>
      api(`/offers/${offerId}/decline`, { method: "POST" }),
    onSuccess: () => {
      toast("Oferta recusada.");
      invalidate();
    },
    onError: (e: unknown) => {
      toast.error(
        e instanceof ApiError ? e.message : "Não foi possível recusar.",
      );
      invalidate();
    },
  });

  return (
    <div>
      <header className="mb-5">
        <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
          Ofertas
        </h1>
        <p className="mt-0.5 text-sm text-muted">
          Plantões abertos para você agora. Decida antes da janela fechar.
        </p>
      </header>

      {isLoading && (
        <div className="flex flex-col gap-4">
          {[0, 1].map((i) => (
            <div
              key={i}
              className="rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] p-5"
            >
              <Skeleton className="h-6 w-40" />
              <Skeleton className="mt-3 h-4 w-24" />
              <Skeleton className="mt-4 h-10 w-full" />
              <Skeleton className="mt-4 h-11 w-full" />
            </div>
          ))}
        </div>
      )}

      {isError && (
        <ErrorState
          message={
            error instanceof ApiError
              ? error.message
              : "Não foi possível carregar suas ofertas."
          }
          onRetry={() => refetch()}
        />
      )}

      {data && filtered.length === 0 && (
        <EmptyState
          glyph={<Moon className="h-8 w-8" />}
          title={
            hospitalFilter !== "all"
              ? "Nenhuma oferta nesse hospital"
              : "Nenhuma oferta agora"
          }
          description="Quando surgir um plantão para você, aparece aqui — pode fechar o app, a gente avisa na próxima janela."
        />
      )}

      {data && filtered.length > 0 && (
        <>
          {hospitals.length > 1 && (
            <div className="mb-4 max-w-[16rem]">
              <Select
                label=""
                aria-label="Filtrar por hospital"
                value={hospitalFilter}
                onChange={(e) => setHospitalFilter(e.target.value)}
                className="h-9 py-0"
              >
                <option value="all">Todos os hospitais</option>
                {hospitals.map(([hid, name]) => (
                  <option key={hid} value={hid}>
                    {name}
                  </option>
                ))}
              </Select>
            </div>
          )}

          <div className="flex flex-col gap-4">
            {filtered.map((offer) => (
              <OfferCard
                key={offer.id}
                offer={offer}
                accepting={
                  acceptMut.isPending && acceptMut.variables === offer.id
                }
                declining={
                  declineMut.isPending && declineMut.variables === offer.id
                }
                onAccept={() => acceptMut.mutate(offer.id)}
                onDecline={() => declineMut.mutate(offer.id)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
