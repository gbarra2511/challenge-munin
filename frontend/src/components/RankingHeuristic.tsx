// Explica a heurística do ranking — o README pede "explique a heurística"
// (bônus Tier 1), então ela precisa ser VISÍVEL no produto, não só no código.
// Os pesos espelham services/ranking.py (aceite 40 / recência 25 / carga 20 /
// resposta 15).
const FACTORS = [
  {
    w: "40%",
    name: "Taxa de aceite",
    desc: "histórico de ofertas aceitas vs. recusadas/expiradas",
  },
  {
    w: "25%",
    name: "Recência",
    desc: "há quanto tempo não pega plantão (distribui melhor a escala)",
  },
  {
    w: "20%",
    name: "Carga na semana",
    desc: "menos plantões na semana do turno = maior prioridade",
  },
  {
    w: "15%",
    name: "Tempo de resposta",
    desc: "quem costuma responder mais rápido às ofertas",
  },
];

export function RankingHeuristic() {
  return (
    <details className="mt-2 rounded-[var(--radius-sm)] border border-rule bg-[var(--color-surface-sunk)] px-3 py-2">
      <summary className="cursor-pointer text-sm font-medium text-ink-2">
        Como o ranking funciona?
      </summary>
      <p className="mt-2 text-xs text-muted">
        <span className="text-ink-2">Especialistas primeiro.</span> Médicos de
        outra especialidade entram como <em>fallback</em> (marcados “fora da
        especialidade”), só pra não deixar buraco quando faltam especialistas.
        Dentro de cada grupo, o score combina:
      </p>
      <ul className="mt-2 flex flex-col gap-1.5">
        {FACTORS.map((f) => (
          <li key={f.name} className="flex gap-2 text-xs text-muted">
            <span className="font-data w-9 shrink-0 font-semibold text-ink">
              {f.w}
            </span>
            <span>
              <span className="text-ink-2">{f.name}</span> — {f.desc}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-faint">
        Score 0–100; sem histórico vale 50 (neutro). Só entram médicos da
        especialidade, com vínculo ativo ao hospital e livres na janela do
        plantão.
      </p>
    </details>
  );
}
