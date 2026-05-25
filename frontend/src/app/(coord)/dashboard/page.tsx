import { ButtonLink } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";

export default function DashboardPage() {
  return (
    <div>
      <header className="mb-5">
        <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
          Dashboard
        </h1>
        <p className="mt-0.5 text-sm text-muted">
          Visão geral do hospital — KPIs e plantões em risco.
        </p>
      </header>
      <EmptyState
        glyph="◧"
        title="Em construção"
        description="Os KPIs (abertos · em oferta · preenchidos · em risco) e a tabela de plantões em risco chegam no próximo passo. Enquanto isso, comece por aqui:"
        action={<ButtonLink href="/plantoes/novo">Criar plantão</ButtonLink>}
      />
    </div>
  );
}
