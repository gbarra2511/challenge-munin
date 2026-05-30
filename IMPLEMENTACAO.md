# IMPLEMENTACAO.md — Tracking

> Estado atual da implementação do Mini-WFM e próximos passos.
> **Atualizar após cada feature grande. Revisar no início de cada sessão.**

Última atualização: 2026-05-30 (**Todo o obrigatório concluído** — deploy público no ar (Fly+Supabase+Vercel), WhatsApp real + inline-dispatch, correções mobile, e **README de submissão**. Só restam bônus opcionais: check-in/geo, OpenAPI, Mini-Luis/copiloto LLM.)

---

## Como rodar e acessar (local)

**Subir tudo (do repo root):**
1. `colima start && docker compose up -d` — Postgres `munin-postgres` na :5432.
2. Backend: `cd backend` → `cp .env.example .env` (preenche o que quiser; a config
   é **auto-carregada do `.env`** via pydantic-settings — sem `export`) →
   `uv run alembic upgrade head` →
   `FLASK_APP="app:create_app" uv run flask run --port 5000 --host 127.0.0.1`
3. Seed: `curl -X POST http://127.0.0.1:5000/admin/seed -H "Authorization: Bearer dev-only-change-me-admin"`
4. Frontend: `cd frontend && npm install && npm run dev` → http://localhost:3000
   (API via `NEXT_PUBLIC_API_URL`, default `http://127.0.0.1:5000` — ver `.env.example`).

**WhatsApp real (Twilio sandbox):** preencher `TWILIO_ACCOUNT_SID/AUTH_TOKEN/WHATSAPP_FROM`
+ `MUNIN_DEMO_PHONE` no `backend/.env` (gitignored). Sem isso → `NullNotifier` (não envia).
Disparar entrega: ação que notifica (oferta/troca) → `curl -X POST .../jobs/tick`. ⚠️ **Celular BR
sem o nono dígito** no `MUNIN_DEMO_PHONE` (com o 9 extra → erro Twilio 63015). Verificar com
`RUN_TWILIO_LIVE=1 uv run pytest tests/test_whatsapp.py -k live`.

**Acesso mobile (iPhone no mesmo Wi-Fi):** porta **5001** pro backend (a 5000 é do AirPlay
Receiver no macOS, `*:5000` → 403); subir front/back em `0.0.0.0`, apontar `NEXT_PUBLIC_API_URL`
e `CORS_ORIGINS` pro IP da LAN (`ipconfig getifaddr en0`).

**Credenciais de demo (seed, senha `123456`):**
- Coordenadora: `coordenadora@hospital.com`
- Médico (demo, com 2 ofertas + 1 aceito): `medico@hospital.com`
- Outros médicos: `medico1@hospital.com` … `medico29@hospital.com`

**Gotcha macOS:** use `127.0.0.1` (não `localhost`) pra API — a porta 5000 em
IPv6/`::1` é do AirPlay Receiver. O frontend já aponta pra `127.0.0.1` via `.env.local`.

---

## Status global

| Bloco | Status |
|---|---|
| Esqueleto do projeto | ✅ feito |
| Schema do banco + state machines | ✅ feito |
| Auth + CRUD básicos | ✅ feito |
| Pipeline de ofertas + tick | ✅ feito (tick corrigido: não auto-oferta OPEN) |
| Accept atômico (race condition) | ✅ feito |
| Endpoints faltantes (cancel, expand, offers) | ✅ feito |
| Frontend (Hallmark + telas) | ✅ feito (Dias 4–6: auth + todas as telas + ações completas) |
| Qualidade de código + robustez | ✅ feito (CORS, N+1, error boundary, JSON.parse) |
| Deploy público + seed | ✅ feito (Fly + Supabase + Vercel; cron do tick ativo; smoke test OK) |
| Testes obrigatórios (5) | ✅ feito (5/5 + extras — **160/160**, 1 skip opt-in) |
| README final | ✅ feito (submissão; enunciado → CHALLENGE.md; prints + Mermaid) |
| Bônus: swap (backend atômico) | ✅ feito (transferência A→B + concorrência, 28 testes) |
| Bônus: notificação outbox + WhatsApp (backend) | ✅ feito + **entrega real verificada** (`delivered` no sandbox; 17 testes: 7 outbox + 10 adapter) |
| Bônus: telas de swap + sininho de notificação | ✅ feito (agenda, /trocas med+coord, NotificationBell) |
| Bônus | ⏳ depois do obrigatório |

---

## Feito

### Inline-dispatch de notificação + correções de responsividade mobile (2026-05-30)

Dois ajustes pós-deploy, ambos **verificados em prod** (headless 390px + Twilio).

- **WhatsApp instantâneo (inline-dispatch).** Notificação de swap/oferta só
  chegava no próximo `/jobs/tick` (cron 5min, que ainda atrasa no GitHub
  Actions). `flush_notifications` (novo `app/api/notify.py`) drena o outbox logo
  após request/approve/reject de swap e abrir/ampliar ofertas, via
  `dispatch_pending_safe` (best-effort — erro não quebra a request; cron segue
  como fallback durável; `SKIP LOCKED` evita envio duplo). Não toca em
  accept/decline (não notificam + caminho crítico de concorrência). Verificado em
  prod: oferta → notificação `sent`/`attempts=1` **sem** tick.
- **Mobile (auditado a 390px em todas as telas via Playwright).** Detalhe do
  plantão e de médico **cortavam os cards**: grid só com `md:grid-cols-[1fr_Npx]`
  virava coluna `auto` (max-content) no mobile → `grid-cols-1` resolve (desktop
  intacto). `min-w-0` nos nomes truncados (RankingCard + lista de ofertas). Sino:
  dropdown `z-50` preso no header `z-10` ficava **atrás da barra de abas** (nav
  irmã z-10, posterior no DOM) → header `z-30` / nav `z-20`; e o painel
  `absolute right-0` **vazava pela esquerda** no mobile → `fixed` à direita da
  viewport (md+ volta a ancorar no sino). Telas do médico: 0 overflow.

### Deploy público — Fly (backend) + Supabase (DB) + Vercel (frontend) (2026-05-30)

Fecha o maior gap obrigatório. Stack pública no ar, cron do tick ativo, smoke
test ponta-a-ponta verde.

- **Backend → Fly.io** — `https://munin-backend.fly.dev`. `Dockerfile` (uv +
  gunicorn `app:create_app`), `.dockerignore`, `fly.toml` com `release_command`
  rodando `alembic upgrade head`. 1 máquina `shared-cpu-1x`/256MB, scale-to-zero
  (~US$2/mês). Pra hibernar: `fly scale count 0 -a munin-backend`; pra zerar:
  `fly apps destroy munin-backend`.
- **DB → Supabase** (Postgres 17, `sa-east-1`): conexão via **Session pooler**
  (porta 5432, IPv4 — a direta é só IPv6 no free; a transaction pool/6543
  quebraria prepared statements do psycopg3). `DATABASE_URL` com scheme
  `postgresql+psycopg://` e senha URL-encoded. Secrets via `fly secrets`.
