"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { NotificationBell } from "@/components/NotificationBell";
import { useAuth } from "@/lib/auth";
import { useLogout } from "@/lib/useLogout";
import { useRequireRole } from "@/lib/useRequireRole";

const TABS = [
  { href: "/ofertas", label: "Ofertas", icon: "●" },
  { href: "/agenda", label: "Agenda", icon: "▦" },
  { href: "/minhas-trocas", label: "Trocas", icon: "⇄" },
  { href: "/historico", label: "Histórico", icon: "↻" },
  { href: "/perfil", label: "Perfil", icon: "◎" },
];

// Largura da coluna de conteúdo — header, main e abas compartilham para alinhar.
const CONTAINER = "mx-auto w-full max-w-3xl";

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
    <div className="flex min-h-dvh flex-col">
      {/* Top bar full-width; conteúdo interno centrado na coluna. */}
      <header className="sticky top-0 z-20 border-b border-rule bg-[var(--color-paper)]/90 backdrop-blur">
        <div className={`${CONTAINER} flex items-center justify-between gap-3 px-4 py-3`}>
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="font-display text-lg font-extrabold tracking-[-0.02em]">
              Munin
            </span>
            {account?.email && (
              <span className="hidden truncate text-xs text-muted sm:inline">
                {account.email}
              </span>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <NotificationBell />
            <button
              id="btn-logout"
              onClick={doLogout}
              className="h-9 rounded-[var(--radius-sm)] border border-rule px-3 text-sm font-medium text-muted transition-colors hover:bg-[var(--color-surface-2)] hover:text-ink"
            >
              Sair
            </button>
          </div>
        </div>
      </header>

      {/* Conteúdo centrado; padding inferior p/ não ficar sob a tab bar. */}
      <main id="main-content" className={`${CONTAINER} flex-1 px-4 pb-28 pt-5`}>
        {children}
      </main>

      {/* Tab bar inferior full-width (dock ancorada na borda); abas centradas na
          coluna. Funciona igual no mobile e no desktop. Alvos ≥44px. */}
      <nav className="fixed inset-x-0 bottom-0 z-20 border-t border-rule bg-[var(--color-surface)]">
        <ul className={`${CONTAINER} grid grid-cols-5`}>
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
                  <span aria-hidden className="text-lg leading-none">
                    {t.icon}
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
