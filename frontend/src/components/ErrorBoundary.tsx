"use client";
import { Component, type ReactNode } from "react";
import { Button } from "@/components/ui/Button";

interface Props {
  children: ReactNode;
}
interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-dvh items-center justify-center p-8">
          <div className="mx-auto max-w-md text-center">
            <p className="text-4xl" aria-hidden>
              ⚠️
            </p>
            <h1 className="mt-4 font-display text-xl font-bold text-ink">
              Algo deu errado
            </h1>
            <p className="mt-2 text-sm text-muted">
              Ocorreu um erro inesperado. Tente recarregar a página.
            </p>
            <Button
              className="mt-6"
              onClick={() => {
                this.setState({ hasError: false, error: undefined });
                window.location.reload();
              }}
            >
              Recarregar
            </Button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