- **Frontend → Vercel** — `https://challenge-munin-ai.vercel.app`. Import do
  GitHub, **root `frontend/`**, `NEXT_PUBLIC_API_URL` → Fly. Auto-deploy a cada push.
- **🐛 Pego no 1º deploy:** `migrations/env.py` passava a `DATABASE_URL` pelo
  `ConfigParser` do alembic (`set_main_option`), que interpola `%` — a senha
  URL-encoded (`%40` = `@`) quebrava com "invalid interpolation syntax".
  Corrigido criando o engine **direto** da env var (fallback pro `alembic.ini`).
- **Cron do tick reativado** (`tick.yml` `*/5`): secrets `API_URL`/`TICK_SECRET`
  no GitHub. Avança pipeline + drena outbox, e mantém Fly+Supabase acordados
  (mata o pause de 7 dias do Supabase free).
- **Smoke test:** `/health` 200, seed (1 coord + 30 médicos + 10 plantões),
  login coord/médico, `/me/offers`, `/jobs/tick` (200 c/ auth · 401 sem), CORS
  (allow no Vercel · bloqueia outros), front Vercel 200.
- **WhatsApp real LIGADO em prod** (2026-05-30): `TWILIO_*`+`MUNIN_DEMO_PHONE`
  setados via `fly secrets` (importados do `.env` com `python-dotenv`, sem expor
  valores); re-seed aponta coord+médico-demo pro celular real; **`delivered`
  verificado no Twilio (3 ofertas)**. ⚠️ Sandbox expira em **72h** → re-`join`
  antes da avaliação (senão volta a falhar com 63015 mesmo com número correto).
- **Próximo:** README final (passo 7) — agora o único gap obrigatório.

### WhatsApp real entregue + testes do adapter + `.env` auto-carregado (2026-05-26)

Fecha o bônus de notificação **com entrega real verificada** (antes só rodava via
NullNotifier). **160 testes (150 → +10)**, ruff limpo.

- **Entrega real confirmada** no sandbox do Twilio, ponta-a-ponta pelo fluxo do app:
  `seed`/`request_swap` → `jobs/tick` → `dispatch_pending` → Twilio. 3× `offer.created`
  (→ médico-demo) e 1× `swap.requested` (→ coordenadora) chegaram com status **`delivered`**
  (confirmado via `messages(sid).fetch().status`, não só o SID que a Twilio devolve).
- **🐛 Pegadinha do nono dígito (BR):** o WhatsApp identifica celular brasileiro **sem** o 9
  extra. Enviar com ele (`+5532999872511`) → **erro 63015**; sem (`+553299872511`) → entrega.
  Documentado no `.env` e na seção "Como rodar".
- **`config.py`/`seed.py`:** `MUNIN_DEMO_PHONE` virou campo do `Settings` (`munin_demo_phone`),
  lido do `.env` — antes era `os.environ.get` direto, que o `.env` do pydantic não populava
  (exigia `export`). Agora o `.env` sozinho resolve.
- **`.env.example`** estendido (Twilio + `FRONTEND_URL` + `MUNIN_DEMO_PHONE`); `.env` real
  segue gitignored. Credenciais **nunca** commitadas (sinal de alerta da rubrica evitado).
- **Testes** `test_whatsapp.py` (10 unit, sem DB/rede): normalização do número (parametrizado),
  montagem da requisição com `twilio.rest.Client` **mockado**, seleção do adapter por credenciais
  (`get_notifier` → WhatsApp/Null), e PII fora do log. **+1 teste opt-in** (`RUN_TWILIO_LIVE=1`)
  que entrega de verdade e checa o status final — verde quando rodado.
- **Próximo:** os dois gaps obrigatórios — **deploy público** (passo 6) e **README final**
  (passo 7). É o que falta pra rubrica /35.

### Frontend do swap + sininho de notificação + e2e verificado (2026-05-26)

Fecha os dois bônus ponta a ponta. `next build` verde (17 rotas, TS limpo),
backend 150 testes, fluxo validado contra o stack real.

- **`/agenda`** (médico): botão "Pedir troca" nos plantões aceitos no futuro →
  `SwapRequestModal` (carrega candidatos ranqueados, escolhe colega, envia);
  badge "Troca pendente"; link "Minhas trocas".
- **`/minhas-trocas`** (médico): lista de pedidos com status, alvo e motivo da
  recusa; cancelar enquanto pendente. (Rota separada de `/trocas` porque route
  groups não criam segmento — colidiria com a da coord.)
- **`/trocas`** (coordenação): pendentes em grid; **aprovar/recusar com modal de
  motivo** (textarea); é o destino do deep link do WhatsApp.
- **`NotificationBell`** (med + coord): polla `/me/notifications` (20s), badge de
  não-lidas, dropdown com deep links, marcar lida(s). Nav: aba/link "Trocas".
- **Tipos/format**: `SwapRequest`/`SwapCandidate`/`NotificationItem` em
  `types.ts`; `formatRelative` em `format.ts`.
- **E2E verificado** (stack real + seed): médico pede troca → coord aprova →
  banco mostra A `swapped_out` + B `active` (1 ativa) + swap `approved`; tick
  drenou 12 notificações WhatsApp (NullNotifier, sem creds) → todas `sent`; feed
  do médico mostra "Troca aprovada".
- **WhatsApp real**: basta definir `TWILIO_ACCOUNT_SID/AUTH_TOKEN/WHATSAPP_FROM`
  + `MUNIN_DEMO_PHONE` (celular opt-in do sandbox) — sem isso, NullNotifier.

### Notificação real — outbox + dispatch no tick + adapter WhatsApp (Twilio) (2026-05-26)

Segundo pilar do bônus. **150 testes (143 → +7)**, ruff limpo. Oferta de plantão
e eventos de swap agora notificam por **in-app (feed) + WhatsApp**.

- **`app/services/notifications.py`** — outbox: `enqueue` idempotente
  (`ON CONFLICT (dedupe_key) DO NOTHING`), `notify_event`/`notify_doctor`/
  `notify_hospital_coords` (resolvem destinatário por conta), e `dispatch_pending`
  **claim-then-send**: trava+marca `sending` com `FOR UPDATE SKIP LOCKED` (dois
  ticks não pegam a mesma linha), commita pra soltar o lock, e SÓ ENTÃO chama o
  provedor (fora de qualquer lock de banco). At-least-once. `feed`/`mark_read`.
- **Canal `in_app` nasce `sent`** (lido direto pelo feed); `whatsapp` é entregue
  pelo dispatch. Telefone (PII) resolvido só no envio (coord → `accounts.phone`,
  médico → `doctors.phone`), nunca no audit/payload.
- **Adapter** `app/infra/notifier.py` (`Notifier`/`NullNotifier`/`get_notifier`)
  + `app/infra/whatsapp.py` (`WhatsAppNotifier`, Twilio, import preguiçoso). Sem
  credenciais → `NullNotifier` (dev/test não tocam a rede). Dep `twilio` add.
- **Wiring**: `offers._send_batch` (oferta→médico), `swaps.request_swap`
  (→coordenação), `approve_swap` (→A e B), `reject_swap` (→A com motivo).
