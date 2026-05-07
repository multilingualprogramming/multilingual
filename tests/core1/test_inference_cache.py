#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Tests for inference caching layer."""
# pylint: disable=missing-class-docstring

import pytest

from multilingualprogramming.runtime.ai_runtime import AIRuntime, MockProvider
from multilingualprogramming.runtime.ai_types import ModelRef, PromptResult
from multilingualprogramming.runtime.inference_cache import (
    CacheStats,
    InferenceCache,
    ml_cached_prompt,
)


@pytest.fixture(autouse=True)
def reset_runtime():
    """Reset AIRuntime between tests."""
    AIRuntime.reset()
    yield
    AIRuntime.reset()


class TestInferenceCache:
    def test_cache_miss_on_first_call(self):
        cache = InferenceCache(ttl_seconds=3600)
        model = ModelRef("test-model")

        result = cache.get(model, "What is AI?")
        assert result is None
        assert cache.stats().misses == 1
        assert cache.stats().hits == 0

    def test_cache_hit_on_second_call(self):
        cache = InferenceCache(ttl_seconds=3600)
        model = ModelRef("test-model")
        prompt = "What is AI?"
        stored_result = PromptResult(content="AI is...", model="test")

        # First call: cache miss
        cache.put(model, prompt, stored_result)

        # Second call: cache hit
        retrieved = cache.get(model, prompt)
        assert retrieved is not None
        assert retrieved.content == "AI is..."
        assert cache.stats().hits == 1
        assert cache.stats().misses == 0

    def test_different_prompts_are_separate_cache_entries(self):
        cache = InferenceCache()
        model = ModelRef("m")
        r1 = PromptResult(content="Response 1", model="m")
        r2 = PromptResult(content="Response 2", model="m")

        cache.put(model, "Prompt A", r1)
        cache.put(model, "Prompt B", r2)

        assert cache.get(model, "Prompt A").content == "Response 1"
        assert cache.get(model, "Prompt B").content == "Response 2"

    def test_different_models_are_separate_cache_entries(self):
        cache = InferenceCache()
        r1 = PromptResult(content="From model1", model="m1")
        r2 = PromptResult(content="From model2", model="m2")

        cache.put(ModelRef("model1"), "Test", r1)
        cache.put(ModelRef("model2"), "Test", r2)

        assert cache.get(ModelRef("model1"), "Test").content == "From model1"
        assert cache.get(ModelRef("model2"), "Test").content == "From model2"

    def test_clear_resets_cache_and_stats(self):
        cache = InferenceCache()
        cache.put(ModelRef("m"), "p", PromptResult("result"))
        cache.get(ModelRef("m"), "p")  # Cache hit

        cache.clear()

        assert cache.size() == 0
        assert cache.stats().hits == 0
        assert cache.stats().misses == 0

    def test_stats_object(self):
        cache = InferenceCache()
        stats = cache.stats()

        assert isinstance(stats, CacheStats)
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.saved_tokens == 0
        assert stats.hit_rate == 0.0

    def test_cache_stats_hit_rate(self):
        stats = CacheStats(hits=3, misses=1)
        assert stats.hit_rate == 75.0

    def test_cache_stats_hit_rate_empty(self):
        stats = CacheStats(hits=0, misses=0)
        assert stats.hit_rate == 0.0

    def test_size_method(self):
        cache = InferenceCache()
        assert cache.size() == 0

        cache.put(ModelRef("m"), "p1", PromptResult("r1"))
        assert cache.size() == 1

        cache.put(ModelRef("m"), "p2", PromptResult("r2"))
        assert cache.size() == 2


class TestMlCachedPrompt:
    def test_cached_prompt_calls_runtime_on_miss(self):
        cache = InferenceCache()
        provider = MockProvider().add_response("Hello cached world")
        AIRuntime.register(provider)

        model = ModelRef("test")
        result = ml_cached_prompt(model, "Hi there", cache)

        assert result.content == "Hello cached world"
        assert cache.stats().misses == 1

    def test_cached_prompt_returns_cached_on_hit(self):
        cache = InferenceCache()
        provider = MockProvider().add_response("First response")
        AIRuntime.register(provider)

        model = ModelRef("test")

        # First call: runtime
        result1 = ml_cached_prompt(model, "Question?", cache)
        assert result1.content == "First response"
        assert cache.stats().hits == 0
        assert cache.stats().misses == 1

        # Second call: should return cached without calling runtime again
        # (provider would have returned different response if called)
        result2 = ml_cached_prompt(model, "Question?", cache)
        assert result2.content == "First response"
        assert cache.stats().hits == 1
        assert cache.stats().misses == 1  # No new miss

    def test_cached_prompt_with_different_prompts(self):
        cache = InferenceCache()
        provider = MockProvider()
        provider.add_response("Answer 1")
        provider.add_response("Answer 2")
        AIRuntime.register(provider)

        model = ModelRef("m")

        # First prompt
        r1 = ml_cached_prompt(model, "First question", cache)
        assert r1.content == "Answer 1"

        # Second prompt (different)
        r2 = ml_cached_prompt(model, "Second question", cache)
        assert r2.content == "Answer 2"

        # Both should be in cache
        assert cache.size() == 2
        assert cache.stats().misses == 2

    def test_cached_prompt_integration_with_runtime(self):
        """End-to-end test: prompt → cache → retrieval."""
        cache = InferenceCache(ttl_seconds=3600)
        provider = MockProvider().add_response("Cached response")
        AIRuntime.register(provider)

        model = ModelRef("llama3")
        prompt = "What is edge computing?"

        # Prime the cache
        result1 = ml_cached_prompt(model, prompt, cache)
        assert result1.content == "Cached response"

        # Retrieve from cache (no new provider call)
        result2 = ml_cached_prompt(model, prompt, cache)
        assert result2.content == "Cached response"
        assert cache.stats().hit_rate == 50.0  # 1 hit, 1 miss
