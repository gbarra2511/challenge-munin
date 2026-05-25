"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useLogout } from "@/lib/useLogout";
import { useRequireRole } from "@/lib/useRequireRole";

const TABS = [
  { href: "/ofertas", label: "Ofertas", glyph: "●" },
  { href: "/agenda", label: "Agenda", glyph: "▦" },
  { href: "/historico", label: "Histórico", glyph: "↻" },
];

export default function MedicoLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { ok, ready } = useRequireRole("medico");
  const { account } = useAuth();
  const doLogout = useLogout();
  const pathname = usePathname();

  if (!ready || !ok) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-sm text-muted">
        Carregando…
      </div>
    );
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col">
      {/* Top bar fina */}
      <header className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-rule bg-[var(--color-paper)]/90 px-4 py-3 backdrop-blur">
        <div className="flex min-w-0 items-baseline gap-2">
          <span className="font-display text-lg font-extrabold tracking-[-0.02em]">
            Munin
          </span>
          {account?.email && (
            <span className="hidden truncate text-xs text-muted sm:inline">
              {account.email}
            </span>
          )}
        </div>
        <button
          onClick={doLogout}
          className="h-9 shrink-0 rounded-[var(--radius-sm)] px-2.5 text-sm font-medium text-muted hover:bg-[var(--color-surface-2)] hover:text-ink"
        >
          Sair
        </button>
      </header>

      {/* Conteúdo (padding extra embaixo p/ não cobrir com a tab bar) */}
      <main className="flex-1 px-4 pb-28 pt-5">{children}</main>

      {/* Tab bar inferior — alvos ≥44px */}
      <nav className="fixed inset-x-0 bottom-0 z-10 mx-auto max-w-2xl border-t border-rule bg-[var(--color-surface)]">
        <ul className="grid grid-cols-3">
          {TABS.map((t) => {
            const active = pathname === t.href;
            return (
              <li key={t.href}>
                <Link
                  href={t.href}
                  aria-current={active ? "page" : undefined}
                  className={`flex h-16 flex-col items-center justify-center gap-1 text-xs font-medium transition-colors ${
                    active ? "text-accent" : "text-muted hover:text-ink"
                  }`}
                >
                  <span aria-hidden className="text-base leading-none">
                    {t.glyph}
                  </span>
                  {t.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
