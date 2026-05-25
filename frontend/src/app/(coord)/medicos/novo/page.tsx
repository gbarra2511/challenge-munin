"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { ApiError, api } from "@/lib/api";
import { SPECIALTIES } from "@/lib/specialties";

export default function NovoMedicoPage() {
  const router = useRouter();
  const qc = useQueryClient();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  
  // No Munin, usamos hospitais fixos por enquanto ou o hospital logado?
  // Pelo requirements do desafio "Um hospital só basta", vou amarrar ao hospital padrão.
  // Vou deixar a seleção de especialidade.
  const [specialtyId, setSpecialtyId] = useState<number>(SPECIALTIES[0].id);

  const createMut = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api("/doctors", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      toast.success("Médico cadastrado com sucesso.");
      qc.invalidateQueries({ queryKey: ["doctors"] });
      router.push("/medicos");
    },
    onError: (e: unknown) =>
      toast.error(
        e instanceof ApiError ? e.message : "Erro ao cadastrar médico.",
      ),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email || !password) {
      toast.error("Preencha os campos obrigatórios (nome, email, senha).");
      return;
    }
    
    // O backend requer specialty_ids e hospital_ids
    // Para simplificar no challenge, vamos buscar o hospital_id do account logado.
    // Como a API espera hospital_ids, precisamos passar. 
    // Na verdade, a API precisa do hospital logado, mas o payload aceita hospital_ids.
    // Vou checar como o user model está. 
    // O account do coordenador tem um hospital_id. 
    const accountStr = localStorage.getItem("munin_account");
    let hId = "";
    if (accountStr) {
      const acc = JSON.parse(accountStr);
      hId = acc.hospital_id;
    }

    createMut.mutate({
      name,
      email,
      password,
      phone: phone || null,
      specialty_ids: [specialtyId],
      hospital_ids: hId ? [hId] : [], // Passando o hospital do coordenador logado
    });
  };

  return (
    <div>
      <header className="mb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.back()}
            className="text-sm text-muted hover:text-ink transition-colors"
          >
            ← Voltar
          </button>
        </div>
        <div className="mt-3">
          <h1 className="font-display text-2xl font-extrabold tracking-[-0.02em]">
            Cadastrar Médico
          </h1>
          <p className="mt-0.5 text-sm text-muted">
            Crie uma nova conta para um médico atuar no seu hospital.
          </p>
        </div>
      </header>

      <form
        onSubmit={handleSubmit}
        className="max-w-md rounded-[var(--radius-md)] border border-rule bg-[var(--color-surface)] p-5 shadow-[var(--shadow-sm)] flex flex-col gap-4"
      >
        <Input
          label="Nome completo"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <Input
          label="E-mail"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input
          label="Senha provisória"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <Input
          label="Telefone (opcional)"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />

        <Select
          label="Especialidade principal"
          value={String(specialtyId)}
          onChange={(e) => setSpecialtyId(parseInt(e.target.value))}
        >
          {SPECIALTIES.map((s) => (
            <option key={s.id} value={String(s.id)}>
              {s.name}
            </option>
          ))}
        </Select>

        <Button
          type="submit"
          className="mt-2"
          disabled={createMut.isPending}
        >
          {createMut.isPending ? "Cadastrando…" : "Cadastrar médico"}
        </Button>
      </form>
    </div>
  );
}
