// Traduz os eventos do audit log (GET /shifts/:id/audit) para uma timeline
// legível: "Lote 1 enviado para Dr. A, Dr. B · Dr. A recusou · expirou · …".
import { formatDateTime } from "@/lib/format";

export interface AuditEvent {
  id: number;
  event_type: string;
  actor_type: string | null;
  actor_id: string | null;
  payload: Record<string, unknown> | null;
  created_at: string | null;
}

export interface TimelineItem {
  id: number;
  text: string;
  color: string;
  time: string;
}

type DoctorNameFn = (id: string) => string;

const ACCENT = "var(--color-accent)";
const SUCCESS = "var(--status-accepted)";
const DANGER = "var(--status-needs-attention)";
const MUTED = "var(--color-muted)";

export function describeEvent(
  e: AuditEvent,
  doctorName: DoctorNameFn,
): TimelineItem {
  const p = e.payload ?? {};
  let text = e.event_type;
  let color = MUTED;

  switch (e.event_type) {
    case "shift.offering_started":
      color = ACCENT;
      text = `Pipeline de ofertas iniciado${
        p.batch_size ? ` — lotes de ${p.batch_size}` : ""
      }`;
      break;
    case "offer.batch_sent": {
      const ids = Array.isArray(p.doctor_ids) ? (p.doctor_ids as string[]) : [];
      const names = ids.map(doctorName).join(", ");
      color = ACCENT;
      text = `Lote ${p.batch ?? "?"} enviado para ${ids.length} médico(s)${
        names ? `: ${names}` : ""
      }`;
      break;
    }
    case "shift.batch_advanced":
      text = `Avançou para o lote ${p.batch ?? "?"}`;
      break;
    case "offer.expired":
      text =
        p.on === "accept_attempt"
          ? "Oferta expirada detectada no aceite"
          : `Oferta do lote ${p.batch ?? "?"} expirou`;
      break;
    case "shift.escalated":
      color = DANGER;
      text = "Escalado para a coordenadora — sem médico elegível ou janela curta";
      break;
    case "shift.accepted":
      color = SUCCESS;
      text = `${e.actor_id ? doctorName(e.actor_id) : "Médico"} aceitou o plantão`;
      break;
    case "offer.declined":
      text = `${e.actor_id ? doctorName(e.actor_id) : "Médico"} recusou`;
      break;
  }

  return {
    id: e.id,
    text,
    color,
    time: e.created_at ? formatDateTime(e.created_at) : "",
  };
}
