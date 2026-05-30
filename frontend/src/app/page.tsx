import Link from "next/link";

const STATUSES = [
  { token: "open", label: "aberto", glyph: "○" },
  { token: "offering", label: "em oferta", glyph: "●" },
  { token: "accepted", label: "preenchido", glyph: "✓" },
  { token: "confirmed", label: "confirmado", glyph: "✓✓" },
  { token: "needs-attention", label: "em risco", glyph: "▲" },
  { token: "cancelled", label: "cancelado", glyph: "⊘" },
] as const;

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-16 sm:py-24">
      <p className="text-sm font-medium uppercase tracking-[0.06em] text-muted">
        Munin WFM
      </p>
      <h1
        className="mt-3 font-display font-extrabold leading-[1.08] tracking-[-0.02em]"
        style={{ fontSize: "var(--text-display)" }}
      >
        Plantões preenchidos
        <br />
        sem ninguém no telefone.
      </h1>
      <p className="mt-4 max-w-[60ch] text-ink-2">
        Coordene ofertas em lote, deixe o pipeline rodar, e veja o aceite acontecer
        em tempo real. Um único toque para o médico; visão completa para a
        coordenadora.
      </p>

      {/* Sistema de status — prova de que os tokens chegaram ao Tailwind */}
      <div className="mt-8 flex flex-wrap gap-2">
        {STATUSES.map((s) => (
          <span
            key={s.token}
            className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm font-medium text-ink"
            style={{ background: `var(--status-${s.token}-soft)` }}
          >
            <span style={{ color: `var(--status-${s.token})` }}>{s.glyph}</span>
            {s.label}
          </span>
        ))}
      </div>

      {/* Duas portas de entrada */}
      <div className="mt-12 grid gap-4 sm:grid-cols-2">
        <Link
          href="/login"
          className="rounded-[var(--radius-md)] border border-rule bg-surface p-6 shadow-[var(--shadow-sm)] transition-transform duration-150 hover:-translate-y-0.5"
        >
          <h2 className="font-display text-xl font-bold">Coordenadora</h2>
          <p className="mt-1 text-sm text-muted">
            Dashboard, calendário, criar plantões e acompanhar ofertas.
          </p>
          <span className="mt-4 inline-block text-sm font-medium text-accent">
            Entrar →
          </span>
        </Link>

        <Link
          href="/login"
          className="rounded-[var(--radius-md)] border border-rule bg-surface p-6 shadow-[var(--shadow-sm)] transition-transform duration-150 hover:-translate-y-0.5"
        >
          <h2 className="font-display text-xl font-bold">Médico</h2>
          <p className="mt-1 text-sm text-muted">
            Suas ofertas com countdown ao vivo, aceitos e histórico.
          </p>
          <span className="mt-4 inline-block text-sm font-medium text-accent">
            Ver ofertas →
          </span>
        </Link>
      </div>
    </main>
  );
}
