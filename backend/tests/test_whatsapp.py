"""Adapter WhatsApp/Twilio: normalização do número, montagem da requisição
(com o `Client` do Twilio mockado — sem rede) e seleção do adapter por
credenciais. Estes testes NÃO tocam o banco nem a rede, então rodam no CI
mesmo sem Postgres.

O teste de integração real (que entrega no sandbox do Twilio) é **opt-in**:
só roda com `RUN_TWILIO_LIVE=1` + credenciais no ambiente. Reproduz a conexão
validada manualmente, mantendo o CI offline e barato.
"""

from __future__ import annotations

import logging
import os

import pytest

from app.infra.notifier import NullNotifier, get_notifier
from app.infra.whatsapp import WhatsAppNotifier, _to_whatsapp_address

# --- duplo de teste do Client do Twilio (sem rede) --------------------------


class _FakeMessage:
    def __init__(self, sid: str) -> None:
        self.sid = sid


class _FakeMessages:
    def __init__(self, recorder: list[dict]) -> None:
        self._rec = recorder

    def create(self, **kwargs):  # espelha twilio Client.messages.create
        self._rec.append(kwargs)
        return _FakeMessage("SM_fake_123")


class _FakeClient:
    last_init: tuple[str, str] | None = None

    def __init__(self, account_sid: str, auth_token: str) -> None:
        type(self).last_init = (account_sid, auth_token)
        self.sent: list[dict] = []
        self.messages = _FakeMessages(self.sent)


@pytest.fixture()
def fake_twilio(monkeypatch):
    """Substitui `twilio.rest.Client` (import preguiçoso do adapter) por um
    fake que registra a chamada e nunca toca a rede."""
    import twilio.rest

    monkeypatch.setattr(twilio.rest, "Client", _FakeClient)
    return _FakeClient


# --- normalização do número (E.164 → endereço whatsapp:) --------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+55 11 90000-0000", "whatsapp:+5511900000000"),
        ("+55 (32) 9987-2511", "whatsapp:+553299872511"),
        ("5511999999999", "whatsapp:+5511999999999"),  # adiciona o '+' ausente
        ("+5511999999999", "whatsapp:+5511999999999"),
        ("  +55 11 9 9999-9999  ", "whatsapp:+5511999999999"),  # espaços/traços
    ],
)
def test_to_whatsapp_address_normalizes(raw: str, expected: str) -> None:
    assert _to_whatsapp_address(raw) == expected


# --- montagem da requisição (Client mockado) --------------------------------


def test_send_builds_twilio_request_and_returns_sid(fake_twilio) -> None:
    notifier = WhatsAppNotifier(
        account_sid="AC_test",
        auth_token="tok_test",
        from_whatsapp="whatsapp:+14155238886",
    )
    sid = notifier.send("+55 11 90000-0000", "Plantão disponível: Clínica, sáb 19h")

    assert sid == "SM_fake_123"
    assert fake_twilio.last_init == ("AC_test", "tok_test")  # creds repassadas ao Client
    # exatamente 1 mensagem, com from/to/body corretos e número normalizado
    assert notifier._client.sent == [
        {
            "from_": "whatsapp:+14155238886",
            "to": "whatsapp:+5511900000000",
            "body": "Plantão disponível: Clínica, sáb 19h",
        }
    ]


# --- seleção do adapter por credenciais (get_notifier) ----------------------


def test_get_notifier_returns_whatsapp_when_creds_present(fake_twilio) -> None:
    notifier = get_notifier(
        {
            "TWILIO_ACCOUNT_SID": "AC",
            "TWILIO_AUTH_TOKEN": "tok",
            "TWILIO_WHATSAPP_FROM": "whatsapp:+1",
        }
    )
    assert isinstance(notifier, WhatsAppNotifier)


def test_get_notifier_falls_back_to_null_without_creds() -> None:
    assert isinstance(get_notifier({}), NullNotifier)


def test_get_notifier_falls_back_to_null_with_partial_creds() -> None:
    # só o SID, sem token → NullNotifier (não tenta instanciar o Twilio)
    assert isinstance(get_notifier({"TWILIO_ACCOUNT_SID": "AC"}), NullNotifier)


def test_null_notifier_returns_id_and_does_not_log_phone(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="munin.notify"):
        sid = NullNotifier().send("+55 11 98888-7777", "corpo da mensagem")
    assert sid.startswith("null-")
    assert "98888" not in caplog.text  # número (PII) nunca é logado


# --- integração real com o Twilio (opt-in) ----------------------------------


@pytest.mark.skipif(
    os.environ.get("RUN_TWILIO_LIVE") != "1",
    reason="integração real: defina RUN_TWILIO_LIVE=1 e as credenciais TWILIO_* + MUNIN_DEMO_PHONE",
)
def test_live_whatsapp_delivers_to_demo_phone() -> None:
    """Reproduz a conexão validada manualmente: envia uma mensagem real pelo
    sandbox e confirma que o Twilio a aceitou (SID) e não falhou na entrega.

    Custa 1 mensagem. O destinatário (`MUNIN_DEMO_PHONE`) precisa de opt-in no
    sandbox. Lembrete BR: o WhatsApp identifica o celular SEM o nono dígito.
    """
    import time

    from twilio.rest import Client

    from app.infra.config import get_settings

    s = get_settings()
    assert s.twilio_account_sid and s.twilio_auth_token and s.twilio_whatsapp_from
    assert s.munin_demo_phone, "defina MUNIN_DEMO_PHONE"

    notifier = WhatsAppNotifier(
        account_sid=s.twilio_account_sid,
        auth_token=s.twilio_auth_token,
        from_whatsapp=s.twilio_whatsapp_from,
    )
    sid = notifier.send(s.munin_demo_phone, "🩺 Munin: teste automatizado (pytest live).")
    assert sid and sid.startswith(("SM", "MM"))

    # Twilio aceita (SID) mesmo sem entregar; confirma o status final de verdade.
    client = Client(s.twilio_account_sid, s.twilio_auth_token)
    status = None
    for _ in range(8):
        status = client.messages(sid).fetch().status
        if status in ("delivered", "read", "failed", "undelivered"):
            break
        time.sleep(2)
    assert status in ("sent", "delivered", "read"), f"entrega falhou (status={status})"
