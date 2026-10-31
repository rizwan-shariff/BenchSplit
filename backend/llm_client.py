import json
import logging
import re
from typing import Any

import httpx
from pydantic import ValidationError

from backend.config import (
    GEMINI_API_KEY,
    GROQ_API_KEY,
    GROQ_MODEL,
    LLM_TIMEOUT_SECONDS,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)
from backend.models import LLMEntailmentOutput, LLMExtractionOutput

LOGGER = logging.getLogger(__name__)


def active_provider() -> str:
    if LLM_PROVIDER == "groq" and GROQ_API_KEY:
        return "groq"
    if LLM_PROVIDER == "gemini" and GEMINI_API_KEY:
        return "gemini"
    if LLM_PROVIDER == "ollama":
        return "ollama"
    return "rule-based"


def _extract_json(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise ValueError("LLM response did not contain a JSON object")
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be a JSON object")
    return parsed


def _request_ollama(prompt: str, temperature: float = 0.0) -> str:
    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature},
        },
        timeout=LLM_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return str(response.json()["response"])


def _request_groq(prompt: str, temperature: float = 0.0) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")
    response = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": "Bearer " + GROQ_API_KEY},
        json={
            "model": GROQ_MODEL,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": "Return only a JSON object that satisfies the requested schema."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        },
        timeout=LLM_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return str(response.json()["choices"][0]["message"]["content"])


def _request_gemini(prompt: str, temperature: float = 0.0) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    response = httpx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
        params={"key": GEMINI_API_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
        },
        timeout=LLM_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return str(response.json()["candidates"][0]["content"]["parts"][0]["text"])


def request_json(prompt: str, fallback: dict[str, Any], temperature: float = 0.0) -> tuple[dict[str, Any], str]:
    provider = active_provider()
    try:
        if provider == "ollama":
            content = _request_ollama(prompt, temperature)
        elif provider == "groq":
            content = _request_groq(prompt, temperature)
        elif provider == "gemini":
            content = _request_gemini(prompt, temperature)
        else:
            return fallback, "rule-based"
        return _extract_json(content), provider
    except (httpx.HTTPError, KeyError, ValueError, RuntimeError) as error:
        LOGGER.warning("%s inference unavailable; using deterministic rule-based result: %s", provider, error)
        return fallback, "rule-based"


def deterministic_extraction(passage_text: str, statute_key: str, feedback: str = "") -> dict[str, str]:
    sentence_match = re.search(r"[^.!?]+[.!?](?:[\"'])?", passage_text, re.DOTALL)
    sentence = sentence_match.group(0).strip() if sentence_match else passage_text.strip()
    if not sentence:
        sentence = "The court considered the statutory question on the record before it."
    if statute_key == "NI_ACT_S138":
        question = (
            "Whether interim compensation under Section 143A of the Negotiable Instruments Act is "
            "mandatory or discretionary at the stage of framing notice."
            if re.search(r"143A|interim compensation", passage_text, re.IGNORECASE)
            else "Whether a Section 138 complaint is maintainable for dishonour of a cheque issued towards "
            "a time-barred debt without a fresh written promise under Section 25(3) of the Contract Act."
        )
    elif statute_key == "ARB_ACT_S11":
        question = (
            "Whether limitation for a Section 11(6) petition commences automatically upon expiry of "
            "30 days from notice invoking arbitration."
        )
    else:
        question = (
            "Whether a High Court may quash a non-compoundable offence involving serious economic or "
            "financial fraud solely on a post-FIR private settlement."
        )
    return {
        "statute_key": statute_key,
        "question": question,
        "holding": sentence,
        "quote": sentence,
    }


def extract_proposition(passage_text: str, statute_key: str, feedback: str = "") -> tuple[dict[str, str], str]:
    fallback = deterministic_extraction(passage_text, statute_key, feedback)
    prompt = (
        "Extract one legal proposition from this court passage. Return JSON with keys "
        "statute_key, question, holding, quote. The quote must be a contiguous verbatim excerpt. "
        f"Repair feedback: {feedback or 'none'}\nPassage:\n{passage_text}"
    )
    result, provider = request_json(prompt, fallback)
    try:
        extraction = LLMExtractionOutput.model_validate(result)
    except ValidationError as error:
        LOGGER.warning("Invalid structured extraction; using deterministic result: %s", error)
        extraction = LLMExtractionOutput.model_validate(fallback)
        provider = "rule-based"
    return extraction.model_dump(), provider


def entailment_supported(quote: str, holding: str) -> tuple[bool, str]:
    quote_tokens = {token.lower() for token in re.findall(r"\w+", quote)}
    holding_tokens = {token.lower() for token in re.findall(r"\w+", holding)}
    overlap = len(quote_tokens & holding_tokens) / max(1, len(holding_tokens))
    return overlap >= 0.25, "Deterministic lexical support check."


def check_entailment(quote: str, holding: str) -> tuple[bool, str, str]:
    deterministic_support, deterministic_rationale = entailment_supported(quote, holding)
    result, provider = request_json(
        "Decide whether the exact evidence quote directly supports the stated legal holding. "
        "Return JSON with boolean supports and a concise rationale. Be conservative.\n"
        f"Quote: {quote}\nHolding: {holding}",
        {"supports": deterministic_support, "rationale": deterministic_rationale},
    )
    try:
        entailment = LLMEntailmentOutput.model_validate(result)
    except ValidationError as error:
        LOGGER.warning("Invalid structured entailment; using deterministic result: %s", error)
        entailment = LLMEntailmentOutput.model_validate({
            "supports": deterministic_support,
            "rationale": deterministic_rationale,
        })
        provider = "rule-based"
    return entailment.supports, entailment.rationale, provider
