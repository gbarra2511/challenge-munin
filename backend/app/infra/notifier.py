"""Porta de notificação externa (adapter pattern).

`Notifier` é a interface que o dispatch usa para entregar; `NullNotifier` é o
default seguro (loga e devolve um id fake) — usado em dev/test, onde nunca
tocamos a rede. O adapter real de WhatsApp (Twilio) vive em `infra/whatsapp.py`
e é escolhido por `get_notifier` quando há credenciais (Fase 3).
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger("munin.notify")


class Notifier(Protocol):
    def send(self, to_phone: str, text: str) -> str:
        """Entrega `text` para `to_phone`; devolve o id da mensagem no provedor."""
        ...


class NullNotifier:
    """Não envia nada — só loga. Mantém o sistema 100% demoável/testável sem
    credenciais externas. O número NÃO é logado (PII)."""

    def send(self, to_phone: str, text: str) -> str:
        logger.info("notify.null: would send %d chars to a recipient", len(text))
        return f"null-{uuid.uuid4()}"


def get_notifier(config: Mapping[str, object]) -> Notifier:
    """Escolhe o adapter pelas credenciais em `config`. Sem credenciais de
    WhatsApp → NullNotifier. A Fase 3 liga o `WhatsAppNotifier` aqui."""
    if config.get("TWILIO_ACCOUNT_SID") and config.get("TWILIO_AUTH_TOKEN"):
        from app.infra.whatsapp import WhatsAppNotifier

        return WhatsAppNotifier(
            account_sid=str(config["TWILIO_ACCOUNT_SID"]),
            auth_token=str(config["TWILIO_AUTH_TOKEN"]),
            from_whatsapp=str(config["TWILIO_WHATSAPP_FROM"]),
        )
    return NullNotifier()
