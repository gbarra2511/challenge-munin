import { Button } from "./Button";

// Erro legível + ação de retry. Mostra a mensagem do backend quando há uma.
export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[var(--radius-md)] border border-[var(--color-rule)] bg-[var(--color-surface)] px-6 py-12 text-center">
      <span aria-hidden className="text-2xl" style={{ color: "var(--color-danger)" }}>
        ▲
      </span>
      <p className="mt-2 font-medium text-ink">Algo deu errado</p>
      <p className="mt-1 max-w-sm text-pretty text-sm text-muted">{message}</p>
      {onRetry && (
        <Button variant="secondary" className="mt-4" onClick={onRetry}>
          Tentar de novo
        </Button>
      )}
    </div>
  );
}