- **Tick** (`/jobs/tick`) agora roda `run_tick` **e** `dispatch_pending` (reusa
  o cron; sem worker novo). Config: `FRONTEND_URL` (deep links) + `TWILIO_*`.
- **Seed**: `accounts.phone` da coordenadora + override `MUNIN_DEMO_PHONE` p/
  apontar coordenadora e médico-demo ao celular opt-in real do sandbox.
- **Testes** `test_notifications.py`: enqueue idempotente, feed+mark_read,
  dispatch via NullNotifier (sent/skipped/idempotente), in_app não-dispatchado,
  oferta enfileira notificação.
- **Próximo**: telas (Fase 1.5) — `/agenda` pedir troca, `/trocas` (médico+coord),
  sininho de notificação; reativar cron no deploy.

### Swap de plantão — backend atômico (handoff aprovado pela coordenação) (2026-05-26)

Primeiro pilar do bônus de troca + notificação real (plano em
`~/.claude/plans/goofy-moseying-pinwheel.md`). Médico A pede para passar um
plantão aceito a um colega elegível B; a coordenação aprova/recusa com motivo.
**143 testes (115 → +28)**, ruff limpo, concorrência 5× sem flaky.

- **Migração 0002** (aditiva): `accounts.phone`; `swap_requests` +
  `reason`/`decided_by`/`decided_at` + índice **parcial único**
  `uq_swap_pending_per_assignment` (no máx. 1 pendente por assignment); CHECK de
  `shift_assignments` estendido com `'swapped_out'`; nova tabela `notifications`
  (outbox — usada na Fase 2). `app/models.py` espelha tudo (+ classe `Notification`).
- **`app/domain/swap.py`** — state machine pura (pending → approved/rejected/
  cancelled), espelhando `domain/shift.py`.
- **`app/services/swaps.py`** — `approve_swap` espelha a disciplina do
  `accept_offer`: **shift travado `FOR UPDATE` como ponto único de
  serialização**, todas as invariantes re-checadas sob o lock, e transferência
  na ordem `UPDATE A→swapped_out` (Core, executa antes) **depois**
  `INSERT B active` — respeitando `one_active_assignment_per_shift`. Também:
  `request_swap`, `reject_swap`, `cancel_swap`, `swap_candidates`, listagens.
- **🐛 Pego pelos testes** — *stale identity-map*: o peek via `session.get`
  cacheava o swap como `pending`; o reload `FOR UPDATE` devolvia o objeto antigo
  e o perdedor da corrida não via `approved` → violava o índice. Corrigido
  peekando por **colunas** (não ORM), como o `accept_offer` faz.
- **Endpoints** `app/api/swaps.py` (médico: `POST /swaps`, `/swaps/:id/cancel`;
  coord: `GET /swaps`, `/swaps/:id/approve|reject`) + `/me/swaps` e
  `/me/assignments/:id/swap-candidates` no blueprint `me`. Schemas Pydantic.
- **Testes**: `test_domain_swap.py`, `test_swaps.py` (request/approve/reject/
  cancel + guards 404/409/422), `test_swap_concurrency.py` (2 threads aprovando
  → 1 ok / 1 409, A `swapped_out`, 1 ativa, shift `accepted`).
- **Próximo**: notificação outbox (Fase 2) + WhatsApp (Fase 3) + telas (Fase 1.5).

### Dashboard — gráfico de 7 dias redesenhado + "em risco" consistente (2026-05-26)

Iteração de UX no dashboard (só frontend). `tsc`/`eslint` limpos.

- **Gráfico "Próximos 7 dias" → colunas verticais empilhadas.** As barras
  horizontais não codificavam o total (toda linha enchia a largura → 1 plantão
  parecia 3; `maxTotal` era calculado e ignorado). Agora a **altura = carga do
  dia** relativa ao pico da semana, segmentos por status, total acima, "Hoje" em
  accent. (commit `02c35c7`)
- **`open` em azul-slate nítido.** O slate de "não ofertado" era apagado demais
  (chroma 0.04) e lia como placeholder — os abertos "sumiam" no gráfico. Subido
  pra `oklch(55% 0.11 256)` (+ dark); vale p/ gráfico, pills e calendário.
  (commit `83bef0e`)
- **"Em risco" consistente (KPI = lista = gráfico).** O KPI contava só
  `needs_attention` (0) enquanto a lista usava a regra ampla (`isAtRisk`:
  needs_attention OU aberto/em oferta a <12h) e mostrava 2. KPI passou a usar
  `view.risk` (bate com a lista e com "em risco de buraco" do README); gráfico
  ganhou marcador ▲ laranja (overlay, sem contagem dupla) + legenda. (commit
  `4e74962`)

### Tier de especialidade no ranking — fallback anti-buraco (2026-05-26)

Decisão de produto: especialidade deixou de ser **filtro duro** e virou **tier**.
Especialistas sempre primeiro (ranqueados pelos 4 fatores); não-especialistas
afiliados e disponíveis entram como **fallback** — só pra não deixar buraco —
caindo nos lotes seguintes / no ampliar pool. Backend: **115 testes** (+2), ruff
limpo.

- **`eligible_doctors(specialty_match: bool)`** — `True` (padrão) = só da
  especialidade; `False` = só de fora (EXISTS, não JOIN, p/ negar sem duplicar).
- **`ranked_doctors`** compõe os dois tiers e ordena por
  `(not is_specialist, -score, nome)` — tier vence o score (um generalista com
  score 68 fica abaixo de um especialista com 60). `RankedDoctor.is_specialist`.
- **`expand_pool`** passou a usar `ranked_doctors` (não `eligible_doctors`), pra
  o ampliar pool alcançar o fallback quando os especialistas se esgotam.
- **Frontend:** `is_specialist` no tipo; tag âmbar "fora da especialidade" no
  `RankingCard`; `RankingHeuristic` explica o tier. 2 testes novos (tier vence
  score; `specialty_match=False` traz só os de fora).
- **Caveat documentado:** no mundo real, cross-coverage deveria ser por flag de
  tipo de plantão (CTI/peds não são substituíveis). Fica como evolução.

### Preview do ranking na criação + heurística visível + status "Não ofertado" (2026-05-26)

Continuação do dia. Backend: **113 testes** (110 → +3), ruff limpo.

- **Ranking preview na criação (dry-run).** `POST /shifts/ranking-preview`
  (coord, escopado ao hospital) ranqueia elegíveis para `(especialidade,
  janela)` **sem criar plantão** — usa `ranked_doctors` com um `Shift`
  transiente (não persistido). `shift_actions.get_ranking_preview` +
  `_serialize_ranked` (extraído de `get_shift_ranking`). 3 testes: lista sem
  criar shift, valida janela (422), guard de papel (403).
- **Frontend** `/plantoes/novo`: `useWatch` em especialidade+janela dispara o
  preview ao vivo (card "Quem seria ofertado" + nº de elegíveis), antes de
  comprometer a criação.
