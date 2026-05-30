"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import type { NotificationFeed } from "@/lib/types";

// Sininho de notificações in-app. Polla /me/notifications (20s), mostra contagem
// não-lida e um dropdown; clicar marca como lida e navega pro deep link.
// `align`: "end" abre o painel pra esquerda (botões no canto direito, ex. top bar);
// "start" abre pra direita (botão na borda esquerda, ex. sidebar da coordenação).
export function NotificationBell({ align = "end" }: { align?: "start" | "end" }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const qc = useQueryClient();

  const { data } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<NotificationFeed>("/me/notifications"),
    refetchInterval: 20_000,
  });

  const markRead = useMutation({
    mutationFn: (id?: string) =>
      api<void>(id ? `/me/notifications/${id}/read` : "/me/notifications/read", {
        method: "POST",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  const unread = data?.unread ?? 0;
  const items = data?.notifications ?? [];

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={`Notificações${unread ? ` (${unread} não lidas)` : ""}`}
        aria-expanded={open}
        className="relative flex h-9 w-9 items-center justify-center rounded-[var(--radius-sm)] border border-rule text-muted transition-colors hover:bg-[var(--color-surface-2)] hover:text-ink"
      >
        <span aria-hidden className="text-base leading-none">
          ◔
        </span>
        {unread > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--color-accent)] px-1 text-[10px] font-bold leading-none text-[var(--color-accent-ink)]">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className={`fixed top-14 z-50 w-80 max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] shadow-lg md:absolute md:top-11 ${
            align === "start" ? "left-3 md:left-0" : "right-3 md:right-0"
          }`}
        >
          <div className="flex items-center justify-between border-b border-rule px-4 py-2.5">
            <span className="text-sm font-semibold text-ink">Notificações</span>
            {unread > 0 && (
              <button
                onClick={() => markRead.mutate(undefined)}
                className="text-xs font-medium text-accent hover:underline"
              >
                Marcar todas
              </button>
            )}
          </div>
          <ul className="max-h-[60vh] divide-y divide-[var(--color-rule)] overflow-y-auto">
            {items.length === 0 ? (
              <li className="px-4 py-6 text-center text-sm text-muted">
                Nada por aqui ainda.
              </li>
            ) : (
              items.map((n) => (
                <li key={n.id}>
                  <button
                    onClick={() => {
                      if (!n.read) markRead.mutate(n.id);
                      setOpen(false);
                      if (n.path) router.push(n.path);
                    }}
                    className={`flex w-full flex-col gap-0.5 px-4 py-3 text-left transition-colors hover:bg-[var(--color-surface-2)] ${
                      n.read ? "" : "bg-[var(--color-accent-soft)]/40"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      {!n.read && (
                        <span
                          aria-hidden
                          className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-accent)]"
                        />
                      )}
                      <span className="text-sm font-semibold text-ink">{n.title}</span>
                    </div>
                    {n.body && <span className="text-xs text-muted">{n.body}</span>}
                    {n.created_at && (
                      <span className="text-[11px] text-faint">
                        {formatRelative(n.created_at)}
                      </span>
                    )}
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
