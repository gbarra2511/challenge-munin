import { ButtonLink } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";

export default function CalendarioPage() {
  return (
    <div>
      <header className="mb-5">
        <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
          Calendário
        </h1>
        <p className="mt-0.5 text-sm text-muted">
          Grade semanal com os plantões coloridos por status.
        </p>
      </header>
      <EmptyState
        glyph="▦"
        title="Em construção"
        description="A grade semanal densa, com filtro por especialidade, chega no próximo passo. Por ora, a lista de plantões dá a visão completa."
        action={<ButtonLink href="/plantoes" variant="secondary">Ver plantões</ButtonLink>}
      />
    </div>
  );
}
