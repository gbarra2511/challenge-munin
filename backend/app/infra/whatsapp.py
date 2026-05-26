"""Adapter de WhatsApp via Twilio (saída apenas).

Escolhido por `infra/notifier.get_notifier` quando há credenciais. O SDK `twilio`
é importado de forma preguiçosa (só quando o adapter é instanciado), então
dev/test sem WhatsApp não precisam da dependência nem tocam a rede.

Segurança: o auth token vem do env e NUNCA é logado; o número (PII) é resolvido
só no envio (ver `services/notifications._resolve_phone`).

Modo sandbox: cada destinatário precisa fazer opt-in uma vez enviando
"join <palavra>" para o número do sandbox. Documentado no README/IMPLEMENTACAO.
"""

from __future__ import annotations

import re


def _to_whatsapp_address(phone: str) -> str:
    """Normaliza '+55 11 90000-0000' → 'whatsapp:+5511900000000'."""
    digits = re.sub(r"[^\d+]", "", phone)
    if not digits.startswith("+"):
        digits = "+" + digits
    return f"whatsapp:{digits}"


class WhatsAppNotifier:
    def __init__(self, *, account_sid: str, auth_token: str, from_whatsapp: str) -> None:
        from twilio.rest import Client  # import preguiçoso

        self._client = Client(account_sid, auth_token)
        self._from = from_whatsapp

    def send(self, to_phone: str, text: str) -> str:
        message = self._client.messages.create(
            from_=self._from,
            to=_to_whatsapp_address(to_phone),
            body=text,
        )
        return message.sid
