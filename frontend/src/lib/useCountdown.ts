"use client";
import { useEffect, useState } from "react";
import { msUntil } from "@/lib/format";

// Relógio local: ms restantes até `expiresAt`, atualizando 1×/s.
// Não pede nada ao servidor — recalcula contra a string ISO (design.md §7).
export function useCountdown(expiresAt: string): number {
  const [ms, setMs] = useState(() => msUntil(expiresAt));
  useEffect(() => {
    setMs(msUntil(expiresAt));
    const id = setInterval(() => setMs(msUntil(expiresAt)), 1000);
    return () => clearInterval(id);
  }, [expiresAt]);
  return ms;
}
