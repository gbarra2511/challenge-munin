# Mini-WFM — Sistema de design

> Gerado via `/hallmark` (Dia 4). **Sistema travado**: toda tela do frontend
> defere a este arquivo e a `tokens.css`. Não improvisar cor/fonte/espaço fora
> dos tokens. Genre: **modern-minimal** · Tema: **custom** · Eixos: **light /
> geometric-sans / cool**.

`/* Hallmark · pre-emit critique: P5 H5 E5 S5 R4 V5 */`

---

## 1. A ideia central

Ferramenta de **operações hospitalares sob stress**. Dois usuários, um sistema:

- **Coordenadora** — desktop, vê muita coisa de uma vez, decide rápido.
  Densidade > respiro. Linear/Cron: tabelas limpas, hierarquia por peso e cor,
  não por caixas.
- **Médico** — celular, no corredor entre plantões. Cards grandes, alvo de
  toque ≥44px, uma decisão por vez (aceitar/recusar) com **countdown ao vivo**.

**Sacada do domínio:** o status `offering` — o plantão vivo, com a janela
correndo, que pede ação — É a cor de marca (índigo elétrico `#040DC1`). A cor que
mais chama atenção marca exatamente o estado que mais precisa de atenção. O resto
da interface é quase monocromático azul; o índigo é cirúrgico (≤5% da viewport).

**Base fria, um acento quente:** o canvas é azul-claro (`#DDEAFF`), os cards são
near-white e saltam dele, e tudo é frio (índigo + ciano) — exceto **uma única**
cor quente em todo o sistema: o vermelho-alarme do `needs_attention`. Interface
clínica e calma, com um único ponto laranja que diz "aja agora" (complementar do
índigo). Essa tensão é o "inovador".

Tom: **confiável, calmo, denso, não-genérico.** Nada de gradiente roxo-ciano,
nada de card 3-features, nada de hero gigante. É um app, não uma landing.

---

## 2. Cor

Paleta completa em `tokens.css`. Regras de uso:

- **OKLCH only**, sempre por token (`var(--color-accent)`), nunca inline.
- **Accent primário.** Índigo elétrico `#040DC1` = `oklch(37.4% 0.249 265)`.
  Reservado para: CTA primário, item de nav ativo, link, anel de foco, status
  `offering`. Já é escuro o bastante pra texto branco por cima. Cirúrgico — se
  sentir vontade de usar mais, é slop.
- **Accent secundário** (escolha da casa): violeta elétrico `#7B2FF7` =
  `oklch(54% 0.266 292)`, *análogo* ao índigo (faz "match" com os azuis). Usado no
  status `confirmed` + realces de dados/gráfico. Harmoniza, nunca compete.
- **Neons de status são SINAIS, não texto.** `accepted` `#48FF00` (lime, L87) e
  `needs_attention` `#FF4800` (laranja, L66) são claros demais p/ texto miúdo.
  Aparecem só como **ponto/ícone/borda/número grande**. As pills usam o modelo
  Linear: fundo soft + texto `--color-ink` + ponto neon. Para texto de feedback
  (toasts, validação) há `--color-success`/`--color-danger`, versões legíveis.
- **Paper = canvas azul-claro** `#DDEAFF` = `oklch(93.4% 0.032 260)`. Cards são
  `--color-surface` near-white e **saltam** do canvas (mais claros, menos croma).
- **Ink = azul-preto** `oklch(20% 0.03 265)` (o "tom de preto" pedido — nunca
  `#000`). Greys tintados **cool** (hue ~260) pra casar com o azul.

### Sistema de status (o token mais importante do app)

