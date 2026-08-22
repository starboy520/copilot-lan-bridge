from __future__ import annotations

from typing import Any


def _normalized_endpoints(model: dict[str, Any]) -> set[str]:
    endpoints = model.get("supported_endpoints")
    if not isinstance(endpoints, list):
        return set()
    return {
        endpoint.strip().lower() if endpoint.startswith("/") else f"/{endpoint.strip().lower()}"
        for endpoint in endpoints
        if isinstance(endpoint, str) and endpoint.strip()
    }


def supports_responses(model: dict[str, Any]) -> bool:
    return bool(_normalized_endpoints(model) & {"/responses", "/v1/responses"})


def visible_models(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    for source in models:
        model_id = source.get("id")
        policy = source.get("policy")
        if not isinstance(model_id, str) or not model_id:
            continue
        if isinstance(policy, dict) and policy.get("state") == "disabled":
            continue
        if not supports_responses(source):
            continue

        model = dict(source)
        model.update(
            {
                "id": model_id,
                "slug": model_id,
                "object": "model",
                "display_name": source.get("name") or model_id,
                "owned_by": "github-copilot",
            }
        )
        visible.append(model)
    return visible