- **Heurística visível (README bônus).** `components/RankingHeuristic.tsx` —
  `<details>` "Como o ranking funciona?" com os 4 fatores ponderados; aparece
  no preview e no detalhe do plantão.
- **`open` → "Não ofertado".** `STATUS_META.open` relabel + flag `outline`;
  `StatusPill` renderiza pill **tracejada sem preenchimento** (distinta do
  soft-fill dos estados ativos). KPI do dashboard idem.

### Audit UI/UX (hallmark + ui-ux-pro-max) + override do 1º lote (2026-05-26)

Revisão de frontend com a skill `ui-ux-pro-max` e `/hallmark` (projeto é
gerenciado por `frontend/design.md` — telas seguem o sistema). `tsc`/`eslint`/
`next build` limpos.

- **Override manual do 1º lote (preview + seleção).** O endpoint `/offer` já
  aceitava `doctor_ids`; o ranking deixou de ser só leitura. Em `/plantoes/:id`
  com status `open`, o `RankingCard` ganha checkboxes (pré-marca os
  `batch_size` melhores), divisores de **Lote 1/2/…** ligando ranking↔pipeline,
  e CTA "Disparar ofertas (N)" no rodapé. Seleção é derivada em render
  (`defaultSelection` via `useMemo` + override em estado), sem `useEffect`.
  `/plantoes/novo` ganha atalho "Escolher médicos do 1º lote" → detalhe.
- **Explicabilidade do score.** Tooltip no número mostra os 4 sub-scores
  ponderados (aceite 40% · recência 25% · carga 20% · resposta 15%). Barra
  tonal: índigo cheio só no líder (accent cirúrgico, design.md §2).
- **Correções de a11y do audit.** Emoji→SVG (`ui/Icon.tsx`: Moon/Hourglass no
  empty de ofertas e no countdown); número das barras do dashboard num chip
  near-white (contraste AA sobre neon); calendário usa glyph por status (não só
  cor); countdown com `aria-live="off"` (parava de tagarelar 1×/s).

### Cobertura de testes do código novo + bug de ranking (2026-05-25)

Revisão de alinhamento ao PLANO após os commits de WFM completo. O código
ficou aderente, mas as ~3200 linhas novas (ranking, gestão de médicos,
indisponibilidades, perfil) estavam **sem testes**. Fechado esse flanco com
**26 testes novos (83 → 109)**, ruff limpo.

- **`test_ranking.py`** (6): elegibilidade (specialty/hospital, exclusão por
  indisponibilidade sobreposta) + direção dos 4 fatores (aceite, carga,
  desempate determinístico por nome, breakdown explicável).
- **`test_unavailabilities.py`** (5): criação, **repetição semanal** gera N
  instâncias, validação de janela/passado, posse na exclusão.
- **`test_api_shift_actions.py`** (6): cancel (supersede + audit + escopo de
  hospital), expand-pool (novo batch excluindo já ofertados, exige
  needs_attention), listar ofertas, guard de papel.
- **`test_api_doctor_mgmt.py`** (6): PATCH, deactivate/activate (soft-delete
  via afiliação), stats, guard de papel.
- **`test_api_me_profile.py`** (4): perfil enriquecido, médico edita
  nome mas NÃO especialidades, CRUD de indisponibilidades próprias.

- **🐛 Bug real pego pelos testes**: `func.avg()` do Postgres devolve
  `Decimal`. No `ranking._score_response` isso causava `TypeError: Decimal *
  float` → **`ranked_doctors` (caminho default de oferta) crashava para
  qualquer médico com histórico de resposta**. O mesmo `Decimal` quebraria a
  serialização de `GET /doctors/:id/stats` (jsonify não serializa Decimal).
  Corrigido coagindo pra `float` na origem (`ranking._offer_stats_bulk` e
  `doctors.doctor_stats`), com testes de regressão nos dois caminhos.
- Limpezas: docstring de `offers.py` dizia "offer→shift" (a ordem real é
  shift→offer); `select` morto em `update_doctor`.

### Ranking explicável exposto na UI (Bônus Tier 1 completo) (2026-05-25)

Fecha o gap acima: o `breakdown` deixou de ser código morto e virou o bônus
Tier 1 de verdade (PLANO §13 — mostrar o *motivo* do ranking).

- **Backend** `GET /shifts/:id/ranking` (coord, escopado ao hospital):
  `shift_actions.get_shift_ranking` serializa os médicos elegíveis ordenados
  por score, com breakdown (aceite/recência/carga/resposta) e flag
  `already_offered`. +1 teste (110 total) cobrindo ordem, flag e serialização.
- **Frontend** `components/RankingCard.tsx` + card na tela de detalhe do
  plantão: posição, score (barra), nome, badge "já ofertado" e motivos em
  pt-BR ("aceita 80% das ofertas · 6d sem plantão · responde em ~4min").
  Aparece enquanto o plantão está open/offering/needs_attention; refetch 30s.
- Limpeza: import morto `DoctorStats` em `medicos/page.tsx`. ESLint limpo.

### Dia 6 — Endpoints faltantes + fixes + features frontend + qualidade (2026-05-25)

Fechamento das lacunas técnicas: todos os endpoints do PLANO §8 implementados,
bugs corrigidos, features novas no frontend, hardening de código. **83/83 testes
passando**, `npm run build` limpo.

**Backend — 3 endpoints novos + 5 fixes:**

- **`POST /shifts/:id/cancel`** (novo): lock pessimista no shift, supersede ofertas
  pendentes, cancela assignment ativa, transiciona para `cancelled`, grava audit.
  Adicionada transição `offering → cancelled` na state machine.
- **`POST /shifts/:id/expand-pool`** (novo): para shifts em `needs_attention` —
  busca novos médicos elegíveis excluindo já ofertados, envia novo batch,
  transiciona de volta para `offering`. Retorna `new_offers` no response.
- **`GET /shifts/:id/offers`** (novo): JOIN único `ShiftOffer + Doctor`,
  retorna lista agrupável por batch com nome do médico — alimenta a sidebar.
- **Fix `decline_offer`**: agora carrega o shift para incluir `hospital_id`
  no audit event (antes ficava `None`).
- **Fix tick auto-offering**: removido `ShiftStatus.OPEN` do filtro do tick.
  A coordenadora agora tem controle total sobre quando disparar ofertas
  (via `POST /shifts/:id/offer`). Teste `test_tick_is_idempotent` atualizado.
- **Fix N+1 em `GET /doctors`**: nova função `doctors_view_batch` carrega
  especialidades e afiliações em 2 queries bulk em vez de 2×N.
- **`hospital_name` em `/me/offers` e `/me/assignments`**: JOIN com `Hospital`
  para que o médico veja de qual hospital é cada oferta/plantão.
- **Filtros `from`/`to` em `GET /shifts`**: parâmetros de data opcionais.
- **CORS melhorado**: `Access-Control-Max-Age: 600` + handler explícito de
  `OPTIONS` via `before_request` (204 sem body).