| Status | Token fg | Pill bg | Forma/ícone (nunca só cor) |
|---|---|---|---|
| `open` | `--status-open` (slate-azul) | `--status-open-soft` | ○ contorno |
| `offering` | `--status-offering` (índigo accent) | `--status-offering-soft` | ● + ⏳ countdown, **ponto pulsa** |
| `accepted` | `--status-accepted` (lime neon #48FF00) | `--status-accepted-soft` | ✓ |
| `confirmed` | `--status-confirmed` (violeta #7B2FF7, accent-2) | `--status-confirmed-soft` | ✓✓ |
| `needs_attention` | `--status-needs-attention` (laranja neon #FF4800) | `--status-needs-attention-soft` | ▲ alerta |
| `cancelled` | `--status-cancelled` (cinza azulado) | `--status-cancelled-soft` | ⊘ + texto riscado |

Frio na maior parte (índigo `offering` · violeta `confirmed` · slate `open`),
com dois neons de alta energia: lime `accepted` e laranja `needs_attention` (o
único quente, complementar do índigo — salta como alarme). Cor é sempre **ponto/
ícone**, nunca texto sozinho (legibilidade + daltonismo). Contraste AA em todos.

---

## 3. Tipografia

Regra **2+1**: display + corpo + um outlier de dados.

- **Display** — `Cabinet Grotesk` (Fontshare), 700/800. Títulos de página,
  wordmark, números de KPI. Tracking `-0.02em`. Caráter editorial que diferencia
  do corpo neutro.
- **Corpo/UI** — `Geist` (Google), 400/500. Toda prosa, labels, tabelas, botões.
  Excelente em tamanho pequeno e denso.
- **Dados** — `JetBrains Mono`, com `font-variant-numeric: tabular-nums`.
  **Obrigatório** em: countdown, valores R$, horários, IDs. Números que mudam ou
  se alinham em coluna vão de mono tabular — nunca "pulam".

Escala 1.25 (terça maior), corpo 16px, display `clamp(...)` ≤ 3.81rem (é app, não
poster). Medida de prosa 65ch. Pontuação tipográfica de verdade (— … " ").

**Carregamento (no scaffold):** Geist via pacote `geist` (next/font, zero-CLS),
JetBrains Mono via `next/font/google`, Cabinet Grotesk via `<link>` Fontshare no
root layout com `font-display: swap`.

---

## 4. Espaço, raios, elevação

- **Espaçamento 4pt** (`--space-*`). Densidade da coordenadora usa `sm`/`md`;
  respiro do médico usa `lg`/`xl`.
- **Raios**: inputs 6px, cards 10px, modais 14px, pills 999px.
- **Elevação por sombra tênue** (`--shadow-*`), não por borda grossa. Cards =
  `--color-surface` + `--shadow-sm` + borda `--color-rule`. Popover/modal =
  `--shadow-lg`. Nada de glassmorphism.

---

## 5. Movimento (modern-minimal: cortar antes de adicionar)

- Anima só `transform`/`opacity`. Easings nomeados (`--ease-out` etc.), nunca o
  `ease` do browser, nunca bounce/overshoot em estado de UI.
- **Reveals na entrada: OFF.** A página chega composta.
- As três únicas animações que ganham seu lugar:
  1. **Pulse do ponto `offering`** — `opacity` 1→0.4→1, 2s, `--ease-in-out`.
     Diz "vivo" sem distrair.
  2. **Hover/active de botões e cards** — translateY 1px + sombra, `--dur-fast`.
  3. **Countdown** — texto mono atualizando 1×/s (não é animação CSS).
- `prefers-reduced-motion`: durações → 0, pulse vira ponto estático.
- **Foco nunca anima** — `:focus-visible` com anel `--color-focus` aparece
  instantâneo, ≥3:1.

---

## 6. Layout das telas (estrutura, não decoração)

### Shell
- **Coordenadora (desktop):** sidebar fixa `--app-sidebar` (248px) com nav +
  wordmark; conteúdo `max-width: --app-maxw`, padding `--space-xl`.
- **Médico (mobile-first):** sem sidebar; top bar fina + conteúdo full-width;
  nav inferior (tab bar) com alvos ≥44px.

### Coordenadora
- **/dashboard** — 4 KPI cards (Abertos · Em oferta · Preenchidos · Em risco),
  número em Cabinet Grotesk grande + label pequeno. Abaixo, tabela "Em risco"
  (needs_attention ou <12h sem aceite), ordenada por urgência.
- **/calendario** — grade semanal densa (Cron-like), slots coloridos por status,
  filtro por especialidade. Hairlines, não caixas pesadas.
- **/plantoes/:id** — coluna principal = **timeline do audit log** ("Batch 1
  enviado p/ Dr. A, B, C às 14:32 · Dr. A recusou 14:33 · expirou · Batch 2…");
  lateral = lista de ofertas com status; ações (cancelar, ampliar pool).
- **/plantoes/novo** — form React Hook Form + Zod, campos agrupados, inline
  validation, datas tz-aware.

### Médico
- **/ofertas** — cards grandes empilhados. Cada um: especialidade · hospital ·
  horário · **R$ em mono** · **countdown ⏳ ao vivo** (recalcula contra
  `expires_at` ISO, sem pedir nada ao server) · botões Aceitar/Recusar grandes.
- **/plantoes** — calendário pessoal dos aceitos.
- **/historico** — tabela paginada.

---

## 7. Estados não-negociáveis (todas as telas)

- **Loading = skeleton** com a forma do conteúdo. Nunca spinner gigante centrado.
- **Empty state com CTA** e voz humana: *"Nenhuma oferta agora. Quando surgir,
  você vê aqui — pode fechar o app."* (escola Notion).
- **Error state** legível + ação de retry. Erros de API mostram a mensagem do
  backend (`{error:{code,message}}`).
- **Toast (sonner)** após ação:
  - sucesso: silencioso/discreto (aceite vira card "Confirmado").
  - **409** → *"Esse plantão acabou de ser preenchido."* (calmo, não-culpa).
  - **410** → *"Essa oferta expirou."*
- **Tempo real sem WebSocket:** React Query `refetchInterval: 15s` nas listas
  críticas (ofertas pendentes, dashboard de risco); countdown local por
  `setInterval`.

---

## 8. Responsivo (piso duro)

- Verificado a **360 / 375 / 414 / 768px**. Sem scroll horizontal.
- Alvo de toque ≥44px no fluxo do médico. Texto-clicável nunca quebra em 2 linhas.
- Grids com imagem usam `minmax(0, 1fr)`. `overflow-x: clip` no root.
- Sidebar da coordenadora colapsa para drawer/tab abaixo de 768px.

## 9. Acessibilidade (piso duro)

- Contraste **AA** (4.5:1 corpo, 3:1 large/UI) — paleta já calibrada.
- `:focus-visible` visível em tudo. Labels em todos os campos. Navegação por
  teclado em modais (trap + Esc). Status nunca comunicado só por cor.

---

## 10. Stack & componentes

- **Next.js 16** (App Router, TS) · **Tailwind 4** (tokens via `@theme inline`
  lendo `tokens.css`) · **shadcn/ui** (Radix, acessível) re-skinado com os tokens.
- **TanStack Query** (server state + refetch) · **React Hook Form + Zod** (forms)
  · **sonner** (toasts).
- shadcn entra como base, mas **re-tematizado** com estes tokens — nada de roxo
  default, nada de raio/sombra padrão do shadcn. O sistema manda.

---

## Exports

Tokens canônicos em `tokens.css` (`:root` + `[data-theme="dark"]`). Mapear para o
`@theme inline` do Tailwind 4 no scaffold (próximo passo do Dia 4).
