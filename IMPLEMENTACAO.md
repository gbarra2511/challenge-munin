# IMPLEMENTACAO.md — Tracking

> Estado atual da implementação do Mini-WFM e próximos passos.
> **Atualizar após cada feature grande. Revisar no início de cada sessão.**

Última atualização: 2026-05-24 (Dia 2 fechado — camada Flask: auth + CRUD de médicos/plantões)

---

## Status global

| Bloco | Status |
|---|---|
| Esqueleto do projeto | ✅ feito |
| Schema do banco + state machines | ✅ feito |
| Auth + CRUD básicos | ✅ feito |
| Pipeline de ofertas + tick | ⏳ pendente |
| Accept atômico (race condition) | ⏳ pendente |
| Frontend (Hallmark + telas) | ⏳ pendente |
| Deploy público + seed | ⏳ pendente |
| Testes obrigatórios (5) | ⏳ pendente |
| README final | ⏳ pendente |
| Bônus | ⏳ depois do obrigatório |

---

## Feito

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

### 2. Pipeline de ofertas (Dia 2-3)
- [ ] `POST /shifts/:id/offer` → cria batch 1
- [ ] `POST /jobs/tick` → avança pipeline (idempotente).
  Ranking JOIN: `doctor_specialties` × `doctor_hospital_affiliations`
  × `NOT EXISTS doctor_unavailabilities` (ver PLANO §7)
- [ ] Lógica de expiração e escalação para `needs_attention`
- [ ] Audit log gravando cada transição (usar state machines de §1 acima)

### 3. Accept atômico (Dia 3)
- [ ] `POST /offers/:id/accept` com `SELECT FOR UPDATE`
- [ ] `POST /offers/:id/decline`
- [ ] **Teste de race condition com 2 threads** passando

### 4. Frontend (Dia 4-6)
- [ ] Invocar `/hallmark` para gerar tokens + princípios
- [ ] `pnpm create next-app frontend` (Next 16, App Router, TS, Tailwind 4)
- [ ] Instalar shadcn/ui, TanStack Query, React Hook Form, Zod, sonner
- [ ] Auth flow (login + cookie JWT)
- [ ] Telas coordenadora: dashboard, calendário, detalhe, criar
- [ ] Telas médico: ofertas (com countdown), aceitos, histórico
- [ ] Empty/loading/error states em tudo

### 5. Deploy (Dia 6)
- [ ] Backend → Fly.io (Dockerfile + `fly launch`)
- [ ] Frontend → Vercel
- [ ] DB → Supabase
- [ ] Configurar secrets `API_URL` e `TICK_SECRET` no GitHub
- [ ] **Reativar cron do `tick.yml`** (descomentar bloco `schedule:`) —
  está desativado desde 2026-05-22 porque estava falhando sem backend
  e sem secrets, gerando emails de "tick failed" a cada 5 min

### 6. Seed + README (Dia 6-7)
- [ ] `POST /admin/seed`: 2 hospitais, 2 coordenadoras, 30 médicos
  (1–2 specialties cada, ~25% afiliados a ambos), 12 plantões, algumas
  indisponibilidades. **Não recria specialties** — vem da migration.
- [ ] README com link, credenciais, diagramas, decisões, prints/GIF

### 7. Bônus (Dia 7, se houver tempo)
- [ ] Ranking de médicos com explicabilidade
- [ ] Timeline rica no detalhe do plantão (a partir do audit log)
- [ ] Mini-Luis: chat LLM com tool calling (`claude-haiku-4-5-20251001`)

---

## Decisões já tomadas

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
