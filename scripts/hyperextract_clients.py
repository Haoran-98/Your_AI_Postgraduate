#!/usr/bin/env python3
"""Create Hyper-Extract clients from separate OpenAI-compatible endpoints."""

from __future__ import annotations

import os
import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.callbacks import BaseCallbackHandler


@dataclass(frozen=True)
class ProviderSettings:
    base_url: str
    api_key: str
    model: str


def _settings(prefix: str) -> ProviderSettings:
    names = {
        "base_url": f"{prefix}_BASE_URL",
        "api_key": f"{prefix}_API_KEY",
        "model": f"{prefix}_MODEL_ID",
    }
    missing = [env_name for env_name in names.values() if not os.environ.get(env_name)]
    if missing:
        raise ValueError(f"Missing provider configuration: {', '.join(missing)}")
    return ProviderSettings(
        base_url=os.environ[names["base_url"]].rstrip("/"),
        api_key=os.environ[names["api_key"]],
        model=os.environ[names["model"]],
    )


def llm_settings(strength: str = "strong") -> ProviderSettings:
    """Resolve a task-tier model, falling back to the strong model when blank."""
    strength = strength.lower()
    if strength not in {"strong", "medium", "weak"}:
        raise ValueError(f"Unknown LLM strength: {strength}")
    model = (
        os.environ.get(f"OPENAI_{strength.upper()}_MODEL_ID")
        or os.environ.get("OPENAI_STRONG_MODEL_ID")
        or os.environ.get("OPENAI_MODEL_ID")
    )
    missing = [
        name
        for name, value in (
            ("OPENAI_BASE_URL", os.environ.get("OPENAI_BASE_URL")),
            ("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY")),
            (f"OPENAI_{strength.upper()}_MODEL_ID", model),
        )
        if not value
    ]
    if missing:
        raise ValueError(f"Missing provider configuration: {', '.join(missing)}")
    return ProviderSettings(
        base_url=os.environ["OPENAI_BASE_URL"].rstrip("/"),
        api_key=os.environ["OPENAI_API_KEY"],
        model=model,
    )


def provider_configured() -> tuple[bool, str]:
    try:
        llm_settings("strong")
        _settings("EMBEDDING")
    except ValueError as exc:
        return False, str(exc)
    return True, "separate LLM and embedding providers configured"


class UsageRecorder(BaseCallbackHandler):
    """Append one auditable record per logical LLM request."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.context: dict[str, object] = {}
        self.started: dict[str, dict[str, object]] = {}
        self.request_counts: dict[tuple[object, ...], int] = {}
        self.lock = threading.Lock()

    def set_context(self, **values: object) -> None:
        self.context = values

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs) -> None:
        with self.lock:
            context = dict(self.context)
            key = (
                context.get("unit_id"),
                context.get("mode"),
                context.get("attempt"),
            )
            request_index = self.request_counts.get(key, 0) + 1
            self.request_counts[key] = request_index
            input_payload = [
                [self._message_payload(message) for message in batch]
                for batch in messages
            ]
            self.started[str(run_id)] = {
                "started": time.monotonic(),
                "context": context,
                "request_index": request_index,
                "invocation": self._jsonable(kwargs.get("invocation_params") or {}),
                "input": input_payload,
                "input_chars": len(json.dumps(input_payload, ensure_ascii=False)),
            }

    def on_llm_end(self, response, *, run_id, **kwargs) -> None:
        usage = dict((response.llm_output or {}).get("token_usage") or {})
        message = response.generations[0][0].message if response.generations else None
        if message is not None and getattr(message, "usage_metadata", None):
            metadata = message.usage_metadata
            usage = {
                "prompt_tokens": metadata.get("input_tokens", 0),
                "completion_tokens": metadata.get("output_tokens", 0),
                "total_tokens": metadata.get("total_tokens", 0),
            }
        output_payload = {
            "llm_output": self._jsonable(response.llm_output or {}),
            "generations": [
                [self._message_payload(generation.message) for generation in batch]
                for batch in response.generations
            ],
        }
        self._write(str(run_id), "success", usage, output=output_payload)

    def on_llm_error(self, error, *, run_id, **kwargs) -> None:
        self._write(str(run_id), "error", {}, error=f"{type(error).__name__}: {error}")

    def _write(
        self,
        run_id: str,
        status: str,
        usage: dict[str, object],
        *,
        output: object | None = None,
        error: str = "",
    ) -> None:
        with self.lock:
            state = self.started.pop(
                run_id,
                {
                    "started": time.monotonic(),
                    "context": dict(self.context),
                    "request_index": 0,
                    "invocation": {},
                    "input": [],
                    "input_chars": 0,
                },
            )
            output_payload = self._jsonable(output or {})
            output_chars = len(json.dumps(output_payload, ensure_ascii=False))
            request_path = self.path.parent / "requests" / f"{run_id}.json"
            self._atomic_json(
                request_path,
                {
                    **state["context"],
                    "run_id": run_id,
                    "request_index": state["request_index"],
                    "status": status,
                    "invocation": state["invocation"],
                    "input": state["input"],
                    "output": output_payload,
                    "error": error[:1000],
                },
            )
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **state["context"],
                "run_id": run_id,
                "request_index": state["request_index"],
                "status": status,
                "elapsed_s": round(time.monotonic() - float(state["started"]), 3),
                "input_chars": state["input_chars"],
                "output_chars": output_chars,
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "sdk_retries": 0,
                "unit_retries": max(int(state["context"].get("attempt", 1)) - 1, 0),
                "request_file": str(request_path.relative_to(self.path.parent)),
                "error": error[:1000],
            }
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _message_payload(message: object) -> object:
        if hasattr(message, "model_dump"):
            return message.model_dump(mode="json")
        return UsageRecorder._jsonable(message)

    @staticmethod
    def _jsonable(value: object) -> object:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {str(key): UsageRecorder._jsonable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [UsageRecorder._jsonable(item) for item in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    @staticmethod
    def _atomic_json(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)


def create_llm_client(
    usage_recorder: UsageRecorder | None = None,
    *,
    strength: str = "strong",
    timeout: float = 180,
):
    """Return one task-tier LLM client without persisting credentials to disk."""
    from langchain_openai import ChatOpenAI

    llm = llm_settings(strength)
    return ChatOpenAI(
        model=llm.model,
        api_key=llm.api_key,
        base_url=llm.base_url,
        temperature=0,
        timeout=timeout,
        max_retries=0,
        callbacks=[usage_recorder] if usage_recorder else None,
    )


def create_hyperextract_clients(
    usage_recorder: UsageRecorder | None = None,
    *,
    strength: str = "strong",
):
    """Return a task-tier LLM and embedder without persisting credentials."""
    from hyperextract import create_embedder

    embedding = _settings("EMBEDDING")
    llm_client = create_llm_client(usage_recorder, strength=strength)
    embedder = create_embedder(
        {
            "provider": "vllm",
            "model": embedding.model,
            "base_url": embedding.base_url,
            "api_key": embedding.api_key,
        },
        max_batch_size=10,
    )
    return llm_client, embedder
