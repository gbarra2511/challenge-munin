"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const schema = z.object({
  email: z.string().min(3, "Informe seu e-mail"),
  password: z.string().min(1, "Informe sua senha"),
});
type Values = z.infer<typeof schema>;

export default function LoginPage() {
  const { account, ready, login } = useAuth();
  const router = useRouter();

  const home = (role: string) =>
    role === "coordenador" ? "/plantoes" : "/ofertas";

  // Já logado → vai direto pra home da persona.
  useEffect(() => {
    if (ready && account) router.replace(home(account.role));
  }, [ready, account, router]);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  const onSubmit = async (v: Values) => {
    try {
      const acc = await login(v.email, v.password);
      router.replace(home(acc.role));
    } catch (e) {
      // Backend é anti-enumeração: mesma resposta p/ e-mail e senha.
      const msg =
        e instanceof ApiError && e.status === 401
          ? "E-mail ou senha incorretos."
          : e instanceof ApiError
            ? e.message
            : "Não foi possível entrar.";
      toast.error(msg);
    }
  };

  return (
    <main className="flex min-h-dvh items-center justify-center px-5 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8">
          <span className="font-display text-2xl font-extrabold tracking-[-0.02em]">
            Munin
          </span>
          <h1 className="mt-4 font-display text-xl font-bold text-ink">
            Entrar
          </h1>
          <p className="mt-1 text-sm text-muted">
            Coordenação de plantões hospitalares.
          </p>
        </div>

        <form
          onSubmit={handleSubmit(onSubmit)}
          noValidate
          className="flex flex-col gap-4 rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] p-6 shadow-[var(--shadow-sm)]"
        >
          <Input
            label="E-mail"
            type="email"
            autoComplete="email"
            autoFocus
            placeholder="voce@hospital.br"
            error={errors.email?.message}
            {...register("email")}
          />
          <Input
            label="Senha"
            type="password"
            autoComplete="current-password"
            placeholder="••••••••"
            error={errors.password?.message}
            {...register("password")}
          />
          <Button type="submit" fullWidth loading={isSubmitting} className="mt-1">
            {isSubmitting ? "Entrando…" : "Entrar"}
          </Button>
        </form>
      </div>
    </main>
  );
}
