"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Toaster } from "sonner";
import { AuthProvider } from "@/lib/auth";

export function Providers({ children }: { children: React.ReactNode }) {
  const [qc] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
            staleTime: 5_000,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={qc}>
      <AuthProvider>
        {children}
        <Toaster
          position="top-center"
          gap={8}
          toastOptions={{
            style: {
              background: "var(--color-surface)",
              color: "var(--color-ink)",
              border: "1px solid var(--color-rule)",
              borderRadius: "var(--radius-md)",
              boxShadow: "var(--shadow-md)",
              fontFamily: "var(--font-body)",
            },
          }}
        />
      </AuthProvider>
    </QueryClientProvider>
  );
}
