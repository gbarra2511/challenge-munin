"""Ranking inteligente (Bônus Tier 1 — PLANO §13) + filtro de elegibilidade.

O ranking é o caminho DEFAULT de oferta: `open_offers` e `run_tick` chamam
`ranked_doctors`, então a ordem precisa ser correta e determinística.

A heurística tem 4 fatores (aceite, recência, carga, resposta). Aqui validamos
a *direção* de cada fator e o desempate estável — não os scores exatos, que
mudam se a calibração mudar. Testar direção é mais robusto a recalibração.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import DoctorUnavailability, Hospital, ShiftAssignment, ShiftOffer
from app.services.ranking import eligible_doctors, ranked_doctors
from tests.conftest import seed_doctor, seed_shift

SHIFT_START = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)  # terça-feira
SHIFT_END = SHIFT_START + timedelta(hours=12)
NOW = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)


def _shift(session, hospital, **kw):
    return seed_shift(
        session, hospital_id=hospital.id, starts_at=SHIFT_START, ends_at=SHIFT_END, **kw
    )


def _med(session, hospital, name, email, specialties=(1,)):
    return seed_doctor(
        session,
        name=name,
        email=email,
        specialty_ids=list(specialties),
        hospital_ids=[hospital.id],
    )


def _add_offers(session, ref_shift, doctor, *, status, count, start_batch, resp_min=10):
    """Histórico de ofertas. Batches distintos respeitam a unique
    (shift, doctor, batch). `expired` não tem responded_at."""
    sent = NOW - timedelta(days=3)
    responded = None if status == "expired" else sent + timedelta(minutes=resp_min)
    for i in range(count):
        session.add(
            ShiftOffer(
                shift_id=ref_shift.id,
                doctor_id=doctor.id,
                batch_number=start_batch + i,
                status=status,
                sent_at=sent,
                expires_at=sent + timedelta(minutes=30),
                responded_at=responded,
            )
        )
    session.commit()


def _add_weekly_assignments(session, hospital, doctor, count):
    """`count` assignments ativos na semana do plantão-alvo. Cada um num
    plantão próprio — o índice único parcial proíbe 2 ativos no mesmo shift."""
    for _ in range(count):
        sh = _shift(session, hospital, status="accepted")
        session.add(
            ShiftAssignment(
                shift_id=sh.id,
                doctor_id=doctor.id,
                status="active",
                accepted_at=SHIFT_START + timedelta(hours=2),
            )
        )
    session.commit()


# --- filtro de elegibilidade -----------------------------------------------


def test_eligible_doctors_filters_by_specialty_and_hospital(session, hospital) -> None:
    other = Hospital(name="Outro Hospital")
    session.add(other)
    session.commit()

    _med(session, hospital, "Match", "match@t.test", specialties=[1])
    _med(session, hospital, "WrongSpecialty", "ws@t.test", specialties=[2])
    seed_doctor(
        session,
        name="WrongHospital",
        email="wh@t.test",
        specialty_ids=[1],
        hospital_ids=[other.id],
    )

    shift = _shift(session, hospital, specialty_id=1)
    names = {d.name for d in eligible_doctors(session, shift)}
    assert names == {"Match"}


def test_eligible_doctors_excludes_overlapping_unavailability(session, hospital) -> None:
    busy = _med(session, hospital, "Busy", "busy@t.test")
    _med(session, hospital, "Free", "free@t.test")

    # Indisponibilidade do Busy cobre toda a janela do plantão.
    session.add(
        DoctorUnavailability(
            doctor_id=busy.id,
            starts_at=SHIFT_START - timedelta(hours=1),
            ends_at=SHIFT_END + timedelta(hours=1),
            reason="férias",
        )
    )
    session.commit()

    shift = _shift(session, hospital, specialty_id=1)
    names = {d.name for d in eligible_doctors(session, shift)}
    assert "Free" in names
    assert "Busy" not in names


# --- direção dos fatores da heurística --------------------------------------


def test_ranking_prefers_higher_acceptance_rate(session, hospital) -> None:
    shift = _shift(session, hospital, specialty_id=1)
    good = _med(session, hospital, "Good", "good@t.test")
    bad = _med(session, hospital, "Bad", "bad@t.test")

    _add_offers(session, shift, good, status="accepted", count=8, start_batch=1)
    _add_offers(session, shift, good, status="declined", count=2, start_batch=50)
    _add_offers(session, shift, bad, status="accepted", count=1, start_batch=1)
    _add_offers(session, shift, bad, status="declined", count=9, start_batch=50)

    ranked = ranked_doctors(session, shift, now=NOW)
    by_name = {r.doctor.name: r for r in ranked}

    assert ranked[0].doctor.name == "Good"
    assert by_name["Good"].score > by_name["Bad"].score
    assert by_name["Good"].breakdown.acceptance_rate > by_name["Bad"].breakdown.acceptance_rate


def test_ranking_deprioritizes_doctor_loaded_in_target_week(session, hospital) -> None:
    shift = _shift(session, hospital, specialty_id=1)
    busy = _med(session, hospital, "Busy", "busy@t.test")
    _med(session, hospital, "Free", "free@t.test")
    _add_weekly_assignments(session, hospital, busy, 3)

    ranked = ranked_doctors(session, shift, now=NOW)
    by_name = {r.doctor.name: r for r in ranked}

    assert ranked[0].doctor.name == "Free"
    assert by_name["Busy"].breakdown.weekly_load == 3
    assert by_name["Free"].score > by_name["Busy"].score


def test_ranking_tie_break_is_deterministic_by_name(session, hospital) -> None:
    shift = _shift(session, hospital, specialty_id=1)
    _med(session, hospital, "Bruno", "bruno@t.test")
    _med(session, hospital, "Ana", "ana@t.test")

    ranked = ranked_doctors(session, shift, now=NOW)

    assert [r.doctor.name for r in ranked] == ["Ana", "Bruno"]
    assert ranked[0].score == ranked[1].score  # sem histórico → empate → nome


def test_ranking_breakdown_is_explainable(session, hospital) -> None:
    shift = _shift(session, hospital, specialty_id=1)
    doc = _med(session, hospital, "Histórico", "hist@t.test")
    _add_offers(session, shift, doc, status="accepted", count=3, start_batch=1, resp_min=4)
    _add_offers(session, shift, doc, status="declined", count=1, start_batch=50)

    ranked = ranked_doctors(session, shift, now=NOW)
    b = ranked[0].breakdown

    assert b.acceptance_rate is not None
    assert b.avg_response_min is not None  # respondeu em ~4min
    assert 0 <= ranked[0].score <= 100
    for component in (b.score_acceptance, b.score_recency, b.score_load, b.score_response):
        assert 0 <= component <= 100
