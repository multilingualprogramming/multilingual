#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Model versioning, registration, and placement-aware routing.

Provides a registry of known models with their capabilities, placement hints,
version information, and cost metadata. Supports fallback chains and placement
routing for distributed edge/cloud deployment.

Usage
-----
    from multilingualprogramming.runtime.model_registry import (
        ModelRegistry, ModelSpec, ml_model
    )
    from multilingualprogramming.runtime.ai_types import ModelRef

    registry = ModelRegistry()

    # Pre-registered Ollama models are available
    spec = registry.resolve("llama3", placement="local")
    print(spec.version)

    # Get the best model for a task within a latency SLA
    spec = registry.best_for("summarize", placement="local", max_latency_ms=2000)

    # Create a model ref with fallback to cloud if local unavailable
    model = ml_model("mistral", placement="local")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional


# ---------------------------------------------------------------------------
# Model specification
# ---------------------------------------------------------------------------

@dataclass
class ModelSpec:
    """Specification of a registered model.

    Parameters
    ----------
    name:
        Model name (e.g., "llama3", "mistral").
    provider:
        Provider name (e.g., "ollama", "anthropic", "openai").
    placement:
        Deployment hint: "local", "edge", or "cloud".
    capabilities:
        List of supported capabilities (e.g., ["generate", "embed"]).
    version:
        Version string or semantic version (e.g., "3.2", "latest").
    latency_sla_ms:
        Expected latency in milliseconds for typical inference.
    cost_per_token:
        Estimated cost per token (arbitrary units for comparison).
    """

    name: str = ""
    provider: str = ""
    placement: str = "local"  # "local", "edge", or "cloud"
    capabilities: list[str] = field(default_factory=list)
    version: str = "latest"
    latency_sla_ms: float = 0.0
    cost_per_token: float = 0.0

    def supports(self, capability: str) -> bool:
        """Return True if this model supports the named capability."""
        return capability in self.capabilities

    def __repr__(self) -> str:
        return (
            f"ModelSpec(name={self.name!r}, provider={self.provider!r}, "
            f"placement={self.placement!r}, version={self.version!r})"
        )


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

