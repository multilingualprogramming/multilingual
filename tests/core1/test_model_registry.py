#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Tests for model registry and versioning."""
# pylint: disable=missing-class-docstring

import pytest

from multilingualprogramming.runtime.model_registry import (
    ModelRegistry,
    ModelSpec,
    get_registry,
    ml_model,
)


class TestModelSpec:
    def test_model_spec_creation(self):
        spec = ModelSpec(
            name="llama3",
            provider="ollama",
            placement="local",
            version="3.2",
        )
        assert spec.name == "llama3"
        assert spec.version == "3.2"

    def test_supports_capability(self):
        spec = ModelSpec(name="m", capabilities=["generate", "embed"])
        assert spec.supports("generate")
        assert spec.supports("embed")
        assert not spec.supports("classify")

    def test_model_spec_defaults(self):
        spec = ModelSpec(name="m")
        assert spec.provider == ""
        assert spec.placement == "local"
        assert spec.version == "latest"
        assert spec.capabilities == []

    def test_model_spec_repr(self):
        spec = ModelSpec(name="test", version="1.0", placement="cloud")
        repr_str = repr(spec)
        assert "test" in repr_str
        assert "1.0" in repr_str


class TestModelRegistry:
    def test_default_registry_has_ollama_models(self):
        registry = ModelRegistry()
        names = registry.list_models()
        assert "llama3" in names
        assert "mistral" in names
        assert "phi3" in names

    def test_resolve_by_name(self):
        registry = ModelRegistry()
        spec = registry.resolve("llama3")
        assert spec.name == "llama3"
        assert spec.provider == "ollama"

    def test_resolve_by_placement(self):
        registry = ModelRegistry()
        spec = registry.resolve("llama3", placement="local")
        assert spec.placement == "local"

    def test_resolve_unknown_model_raises(self):
        registry = ModelRegistry()
        with pytest.raises(KeyError, match="Unknown model"):
            registry.resolve("nonexistent")

    def test_resolve_wrong_placement_raises(self):
        registry = ModelRegistry()
        with pytest.raises(KeyError, match="not available for placement"):
            registry.resolve("llama3", placement="cloud")

    def test_resolve_by_capability(self):
        registry = ModelRegistry()
        spec = registry.resolve("llama3", capability="embed")
        assert spec.supports("embed")

    def test_resolve_missing_capability_raises(self):
        registry = ModelRegistry()
        with pytest.raises(KeyError, match="does not support capability"):
            registry.resolve("phi3", capability="embed")

    def test_register_new_model(self):
        registry = ModelRegistry()
        spec = ModelSpec(
            name="custom-model",
            provider="test",
            placement="edge",
            version="1.0",
        )
        registry.register(spec)

        resolved = registry.resolve("custom-model", placement="edge")
        assert resolved.name == "custom-model"
        assert resolved.version == "1.0"

    def test_register_overwrites_same_version(self):
        registry = ModelRegistry()
        spec1 = ModelSpec(name="m", version="1.0", cost_per_token=0.5)
        spec2 = ModelSpec(name="m", version="1.0", cost_per_token=0.1)

        registry.register(spec1)
        registry.register(spec2)

        resolved = registry.resolve("m")
        assert resolved.cost_per_token == 0.1

    def test_best_for_returns_lowest_cost(self):
        registry = ModelRegistry()
        spec = registry.best_for("generate", placement="local")
        assert spec.placement == "local"

    def test_best_for_with_latency_sla(self):
        registry = ModelRegistry()
        spec = registry.best_for("generate", placement="local", max_latency_ms=300)
        assert spec.latency_sla_ms <= 300

    def test_best_for_no_matching_model_raises(self):
        registry = ModelRegistry()
        with pytest.raises(KeyError):
            registry.best_for("generate", placement="mars")

    def test_list_models_all(self):
        registry = ModelRegistry()
        names = registry.list_models()
        assert isinstance(names, list)
        assert len(names) > 0
        assert names == sorted(names)

    def test_list_models_by_placement(self):
        registry = ModelRegistry()
        local_models = registry.list_models(placement="local")
        assert len(local_models) > 0
        for name in local_models:
            spec = registry.resolve(name, placement="local")
            assert spec.placement == "local"


class TestGlobalRegistry:
    def test_get_registry_returns_singleton(self):
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_ml_model_returns_model_string(self):
        result = ml_model("llama3", placement="local")
        assert isinstance(result, str)
        assert "@" in result
        assert "llama3" in result

    def test_ml_model_with_capability(self):
        result = ml_model("mistral", capability="embed")
        assert isinstance(result, str)
        assert "@mistral" in result
