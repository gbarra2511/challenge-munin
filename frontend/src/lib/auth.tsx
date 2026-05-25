"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { api, clearToken, getToken, setToken } from "@/lib/api";
import type { Account, LoginResponse } from "@/lib/types";

interface AuthState {
  account: Account | null;
  ready: boolean; // hidratou do localStorage e validou (ou descartou) o token
  login: (email: string, password: string) => Promise<Account>;
  logout: () => void;
}

const AuthCtx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [account, setAccount] = useState<Account | null>(null);
  const [ready, setReady] = useState(false);

  // Ao montar: se há token guardado, valida contra /auth/me.
  useEffect(() => {
    if (!getToken()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setReady(true);
      return;
    }
    api<{ account: Account }>("/auth/me")
      .then((r) => setAccount(r.account))
      .catch(() => {
        clearToken();
        setAccount(null);
      })
      .finally(() => setReady(true));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const r = await api<LoginResponse>("/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    });
    setToken(r.token);
    setAccount(r.account);
    return r.account;
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setAccount(null);
  }, []);

  return (
    <AuthCtx.Provider value={{ account, ready, login, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth precisa estar dentro de <AuthProvider>");
  return ctx;
}
