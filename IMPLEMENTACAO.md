# IMPLEMENTACAO.md — Tracking

> Estado atual da implementação do Mini-WFM e próximos passos.
> **Atualizar após cada feature grande. Revisar no início de cada sessão.**

Última atualização: 2026-05-22 (cron do tick desativado, ver §Bloqueios)

---

## Status global

| Bloco | Status |
|---|---|
| Esqueleto do projeto | ✅ feito |
| Schema do banco + state machines | ⏳ próximo |
| Auth + CRUD básicos | ⏳ pendente |
| Pipeline de ofertas + tick | ⏳ pendente |
| Accept atômico (race condition) | ⏳ pendente |
| Frontend (Hallmark + telas) | ⏳ pendente |
| Deploy público + seed | ⏳ pendente |
| Testes obrigatórios (5) | ⏳ pendente |
| README final | ⏳ pendente |
| Bônus | ⏳ depois do obrigatório |

---

## Feito

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

### 1. Schema + state machines (Dia 1, restante)
- [ ] Modelar tabelas em `backend/app/models.py` (SQLAlchemy 2 declarative)
- [ ] Primeira migração Alembic com as 7 tabelas
  - accounts, hospitals, doctors, shifts, shift_offers,
    shift_assignments, audit_events
  - **Crítico**: `UNIQUE INDEX one_active_assignment_per_shift ON shift_assignments(shift_id) WHERE status='active'`
- [ ] State machine pura em `app/domain/shift.py` (transições válidas + validação)
- [ ] State machine pura em `app/domain/offer.py`
- [ ] Testes unitários da state machine (sem banco)
- [ ] Subir Postgres local (docker compose), rodar migration, validar

### 2. Auth + CRUD (Dia 2)
- [ ] Hashing de senha com bcrypt em `app/infra/hashing.py`
- [ ] JWT em `app/infra/jwt.py` (sign + verify)
- [ ] `POST /auth/login` e `GET /auth/me`
- [ ] CRUD básico de médicos e plantões
- [ ] Decorator `@require_role('coordenador')`

### 3. Pipeline de ofertas (Dia 2-3)
- [ ] `POST /shifts/:id/offer` → cria batch 1
- [ ] `POST /jobs/tick` → avança pipeline (idempotente)
- [ ] Lógica de expiração e escalação para `needs_attention`
- [ ] Audit log gravando cada transição

### 4. Accept atômico (Dia 3)
- [ ] `POST /offers/:id/accept` com `SELECT FOR UPDATE`
- [ ] `POST /offers/:id/decline`
- [ ] **Teste de race condition com 2 threads** passando

### 5. Frontend (Dia 4-6)
- [ ] Invocar `/hallmark` para gerar tokens + princípios
- [ ] `pnpm create next-app frontend` (Next 16, App Router, TS, Tailwind 4)
- [ ] Instalar shadcn/ui, TanStack Query, React Hook Form, Zod, sonner
- [ ] Auth flow (login + cookie JWT)
- [ ] Telas coordenadora: dashboard, calendário, detalhe, criar
- [ ] Telas médico: ofertas (com countdown), aceitos, histórico
- [ ] Empty/loading/error states em tudo

### 6. Deploy (Dia 6)
- [ ] Backend → Fly.io (Dockerfile + `fly launch`)
- [ ] Frontend → Vercel
- [ ] DB → Supabase
- [ ] Configurar secrets `API_URL` e `TICK_SECRET` no GitHub
- [ ] **Reativar cron do `tick.yml`** (descomentar bloco `schedule:`) —
  está desativado desde 2026-05-22 porque estava falhando sem backend
  e sem secrets, gerando emails de "tick failed" a cada 5 min

### 7. Seed + README (Dia 6-7)
- [ ] `POST /admin/seed`: 1 hospital, 30 médicos, 1 coordenadora, 10 plantões
- [ ] README com link, credenciais, diagramas, decisões, prints/GIF

### 8. Bônus (Dia 7, se houver tempo)
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

---

## Bloqueios e dúvidas em aberto

- Docker Desktop não está instalado na máquina. Precisa instalar antes de
  rodar `docker compose up` para o Postgres local. Alternativa: Colima
  ou Postgres via Homebrew.
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
