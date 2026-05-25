# IMPLEMENTACAO.md — Tracking

> Estado atual da implementação do Mini-WFM e próximos passos.
> **Atualizar após cada feature grande. Revisar no início de cada sessão.**

Última atualização: 2026-05-24 (Dia 5 fechado — dashboard + calendário + detalhe do plantão com timeline)

---

## Como rodar e acessar (local)

**Subir tudo (do repo root):**
1. `colima start && docker compose up -d` — Postgres `munin-postgres` na :5432.
2. Backend: `cd backend` →
   `export DATABASE_URL="postgresql+psycopg://munin:munin@localhost:5432/munin"` →
   `uv run alembic upgrade head` →
   `FLASK_APP="app:create_app" uv run flask run --port 5000 --host 127.0.0.1`
3. Seed: `curl -X POST http://127.0.0.1:5000/admin/seed -H "Authorization: Bearer dev-only-change-me-admin"`
4. Frontend: `cd frontend && npm install && npm run dev` → http://localhost:3000
   (API via `NEXT_PUBLIC_API_URL`, default `http://127.0.0.1:5000` — ver `.env.example`).

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
| Pipeline de ofertas + tick | ✅ feito |
| Accept atômico (race condition) | ✅ feito |
| Frontend (Hallmark + telas) | 🔄 em andamento (Dias 4–5 ✅: auth + todas as telas-núcleo) |
| Deploy público + seed | ⏳ pendente |
| Testes obrigatórios (5) | ✅ feito (5/5 + extras) |
| README final | ⏳ pendente |
| Bônus | ⏳ depois do obrigatório |

---

## Feito

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
- [ ] **Backend p/ ações do detalhe** (PLANO §8): `POST /shifts/:id/cancel`,
      `/expand-pool`, marcar preenchido manualmente (precisam de service + teste)
- [ ] **Polish** — médico: histórico paginado; agenda como calendário pessoal;
      sidebar→drawer real <768px (hoje colapsa pra top-bar + nav horizontal)

### 5. Deploy (Dia 6)
- [ ] Backend → Fly.io (Dockerfile + `fly launch`)
- [ ] Frontend → Vercel
- [ ] DB → Supabase
- [ ] Configurar secrets `API_URL` e `TICK_SECRET` no GitHub
- [ ] **Reativar cron do `tick.yml`** (descomentar bloco `schedule:`) —
  está desativado desde 2026-05-22 porque estava falhando sem backend
  e sem secrets, gerando emails de "tick failed" a cada 5 min

### 6. Seed + README (Dia 6-7)
- [x] `POST /admin/seed` (guard `ADMIN_SECRET`) ✅ 2026-05-24 — idempotente
  (TRUNCATE + recria; preserva specialties). 2 hospitais, coordenadora +
  30 médicos (1–2 specialties, afiliações variadas A/B), 10 plantões em
  estados reais (open/offering/accepted/needs_attention). Usa os serviços
  reais (`open_offers`/`accept_offer`) → gera audit events (timeline povoada).
  Credenciais: `coordenadora@hospital.com` / `medico@hospital.com` (`123456`).
- [ ] README com link, credenciais, diagramas, decisões, prints/GIF

### 7. Bônus (Dia 7, se houver tempo)
- [ ] Ranking de médicos com explicabilidade
- [ ] Timeline rica no detalhe do plantão (a partir do audit log)
- [ ] Mini-Luis: chat LLM com tool calling (`claude-haiku-4-5-20251001`)

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
