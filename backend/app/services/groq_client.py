"""Wrapper delgado sobre el SDK `groq`. La lógica de negocio (validar el JSON,
mapear categorías, etc.) vive en los routers/servicios que llaman a este
módulo — aquí solo se habla con la API de Groq."""

import json
from datetime import date
from decimal import Decimal, InvalidOperation

from groq import Groq

from app.core.config import settings
from app.services.prompts import (
    build_expense_parse_prompt,
    build_receipt_parse_prompt,
    build_weekly_report_prompt,
)

# El plan original fijaba "llama-3.1-8b-instant", pero Groq lo descontinuó
# (404 model_not_found al probarlo en sep/2026). De los modelos de propósito
# general disponibles hoy en la cuenta, "openai/gpt-oss-20b" es el más chico
# y barato, y respondió bien al prompt de extracción en español al probarlo
# a mano. Si se prefiere otro modelo, cambiar solo esta constante.
MODEL = "openai/gpt-oss-20b"
# Modelo del coach (mensajes, consejos, chat). Separado del de extracción para
# poder subirlo a uno más capaz (ej. "openai/gpt-oss-120b") sin encarecer el parseo.
COACH_MODEL = MODEL

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


class GroqServiceError(Exception):
    """Error genérico llamando a Groq (red, API caída, etc.)."""


class ExpenseParseError(GroqServiceError):
    """El modelo no devolvió un JSON válido o no pudo extraer un monto."""


def _chat(messages: list[dict], *, model: str = MODEL, temperature: float = 0, json_mode: bool = False) -> str:
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    try:
        completion = _get_client().chat.completions.create(
            model=model, messages=messages, temperature=temperature, **kwargs
        )
        return completion.choices[0].message.content
    except Exception as exc:  # errores de red / API de Groq
        raise GroqServiceError(f"Error llamando a Groq: {exc}") from exc


def _validar_gasto(raw: str, categorias: list[str]) -> dict:
    """Valida el JSON de un gasto devuelto por el modelo. Nunca inventa datos:
    si falta algo o no es interpretable, lanza ExpenseParseError."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ExpenseParseError("El modelo no devolvió un JSON válido.") from exc

    if not isinstance(data, dict):
        raise ExpenseParseError("El modelo no devolvió un objeto JSON.")

    if "error" in data:
        raise ExpenseParseError("No se pudo identificar un monto en el texto.")

    faltantes = {"monto", "categoria", "descripcion", "fecha"} - data.keys()
    if faltantes:
        raise ExpenseParseError(f"La respuesta del modelo no incluye: {', '.join(sorted(faltantes))}.")

    try:
        monto = Decimal(str(data["monto"]))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ExpenseParseError("No se pudo interpretar el monto como número.") from exc
    if monto <= 0:
        raise ExpenseParseError("El monto debe ser mayor que cero.")

    if data["categoria"] not in categorias:
        raise ExpenseParseError(f"El modelo devolvió una categoría inválida: {data['categoria']!r}.")

    try:
        fecha = date.fromisoformat(str(data["fecha"]))
    except ValueError as exc:
        raise ExpenseParseError("La fecha devuelta por el modelo no es válida.") from exc

    comercio = data.get("comercio")
    return {
        "monto": monto,
        "categoria": data["categoria"],
        "descripcion": str(data["descripcion"]),
        "fecha": fecha,
        "comercio": str(comercio).strip() if comercio else None,
    }


def parse_expense_text(texto: str, categorias: list[str], hoy: date | None = None) -> dict:
    """Extrae {monto, categoria, descripcion, fecha} de un texto libre.

    Lanza ExpenseParseError con un mensaje claro si el modelo no devuelve un
    JSON usable o no logra identificar un monto — nunca inventa un monto.
    """
    hoy = hoy or date.today()
    raw = _chat(
        [
            {"role": "system", "content": build_expense_parse_prompt(categorias, hoy.isoformat())},
            {"role": "user", "content": texto},
        ],
        json_mode=True,
    )
    data = _validar_gasto(raw, categorias)
    data.pop("comercio")
    return data


def parse_receipt_text(texto_ocr: str, categorias: list[str], hoy: date | None = None) -> dict:
    """Extrae {monto, categoria, descripcion, fecha, comercio} del texto que el
    OCR del teléfono reconoció en un recibo. Mismas garantías que
    `parse_expense_text`."""
    hoy = hoy or date.today()
    raw = _chat(
        [
            {"role": "system", "content": build_receipt_parse_prompt(categorias, hoy.isoformat())},
            {"role": "user", "content": texto_ocr},
        ],
        json_mode=True,
    )
    return _validar_gasto(raw, categorias)


def generate_weekly_recommendations(resumen: str) -> str:
    """Devuelve 2-3 recomendaciones en texto natural a partir de un resumen agregado."""
    return _chat([{"role": "system", "content": build_weekly_report_prompt(resumen)}], temperature=0.4).strip()


def generate_coach_text(system_prompt: str, messages: list[dict] | None = None) -> str:
    """Respuesta en texto del coach. `messages` son los turnos previos del chat."""
    return _chat(
        [{"role": "system", "content": system_prompt}, *(messages or [])],
        model=COACH_MODEL,
        temperature=0.6,
    ).strip()


def generate_coach_json(system_prompt: str, contenido: str) -> dict:
    """Respuesta del coach como objeto JSON. Lanza GroqServiceError si no lo es."""
    raw = _chat(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": contenido}],
        model=COACH_MODEL,
        temperature=0.5,
        json_mode=True,
    )
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise GroqServiceError("El coach no devolvió un JSON válido.") from exc
    if not isinstance(data, dict):
        raise GroqServiceError("El coach no devolvió un objeto JSON.")
    return data