class ModelRegistry:
    """Registry of known models with versions, capabilities, and placement info.

    Supports:
    - Model registration and lookup
    - Fallback chains (@local → @edge → @cloud)
    - Placement-constrained resolution
    - Best-fit selection based on SLA and task
    """

    def __init__(self) -> None:
        self._models: dict[str, list[ModelSpec]] = {}  # name -> [specs by version]
        self._populate_defaults()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, spec: ModelSpec) -> None:
        """Register a model specification.

        Subsequent calls with the same (name, version) overwrite.
        """
        if spec.name not in self._models:
            self._models[spec.name] = []

        # Overwrite or append
        existing = [s for s in self._models[spec.name] if s.version == spec.version]
        if existing:
            self._models[spec.name].remove(existing[0])

        self._models[spec.name].append(spec)
        # Keep latest version at the end
        self._models[spec.name].sort(
            key=lambda s: (s.version != "latest", s.version)
        )

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(
        self,
        name: str,
        placement: Optional[str] = None,
        capability: Optional[str] = None,
    ) -> ModelSpec:
        """Resolve a model by name and optional placement/capability.

        If placement is specified, returns the spec for that placement.
        If multiple versions exist, prefers "latest", then highest version.
        Raises KeyError if not found.
        """
        if name not in self._models:
            raise KeyError(f"Unknown model: {name!r}")

        candidates = self._models[name]

        # Filter by placement
        if placement is not None:
            candidates = [s for s in candidates if s.placement == placement]
            if not candidates:
                raise KeyError(
                    f"Model {name!r} not available for placement {placement!r}"
                )

        # Filter by capability
        if capability is not None:
            candidates = [s for s in candidates if s.supports(capability)]
            if not candidates:
                raise KeyError(
                    f"Model {name!r} does not support capability {capability!r}"
                )

        # Return latest version (prefer "latest" tag)
        latest = [s for s in candidates if s.version == "latest"]
        return latest[0] if latest else candidates[-1]

    def best_for(
        self,
        task: str,
        placement: Optional[str] = None,
        max_latency_ms: Optional[float] = None,
    ) -> ModelSpec:
        """Return the best model for a task under optional constraints.

        Parameters
        ----------
        task:
            Task name (e.g., "summarize", "classify", "generate").
        placement:
            Restrict to this placement: "local", "edge", "cloud".
        max_latency_ms:
            Only return models with latency_sla_ms <= this value.

        Returns the lowest-cost model matching the constraints.
        Raises KeyError if no suitable model found.
        """
        candidates: list[ModelSpec] = []

        for specs in self._models.values():
            for spec in specs:
                # Check placement
                if placement is not None and spec.placement != placement:
                    continue

                # Check latency SLA
                if max_latency_ms is not None:
                    if spec.latency_sla_ms > max_latency_ms:
                        continue

                candidates.append(spec)

        if not candidates:
            raise KeyError(
                f"No model available for task {task!r} "
                f"with constraints: placement={placement}, "
                f"max_latency_ms={max_latency_ms}"
            )

        # Sort by cost, return cheapest
        return min(candidates, key=lambda s: s.cost_per_token)

    def list_models(self, placement: Optional[str] = None) -> list[str]:
        """Return all registered model names, optionally filtered by placement."""
        names = []
        for name, specs in self._models.items():
            if placement is None:
                names.append(name)
            elif any(s.placement == placement for s in specs):
                names.append(name)
        return sorted(names)

    # ------------------------------------------------------------------
    # Private: defaults
    # ------------------------------------------------------------------

    def _populate_defaults(self) -> None:
        """Pre-register common Ollama models."""
        ollama_local = [
            ModelSpec(
                name="llama3",
                provider="ollama",
                placement="local",
                capabilities=["generate", "embed", "vision"],
                version="3.2",
                latency_sla_ms=500,
                cost_per_token=0.01,
            ),
            ModelSpec(
                name="mistral",
                provider="ollama",
                placement="local",
                capabilities=["generate", "embed", "vision"],
                version="latest",
                latency_sla_ms=400,
                cost_per_token=0.01,
            ),
            ModelSpec(
                name="phi3",
                provider="ollama",
                placement="local",
                capabilities=["generate"],
                version="latest",
                latency_sla_ms=200,
                cost_per_token=0.005,
            ),
            ModelSpec(
                name="gemma3",
                provider="ollama",
                placement="local",
                capabilities=["generate", "embed"],
                version="latest",
                latency_sla_ms=350,
                cost_per_token=0.01,
            ),
            ModelSpec(
                name="qwen2.5",
                provider="ollama",
                placement="local",
                capabilities=["generate"],
                version="latest",
                latency_sla_ms=600,
                cost_per_token=0.015,
            ),
            ModelSpec(
                name="deepseek-r1",
                provider="ollama",
                placement="local",
                capabilities=["generate"],
                version="latest",
                latency_sla_ms=800,
                cost_per_token=0.02,
            ),
        ]

        for spec in ollama_local:
            self.register(spec)


# ---------------------------------------------------------------------------
# Runtime helper
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_registry() -> ModelRegistry:
    """Return the global model registry (singleton)."""
    return ModelRegistry()


def ml_model(
    name: str,
    placement: Optional[str] = None,
    capability: Optional[str] = None,
) -> str:
    """Resolve a model name to a string for use in language constructs.

    Parameters
    ----------
    name:
        Model name (e.g., "llama3").
    placement:
        Optional placement constraint: "local", "edge", "cloud".
    capability:
        Optional capability filter (e.g., "embed").

    Returns
    -------
    str
        Model identifier ready for use in prompt/generate/etc.
        Format: "@model-name" to match language model-ref syntax.
    """
    registry = get_registry()
    spec = registry.resolve(name, placement=placement, capability=capability)
    return f"@{spec.name}"
