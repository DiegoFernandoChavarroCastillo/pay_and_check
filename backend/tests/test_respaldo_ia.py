"""Proveedor de respaldo: si Groq falla, el mismo modelo en otro proveedor compatible con OpenAI responde."""

import pytest

from app.core.config import settings
from app.services import groq_client


class _Caido:
    class chat:  # noqa: N801 - imita la forma del SDK
        class completions:  # noqa: N801
            @staticmethod
            def create(**_kw):
                raise RuntimeError("Groq caído")


class _Respuesta:
    def __init__(self, contenido):
        self._contenido = contenido

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._contenido}}],
                "usage": {"prompt_tokens": 500, "completion_tokens": 90}}


@pytest.fixture()
def groq_caido(monkeypatch):
    monkeypatch.setattr(groq_client, "_get_client", lambda: _Caido())


def test_sin_respaldo_configurado_el_error_sigue(groq_caido, monkeypatch):
    monkeypatch.setattr(settings, "AI_FALLBACK_URL", "")
    with pytest.raises(groq_client.GroqServiceError):
        groq_client._chat([{"role": "user", "content": "hola"}])


def test_con_respaldo_responde_el_otro_proveedor(groq_caido, monkeypatch):
    llamadas = []
    monkeypatch.setattr(settings, "AI_FALLBACK_URL", "https://respaldo.example/v1/openai/")
    monkeypatch.setattr(settings, "AI_FALLBACK_API_KEY", "clave")

    def _post(url, **kw):
        llamadas.append((url, kw["json"]["model"], kw["headers"]["Authorization"]))
        return _Respuesta("respuesta del respaldo")

    monkeypatch.setattr(groq_client.httpx, "post", _post)
    assert groq_client._chat([{"role": "user", "content": "hola"}]) == "respuesta del respaldo"
    assert llamadas == [("https://respaldo.example/v1/openai/chat/completions", "openai/gpt-oss-20b", "Bearer clave")]


def test_si_el_respaldo_tambien_falla_es_un_error_de_ia(groq_caido, monkeypatch):
    monkeypatch.setattr(settings, "AI_FALLBACK_URL", "https://respaldo.example/v1/openai")
    monkeypatch.setattr(settings, "AI_FALLBACK_API_KEY", "clave")

    def _post(*_a, **_kw):
        raise RuntimeError("también caído")

    monkeypatch.setattr(groq_client.httpx, "post", _post)
    with pytest.raises(groq_client.GroqServiceError):
        groq_client._chat([{"role": "user", "content": "hola"}])
