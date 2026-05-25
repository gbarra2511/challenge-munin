"use client";
import { Button } from "@/components/ui/Button";
import { StatusPill } from "@/components/ui/StatusPill";
import {
  formatBRL,
  formatCountdown,
  formatShiftWindow,
} from "@/lib/format";
import { specialtyName } from "@/lib/specialties";
import type { Offer } from "@/lib/types";
import { useCountdown } from "@/lib/useCountdown";

const FIVE_MIN = 5 * 60 * 1000;

export function OfferCard({
  offer,
  onAccept,
  onDecline,
  accepting,
  declining,
}: {
  offer: Offer;
  onAccept: () => void;
  onDecline: () => void;
  accepting: boolean;
  declining: boolean;
}) {
  const ms = useCountdown(offer.expires_at);
  const expired = ms <= 0;
  const urgent = !expired && ms < FIVE_MIN;
  const busy = accepting || declining;

  // Countdown muda de cor pela urgência: accent → laranja (<5min) → expirado.
  const countdownColor = expired
    ? "var(--color-faint)"
    : urgent
      ? "var(--status-needs-attention)"
      : "var(--color-accent)";

  return (
    <article className="rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] p-5 shadow-[var(--shadow-sm)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-xl font-bold tracking-[-0.01em] text-ink">
            {specialtyName(offer.shift.specialty_id)}
          </h2>
          <p className="font-data mt-0.5 text-xs text-faint">
            Plantão #{offer.shift.id.slice(0, 8)} · lote {offer.batch_number}
          </p>
        </div>
        <StatusPill status="offering" />
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
        <div>
          <dt className="text-xs text-muted">Horário</dt>
          <dd className="font-data mt-0.5 text-sm text-ink">
            {formatShiftWindow(offer.shift.starts_at, offer.shift.ends_at)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Valor</dt>
          <dd className="font-data mt-0.5 text-sm font-medium text-ink">
            {formatBRL(offer.shift.rate_cents)}
          </dd>
        </div>
      </dl>

      {/* Countdown ao vivo — o sinal de urgência */}
      <div className="mt-4 flex items-center gap-2 rounded-[var(--radius-sm)] bg-[var(--color-surface-sunk)] px-3 py-2">
        <span aria-hidden className="text-sm">
          ⏳
        </span>
        <span className="text-xs text-muted">
          {expired ? "Janela encerrada" : "Expira em"}
        </span>
        <span
          className="font-data ml-auto text-lg font-medium tabular-nums"
          style={{ color: countdownColor }}
          aria-live="off"
        >
          {formatCountdown(ms)}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-[1fr_auto] gap-2">
        <Button
          variant="primary"
          onClick={onAccept}
          loading={accepting}
          disabled={expired || busy}
        >
          {expired ? "Expirado" : "Aceitar"}
        </Button>
        <Button
          variant="secondary"
          onClick={onDecline}
          loading={declining}
          disabled={expired || busy}
        >
          Recusar
        </Button>
      </div>
    </article>
  );
}