Arquivos criados/modificados:
- `app/services/shift_actions.py` (novo — `cancel_shift`, `expand_pool`, `get_shift_offers`)
- `app/domain/shift.py` (transição `offering → cancelled`)
- `app/services/offers.py` (fix decline audit + tick não auto-oferta OPEN)
- `app/services/shifts.py` (filtros `from_date`/`to_date`)
- `app/services/doctors.py` (`doctors_view_batch`)
- `app/api/shifts.py` (3 endpoints novos + filtros de data)
- `app/api/me.py` (JOIN Hospital, `hospital_name`)
- `app/__init__.py` (CORS preflight + Max-Age)
- `tests/test_pipeline.py` (fix `test_tick_is_idempotent`)

**Frontend — 4 features + 5 melhorias:**

- **`ConfirmDialog.tsx`** (novo): modal reutilizável com overlay+blur, foco
  automático, Escape para fechar, variante `danger` para ações destrutivas.
- **Detalhe do plantão reescrito** (`plantoes/[id]/page.tsx`): layout 2 colunas
  (`md:grid-cols-[1fr_320px]`), sidebar de ofertas agrupadas por batch com
  dot colorido + nome do médico, botão "Cancelar plantão" (com ConfirmDialog
  danger), botão "Ampliar pool de médicos" para `needs_attention`.
- **Histórico do médico implementado** (`historico/page.tsx`): tabela no desktop,
  cards no mobile, filtro por status, mostra hospital_name.
- **`ErrorBoundary.tsx`** (novo): error boundary global com tela de reload.
- **`OfferCard.tsx`**: mostra `hospital_name`, `aria-live="polite"` no countdown.
- **`Field.tsx`**: chevron visual (▾) no Select (antes `appearance-none` sem indicador).
- **`layout.tsx`**: ErrorBoundary global + skip-to-content link (a11y).
- **`api.ts`**: `JSON.parse` em try/catch — resposta malformada gera `ApiError`.
- **`types.ts`**: `hospital_name` em `EmbeddedShift`, novos tipos `ShiftOfferDetail`
  e `ShiftOfferDoctor`.

### Frontend Dia 5 — dashboard + calendário + detalhe com timeline (2026-05-24)

As três telas da coordenadora, **todas derivadas de endpoints existentes**
(sem mexer no backend). `next build` verde, 11 rotas, TypeScript limpo.
3 commits (um por tela): `7c83b71`, `e2c3335`, `b97c3d5`.

- **/dashboard**: 4 KPIs (abertos · em oferta · preenchidos · em risco),
  barras dos próximos 7 dias empilhadas por status, e tabela "Plantões em
  risco" (`needs_attention` OU começa em <12h sem aceite, ordenada por
  urgência, linkando ao detalhe). Tudo de `GET /shifts` com refetch 15s.
- **/calendario**: grade semanal (segunda→domingo) com navegação de semana,
  filtro por especialidade client-side, chips coloridos por status linkando
  ao detalhe. Empilha no mobile, 7 colunas no desktop (sem scroll horizontal).
- **/plantoes/:id**: resumo + **timeline humanizada do audit log**
  (`GET /shifts/:id/audit` + `/doctors` p/ mapear nomes): "Lote 1 enviado para
  Dr. A, Dr. B · recusou · expirou · Lote 2…". "Disparar ofertas" quando aberto.
- Infra compartilhada: `lib/status.ts` (meta única de status, StatusPill agora
  consome), `lib/week.ts`, `lib/timeline.ts`, componente `Card`.
- **Pendente de backend** (PLANO §8, ainda sem endpoint): `POST /shifts/:id/cancel`,
  `/expand-pool`, marcar preenchido manualmente. Detalhe mostra nota honesta.

### Frontend Dia 4 — base + login + ofertas (médico) + novo plantão (coord) (2026-05-24)

Scaffold Next 16 / React 19 / Tailwind v4 com o design system do Hallmark
aplicado. `design.md` é **system-managed**: toda tela defere a ele + `tokens.css`.
**`next build` verde, 10 rotas, TypeScript limpo.** Backend não roda ponta-a-ponta
ainda (sem seed → sem contas) — validado por build + smoke render.

- **Tokens → Tailwind v4**: `globals.css` importa `tokens.css` e mapeia tudo no
  `@theme inline` (utilities `bg-surface`, `text-accent`, etc. confirmadas no CSS
  de produção). Fontes: Geist + JetBrains Mono via `next/font`, Cabinet Grotesk via
  Fontshare no `<link>`. Corrigida auto-referência potencial no `@theme` (funciona;
  `--color-paper` resolve pra `#ddeaff`).
- **Camada-base** (`src/lib/`): `api.ts` (fetch + Bearer + parse do envelope
  `{error:{code,message}}` → `ApiError` tipado; 401 limpa o token), `auth.tsx`
  (AuthProvider, token no localStorage, valida via `/auth/me` no mount), `types.ts`
  (espelha os shapes reais da API — nada inventado), `format.ts` (R$, datas pt-BR,
  countdown), `specialties.ts` (IDs fixos 1..8 da migration), `useCountdown.ts`
  (relógio local 1×/s contra `expires_at`), `useRequireRole.ts` (guard por papel).
  `providers.tsx`: TanStack Query + sonner Toaster re-tematizado.
- **Primitivos** (`src/components/ui/`): `StatusPill` (o token central — soft bg +
  texto ink + ponto/glyph na cor de status; `offering` pulsa), `Button`
  (4 variantes, 44px, foco instantâneo) + `ButtonLink`, `Field` (Input/Select),
  `Skeleton`, `EmptyState`, `ErrorState`.
- **Shells**: coordenadora = sidebar fixa 248px (md+) / top-bar + nav (mobile);
  médico = top-bar fina + **tab bar inferior** (alvos ≥44px). Ambos com guard.
- **Login** (`/login`): RHF + Zod, anti-enumeração no erro, redireciona por papel.
- **/ofertas** (médico, a estrela): cards com **countdown ao vivo** (cor muda <5min),
  accept/decline via mutation, **toasts 409 ("acabou de ser preenchido") / 410
  ("oferta expirou")**, `refetchInterval: 15s`. Loading=skeleton, empty com voz.
- **/plantoes/novo** (coord): RHF + Zod (input≠output por `z.coerce`), datas
  tz-aware (→ ISO Z), R$→cents, ajustes de pipeline opcionais. No sucesso, botão
  **"Disparar ofertas agora"** (POST `/shifts/:id/offer` via ranking) — fecha o
  loop coordenadora → médico.
- **Telas-loop leves reais**: `/agenda` (aceitos do médico), `/plantoes` (lista da
  coord). **Placeholders honestos** ("Em construção — Dia 5"): `/dashboard`,
  `/calendario`, `/historico`.
- Pisos do `design.md`: `overflow-x: clip` no root, reduced-motion global.

### Pipeline de ofertas + aceite atômico + 5 testes obrigatórios (2026-05-24)

O coração técnico do desafio. **83/83 testes passando**, ruff limpo.
Teste de concorrência rodado 8× seguidas sem flakiness.

- **`services/ranking.py`**: elegíveis = specialty ✓ + afiliação ATIVA ✓ +
  sem indisponibilidade sobreposta (`tstzrange && tstzrange` no Postgres).
  Ordem determinística (nome, id) — base estável pro avanço de batch.
