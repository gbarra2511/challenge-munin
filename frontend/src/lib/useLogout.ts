"use client";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

// Logout robusto: limpa token + sessão, ZERA o cache do React Query (senão
// dados da conta anterior vazam ao trocar de conta) e volta pro login.
export function useLogout() {
  const { logout } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  return () => {
    logout();
    qc.clear();
    router.replace("/login");
  };
}
