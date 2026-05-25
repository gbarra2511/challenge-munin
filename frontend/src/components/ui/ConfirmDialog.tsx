"use client";
import { useCallback, useEffect, useRef } from "react";
import { Button } from "./Button";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  confirmVariant?: "primary" | "danger";
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirmar",
  confirmVariant = "primary",
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape" && !loading) onCancel();
    },
    [onCancel, loading],
  );

  useEffect(() => {
    if (open) {
      document.addEventListener("keydown", handleKeyDown);
      cancelRef.current?.focus();
      return () => document.removeEventListener("keydown", handleKeyDown);
    }
  }, [open, handleKeyDown]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-[2px]"
      onClick={(e) => {
        if (e.target === e.currentTarget && !loading) onCancel();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
      aria-describedby="confirm-desc"
    >
      <div className="mx-4 w-full max-w-sm rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] p-6 shadow-lg">
        <h2
          id="confirm-title"
          className="font-display text-lg font-bold text-ink"
        >
          {title}
        </h2>
        <p id="confirm-desc" className="mt-2 text-sm text-muted">
          {description}
        </p>
        <div className="mt-5 flex justify-end gap-3">
          <Button
            ref={cancelRef}
            variant="secondary"
            onClick={onCancel}
            disabled={loading}
          >
            Voltar
          </Button>
          <Button
            variant={confirmVariant}
            onClick={onConfirm}
            loading={loading}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
