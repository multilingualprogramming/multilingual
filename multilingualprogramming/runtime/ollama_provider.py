#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Ollama provider for the Core 1.0 AI runtime.

Connects Multilingual's AI-native language constructs to a locally running
Ollama instance via the official ``ollama`` Python SDK.

Installation
------------
    pip install ollama
    # and have Ollama running locally: https://ollama.com

Usage
-----
    from multilingualprogramming.runtime.ollama_provider import OllamaProvider
    from multilingualprogramming.runtime.ai_runtime import AIRuntime

    AIRuntime.register(OllamaProvider())               # connects to localhost:11434
    # or
    AIRuntime.register(OllamaProvider(host="http://my-ollama-server:11434"))

Model name mapping
------------------
Model reference literals in Multilingual (@llama3, @mistral, …) are resolved
by the _resolve_model() method.  Any name not in the alias table is passed
through as-is, so @llama3.2:latest works without any configuration.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Iterator

from multilingualprogramming.runtime.ai_runtime import AIProvider
from multilingualprogramming.runtime.ai_types import (
    EmbeddingVector,
    ModelRef,
    PromptResult,
    StreamChunk,
)
from multilingualprogramming.runtime.multimodal_runtime import ImageValue, MultimodalPrompt


# Short name → full Ollama model tag
_MODEL_ALIASES: dict[str, str] = {
    "llama3":   "llama3.2",
    "llama":    "llama3.2",
    "mistral":  "mistral",
    "phi3":     "phi3",
    "phi":      "phi3",
    "gemma":    "gemma3",
    "gemma3":   "gemma3",
    "qwen":     "qwen2.5",
    "deepseek": "deepseek-r1",
}

_DEFAULT_MAX_TOKENS = 4096


