"""Core LLM enrichment logic for extracting model names from code snippets."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ai_bom.detectors.model_registry import lookup_model
from ai_bom.enrichment.prompts import (
    BATCH_ENTRY_TEMPLATE,
    BATCH_USER_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)
from ai_bom.models import AIComponent, ComponentType

logger = logging.getLogger(__name__)

ENRICHABLE_TYPES = {ComponentType.llm_provider, ComponentType.model}
CONTEXT_LINES = 10  # lines above and below the detection site


def _read_context(file_path: str, line_number: int | None, scan_path: Path) -> str:
    """Read ~20 lines of context around a detection site.

    Tries resolving the file relative to the scan path first, then as an
    absolute path.  Returns empty string if the file cannot be read.
    """
    if not file_path or file_path == "dependency files":
        return ""

    candidates = [scan_path / file_path, Path(file_path)]
    for path in candidates:
        try:
            if not path.is_file():
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line_number and line_number > 0:
                start = max(0, line_number - 1 - CONTEXT_LINES)
                end = min(len(lines), line_number + CONTEXT_LINES)
                return "\n".join(lines[start:end])
            return "\n".join(lines[: CONTEXT_LINES * 2])
        except OSError:
            continue
    return ""


def _get_snippet(component: AIComponent, scan_path: Path) -> str:
    """Get a code snippet for a component, reading from source if needed."""
    snippet = _read_context(
        component.location.file_path,
        component.location.line_number,
        scan_path,
    )
    if not snippet:
        snippet = component.location.context_snippet
    return snippet.strip()


def _call_llm(
    messages: list[dict[str, str]],
    model: str,
    api_key: str | None,
    base_url: str | None,
) -> str:
    """Call litellm.completion and return the response text."""
    import litellm

    kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.0}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["api_base"] = base_url

    response = litellm.completion(**kwargs)
    return response.choices[0].message.content or ""


def _parse_single_result(raw: str) -> dict[str, str]:
    """Parse a JSON object from LLM output, tolerating markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return {
                "model_name": str(result.get("model_name", "")),
                "provider": str(result.get("provider", "")),
            }
    except (json.JSONDecodeError, ValueError):
        pass
    return {"model_name": "", "provider": ""}


def _parse_batch_result(raw: str, expected_count: int) -> list[dict[str, str]]:
    """Parse a JSON array of results from a batched LLM response."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        results = json.loads(text)
        if isinstance(results, list):
            parsed = []
            for item in results:
                if isinstance(item, dict):
                    parsed.append(
                        {
                            "model_name": str(item.get("model_name", "")),
                            "provider": str(item.get("provider", "")),
                        }
                    )
                else:
                    parsed.append({"model_name": "", "provider": ""})
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    return [{"model_name": "", "provider": ""}] * expected_count


def _apply_result(component: AIComponent, result: dict[str, str]) -> None:
    """Apply an LLM extraction result to a component, cross-referencing the model registry."""
    model_name = result.get("model_name", "").strip()
    if not model_name:
        return

    component.model_name = model_name

    registry_info = lookup_model(model_name)
    if registry_info:
        provider = str(registry_info.get("provider", ""))
        if provider and not component.provider:
            component.provider = provider
        if registry_info.get("deprecated") and "deprecated_model" not in component.flags:
            component.flags.append("deprecated_model")
    elif result.get("provider", "").strip() and not component.provider:
        component.provider = result["provider"].strip()

    if "llm_enriched" not in component.flags:
        component.flags.append("llm_enriched")


def enrich_components(
    components: list[AIComponent],
    scan_path: Path,
    *,
    model: str = "gpt-4o-mini",
    api_key: str | None = None,
    base_url: str | None = None,
    batch_size: int = 5,
    quiet: bool = False,
) -> int:
    """Enrich components by extracting model names via LLM.

    Only components with type ``llm_provider`` or ``model`` and an empty
    ``model_name`` are eligible.  Source files are read for extra context
    around the detection site.

    Returns the number of components that were enriched.
    """
    eligible = [c for c in components if c.type in ENRICHABLE_TYPES and not c.model_name]

    if not eligible:
        return 0

    snippets: list[tuple[AIComponent, str]] = []
    for comp in eligible:
        snippet = _get_snippet(comp, scan_path)
        if snippet:
            snippets.append((comp, snippet))

    if not snippets:
        return 0

    enriched_count = 0

    if batch_size > 1 and len(snippets) > 1:
        for batch_start in range(0, len(snippets), batch_size):
            batch = snippets[batch_start : batch_start + batch_size]
            entries = ""
            for idx, (comp, snippet) in enumerate(batch, 1):
                entries += BATCH_ENTRY_TEMPLATE.format(
                    index=idx,
                    component_name=comp.name,
                    provider=comp.provider or "unknown",
                    snippet=snippet[:2000],
                )
            user_msg = BATCH_USER_PROMPT_TEMPLATE.format(entries=entries)
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ]
            try:
                raw = _call_llm(messages, model, api_key, base_url)
                results = _parse_batch_result(raw, len(batch))
                for (comp, _snippet), result in zip(batch, results, strict=False):
                    if result.get("model_name"):
                        _apply_result(comp, result)
                        enriched_count += 1
            except Exception:
                logger.warning(
                    "LLM enrichment batch failed, falling back to individual calls",
                    exc_info=True,
                )
                for comp, snippet in batch:
                    try:
                        enriched_count += _enrich_single(comp, snippet, model, api_key, base_url)
                    except Exception:
                        logger.warning(
                            "LLM enrichment failed for %s, skipping",
                            comp.name,
                            exc_info=True,
                        )
    else:
        for comp, snippet in snippets:
            try:
                enriched_count += _enrich_single(comp, snippet, model, api_key, base_url)
            except Exception:
                logger.warning(
                    "LLM enrichment failed for %s, skipping",
                    comp.name,
                    exc_info=True,
                )

    logger.info(
        "LLM enrichment: %d of %d eligible components enriched",
        enriched_count,
        len(eligible),
    )
    return enriched_count


def _enrich_single(
    component: AIComponent,
    snippet: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
) -> int:
    """Enrich a single component. Returns 1 if enriched, 0 otherwise."""
    user_msg = USER_PROMPT_TEMPLATE.format(
        component_name=component.name,
        provider=component.provider or "unknown",
        snippet=snippet[:2000],
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    raw = _call_llm(messages, model, api_key, base_url)
    result = _parse_single_result(raw)
    if result.get("model_name"):
        _apply_result(component, result)
        return 1
    return 0