- **`services/offers.py`** (núcleo):
  - `open_offers` (POST /shifts/:id/offer): abre batch 1 via ranking ou
    lista manual de `doctor_ids`.
  - `run_tick`: avanço **idempotente** (PLANO §7) — expira batch vencido,
    abre próximo batch com médicos não-ofertados, escala p/ `needs_attention`
    se chegou perto demais. Lock `FOR UPDATE` nos shifts candidatos.
  - `accept_offer`: **aceite atômico**. ⚠️ Corrigi a ordem de lock do PLANO:
    travar **shift → offer** (não offer → shift). Travar a oferta primeiro
    causa **deadlock** entre 2 aceites (o supersede de um precisa travar a
    oferta que o outro segura). Com o shift como ponto único de serialização,
    quem perde bloqueia antes de tocar em qualquer oferta → 409 limpo.
  - `decline_offer`.
- **`services/audit.py`**: `record_event` grava cada transição relevante.
- **Endpoints novos**: `POST /shifts/:id/offer`, `GET /shifts/:id/audit`,
  `POST /offers/:id/accept` (409/410), `POST /offers/:id/decline`,
  `GET /me/offers` (filtrado por afiliação), `GET /me/assignments`,
  `POST /jobs/tick` (protegido por `@require_secret('TICK_SECRET')`,
  comparação em tempo constante via `hmac.compare_digest`).
- **Erro `Gone` (410)** pro aceite de oferta expirada.
- **5 testes obrigatórios (PLANO §11)** todos verdes + extras:
  1. `test_concurrent_accept_only_one_wins` — 2 threads, conexões reais,
     Barrier; exatamente 1 ok + 1 conflito (409), 1 assignment ativa.
  2. `test_pipeline_advances_to_next_batch_after_window` — clock +31min.
  3. `test_doctor_only_sees_offers_from_affiliated_hospitals` — oferta
     "vazada" do outro hospital filtrada.
  4. `test_escalation_to_needs_attention` + audit event.
  5. `test_accept_expired_offer_returns_410_and_marks_expired`.
  Extras: `test_tick_is_idempotent`, accept happy-path/supersede, decline.
- **conftest**: helpers `seed_doctor`/`seed_shift` + fixture `real_engine`
  (sem savepoint, com TRUNCATE) pro teste de concorrência.

### Camada Flask — auth + CRUD de médicos/plantões (2026-05-24)

Endpoints de verdade plugados nas fundações puras do Dia 1. Arquitetura
em camadas: `api/` (blueprints finos) → `services/` (orquestração + transações)
→ `models`. **74/74 testes passando** (`uv run pytest`), ruff limpo.

- **App factory** `app/__init__.py` (`create_app`): injeta config em
  `app.config`, liga DB, registra error handlers, CORS e blueprints.
  Aceita `settings`/`session_factory` injetados (testabilidade). `GET /health`.
- **`app/infra/db.py`**: engine + sessionmaker ligados ao request. Serviços
  fazem `commit()` explícito; teardown só faz rollback/close (sem commit
  mágico — deixa espaço pro `SELECT FOR UPDATE` do Dia 3).
- **`app/api/errors.py`**: `ApiError` + subclasses (401/403/404/409/422) e
  handlers que serializam tudo como `{"error": {code, message, details?}}`.
  Captura `pydantic.ValidationError` → 422 campo-a-campo, HTTPException e 500.
- **`app/api/security.py`**: `@require_role(*roles)` extrai Bearer, valida via
  `jwt.verify`, guarda claims em `g`. Helpers `current_account_id/hospital_id`.
- **Auth**: `app/services/auth.py` (erro idêntico p/ e-mail inexistente e senha
  errada — anti-enumeração) + `POST /auth/login`, `GET /auth/me`.
- **CRUD médicos** (`app/services/doctors.py` + blueprint): cria conta+médico+
  especialidades (N:M)+afiliações numa transação; e-mail dup → 409 (tratado no
  `flush`, não no commit); specialty inválida → 422. List (filtro por
  specialty) e get.
- **CRUD plantões** (`app/services/shifts.py` + blueprint): create/list/get
  **escopados ao hospital da coordenadora** (claim). Plantão nasce `open`
  (não dispara oferta). Plantão de outro hospital → 404 (não vaza existência).
  Defaults de batch vêm de settings, sobrescrevíveis no body.
- **`app/infra/jwt.py`**: `verify` agora aceita `now` injetável (simétrico com
  `sign`) — corrigiu teste que apodreceu com a passagem do tempo.
- **Testes de API contra Postgres real**: `conftest.py` com isolamento por
  transação externa + savepoints (`join_transaction_mode="create_savepoint"`),
  banco `munin_test` migrado. 23 testes novos de API (auth, guards de papel,
  CRUD, scoping por hospital).

### Fundações puras de auth — hashing + JWT (2026-05-23)

Camada de infraestrutura pura, sem Flask, sem DB, sem clock global.
Pronta pra ser usada pelos endpoints `/auth/login` e
`@require_role` na próxima sessão.

- **`app/infra/hashing.py`**: `hash_password` / `verify_password`
  via bcrypt. 12 rounds padrão (prod), parametrizável pra teste.
- **`app/infra/jwt.py`**: `sign` / `verify` via PyJWT HS256.
  - `now` injetado como parâmetro → testes sem freezegun
  - Claims: `sub` (account_id), `role`, `hospital_id`, `iat`, `exp`
  - Exceção custom `InvalidToken` encapsula `PyJWTError`
- **12 testes unitários novos** cobrindo: hash diferente do plaintext,
  verificação correta/errada, salts aleatórios (mesmo plaintext →
  hashes distintos), unicode, token válido/expirado/secret-errado/
  malformado, `exp = iat + window`. **51/51 testes totais passando**.

### Schema + state machines (2026-05-23)

- **Postgres local** via Colima — `docker compose up -d` deixa
  `munin-postgres` healthy na 5432 (resolvido conflito com Postgres@14
  do Homebrew parando-o com `brew services stop postgresql@14`).
- **`backend/app/models.py`** com SQLAlchemy 2 declarativo, **12 tabelas**:
  `hospitals`, `accounts`, `doctors`, `specialties`,
  `doctor_specialties`, `doctor_hospital_affiliations`,
  `doctor_unavailabilities`, `shifts`, `shift_offers`,
  `shift_assignments`, `swap_requests`, `audit_events`.
  CHECK constraints (status válidos, `account_hospital_per_role`,
  janelas válidas), índices auxiliares.
- **Primeira migração Alembic** (`0001_initial.py`, escrita manual):
  - `CREATE EXTENSION citext`
  - 12 tabelas + constraints
  - **Índice único PARCIAL** `one_active_assignment_per_shift ON
    shift_assignments(shift_id) WHERE status='active'` — defesa em
    profundidade contra race condition
  - **Data migration** das 8 especialidades-base com IDs fixos 1..8
    + `setval` na sequence