class OllamaProvider(AIProvider):
    """AIProvider implementation backed by a local Ollama instance.

    Parameters
    ----------
    host:
        Base URL of the Ollama server.  Defaults to ``http://localhost:11434``.
    default_model:
        Model tag used when the program does not specify one explicitly.
        Defaults to ``"llama3.2"``.
    max_tokens:
        Maximum tokens to generate.  Defaults to 4096.
    """

    def __init__(
        self,
        host: str = "http://localhost:11434",
        default_model: str = "llama3.2",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> None:
        try:
            import ollama as _ollama  # pylint: disable=import-outside-toplevel
        except ImportError as exc:
            raise ImportError(
                "The 'ollama' package is required to use OllamaProvider.\n"
                "Install it with:  pip install ollama"
            ) from exc

        self._ollama = _ollama
        self._client = _ollama.Client(host=host)
        self._async_client = _ollama.AsyncClient(host=host)
        self._default_model = default_model
        self._max_tokens = max_tokens

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_model(self, model: ModelRef) -> str:
        """Resolve a ModelRef to an Ollama model tag."""
        name = model.name or self._default_model
        return _MODEL_ALIASES.get(name, name)

    def _max_tokens_for(self, kwargs: dict) -> int:
        return kwargs.pop("max_tokens", self._max_tokens)

    def _read_image_bytes(self, image: ImageValue) -> bytes:
        """Return raw bytes for an ImageValue, tolerating legacy path-style use."""
        if isinstance(image.data, (bytes, bytearray)) and image.data:
            return bytes(image.data)
        if image.source_path:
            return Path(image.source_path).read_bytes()
        if isinstance(image.data, str) and image.data:
            candidate = Path(image.data)
            if candidate.exists():
                return candidate.read_bytes()
        raise ValueError(
            "ImageValue has no binary data or readable source_path for Ollama vision input."
        )

    def _build_message(self, template) -> dict[str, object]:
        """Build an Ollama chat message, including images for multimodal prompts."""
        message: dict[str, object] = {"role": "user"}

        if isinstance(template, ImageValue):
            image_data = base64.standard_b64encode(
                self._read_image_bytes(template)
            ).decode("utf-8")
            message["content"] = "Analyze this image."
            message["images"] = [image_data]
            return message

        if isinstance(template, MultimodalPrompt):
            texts: list[str] = []
            images: list[str] = []
            for part in template.parts:
                if isinstance(part, str):
                    texts.append(part)
                elif isinstance(part, ImageValue):
                    images.append(
                        base64.standard_b64encode(
                            self._read_image_bytes(part)
                        ).decode("utf-8")
                    )
                else:
                    texts.append(repr(part))
            message["content"] = "\n".join(t for t in texts if t).strip() or "Analyze this input."
            if images:
                message["images"] = images
            return message

        message["content"] = template
        return message

    # ------------------------------------------------------------------
    # Required abstract methods
    # ------------------------------------------------------------------

    def prompt(self, model: ModelRef, template, **kwargs) -> PromptResult:
        """Send a prompt and return the full text response.

        Supports both text prompts (str) and multimodal prompts with images (ImageValue).
        """
        model_tag = self._resolve_model(model)
        max_tokens = self._max_tokens_for(kwargs)
        options = kwargs.pop("options", {})
        options.setdefault("num_predict", max_tokens)

        chat_kwargs = {"options": options, **kwargs}
        message = self._build_message(template)

        response = self._client.chat(
            model=model_tag,
            messages=[message],
            **chat_kwargs,
        )
        message = getattr(response, "message", None)
        content = getattr(message, "content", "")
        usage = {}
        if hasattr(response, "eval_count") and response.eval_count:
            usage = {
                "input_tokens": getattr(response, "prompt_eval_count", 0),
                "output_tokens": response.eval_count,
            }
        return PromptResult(content=content, model=model_tag, usage=usage)

    def embed(self, model: ModelRef, text: str, **kwargs) -> EmbeddingVector:
        """Return a dense embedding vector using Ollama's embeddings API.

        Falls back to a hash-based mock if the model does not support
        embeddings (e.g. pure chat models).
        """
        model_tag = self._resolve_model(model)
        # Use a dedicated embedding model if the caller requests one;
        # otherwise attempt the current model tag.
        embed_model = kwargs.pop("embed_model", model_tag)
        try:
            response = self._client.embeddings(model=embed_model, prompt=text)
            values = list(getattr(response, "embedding", []))
            return EmbeddingVector(
                values=values, model=embed_model, dimensions=len(values)
            )
        except Exception:
            # Fallback: hash-based mock vector
            dim = kwargs.pop("dimensions", 1536)
            seed = hash(text) & 0xFFFFFFFF
            values = [float((seed >> (i % 32)) & 0xFF) / 255.0 for i in range(dim)]
            mag = sum(v * v for v in values) ** 0.5 or 1.0
            values = [v / mag for v in values]
            return EmbeddingVector(values=values, model=embed_model, dimensions=dim)

    # ------------------------------------------------------------------
    # Override: native streaming
    # ------------------------------------------------------------------

    def stream(self, model: ModelRef, template: str, **kwargs) -> Iterator[StreamChunk]:
        """Stream tokens using Ollama's streaming chat API."""
        model_tag = self._resolve_model(model)
        max_tokens = self._max_tokens_for(kwargs)
        options = kwargs.pop("options", {})
        options.setdefault("num_predict", max_tokens)
        for chunk in self._client.chat(
            model=model_tag,
            messages=[{"role": "user", "content": template}],
            stream=True,
            options=options,
            **kwargs,
        ):
            message = getattr(chunk, "message", None)
            content = getattr(message, "content", "")
            is_final = getattr(chunk, "done", False)
            yield StreamChunk(content=content, is_final=is_final)

    # ------------------------------------------------------------------
    # Override: structured generation with JSON mode
    # ------------------------------------------------------------------

    def generate(
        self,
        model: ModelRef,
        template: str,
        target_type: type | None = None,
        **kwargs,
    ) -> object:
        """Generate a structured value.

        Requests JSON format from Ollama when a non-string target type is
        declared, then attempts to parse the response.
        """
        if target_type is None or target_type is str:
            return self.prompt(model, template, **kwargs).content

        model_tag = self._resolve_model(model)
        max_tokens = self._max_tokens_for(kwargs)
        options = kwargs.pop("options", {})
        options.setdefault("num_predict", max_tokens)
        json_prompt = (
            f"{template}\n\n"
            "Respond with valid JSON only matching the schema for "
            f"{getattr(target_type, '__name__', str(target_type))}. "
            "Do not include any text outside the JSON object."
        )
        response = self._client.chat(
            model=model_tag,
            messages=[{"role": "user", "content": json_prompt}],
            format="json",
            options=options,
            **kwargs,
        )
        message = getattr(response, "message", None)
        raw = getattr(message, "content", "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            data = json.loads(raw)
            if hasattr(target_type, "__dataclass_fields__"):
                return target_type(**{
                    k: v for k, v in data.items()
                    if k in target_type.__dataclass_fields__
                })
            return data
        except Exception:
            return raw

    # ------------------------------------------------------------------
    # Async variants
    # ------------------------------------------------------------------

    async def prompt_async(self, model: ModelRef, template, **kwargs) -> PromptResult:
        """Async prompt using the Ollama async client.

        Supports both text prompts (str) and multimodal prompts with images (ImageValue).
        """
        model_tag = self._resolve_model(model)
        max_tokens = self._max_tokens_for(kwargs)
        options = kwargs.pop("options", {})
        options.setdefault("num_predict", max_tokens)

        chat_kwargs = {"options": options, **kwargs}
        message = self._build_message(template)

        response = await self._async_client.chat(
            model=model_tag,
            messages=[message],
            **chat_kwargs,
        )
        message = getattr(response, "message", None)
        content = getattr(message, "content", "")
        usage = {}
        if hasattr(response, "eval_count") and response.eval_count:
            usage = {
                "input_tokens": getattr(response, "prompt_eval_count", 0),
                "output_tokens": response.eval_count,
            }
        return PromptResult(content=content, model=model_tag, usage=usage)
