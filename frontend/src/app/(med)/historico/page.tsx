import { EmptyState } from "@/components/ui/EmptyState";

export default function HistoricoPage() {
  return (
    <div>
      <header className="mb-5">
        <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
          Histórico
        </h1>
        <p className="mt-0.5 text-sm text-muted">
          Seus plantões passados.
        </p>
      </header>
      <EmptyState
        glyph="↻"
        title="Em construção"
        description="A lista paginada do seu histórico chega no próximo passo. Seus plantões aceitos já aparecem na Agenda."
      />
    </div>
  );
}
