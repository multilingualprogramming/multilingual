#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Tests for multilingual prompt templates and optimization."""
# pylint: disable=missing-class-docstring

import pytest

from multilingualprogramming.runtime.prompt_optimizer import (
    CostBudget,
    PromptOptimizer,
    PromptTemplate,
    _estimate_tokens,
)


class TestTokenEstimation:
    def test_empty_string_is_one_token(self):
        assert _estimate_tokens("") >= 1

    def test_short_string(self):
        # "Hello" = 5 chars ≈ 1-2 tokens
        tokens = _estimate_tokens("Hello")
        assert 1 <= tokens <= 2

    def test_longer_string(self):
        # 100 characters ≈ 25 tokens
        text = "a" * 100
        tokens = _estimate_tokens(text)
        assert 20 <= tokens <= 30

    def test_english_sentence(self):
        text = "The quick brown fox jumps over the lazy dog."
        tokens = _estimate_tokens(text)
        assert tokens > 0


class TestCostBudget:
    def test_within_budget(self):
        budget = CostBudget(max_tokens=100)
        ok, _msg = budget.check(50)
        assert ok is True

    def test_exceeds_budget(self):
        budget = CostBudget(max_tokens=100)
        ok, msg = budget.check(150)
        assert ok is False
        assert "Exceeds" in msg

    def test_warns_at_threshold(self):
        budget = CostBudget(max_tokens=100, warn_threshold=0.8)
        ok, msg = budget.check(85)
        assert ok is True
        assert "Warning" in msg

    def test_ok_when_well_below_threshold(self):
        budget = CostBudget(max_tokens=100, warn_threshold=0.8)
        ok, msg = budget.check(50)
        assert ok is True
        assert "OK" in msg


class TestPromptTemplate:
    def test_single_language_template(self):
        tmpl = PromptTemplate({"en": "Hello {name}"})
        rendered = tmpl.render("en", name="World")
        assert rendered == "Hello World"

    def test_multilingual_template(self):
        tmpl = PromptTemplate({
            "en": "Hello {name}",
            "fr": "Bonjour {name}",
            "es": "Hola {name}",
        })
        assert tmpl.render("en", name="Alice") == "Hello Alice"
        assert tmpl.render("fr", name="Alice") == "Bonjour Alice"
        assert tmpl.render("es", name="Alice") == "Hola Alice"

    def test_fallback_to_default_language(self):
        tmpl = PromptTemplate({"en": "Default", "fr": "Francais"})
        # Request unsupported language, should fall back to default
        rendered = tmpl.render("de")
        assert rendered in ["Default", "Francais"]

    def test_render_missing_variable_raises(self):
        tmpl = PromptTemplate({"en": "Hello {name}"})
        with pytest.raises(ValueError):
            tmpl.render("en")

    def test_languages_list(self):
        tmpl = PromptTemplate({
            "en": "English",
            "fr": "French",
            "es": "Spanish",
        })
        langs = tmpl.languages()
        assert set(langs) == {"en", "es", "fr"}
        assert langs == sorted(langs)

    def test_has_language(self):
        tmpl = PromptTemplate({"en": "E", "fr": "F"})
        assert tmpl.has_language("en")
        assert tmpl.has_language("fr")
        assert not tmpl.has_language("de")

    def test_repr(self):
        tmpl = PromptTemplate({"en": "E", "fr": "F"})
        repr_str = repr(tmpl)
        assert "PromptTemplate" in repr_str

    def test_multiple_variable_placeholders(self):
        tmpl = PromptTemplate({
            "en": "Analyze {topic} with {style} approach"
        })
        rendered = tmpl.render("en", topic="AI", style="analytical")
        assert rendered == "Analyze AI with analytical approach"


class TestPromptOptimizer:
    def test_optimize_renders_template(self):
        optimizer = PromptOptimizer()
        # optimize() doesn't fill in variables, so use a template without placeholders
        tmpl_no_vars = PromptTemplate({"en": "Question without variables"})
        result = optimizer.optimize(tmpl_no_vars, "en", max_tokens=100)
        assert result == "Question without variables"

    def test_optimize_without_budget(self):
        optimizer = PromptOptimizer()
        tmpl = PromptTemplate({"en": "Long " + "text " * 100})
        result = optimizer.optimize(tmpl, "en")
        assert isinstance(result, str)

    def test_optimize_within_budget_succeeds(self):
        optimizer = PromptOptimizer()
        tmpl = PromptTemplate({"en": "Short"})
        result = optimizer.optimize(tmpl, "en", max_tokens=100)
        assert result == "Short"

    def test_optimize_exceeds_budget_raises(self):
        optimizer = PromptOptimizer()
        # Create a very long prompt
        long_text = "word " * 1000
        tmpl = PromptTemplate({"en": long_text})
        with pytest.raises(ValueError, match="Exceeds|exceeded"):
            optimizer.optimize(tmpl, "en", max_tokens=10)

    def test_estimate_tokens(self):
        optimizer = PromptOptimizer()
        tokens = optimizer.estimate_tokens("Hello world this is a test")
        assert tokens > 0

    def test_find_shortest_language(self):
        optimizer = PromptOptimizer()
        tmpl = PromptTemplate({
            "en": "The quick brown fox jumps over the lazy dog",
            "fr": "Bonjour",
            "es": "Hola mundo",
        })
        shortest = optimizer.find_shortest_language(tmpl)
        assert shortest == "fr"

    def test_sentiment_template(self):
        tmpl = PromptOptimizer.sentiment_template()
        assert tmpl.has_language("en")
        assert tmpl.has_language("fr")
        assert tmpl.has_language("es")
        rendered = tmpl.render("en", text="This is good")
        assert "sentiment" in rendered.lower()

    def test_summarization_template(self):
        tmpl = PromptOptimizer.summarization_template()
        assert len(tmpl.languages()) > 0
        rendered = tmpl.render("en", text="Long text to summarize")
        assert "Summarize" in rendered or "summarize" in rendered

    def test_extraction_template(self):
        tmpl = PromptOptimizer.extraction_template()
        rendered = tmpl.render("en", text="Sample text")
        assert "Extract" in rendered or "extract" in rendered

    def test_template_preset_languages(self):
        """All preset templates should be multilingual."""
        for template_fn in [
            PromptOptimizer.sentiment_template,
            PromptOptimizer.summarization_template,
            PromptOptimizer.extraction_template,
        ]:
            tmpl = template_fn()
            langs = tmpl.languages()
            assert len(langs) >= 2, f"{template_fn.__name__} should be multilingual"
