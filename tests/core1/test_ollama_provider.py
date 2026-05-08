#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Regression tests for the Ollama provider's multimodal request shaping."""

from __future__ import annotations

import base64
import sys
from types import SimpleNamespace

from multilingualprogramming.runtime.ai_types import ModelRef
from multilingualprogramming.runtime.multimodal_runtime import ImageValue, MultimodalPrompt
from multilingualprogramming.runtime.ollama_provider import OllamaProvider


class _FakeClient:
    """Minimal sync Ollama client stub for request-shaping tests."""

    def __init__(self, host=None):
        """Store the configured host and capture chat payloads."""
        self.host = host
        self.calls = []

    def chat(self, **kwargs):
        """Capture sync chat payloads and return a fake response."""
        self.calls.append(kwargs)
        return SimpleNamespace(
            message=SimpleNamespace(content="ok"),
            eval_count=7,
            prompt_eval_count=3,
        )


class _FakeAsyncClient:
    """Async Ollama client stub that records the same payload shape."""

    def __init__(self, host=None):
        """Store the configured host and capture async chat payloads."""
        self.host = host
        self.calls = []

    async def chat(self, **kwargs):
        """Capture async chat payloads and return a fake response."""
        self.calls.append(kwargs)
        return SimpleNamespace(
            message=SimpleNamespace(content="ok"),
            eval_count=7,
            prompt_eval_count=3,
        )


class _FakeOllamaModule:
    """Module-shaped stub exposing sync and async client constructors."""

    def __init__(self):
        """Track instantiated fake clients for later assertions."""
        self.clients = []
        self.async_clients = []

    def Client(self, host=None):  # pylint: disable=invalid-name
        """Return a fake sync client and remember it."""
        client = _FakeClient(host=host)
        self.clients.append(client)
        return client

    def AsyncClient(self, host=None):  # pylint: disable=invalid-name
        """Return a fake async client and remember it."""
        client = _FakeAsyncClient(host=host)
        self.async_clients.append(client)
        return client


def test_prompt_embeds_image_bytes_in_message_payload(monkeypatch, tmp_path):
    fake_module = _FakeOllamaModule()
    monkeypatch.setitem(sys.modules, "ollama", fake_module)

    image_path = tmp_path / "flower.jpg"
    image_bytes = b"\xff\xd8\xff"
    image_path.write_bytes(image_bytes)

    provider = OllamaProvider()
    result = provider.prompt(
        ModelRef("llama3.2-vision"),
        ImageValue.from_path(image_path, mime_type="image/jpeg"),
    )

    assert result.content == "ok"
    call = fake_module.clients[0].calls[0]
    assert "images" not in call
    assert call["messages"][0]["content"] == "Analyze this image."
    assert call["messages"][0]["images"] == [
        base64.standard_b64encode(image_bytes).decode("utf-8")
    ]


def test_prompt_supports_multimodal_prompt_with_text_and_image(monkeypatch, tmp_path):
    fake_module = _FakeOllamaModule()
    monkeypatch.setitem(sys.modules, "ollama", fake_module)

    image_path = tmp_path / "flower.jpg"
    image_bytes = b"\x89PNG"
    image_path.write_bytes(image_bytes)

    provider = OllamaProvider()
    prompt = MultimodalPrompt()
    prompt.add_text("Describe this flower.")
    prompt.add(ImageValue.from_path(image_path))

    provider.prompt(ModelRef("llama3.2-vision"), prompt)

    call = fake_module.clients[0].calls[0]
    assert call["messages"][0]["content"] == "Describe this flower."
    assert call["messages"][0]["images"] == [
        base64.standard_b64encode(image_bytes).decode("utf-8")
    ]
