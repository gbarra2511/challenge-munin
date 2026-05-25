"""Seed determinístico para demo/avaliação (README §Seed).

Idempotente: TRUNCATE das tabelas de domínio (preserva `specialties`, que vêm
da migration) + recriação. Roda quantas vezes quiser → mesmo estado limpo.

Usa os serviços reais (`create_shift` → `open_offers` → `accept_offer`) para
que os shifts ofertados/aceitos gerem **audit events de verdade** — a timeline
do detalhe do plantão fica populada.

Credenciais (documentadas no README do projeto):
    coordenadora@hospital.com / 123456
    medico@hospital.com       / 123456
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select, text

from app.infra.hashing import hash_password
from app.models import (
    Account,
    Doctor,
    DoctorHospitalAffiliation,
    DoctorSpecialty,
    DoctorUnavailability,
    Hospital,
    Shift,
    ShiftOffer,
)
from app.services.audit import record_event
from app.services.offers import accept_offer, open_offers
from app.services.shifts import create_shift

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

DEMO_PASSWORD = "123456"

_FIRST = [
    "Ana",
    "Bruno",
    "Carla",
    "Diego",
    "Elena",
    "Felipe",
    "Gabriela",
    "Henrique",
    "Isabela",
    "João",
    "Karina",
    "Lucas",
    "Marina",
    "Nuno",
    "Olívia",
    "Paulo",
    "Quésia",
    "Rafael",
    "Sofia",
    "Tiago",
    "Ursula",
    "Vitor",
    "Wagner",
    "Xênia",
    "Yara",
    "Zeca",
    "Beatriz",
    "Caio",
    "Daniela",
]
_LAST = [
    "Costa",
    "Almeida",
    "Pereira",
    "Souza",
    "Lima",
    "Carvalho",
    "Ribeiro",
    "Gomes",
    "Martins",
    "Rocha",
    "Barbosa",
    "Araújo",
    "Nunes",
    "Teixeira",
    "Cardoso",
    "Correia",
    "Dias",
    "Castro",
    "Campos",
    "Moreira",
]

# Tabela de truncamento: tudo de domínio, exceto `specialties` (vem da migration).
_TRUNCATE = (
    "TRUNCATE audit_events, swap_requests, shift_assignments, shift_offers, "
    "shifts, doctor_unavailabilities, doctor_hospital_affiliations, "
    "doctor_specialties, doctors, accounts, hospitals RESTART IDENTITY CASCADE"
)


def _shift_at(now: datetime, *, days: float, hour: int, dur_h: int = 12):
    """Início ancorado em `now + days`, na hora local pedida; fim = +dur_h."""
    start = (now + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)
    return start, start + timedelta(hours=dur_h)


def run_seed(session: Session, *, defaults: dict[str, int]) -> dict:
    session.execute(text(_TRUNCATE))
    session.commit()

    now = datetime.now(UTC)

    # Inserção em estágios (hospitais → contas → médicos → vínculos) com flush
    # entre cada um, garantindo a ordem das FKs.
    hosp_a = Hospital(id=uuid.uuid4(), name="Hospital São Lucas")
    hosp_b = Hospital(id=uuid.uuid4(), name="Hospital Santa Marta")
    session.add_all([hosp_a, hosp_b])
    session.flush()

    accounts: list[Account] = []
    doctors: list[Doctor] = []
    links: list = []  # specialties + affiliations + unavailabilities

    # Coordenadora (hospital A)
    accounts.append(
        Account(
            id=uuid.uuid4(),
            email="coordenadora@hospital.com",
            password_hash=hash_password(DEMO_PASSWORD),
            role="coordenador",
            hospital_id=hosp_a.id,
        )
    )

    # Médico demo: especialidades 1 (Clínica) e 8 (PS), afiliado ao A
    demo_acc_id = uuid.uuid4()
    demo_doc_id = uuid.uuid4()
    accounts.append(
        Account(
            id=demo_acc_id,
            email="medico@hospital.com",
            password_hash=hash_password(DEMO_PASSWORD),
            role="medico",
            hospital_id=None,
        )
    )
    doctors.append(
        Doctor(
            id=demo_doc_id,
            account_id=demo_acc_id,
            name="Dra. Ana Beatriz Costa",
            phone="+55 11 90000-0000",
        )
    )
    links += [
        DoctorSpecialty(doctor_id=demo_doc_id, specialty_id=1),
        DoctorSpecialty(doctor_id=demo_doc_id, specialty_id=8),
        DoctorHospitalAffiliation(doctor_id=demo_doc_id, hospital_id=hosp_a.id, status="active"),
    ]

    # 29 médicos gerados; coleta pools (afiliados ao A) por especialidade.
    pool_a: dict[int, list[uuid.UUID]] = {s: [] for s in range(1, 9)}
    for i in range(1, 30):
        acc_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        first = _FIRST[i % len(_FIRST)]
        last = _LAST[i % len(_LAST)]
        accounts.append(
            Account(
                id=acc_id,
                email=f"medico{i}@hospital.com",
                password_hash=hash_password(DEMO_PASSWORD),
                role="medico",
                hospital_id=None,
            )
        )
        doctors.append(
            Doctor(
                id=doc_id,
                account_id=acc_id,
                name=f"Dr(a). {first} {last}",
                phone=f"+55 11 9{i:04d}-0000",
            )
        )

        primary = (i % 8) + 1
        specs = {primary}
        if i % 2 == 0:
            specs.add(((i + 3) % 8) + 1)
        for s in specs:
            links.append(DoctorSpecialty(doctor_id=doc_id, specialty_id=s))

        to_a = i % 4 != 0
        to_b = i % 5 == 0
        if not to_a and not to_b:
            to_a = True
        if to_a:
            links.append(
                DoctorHospitalAffiliation(doctor_id=doc_id, hospital_id=hosp_a.id, status="active")
            )
            for s in specs:
                pool_a[s].append(doc_id)
        if to_b:
            links.append(
                DoctorHospitalAffiliation(doctor_id=doc_id, hospital_id=hosp_b.id, status="active")
            )

        if i % 7 == 0:
            us, ue = _shift_at(now, days=2, hour=8, dur_h=24)
            links.append(
                DoctorUnavailability(
                    id=uuid.uuid4(), doctor_id=doc_id, starts_at=us, ends_at=ue, reason="Folga"
                )
            )

    session.add_all(accounts)
    session.flush()
    session.add_all(doctors)
    session.flush()
    session.add_all(links)
    session.commit()

    d = defaults

    def mk(
        specialty: int, *, days: float, hour: int, rate: int, window: int | None = None
    ) -> Shift:
        s, e = _shift_at(now, days=days, hour=hour)
        return create_shift(
            session,
            hospital_id=hosp_a.id,
            specialty_id=specialty,
            starts_at=s,
            ends_at=e,
            rate_cents=rate,
            batch_size=None,
            batch_window_minutes=window,
            escalate_hours_before=None,
            defaults=d,
        )

    # --- Plantões ABERTOS espalhados na semana (calendário/lista) ----------
    mk(2, days=2, hour=19, rate=150000)
    mk(5, days=3, hour=7, rate=180000)
    mk(4, days=4, hour=19, rate=165000)
    mk(6, days=6, hour=7, rate=210000)
    mk(7, days=5, hour=19, rate=175000)
    # Abertos começando logo (<12h) → aparecem na tabela de risco do dashboard.
    mk(2, days=0, hour=(now.hour + 8) % 24, rate=160000)

    # --- OFERTANDO p/ o médico demo (countdown ao vivo em /ofertas) --------
    off1 = mk(1, days=2, hour=7, rate=190000)
    open_offers(session, off1, doctor_ids=[demo_doc_id, *pool_a[1][:2]])

    off2 = mk(8, days=1, hour=19, rate=205000, window=45)
    open_offers(session, off2, doctor_ids=[demo_doc_id, *pool_a[8][:2]])

    # --- ACEITO pelo demo (aparece em /agenda + timeline rica) -------------
    acc_shift = mk(8, days=3, hour=19, rate=220000)
    open_offers(session, acc_shift, doctor_ids=[demo_doc_id, *pool_a[8][2:4]])
    demo_offer_id = session.scalar(
        select(ShiftOffer.id)
        .where(ShiftOffer.shift_id == acc_shift.id)
        .where(ShiftOffer.doctor_id == demo_doc_id)
        .where(ShiftOffer.status == "pending")
    )
    if demo_offer_id is not None:
        accept_offer(session, offer_id=demo_offer_id, doctor_id=demo_doc_id)

    # --- EM RISCO / escalado (dashboard + pill needs_attention) ------------
    risk = mk(3, days=0, hour=(now.hour + 4) % 24, rate=240000)
    risk.status = "needs_attention"
    risk.current_batch = 1
    risk.version += 1
    record_event(
        session,
        event_type="shift.escalated",
        shift_id=risk.id,
        hospital_id=hosp_a.id,
        actor_type="system",
        payload={"reason": "no_eligible_or_too_close"},
    )
    session.commit()

    counts = {
        "hospitals": 2,
        "coordinators": 1,
        "doctors": 30,
        "shifts": session.scalar(select(func.count(Shift.id))),
        "pending_offers_demo": session.scalar(
            select(func.count(ShiftOffer.id))
            .where(ShiftOffer.doctor_id == demo_doc_id)
            .where(ShiftOffer.status == "pending")
        ),
    }
    return {
        "status": "seeded",
        "counts": counts,
        "credentials": {
            "coordenadora": "coordenadora@hospital.com / 123456",
            "medico": "medico@hospital.com / 123456",
        },
    }
