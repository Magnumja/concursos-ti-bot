"""Cliente mínimo da Bot API do Telegram (HTTP puro, sem dependência extra)."""
from __future__ import annotations

import time

import requests


class TelegramErro(Exception):
    def __init__(self, codigo: int, descricao: str):
        super().__init__(f"Telegram {codigo}: {descricao}")
        self.codigo = codigo


class Telegram:
    def __init__(self, token: str, base: str = "https://api.telegram.org"):
        self._url = f"{base.rstrip('/')}/bot{token}/"
        self.sessao = requests.Session()

    def chamar(self, metodo: str, _timeout: float = 30, **params):
        for _ in range(3):
            try:
                r = self.sessao.post(self._url + metodo, json=params, timeout=_timeout)
                d = r.json()
            except (requests.RequestException, ValueError) as e:
                # Nunca repassa a exceção original: a URL dela contém o token.
                raise TelegramErro(0, f"falha de rede ({type(e).__name__})") from None
            if d.get("ok"):
                return d["result"]
            if d.get("error_code") == 429:  # limite de envio: espera o que o Telegram pedir
                time.sleep(d.get("parameters", {}).get("retry_after", 3) + 1)
                continue
            raise TelegramErro(d.get("error_code", r.status_code), d.get("description", ""))
        raise TelegramErro(429, "limite de envio persistente")

    def enviar(self, chat_id: int | str, texto: str, teclado: dict | None = None):
        params = {
            "chat_id": chat_id,
            "text": texto,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if teclado:
            params["reply_markup"] = teclado
        return self.chamar("sendMessage", **params)

    def atualizacoes(self, offset: int, espera: int = 30) -> list[dict]:
        return self.chamar(
            "getUpdates", _timeout=espera + 10, offset=offset, timeout=espera,
            allowed_updates=["message", "channel_post"],
        )