- `migrations/env.py` apontando pra `Base.metadata`.
- **State machines puras**:
  - `app/domain/shift.py`: `ShiftStatus` (StrEnum), set de transições
    válidas estrito ao PLANO §5, `can_transition`/`assert_transition`/`is_terminal`
  - `app/domain/offer.py`: idem para `OfferStatus`
- **Testes unitários**: 38 testes (parametrizados) cobrindo transições
  válidas, inválidas, terminais sem saída e self-loop só em `offering`.
  **39/39 passando em 0.08s** (`uv run pytest`).

### Esqueleto do projeto (2026-05-22)

- Estrutura de pastas:
  - `backend/app/{api,services,domain,repositories,infra}` com `__init__.py`
  - `backend/tests/` para pytest
  - `backend/migrations/` via `alembic init`
  - `frontend/` placeholder (scaffold real no Dia 4)
  - `.github/workflows/` com skeleton de CI
- Backend Python 3.12 com `uv`:
  - `pyproject.toml` com Flask 3, SQLAlchemy 2, Alembic, Pydantic v2, PyJWT, bcrypt, psycopg
  - Dev deps: pytest, httpx, ruff, testcontainers
  - `uv.lock` gerado
- `alembic.ini` + `migrations/env.py` lendo `DATABASE_URL` do env
- `docker-compose.yml` com Postgres 15 (porta 5432, volume nomeado)
- `.env.example` documentando todas as variáveis
- `.gitignore` cobrindo Python, Node, dotenv, IDE
- `.github/workflows/test.yml` skeleton (matriz com Postgres como service)
- `PLANO.md` e este `IMPLEMENTACAO.md`

---

## Próximos passos imediatos

> Estes são os próximos itens em ordem. Ao começar uma sessão, ler daqui.

> 🎯 **Todo o obrigatório /35 está ✅** + bônus polidos (ranking explicável, swap,
> WhatsApp real, audit). Deploy público no ar, README de submissão entregue.
>
> **URLs de prod:** front `https://challenge-munin-ai.vercel.app` · back
> `https://munin-backend.fly.dev`. Logins: `coordenadora@hospital.com` /
> `medico@hospital.com` (senha `123456`).
>
> **Só sobram bônus opcionais** (se houver tempo/vontade): check-in com
> geolocalização (Tier 2), OpenAPI/Swagger (Tier 2), Mini-Luis / copiloto LLM
> (Tier 3). Antes da call: re-`join` no sandbox do Twilio (expira 72h) e,
> se quiser estado limpo, rodar o `POST /admin/seed`.

### 1. Auth + CRUD (Dia 2) ✅ 2026-05-24
- [x] Hashing de senha com bcrypt em `app/infra/hashing.py` ✅ 2026-05-23
- [x] JWT em `app/infra/jwt.py` (sign + verify) ✅ 2026-05-23
- [x] **App factory Flask** (`create_app()`, blueprints, error handlers) ✅
- [x] Session SQLAlchemy / DI nos handlers (`app/infra/db.py`) ✅
- [x] `POST /auth/login` e `GET /auth/me` ✅
- [x] Decorator `@require_role(...)` ✅
- [x] CRUD básico de médicos e plantões (com `specialty_id`) ✅

### 2. Pipeline de ofertas (Dia 3) ✅ 2026-05-24
- [x] `POST /shifts/:id/offer` → cria batch 1 ✅
- [x] `POST /jobs/tick` → avança pipeline (idempotente) ✅
- [x] Lógica de expiração e escalação para `needs_attention` ✅
- [x] Audit log gravando cada transição (`services/audit.py`) ✅

### 3. Accept atômico (Dia 3) ✅ 2026-05-24
- [x] `POST /offers/:id/accept` com `SELECT FOR UPDATE` (lock shift→offer) ✅
- [x] `POST /offers/:id/decline` ✅
- [x] **Teste de race condition com 2 threads** passando (8× sem flaky) ✅

### 4. Frontend (Dia 4-6)
- [x] Invocar `/hallmark` → `frontend/design.md` + `frontend/tokens.css` ✅ 2026-05-24
      (custom: base clara, accent laranja-vermelho OKLCH, Cabinet Grotesk +
      Geist + JetBrains Mono; status `offering` = accent)
- [x] `create-next-app frontend` (Next 16, App Router, TS, Tailwind 4) ✅ 2026-05-24
- [x] Instalar TanStack Query, React Hook Form (+resolvers), Zod, sonner, geist ✅
      (shadcn não usado — primitivos próprios re-tematizados nos tokens)
- [x] Auth flow (login + JWT no localStorage + Bearer; guard por papel) ✅
- [x] Tela médico **/ofertas** (countdown ao vivo + accept/decline 409/410) ✅
- [x] Tela coord **/plantoes/novo** (RHF+Zod + dispara ofertas) ✅
- [x] Empty/loading/error states + toasts (base do design.md §7) ✅
- [x] **Dia 5** — coord: dashboard (KPIs + tabela de risco), calendário semanal,
      detalhe `/plantoes/:id` com timeline do audit log ✅ 2026-05-24
- [x] **Backend p/ ações do detalhe** (PLANO §8): `POST /shifts/:id/cancel`,
      `/expand-pool`, `GET /shifts/:id/offers` ✅ 2026-05-25
- [x] **Histórico do médico**: tabela/cards com filtro de status ✅ 2026-05-25
- [x] **Error boundary + skip-to-content + CORS + N+1 fix** ✅ 2026-05-25
### 5. WFM Completo — Ranking + Gestão de Médicos + UX Médico (aprovado 2026-05-25)

> Plano detalhado em `implementation_plan.md` (Antigravity). Resumo e checklist:

#### Fase 1 — Ranking inteligente (Backend, Bônus Tier 1)
- [x] `ranking.py`: `ranked_doctors()` com score 0–100 (4 fatores: aceite 40%, recência 25%, carga 20%, resposta 15%)
- [x] 2 queries bulk para stats (sem N+1)
- [x] Breakdown por médico (explicabilidade)
- [x] `offers.py`: `open_offers` usa `ranked_doctors` em vez de `eligible_doctors`
- [x] Médico sem histórico = score neutro (50)

#### Fase 2 — Backend gestão de médicos
- [x] `PATCH /doctors/:id` — editar nome, phone, specialties
- [x] `POST /doctors/:id/deactivate` e `/activate` — soft-delete via affiliation
- [x] `GET /doctors/:id/stats` — métricas (aceite %, carga, score)
- [x] `GET/POST/DELETE /doctors/:id/unavailabilities` — CRUD indisponibilidades (coord)
- [x] `GET /me/profile` e `PATCH /me/profile` — médico edita seu perfil
- [x] `GET/POST/DELETE /me/unavailabilities` — médico gerencia suas indisponibilidades

#### Fase 3 — Frontend coord: tela de médicos
- [x] `/medicos` — lista com tabela (nome, specialties, aceite %, plantões, status)
- [x] `/medicos/[id]` — perfil: dados editáveis, métricas, indisponibilidades, histórico
- [x] `/medicos/novo` — formulário de cadastro
- [x] Nav sidebar: adicionar link "Médicos" com ícone ⊕

