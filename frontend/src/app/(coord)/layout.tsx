"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { NotificationBell } from "@/components/NotificationBell";
import { useAuth } from "@/lib/auth";
import { useLogout } from "@/lib/useLogout";
import { useRequireRole } from "@/lib/useRequireRole";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: "◧" },
  { href: "/calendario", label: "Calendário", icon: "▦" },
  { href: "/plantoes", label: "Plantões", icon: "≣" },
  { href: "/trocas", label: "Trocas", icon: "⇄" },
  { href: "/medicos", label: "Médicos", icon: "⊕" },
];

export default function CoordLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { ok, ready } = useRequireRole("coordenador");
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

  const isActive = (href: string) =>
    pathname === href || pathname.startsWith(href + "/");

  const navItems = (orientation: "col" | "row") =>
    NAV.map((n) => {
      const active = isActive(n.href);
      return (
        <Link
          key={n.href}
          href={n.href}
          aria-current={active ? "page" : undefined}
          className={`flex items-center gap-2.5 rounded-[var(--radius-sm)] px-3 py-2.5 text-sm font-medium transition-colors ${
            orientation === "row" ? "whitespace-nowrap" : ""
          } ${
            active
              ? "bg-[var(--color-accent-soft)] text-accent"
              : "text-ink-2 hover:bg-[var(--color-surface-2)] hover:text-ink"
          }`}
        >
          <span aria-hidden className="text-base leading-none">
            {n.icon}
          </span>
          {n.label}
        </Link>
      );
    });

  return (
    <div className="min-h-dvh md:pl-[var(--app-sidebar)]">
      {/* Sidebar fixa (md+) */}
      <aside className="fixed inset-y-0 left-0 z-10 hidden w-[var(--app-sidebar)] flex-col border-r border-rule bg-[var(--color-surface)] px-3 py-5 md:flex">
        <div className="flex items-start justify-between gap-2 px-3">
          <div>
            <span className="font-display text-xl font-extrabold tracking-[-0.02em]">
              Munin
            </span>
            <p className="mt-0.5 text-xs text-faint">Coordenação</p>
          </div>
          <NotificationBell align="start" />
        </div>

        <Link
          href="/plantoes/novo"
          className="mt-6 flex h-10 items-center justify-center gap-2 rounded-[var(--radius-sm)] bg-[var(--color-accent)] px-3 text-sm font-medium text-[var(--color-accent-ink)] shadow-[var(--shadow-sm)] transition-colors hover:bg-[var(--color-accent-hover)]"
        >
          <span aria-hidden>＋</span> Novo plantão
        </Link>

        <nav className="mt-5 flex flex-col gap-1">{navItems("col")}</nav>

        {/* Rodapé: usuário + sair */}
        <div className="mt-auto flex flex-col gap-3 border-t border-rule px-1 pt-4">
          <div className="flex items-center gap-2.5 px-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent-soft)] text-xs font-bold text-accent">
              {account?.email?.charAt(0).toUpperCase() ?? "U"}
            </div>
            <p
              className="min-w-0 truncate text-xs text-muted"
              title={account?.email}
            >
              {account?.email}
            </p>
          </div>
          <button
            id="btn-logout"
            onClick={doLogout}
            className="flex h-9 w-full items-center justify-center gap-2 rounded-[var(--radius-sm)] border border-rule text-sm font-medium text-muted transition-colors hover:bg-[var(--color-surface-2)] hover:text-ink"
          >
            Sair
          </button>
        </div>
      </aside>

      {/* Top bar (mobile < md) */}
      <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-rule bg-[var(--color-paper)]/90 px-4 py-3 backdrop-blur md:hidden">
        <div className="flex min-w-0 items-baseline gap-2">
          <span className="font-display text-lg font-extrabold tracking-[-0.02em]">
            Munin
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <NotificationBell />
          <button
            onClick={doLogout}
            className="h-9 rounded-[var(--radius-sm)] border border-rule px-3 text-sm font-medium text-muted hover:bg-[var(--color-surface-2)] hover:text-ink"
          >
            Sair
          </button>
          <Link
            href="/plantoes/novo"
            className="flex h-9 items-center gap-1.5 rounded-[var(--radius-sm)] bg-[var(--color-accent)] px-3 text-sm font-medium text-[var(--color-accent-ink)]"
          >
            <span aria-hidden>＋</span> Novo
          </Link>
        </div>
      </header>
      <nav className="sticky top-[57px] z-20 flex gap-1 overflow-x-auto border-b border-rule bg-[var(--color-surface)] px-2 py-2 md:hidden">
        {navItems("row")}
      </nav>

      <main
        id="main-content"
        className="mx-auto w-full max-w-[var(--app-maxw)] px-5 py-6 md:px-8 md:py-8"
      >
        {children}
      </main>
    </div>
  );
}
