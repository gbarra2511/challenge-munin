"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { Select } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError, api } from "@/lib/api";
import { specialtyName, SPECIALTIES } from "@/lib/specialties";
import { statusColor, statusLabel, statusSoft } from "@/lib/status";
import type { Shift } from "@/lib/types";
import { addDays, sameDay, startOfWeek, weekDays } from "@/lib/week";

const timeFmt = new Intl.DateTimeFormat("pt-BR", {
  hour: "2-digit",
  minute: "2-digit",
});

function ShiftChip({ shift }: { shift: Shift }) {
  return (
    <Link
      href={`/plantoes/${shift.id}`}
      title={`${specialtyName(shift.specialty_id)} · ${statusLabel(shift.status)}`}
      className="flex items-center gap-1.5 rounded-[var(--radius-sm)] px-2 py-1.5 text-left transition-colors hover:brightness-95"
      style={{ background: statusSoft(shift.status) }}
    >
      <span
        aria-hidden
        className="shrink-0 text-[0.6rem] leading-none"
        style={{ color: statusColor(shift.status) }}
      >
        ●
      </span>
      <span className="font-data shrink-0 text-xs tabular-nums text-ink">
        {timeFmt.format(new Date(shift.starts_at))}
      </span>
      <span className="min-w-0 flex-1 truncate text-xs text-ink-2">
        {specialtyName(shift.specialty_id)}
      </span>
    </Link>
  );
}

export default function CalendarioPage() {
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [specialty, setSpecialty] = useState<number | "all">("all");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["shifts"],
    queryFn: () => api<{ shifts: Shift[] }>("/shifts"),
    refetchInterval: 15_000,
  });

  const days = useMemo(() => {
    const all = data?.shifts ?? [];
    const filtered =
      specialty === "all"
        ? all
        : all.filter((s) => s.specialty_id === specialty);
    return weekDays(weekStart).map((day) => ({
      day,
      shifts: filtered
        .filter((s) => sameDay(new Date(s.starts_at), day))
        .sort((a, b) => +new Date(a.starts_at) - +new Date(b.starts_at)),
    }));
  }, [data, weekStart, specialty]);

  const rangeLabel = `${weekStart.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
  })} – ${addDays(weekStart, 6).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
  })}`;

  return (
    <div>
      <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
            Calendário
          </h1>
          <p className="mt-0.5 text-sm text-muted">
            Semana de <span className="font-data">{rangeLabel}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select
            label=""
            aria-label="Filtrar por especialidade"
            value={specialty}
            onChange={(e) =>
              setSpecialty(
                e.target.value === "all" ? "all" : Number(e.target.value),
              )
            }
            className="h-9 py-0"
          >
            <option value="all">Todas as especialidades</option>
            {SPECIALTIES.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </div>
      </header>

      <div className="mb-4 flex items-center gap-2">
        <Button
          variant="secondary"
          className="h-9 px-3"
          onClick={() => setWeekStart((w) => addDays(w, -7))}
        >
          ← Anterior
        </Button>
        <Button
          variant="ghost"
          className="h-9 px-3"
          onClick={() => setWeekStart(startOfWeek(new Date()))}
        >
          Hoje
        </Button>
        <Button
          variant="secondary"
          className="h-9 px-3"
          onClick={() => setWeekStart((w) => addDays(w, 7))}
        >
          Próxima →
        </Button>
      </div>

      {isError && (
        <ErrorState
          message={
            error instanceof ApiError
              ? error.message
              : "Não foi possível carregar o calendário."
          }
          onRetry={() => refetch()}
        />
      )}

      {isLoading && (
        <div className="grid grid-cols-1 gap-2 md:grid-cols-7">
          {Array.from({ length: 7 }).map((_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      )}

      {data && (
        // Empilha no mobile, vira 7 colunas no desktop — sem scroll horizontal.
        <div className="grid grid-cols-1 gap-2 md:grid-cols-7">
          {days.map(({ day, shifts }) => {
            const today = sameDay(day, new Date());
            return (
              <div
                key={day.toISOString()}
                className={`flex flex-col rounded-[var(--radius-sm)] border bg-[var(--color-surface)] md:min-h-44 ${
                  today
                    ? "border-[var(--color-accent)]"
                    : "border-[var(--color-rule)]"
                }`}
              >
                <div
                  className={`flex items-baseline gap-1.5 border-b border-rule px-2.5 py-2 ${
                    today ? "text-accent" : "text-ink-2"
                  }`}
                >
                  <span className="text-xs font-medium capitalize">
                    {day.toLocaleDateString("pt-BR", { weekday: "short" })}
                  </span>
                  <span className="font-data text-sm tabular-nums">
                    {day.getDate()}
                  </span>
                </div>
                <div className="flex flex-col gap-1.5 p-1.5">
                  {shifts.length === 0 ? (
                    <span className="px-1 py-2 text-xs text-faint">—</span>
                  ) : (
                    shifts.map((s) => <ShiftChip key={s.id} shift={s} />)
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
