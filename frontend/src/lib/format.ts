// Formatadores pt-BR. Dinheiro e datas passam sempre por aqui, nunca inline.

export function formatBRL(cents: number): string {
  return (cents / 100).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

const dateTimeFmt = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

const timeFmt = new Intl.DateTimeFormat("pt-BR", {
  hour: "2-digit",
  minute: "2-digit",
});

export function formatDateTime(iso: string): string {
  return dateTimeFmt.format(new Date(iso));
}

// "24 mai, 19:00 – 07:00" (mesmo dia mostra só a hora no fim)
export function formatShiftWindow(startIso: string, endIso: string): string {
  const start = new Date(startIso);
  const end = new Date(endIso);
  const sameDay = start.toDateString() === end.toDateString();
  return sameDay
    ? `${dateTimeFmt.format(start)} – ${timeFmt.format(end)}`
    : `${dateTimeFmt.format(start)} – ${dateTimeFmt.format(end)}`;
}

// ms restantes até o ISO. Negativo = já expirou.
export function msUntil(iso: string): number {
  return new Date(iso).getTime() - Date.now();
}

// "12:34" (mm:ss) ou "1h 04m" quando passa de uma hora. "Expirado" se <= 0.
export function formatCountdown(ms: number): string {
  if (ms <= 0) return "Expirado";
  const totalSec = Math.floor(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
