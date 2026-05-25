"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import type { Role } from "@/lib/types";

// Guard client-side: sem sessão → /login; persona errada → home da persona certa.
export function useRequireRole(role: Role) {
  const { account, ready } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!ready) return;
    if (!account) {
      router.replace("/login");
      return;
    }
    if (account.role !== role) {
      router.replace(account.role === "coordenador" ? "/plantoes" : "/ofertas");
    }
  }, [account, ready, role, router]);

  return { account, ready, ok: ready && !!account && account.role === role };
}
