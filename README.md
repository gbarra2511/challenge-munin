# Munin — Mini-WFM de plantões hospitalares

> Coordenação cadastra plantões → o sistema oferta em lotes, expira, escala e
> entrega ao **primeiro que aceitar** (com a race condition tratada de verdade).
> Médico vê suas ofertas com countdown, aceita/recusa, pede troca. Tudo com
> dashboard, calendário, ranking explicável de médicos e notificação real por
> WhatsApp.

```
🔗 App:  https://challenge-munin-ai.vercel.app
🔗 API:  https://munin-backend.fly.dev   (health: /health)

Login coordenadora:  coordenadora@hospital.com / 123456
Login médico (demo): medico@hospital.com       / 123456
Outros médicos:      medico1@hospital.com … medico29@hospital.com  (/ 123456)
```

> O médico-demo já tem **2 ofertas com countdown ativo + 1 plantão aceito**. A
> coordenadora vê 2 hospitais, 30 médicos e 10 plantões em estados reais
> (aberto / em oferta / preenchido / em risco). Se quiser zerar pra um estado
> limpo: `POST /admin/seed` (ver [Seed](#seed)).

O enunciado original do desafio está preservado em **[CHALLENGE.md](./CHALLENGE.md)**.

---

## Telas

| Dashboard da coordenação | Detalhe do plantão (ranking + timeline) |
|---|---|
| ![Dashboard](docs/screenshots/coord-dashboard.png) | ![Detalhe](docs/screenshots/coord-plantao-detalhe.png) |

| Calendário semanal | Gestão de médicos | Ofertas do médico |
|---|---|---|
| ![Calendário](docs/screenshots/coord-calendario.png) | ![Médicos](docs/screenshots/coord-medicos.png) | ![Ofertas](docs/screenshots/medico-ofertas.png) |

---

## Sumário

- [O que faz](#o-que-faz)
- [Stack](#stack)
- [Arquitetura](#arquitetura)
- [Modelo de dados](#modelo-de-dados)
- [State machines](#state-machines)
- [Concorrência — o aceite atômico](#concorrência--o-aceite-atômico)
- [Pipeline de ofertas](#pipeline-de-ofertas)
- [Notificações (outbox + WhatsApp)](#notificações-outbox--whatsapp)
- [Ranking explicável de médicos](#ranking-explicável-de-médicos)
- [API](#api)
- [Frontend](#frontend)
- [Testes](#testes)
- [Rodar local](#rodar-local)
- [Deploy](#deploy)
- [Decisões e trade-offs](#decisões-e-trade-offs)
- [O que ficou de fora / com +1 semana](#o-que-ficou-de-fora--com-1-semana)
- [Bônus implementados](#bônus-implementados)
- [Estrutura do repositório](#estrutura-do-repositório)

---

## O que faz

**Obrigatório, ponta a ponta e em produção:**

- **Auth** por e-mail/senha (bcrypt) com JWT e dois papéis (`coordenador`,
  `medico`). Erro idêntico para e-mail inexistente e senha errada (anti-enumeração).
- **Médicos**: CRUD, especialidades (N:M), afiliações a hospitais (N:M),
  indisponibilidades, ativação/desativação (soft-delete via afiliação), stats.
- **Plantões**: CRUD escopado ao hospital da coordenadora, abrir oferta
  (`POST /shifts/:id/offer`), cancelar, ampliar pool, ver ofertas/ranking/audit.
- **Ofertas em lotes**: manda pra N médicos, espera a janela, libera o próximo
  lote, expira, e **escala para "em risco"** quando o plantão se aproxima.
- **Aceite atômico**: o primeiro que aceitar leva; os demais recebem 409
  ("plantão preenchido") — com lock pessimista **+** constraint de banco.
- **Job de avanço** (`POST /jobs/tick`) idempotente, disparado por GitHub
  Actions a cada 5 min (e com tick preguiçoso no dashboard como rede de segurança).
- **SPA** com dashboard (KPIs + gráfico 7 dias + lista de risco), calendário
  semanal, detalhe com timeline do audit log, criar plantão, e a área do médico
  (ofertas com countdown ao vivo, agenda, histórico, perfil). Responsiva no celular.

**Bônus entregues:** ranking explicável de médicos, notificação **real por
WhatsApp** (Twilio, entrega verificada), **troca de plantão** (swap) com
aprovação da coordenação, e **audit log** imutável de toda transição.

---

## Stack

| Camada | Escolha |
|---|---|
| Backend | Python 3.12 · Flask 3 · SQLAlchemy 2 · Pydantic v2 · gunicorn |
| Banco | PostgreSQL 17 (Supabase) · migrações Alembic |
| Frontend | Next.js 16 · React 19 · Tailwind v4 · TanStack Query · React Hook Form + Zod · sonner |
| Auth | JWT (PyJWT HS256) na mão · bcrypt |
| Notificação | Outbox no Postgres + Twilio WhatsApp (sandbox) |
| Testes | pytest contra Postgres real (160 testes) |
| Deploy | Fly.io (API) · Supabase (DB) · Vercel (front) · GitHub Actions (cron do tick) |

Aderente à stack sugerida pela Munin. Sem `shadcn` — os primitivos de UI são
próprios, tematizados por um design system local (`frontend/design.md` + tokens).

---

## Arquitetura

```mermaid
flowchart LR
    subgraph Cliente
      Coord[SPA Coordenação]
      Med[SPA Médico]
    end
    subgraph Vercel
      Next[Next.js 16]
    end
    subgraph Fly.io
      Flask[Flask + gunicorn<br/>API + tick handler]
    end
    subgraph Supabase
      PG[(PostgreSQL 17)]
    end
    subgraph Externo
      GH[GitHub Actions<br/>cron */5]
      TW[Twilio WhatsApp]
    end
    Coord --> Next
    Med --> Next
    Next -->|JSON + Bearer JWT| Flask
    Flask -->|SQLAlchemy| PG
    GH -->|POST /jobs/tick<br/>Bearer TICK_SECRET| Flask
    Flask -->|dispatch do outbox| TW
```

**Backend em camadas** — a API nunca toca SQL direto:

```
backend/app/
├── api/          # blueprints Flask: parsing (Pydantic) + serialização + guards de papel
├── services/     # casos de uso + transações (open_offers, accept_offer, run_tick, swaps, …)
├── domain/       # state machines puras (shift.py, offer.py, swap.py) — testáveis sem banco
├── infra/        # jwt, hashing, config (pydantic-settings), db, notifier/whatsapp
└── models.py     # tabelas SQLAlchemy
```

Decisões-chave: **controle de transação explícito** nos serviços (o teardown só
faz rollback — deixa espaço para o `SELECT ... FOR UPDATE`); o **relógio é
injetável** (parâmetro `now`) para testar expiração sem `time.sleep`.

---

## Modelo de dados

12 tabelas. O `id` é `uuid`; e-mails são `citext` (case-insensitive).

```mermaid
erDiagram
    hospitals ||--o{ accounts : "coordenadora"
    hospitals ||--o{ shifts : possui
    hospitals ||--o{ doctor_hospital_affiliations : vincula
    accounts  ||--o| doctors : "1:1 se médico"
    doctors   ||--o{ doctor_specialties : atua
    doctors   ||--o{ doctor_hospital_affiliations : "trabalha em"
    doctors   ||--o{ doctor_unavailabilities : tem
    doctors   ||--o{ shift_offers : recebe
    doctors   ||--o{ shift_assignments : ganha
    specialties ||--o{ doctor_specialties : "exercida por"
    specialties ||--o{ shifts : "requerida em"
    shifts ||--o{ shift_offers : possui
    shifts ||--o| shift_assignments : "0..1 ativo"
    shifts ||--o{ audit_events : registra
    shift_assignments ||--o{ swap_requests : origem
    accounts ||--o{ notifications : destinatário
```

**Por que assim (e não o mínimo sugerido):**

- **`specialties` é tabela de lookup (FK), não TEXT.** String livre quebra em
  silêncio no match de elegibilidade. 8 especialidades-base com IDs fixos vêm
  numa data migration.
- **Médico ↔ hospital é N:M** (`doctor_hospital_affiliations`): plantonista
  trabalha em vários hospitais. Desativar = afiliação `inactive` (soft-delete,
  preserva auditoria).
- **`doctor_unavailabilities` em tabela própria**, filtrada no ranking via
  `tstzrange && tstzrange`. Repetição semanal vira **instâncias reais** no banco
  (evita RRULE/consultas GIST complexas — trade-off pró-simplicidade).
- **`one_active_assignment_per_shift`**: índice **único parcial**
  (`ON shift_assignments(shift_id) WHERE status='active'`) — a rede de segurança
  da concorrência (ver abaixo).
- **`audit_events`**: toda transição relevante vira evento imutável → alimenta a
  timeline do detalhe do plantão.

---

## State machines

State machine **explícita** no domínio (`domain/shift.py`, `offer.py`, `swap.py`):
um set de transições válidas + `assert_transition` chamado em cada mudança. Nada
de `if` espalhado em controller.

```mermaid
stateDiagram-v2
    [*] --> open: coordenadora cria
    open --> offering: dispara ofertas (1º lote)
    offering --> offering: tick libera próximo lote
    offering --> accepted: médico aceita (atômico)
    offering --> needs_attention: prazo perto, sem aceite
    offering --> cancelled: coord cancela
    needs_attention --> offering: coord amplia o pool
    needs_attention --> cancelled: coord cancela
    accepted --> cancelled: coord cancela
    confirmed --> [*]
    cancelled --> [*]
```

Cada **oferta** é uma máquina menor:
`pending → accepted | declined | expired | superseded`.

E a **troca** (swap): `pending → approved | rejected | cancelled`, com índice
único parcial garantindo no máximo 1 pedido pendente por assignment.

---

## Concorrência — o aceite atômico

É o coração do desafio. Defesa em **duas camadas**:

**1. Constraint de banco** — o índice único parcial
`one_active_assignment_per_shift` torna fisicamente impossível dois assignments
ativos no mesmo plantão, mesmo que a lógica falhe.

**2. Lock pessimista com o _shift_ como ponto único de serialização.**

```python
# services/offers.py::accept_offer  (resumo)
shift  = SELECT … FROM shifts        WHERE id = shift_id FOR UPDATE   # 1) trava o shift
offer  = SELECT … FROM shift_offers  WHERE id = offer_id FOR UPDATE   # 2) só então a oferta
if shift.status != 'offering':  raise Conflict(409, 'shift_no_longer_open')
if offer.status != 'pending':   raise Conflict(409, 'offer_no_longer_pending')
if now > offer.expires_at:      raise Gone(410, 'offer_expired')
# transições atômicas: oferta→accepted, demais pendentes→superseded,
# INSERT assignment active, shift→accepted, version += 1, audit
```

> **⚠️ Ordem de lock: `shift → offer`.**
> Travar a oferta primeiro **deadlocka**: o `UPDATE ... superseded` de um aceite
> precisa travar a oferta que o aceite concorrente já segura. Com o **shift**
> como primeiro lock, ele vira o ponto único de serialização do plantão — quem
> chega segundo bloqueia ali, *antes* de tocar em qualquer oferta, e ao destravar
> lê o shift já `accepted` → **409 limpo**.

**Dois cliques simultâneos:** A pega o lock do shift; B fila. A conclui (shift
`accepted`, ofertas de B `superseded`). B destrava, vê `status != offering` → 409
→ toast *"acabou de ser preenchido"*. Oferta expirada no aceite → **410**.

**Por que pessimista e não otimista?** O lock dura milissegundos e a contenção
real é rara (poucos médicos por plantão); pessimista é mais simples de raciocinar.
O índice único parcial fica como defesa em profundidade de qualquer jeito.

Coberto pelo teste `test_concurrent_accept_only_one_wins` — **2 threads, conexões
reais, `Barrier`** → exatamente 1 OK + 1 conflito, 1 assignment ativa (rodado
várias vezes sem flakiness).

---

## Pipeline de ofertas

`POST /jobs/tick` é **idempotente** e faz, sob `FOR UPDATE` nos plantões em
`offering`:

1. **Expira** o lote vencido (ofertas `pending` além de `expires_at` → `expired`).
2. **Libera o próximo lote** com médicos ainda não ofertados (do ranking).
3. **Escala** para `needs_attention` quando chega perto do início e ninguém pegou.
4. Drena o **outbox** de notificações (`dispatch_pending`).

A coordenadora **dispara o 1º lote explicitamente** (`POST /shifts/:id/offer`) —
o tick **não** auto-oferta plantões `open`. Motivo: um plantão criado para semana
que vem não deve sair ofertando sozinho antes da coordenadora revisar.

**Disparo:** GitHub Actions com `schedule: */5` chamando o endpoint com
`Bearer TICK_SECRET` (comparação em tempo constante via `hmac.compare_digest`).
O mesmo cron mantém a máquina do Fly acordada e o Supabase fora do pause.

---

## Notificações (outbox + WhatsApp)

**Padrão outbox** para nunca fazer dual-write (gravar no banco *e* chamar o
provedor na mesma transação):

- A ação de domínio (oferta enviada, swap pedido/decidido) **enfileira** a
  notificação na mesma transação. `in_app` nasce `sent` (o feed/sininho lê
  direto); `whatsapp` nasce `pending`. `dedupe_key` único torna o enqueue
  idempotente.
- O **dispatch** é *claim-then-send*: trava+marca `sending` num passo curto com
  `FOR UPDATE SKIP LOCKED` (dois ticks não pegam a mesma linha), **commita para
  soltar o lock**, e só então chama o Twilio — **fora de qualquer lock de banco**.
  At-least-once. O telefone (PII) é resolvido só no envio, nunca no payload/audit.
- **Entrega quase-instantânea:** além do cron, as ações que notificam fazem um
  *dispatch inline* best-effort logo após o commit — o WhatsApp do swap/oferta
  chega na hora, sem esperar os 5 min do cron, que segue como **fallback durável**.

**WhatsApp real (Twilio sandbox)** — entrega `delivered` verificada ponta a
ponta. Sem credenciais, o backend usa `NullNotifier` (loga, não envia) — dev e
testes nunca tocam a rede.

> **Caveats documentados:** o **sandbox do Twilio expira
> em ~72h** — para a avaliação, re-envie o `join <código>` antes de abrir o link.
> E o WhatsApp identifica celular **brasileiro sem o 9º dígito** (com ele → erro
> 63015). Sair disso de vez exigiria um WhatsApp Business sender aprovado (fora do
> escopo da semana).

---

## Ranking explicável de médicos

Ao ofertar, os médicos são ordenados por um **score 0–100 explicável** (bônus
Tier 1), com 4 fatores ponderados:

**NOTE QUE: especialistas tem prioridade, entretando dependendo do plantão, é melhor ter um não especialista do que não ter um médico**

| Fator | Peso | Direção |
|---|---|---|
| Taxa de aceite histórica | 40% | aceita mais → score maior |
| Recência (dias sem plantão) | 25% | há mais tempo sem → maior |
| Carga semanal | 20% | menos plantões na semana → maior |
| Tempo de resposta | 15% | responde mais rápido → maior |

Médico sem histórico recebe **50 (neutro)**. As stats vêm em **2 queries bulk**
(sem N+1). Cada médico expõe o *breakdown* — a UI mostra "aceita 80% das ofertas ·
6d sem plantão · responde em ~4min" e os sub-scores no hover.

**Especialidade é _tier_, não filtro duro:** especialistas primeiro; não
especialistas afiliados e disponíveis entram como **fallback anti-buraco**, só
para o plantão não ficar vazio. *Caveat:* no mundo real, cross-coverage deveria
ser por flag de tipo de plantão (CTI/peds não são substituíveis) — fica como
evolução.

---

## API

Envelope de erro padronizado `{ "error": { code, message, details? } }`; papéis
exigidos por decorator (`@require_role`); escopo por hospital (plantão de outro
hospital → 404, não vaza existência).

```
# Auth
POST   /auth/login            GET /auth/me

# Coordenação (role=coordenador)
GET/POST /shifts              GET /shifts/:id
POST   /shifts/:id/offer      POST /shifts/:id/cancel      POST /shifts/:id/expand-pool
GET    /shifts/:id/offers     GET  /shifts/:id/ranking     GET  /shifts/:id/audit
POST   /shifts/ranking-preview                              (dry-run do ranking na criação)
GET/POST /doctors             GET/PATCH /doctors/:id
POST   /doctors/:id/activate  POST /doctors/:id/deactivate  GET /doctors/:id/stats
GET/POST/DELETE /doctors/:id/unavailabilities
GET    /swaps                 POST /swaps/:id/approve       POST /swaps/:id/reject

# Médico (role=medico)
GET    /me/offers             POST /offers/:id/accept       POST /offers/:id/decline
GET    /me/assignments        GET  /me/profile             PATCH /me/profile
POST   /swaps                 POST /swaps/:id/cancel        GET  /me/swaps
GET    /me/assignments/:id/swap-candidates
GET    /me/notifications      POST /me/notifications[/:id]/read
GET/POST/DELETE /me/unavailabilities

# Máquina / admin
POST   /jobs/tick   (Bearer TICK_SECRET)     POST /admin/seed   (Bearer ADMIN_SECRET)
GET    /health
```

---

## Frontend

- **Estados de verdade:** loading com **skeletons**, **empty states** com voz de
  produto, **error boundary** global + estados de erro com retry, **toasts**
  (`sonner`) — inclusive 409 ("acabou de ser preenchido") e 410 ("oferta expirou").
- **Tempo real sem WebSocket:** countdown local 1×/s contra `expires_at` +
  `refetchInterval` do React Query (15–30s). Simples e suficiente pro escopo.
- **Acessibilidade:** alvos ≥44px, foco visível, skip-to-content, glyph por status
  no calendário (não só cor), `aria-live` calibrado no countdown.
- **Responsivo no celular** (auditado a 390px com headless): telas empilham,
  cards não cortam, dropdown de notificações ajustado, tab bar do médico com
  área segura. Override manual do 1º lote (checkbox no ranking) e heurística
  visível ("Como o ranking funciona?").

---

## Testes

**160 testes** (1 skip opt-in de entrega real do Twilio), pytest contra
**Postgres real** (isolamento por transação externa + savepoints; o teste de
concorrência usa conexões reais com `TRUNCATE`). Os **5 obrigatórios** e mais:

| Teste | Cobre |
|---|---|
| `test_concurrent_accept_only_one_wins` | **race condition**: 2 threads, `Barrier`, 1 ganha / 1 → 409 |
| `test_pipeline_advances_to_next_batch_after_window` | tick libera próximo lote (relógio +31min) |
| `test_doctor_only_sees_offers_from_affiliated_hospitals` | **permissão**: oferta de outro hospital filtrada |
| `test_escalation_to_needs_attention` | escala + audit event |
| `test_accept_expired_offer_returns_410_and_marks_expired` | expiração no aceite |
| + extras | swap atômico (concorrência 5×), outbox/dispatch, ranking, indisponibilidades, guards de papel, JWT/hashing… |

```bash
cd backend && uv run pytest          # precisa de um Postgres local (docker compose up -d)
```


---

## Rodar local

Pré-requisitos: Docker (ou Colima), [`uv`](https://docs.astral.sh/uv/), Node 20+.

```bash
# 1. Postgres
docker compose up -d                       # munin-postgres na :5432

# 2. Backend
cd backend
cp .env.example .env                        # config é auto-carregada do .env (pydantic-settings)
uv run alembic upgrade head
FLASK_APP="app:create_app" uv run flask run --port 5000 --host 127.0.0.1

# 3. Seed (popula 2 hospitais, 30 médicos, 10 plantões)
curl -X POST http://127.0.0.1:5000/admin/seed \
     -H "Authorization: Bearer dev-only-change-me-admin"

# 4. Frontend
cd ../frontend && npm install && npm run dev   # http://localhost:3000
```

> **macOS:** use `127.0.0.1` (não `localhost`) para a API — a porta 5000 em
> IPv6/`::1` é do AirPlay Receiver. O `.env.local` do front já aponta pra lá.

WhatsApp real local é opcional: preencha `TWILIO_*` + `MUNIN_DEMO_PHONE` no
`backend/.env` (sem isso → `NullNotifier`).

---

## Deploy

| Camada | Onde | Notas |
|---|---|---|
| **Backend** | Fly.io (`gru`) | `Dockerfile` (uv + gunicorn), `release_command` roda as migrations; 1 máquina `shared-cpu-1x`/256MB com scale-to-zero (~US$2/mês) |
| **Banco** | Supabase (`sa-east-1`) | conexão via **Session pooler** (porta 5432, IPv4) — a conexão direta é IPv6-only no free; `DATABASE_URL` com scheme `postgresql+psycopg://` |
| **Frontend** | Vercel | root `frontend/`, auto-deploy a cada push, `NEXT_PUBLIC_API_URL` → Fly |
| **Cron** | GitHub Actions | `schedule: */5` → `POST /jobs/tick`; mantém Fly+Supabase acordados |

Por que **Fly e não Vercel** no backend: o aceite usa `SELECT … FOR UPDATE` e
transações que abrem e re-checam invariantes — isso é frágil em serverless
(funções stateless, pool em modo transação). Container persistente faz os locks
funcionarem igual ao local e aos testes. Secrets ficam em `fly secrets` /
Vercel / GitHub Actions — **nunca no repo** (`.env` é gitignored).

---

## Decisões e trade-offs

- **Lock `shift → offer`**  — elimina o
  deadlock entre dois aceites; o shift vira o ponto único de serialização.
- **Pessimista > otimista** aqui — contenção rara, lock de milissegundos, mais
  fácil de raciocinar; constraint única como defesa em profundidade.
- **Tick não auto-oferta `open`** — a coordenadora controla quando ofertar.
- **Outbox + dispatch fora da transação** — at-least-once sem dual-write; provedor
  externo nunca dentro de lock. Inline dispatch para latência, cron como fallback.
- **Especialidade como tier** (não filtro) — evita buraco quando faltam especialistas.
- **Indisponibilidade repetida = instâncias reais** — troca elegância de RRULE por
  consultas simples e rápidas.
- **Polling em vez de WebSocket** — simples e suficiente pro escopo.
- **Relógio injetável (`now`)** — testa expiração/escala sem `time.sleep`.
- **shadcn trocado por primitivos próprios** — controle total sobre o design system.

---

## O que ficou de fora / com +1 semana

- **Check-in/check-out com geolocalização** (bônus Tier 2) — modelado mentalmente,
  não implementado.
- **Mini-"Luis" / copiloto LLM** (Tier 3) — o foco foi entregar o obrigatório +
  bônus polidos, conforme o próprio enunciado recomenda.
- **OpenAPI/Swagger UI** — hoje os contratos vivem nos schemas Pydantic.
- **Tempo real por WebSocket/SSE** em vez de polling.
- **E-mail (Resend)** como 2º canal de notificação (o adapter já é plugável).
- **WhatsApp Business sender** para sair do sandbox de 72h.
- **E2E (Playwright) no CI** — hoje a auditoria de responsividade foi feita com
  headless manualmente; valeria fixá-la no pipeline.

---

## Bônus implementados

- ✅ **Tier 1 — Ranking explicável** (4 fatores, breakdown na UI, tier de especialidade)
- ✅ **Tier 1 — Notificação real** (WhatsApp via Twilio, entrega verificada)
- ✅ **Tier 1 — Swap requests** (troca com aprovação da coordenação, atômica)
- ✅ **Tier 2 — Audit log** (toda transição vira evento imutável → timeline)
  
---

## Estrutura do repositório

```
.
├── README.md            # este arquivo
├── CHALLENGE.md          # enunciado original do desafio
├── PLANO.md              # plano técnico detalhado (decisões com racional longo)
├── IMPLEMENTACAO.md      # diário de implementação (o que foi feito, por sessão)
├── docker-compose.yml    # Postgres local
├── docs/screenshots/     # prints usados aqui
├── backend/              # Flask + SQLAlchemy + Alembic (api/services/domain/infra)
│   ├── Dockerfile · fly.toml
│   └── tests/            # 160 testes (pytest)
├── frontend/             # Next.js 16 (App Router) + Tailwind v4
└── .github/workflows/    # test.yml (CI) + tick.yml (cron do pipeline)
```

---

<sub>Feito para o Challenge MuninAI.