#### Fase 4 — Frontend médico: multi-hospital + perfil
- [x] `/ofertas` — filtro por hospital (dropdown, client-side)
- [x] `/agenda` — rewrite: agrupada por dia (igual plantões da coord), filtro hospital
- [x] `/historico` — adicionar filtro por hospital
- [x] `/perfil` — nova tab: nome, phone, hospitais, specialties, indisponibilidades
- [x] Tab bar inferior: adicionar aba "Perfil" com ícone ◎

### 6. Deploy ✅ 2026-05-30
- [x] Backend → Fly.io (`munin-backend.fly.dev`; Dockerfile + fly.toml + release_command)
- [x] Frontend → Vercel (`challenge-munin-ai.vercel.app`; root `frontend/`)
- [x] DB → Supabase (Postgres 17, `sa-east-1`, session pooler)
- [x] Configurar secrets `API_URL` e `TICK_SECRET` no GitHub
- [x] **Reativar cron do `tick.yml`** (`schedule: */5` ativo)

### 7. Seed + README
- [x] `POST /admin/seed` (guard `ADMIN_SECRET`) ✅ 2026-05-24 — idempotente
  (TRUNCATE + recria; preserva specialties). 2 hospitais, coordenadora +
  30 médicos (1–2 specialties, afiliações variadas A/B), 10 plantões em
  estados reais (open/offering/accepted/needs_attention). Usa os serviços
  reais (`open_offers`/`accept_offer`) → gera audit events (timeline povoada).
  Credenciais: `coordenadora@hospital.com` / `medico@hospital.com` (`123456`).
- [x] README com link, credenciais, diagramas, decisões, prints/GIF ✅ 2026-05-30
  (enunciado original movido p/ `CHALLENGE.md`; README de submissão com arquitetura/
  ER/state machine em Mermaid, concorrência, ranking, deploy, trade-offs, 5 prints)

### 8. Bônus extra (se houver tempo)
- [ ] Mini-Luis: chat LLM com tool calling (`claude-haiku-4-5-20251001`)
- [ ] Copiloto da coordenadora (SQL read-only via tool calling)

---

## Decisões já tomadas

- **Ordem de lock do aceite: shift → offer** (corrige o PLANO §6, que travava
  offer → shift). Travar a oferta primeiro causa deadlock entre dois aceites
  do mesmo plantão (o `UPDATE ... superseded` de um precisa travar a oferta que
  o outro já segura). Travar o shift primeiro o torna o ponto único de
  serialização: o perdedor bloqueia antes de tocar em qualquer oferta. Ver
  comentário em `services/offers.py::accept_offer` e o teste de 2 threads.
- **Tick com commit explícito por rodada, sem commit no teardown** — controle de
  transação fica visível no serviço (precisa pro `FOR UPDATE`).
- **Python 3.12** (não 3.14 que tá local) para alinhar com a stack da Munin.
- **`uv`** como gerenciador de pacotes do backend.
- **Fly.io** pro backend (locks + transações longas funcionam melhor que serverless).
- **Tick lazy no dashboard** como rede de segurança caso o GitHub Actions cron atrase.
- **Frontend scaffold só no Dia 4**: evita configurar coisa que vai ser reescrita.
- **Tick não auto-oferta OPEN** (2026-05-25): tick agora só processa shifts em
  `OFFERING`. A coordenadora dispara explicitamente via `POST /shifts/:id/offer`.
  Motivo: o auto-offering tirava controle da coordenadora — um plantão criado
  pro dia seguinte seria ofertado imediatamente pelo tick, sem que ela pudesse
  revisar. O tick continua avançando batches e escalando normalmente.
- **N+1 resolvido com batch view** (2026-05-25): `doctors_view_batch` faz 2
  queries (specialties + affiliations) pra N médicos, em vez de 2×N. O endpoint
  `/doctors` que serve o dropdown da coord escalava mal.
- **Ranking inteligente com 4 fatores** (planejado 2026-05-25): aceite rate
  (40%) + recência (25%) + carga semanal (20%) + tempo de resposta (15%).
  Score 0–100 com breakdown explicável por médico. Médico sem histórico
  recebe 50 (neutro). 2 queries bulk para stats.
- **Soft-delete de médicos** (planejado 2026-05-25): desativar = mudar
  `doctor_hospital_affiliations.status` para `inactive`, não deletar do
  banco. Preserva auditoria e permite reativação.
- **Médico edita nome/phone, não specialties** (planejado 2026-05-25):
  especialidade é credencial — só coordenadora altera via PATCH /doctors/:id.
- **Filtro hospital no frontend = client-side** (planejado 2026-05-25):
  dados de `/me/offers` e `/me/assignments` já vêm com `hospital_name`.
  Filtro é só `.filter()` no array — zero queries extras.
- **Colima como runtime Docker local** (2026-05-23): mesmo
  `docker-compose.yml` que o avaliador vai usar, sem peso do Docker
  Desktop. `docker compose up -d` sobe Postgres 15 healthy.
- **Schema expandido em 2026-05-23** — racional completo em PLANO §4.7:
  - `specialties` como tabela de lookup (FK), não TEXT — string match
    livre quebra silenciosamente.
  - Médico ↔ hospital é **N:M** via `doctor_hospital_affiliations`
    (plantonistas trabalham em vários hospitais).
  - Especialidade "usada" no aceite é **inferida** via shift, não
    armazenada (Opção A).
  - `doctor_unavailabilities` em tabela própria, filtrada pelo tick.
- **Repetição de indisponibilidades** (2026-05-25): para simplificar o
  schema do banco (evitando queries GIST/OVERLAPS lentas para RRULEs), a
  repetição semanal (ex. por 4 semanas) no frontend gera instâncias reais no
  banco via loop no `create_unavailability`, facilitando a verificação no `ranking.py`.
- **Formatação amigável de datas no perfil** (2026-05-25): uso nativo de
  `toLocaleDateString` e `toLocaleTimeString` no frontend para exibição clara
  do formato (ex: `25 Mai, 14:00 até 25 Mai, 18:00`), focando em melhor UX
  tanto para o médico quanto para a coordenação.
  - `audit_events.hospital_id` opcional (custo zero, filtros futuros).

---

## Bloqueios e dúvidas em aberto

- ~~Docker Desktop não está instalado.~~ ✅ resolvido em 2026-05-23
  com **Colima** (`brew install colima docker docker-compose` +
  `colima start`). Container `munin-postgres` rodando healthy.
- Cron do `.github/workflows/tick.yml` está **desativado** (commit
  `c6b1652`). Só roda via `workflow_dispatch` manual. Reativar no Dia 6
  junto com deploy — ver passo 6 acima.

---

## Como atualizar este arquivo

1. Ao **terminar** uma feature grande, mover do "Próximos passos" para
   "Feito" com data e bullets do que foi entregue.
2. Ao **começar** uma sessão, ler o topo inteiro pra retomar contexto.
3. Manter conciso: este arquivo é índice + checklist, não documentação.
   Para detalhes técnicos profundos, ver `PLANO.md`.
