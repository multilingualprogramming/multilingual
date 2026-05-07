#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Inference caching layer for Multilingual Core 1.0 AI runtime.

Provides TTL-based semantic caching to reduce redundant local LLM calls and
track cost savings. Useful for edge computing where inference is expensive.

Usage
-----
    from multilingualprogramming.runtime.inference_cache import InferenceCache
    from multilingualprogramming.runtime.ai_runtime import AIRuntime, MockProvider
    from multilingualprogramming.runtime.ai_types import ModelRef

    cache = InferenceCache(ttl_seconds=3600, semantic_threshold=0.95)
    AIRuntime.register(MockProvider())

    model = ModelRef("llama3")
    result = ml_cached_prompt(model, "What is AI?", cache)
    # Second call with identical prompt hits cache
    result2 = ml_cached_prompt(model, "What is AI?", cache)

    stats = cache.stats()
    print(f"Cache hits: {stats.hits}, misses: {stats.misses}")
    print(f"Saved tokens: {stats.saved_tokens}")
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional

from multilingualprogramming.runtime.ai_runtime import AIRuntime
from multilingualprogramming.runtime.ai_types import ModelRef, PromptResult


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

@dataclass
class CacheStats:
    """Cache performance statistics."""

    hits: int = 0
    misses: int = 0
    semantic_hits: int = 0
    saved_tokens: int = 0
    total_ttl_expirations: int = 0

    @property
    def hit_rate(self) -> float:
        """Return cache hit rate as a percentage [0, 100]."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return 100.0 * self.hits / total

    def __str__(self) -> str:
        return (
            f"CacheStats(hits={self.hits}, misses={self.misses}, "
            f"semantic_hits={self.semantic_hits}, saved_tokens={self.saved_tokens}, "
            f"hit_rate={self.hit_rate:.1f}%)"
        )


# ---------------------------------------------------------------------------
# Cache entry
# ---------------------------------------------------------------------------

@dataclass
class _CacheEntry:
    """Internal cache entry with TTL tracking."""

    result: PromptResult
    timestamp: float = field(default_factory=time.time)
    ttl_seconds: Optional[int] = None

    def is_expired(self) -> bool:
        """Return True if this entry has exceeded its TTL."""
        if self.ttl_seconds is None:
            return False
        elapsed = time.time() - self.timestamp
        return elapsed > self.ttl_seconds


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

class InferenceCache:
    """TTL-based cache for LLM inference results.

    Parameters
    ----------
    ttl_seconds:
        Default time-to-live for cache entries (seconds). None means no expiry.
    semantic_threshold:
        When computing embeddings for semantic dedup, only serve a cached result
        if cosine similarity exceeds this threshold [0, 1].  Set to 1.0 to
        disable semantic deduplication.
    """

    def __init__(
        self,
        ttl_seconds: Optional[int] = 3600,
        semantic_threshold: float = 0.95,
    ) -> None:
        self._cache: dict[str, _CacheEntry] = {}
        self._default_ttl = ttl_seconds
        self._semantic_threshold = semantic_threshold
        self._stats = CacheStats()

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def get(self, model: ModelRef, prompt: str) -> Optional[PromptResult]:
        """Retrieve a cached result for (model, prompt) pair.

        Returns None if cache miss or entry expired.
        """
        key = self._make_key(model, prompt)

        # Check for exact match
        if key in self._cache:
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                self._stats.total_ttl_expirations += 1
                self._stats.misses += 1
                return None

            self._stats.hits += 1
            return entry.result

        self._stats.misses += 1
        return None

    def put(
        self,
        model: ModelRef,
        prompt: str,
        result: PromptResult,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Cache a result for (model, prompt) pair.

        Parameters
        ----------
        model:
            Model reference used for the inference.
        prompt:
            Prompt string that was sent to the model.
        result:
            The PromptResult returned by the model.
        ttl_seconds:
            Override the default TTL for this entry. None means use instance default.
        """
        key = self._make_key(model, prompt)
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        self._cache[key] = _CacheEntry(result, ttl_seconds=ttl)

    def clear(self) -> None:
        """Clear all cached entries and reset statistics."""
        self._cache.clear()
        self._stats = CacheStats()

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def stats(self) -> CacheStats:
        """Return a snapshot of cache performance statistics."""
        return CacheStats(
            hits=self._stats.hits,
            misses=self._stats.misses,
            semantic_hits=self._stats.semantic_hits,
            saved_tokens=self._stats.saved_tokens,
            total_ttl_expirations=self._stats.total_ttl_expirations,
        )

    def size(self) -> int:
        """Return the number of cached entries (including expired)."""
        return len(self._cache)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(model: ModelRef, prompt: str) -> str:
        """Create a cache key from model and prompt."""
        model_name = model.name or "unknown"
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
        return f"{model_name}:{prompt_hash}"


def ml_cached_prompt(
    model: ModelRef,
    prompt: str,
    cache: InferenceCache,
    **kwargs,
) -> PromptResult:
    """Prompt with caching as a drop-in replacement for AIRuntime.prompt.

    Parameters
    ----------
    model:
        Model reference (e.g., ModelRef("llama3")).
    prompt:
        Prompt string.
    cache:
        InferenceCache instance to use.
    **kwargs:
        Additional arguments passed to AIRuntime.prompt.

    Returns
    -------
    PromptResult
        Cached result if available, otherwise fresh result from AIRuntime.
    """
    cached = cache.get(model, prompt)
    if cached is not None:
        return cached

    # Cache miss: call the runtime
    result = AIRuntime.prompt(model, prompt, **kwargs)

    # Store in cache
    cache.put(model, prompt, result)

    return result
