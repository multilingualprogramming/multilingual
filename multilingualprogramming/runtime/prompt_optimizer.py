#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Multilingual prompt template optimization.

Provides language-aware prompt templates that can be rendered in multiple
human languages, with token cost estimation and budget tracking.

This is especially useful for edge computing where local model tokens have
real cost (memory, latency, inference time).

Usage
-----
    from multilingualprogramming.runtime.prompt_optimizer import (
        PromptTemplate, PromptOptimizer
    )

    # Define prompts in multiple languages
    tmpl = PromptTemplate({
        "en": "Analyze this text: {text}",
        "fr": "Analyser ce texte: {text}",
        "es": "Analizar este texto: {text}"
    })

    rendered_en = tmpl.render("en", text="hello world")
    rendered_fr = tmpl.render("fr", text="bonjour monde")

    # Optimize with cost budget
    optimizer = PromptOptimizer()
    optimized = optimizer.optimize(tmpl, "en", max_tokens=100)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str) -> int:
    """Estimate token count from text using character heuristic.

    This is a rough heuristic: ~4 characters per token on average for English.
    For multilingual text, it's approximate.
    """
    # Rough heuristic: 1 token â‰ˆ 4 characters
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Cost budget
# ---------------------------------------------------------------------------

@dataclass
class CostBudget:
    """Token cost budget tracker.

    Parameters
    ----------
    max_tokens:
        Maximum tokens allowed for this operation.
    warn_threshold:
        Warn if estimated tokens exceed this percentage of max_tokens.
    """

    max_tokens: int = 1000
    warn_threshold: float = 0.8

    def check(self, estimated_tokens: int) -> tuple[bool, str]:
        """Check if token count is within budget.

        Returns
        -------
        (within_budget, message)
            within_budget: True if estimated_tokens <= max_tokens
            message: Warning or OK message
        """
        if estimated_tokens > self.max_tokens:
            return False, f"Exceeds budget: {estimated_tokens} > {self.max_tokens}"

        if estimated_tokens > self.max_tokens * self.warn_threshold:
            pct = 100.0 * estimated_tokens / self.max_tokens
            return True, f"Warning: using {pct:.0f}% of budget"

        return True, "OK"


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

class PromptTemplate:
    """Multi-language prompt template.

    Holds the same prompt in multiple human languages and can render
    one based on language code.

    Parameters
    ----------
    templates:
        Dict mapping language code (e.g., "en", "fr") to prompt string.
        Each string can contain {variable} placeholders.
    """

    def __init__(self, templates: dict[str, str]) -> None:
        self._templates = templates
        self._default_lang = "en" if "en" in templates else next(iter(templates))

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, language: str, **variables) -> str:
        """Render the prompt in the specified language.

        Falls back to default language if the requested language is unavailable.

        Parameters
        ----------
        language:
            Language code (e.g., "en", "fr", "es").
        **variables:
            Keyword arguments to fill in {placeholder} positions.

        Returns
        -------
        str
            Rendered prompt string.
        """
        lang = language if language in self._templates else self._default_lang
        template = self._templates.get(lang, self._templates[self._default_lang])

        try:
            return template.format(**variables)
        except KeyError as exc:
            raise ValueError(f"Missing variable in prompt template: {exc}") from exc

    def languages(self) -> list[str]:
        """Return all available language codes."""
        return sorted(self._templates.keys())

    def has_language(self, language: str) -> bool:
        """Return True if this language is available."""
        return language in self._templates

    def __repr__(self) -> str:
        langs = ", ".join(self.languages())
        return f"PromptTemplate(languages={langs})"


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

class PromptOptimizer:
    """Optimize prompts across languages with cost budgeting.

    Estimates token counts for prompts and helps select the most efficient
    language variant under a cost budget.
    """

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Optimization
    # ------------------------------------------------------------------

    def optimize(
        self,
        template: PromptTemplate,
        language: str,
        max_tokens: Optional[int] = None,
        warn_threshold: float = 0.8,
    ) -> str:
        """Optimize and render a prompt under a token budget.

        Parameters
        ----------
        template:
            PromptTemplate with multi-language variants.
        language:
            Preferred language code.
        max_tokens:
            Maximum token budget. If None, no limit.
        warn_threshold:
            Warn if token usage exceeds this percentage of max_tokens.

        Returns
        -------
        str
            Rendered and optimized prompt.

        Raises
        ------
        ValueError:
            If rendered prompt exceeds max_tokens.
        """
        rendered = template.render(language)
        estimated = _estimate_tokens(rendered)

        if max_tokens is not None:
            budget = CostBudget(max_tokens=max_tokens, warn_threshold=warn_threshold)
            within_budget, message = budget.check(estimated)

            if not within_budget:
                raise ValueError(f"Prompt optimization failed: {message}")

            if not message.startswith("OK"):
                print(f"Warning: {message}")

        return rendered

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for arbitrary text."""
        return _estimate_tokens(text)

    def find_shortest_language(self, template: PromptTemplate) -> str:
        """Return the language with the shortest rendered prompt.

        Useful for finding the most cost-efficient language variant.
        This requires rendering all variants, so use sparingly.
        """
        min_lang = template.languages()[0]
        min_tokens = _estimate_tokens(template.render(min_lang))

        for lang in template.languages()[1:]:
            rendered = template.render(lang)
            tokens = _estimate_tokens(rendered)
            if tokens < min_tokens:
                min_lang = lang
                min_tokens = tokens

        return min_lang

    # ------------------------------------------------------------------
    # Preset templates
    # ------------------------------------------------------------------

    @staticmethod
    def sentiment_template() -> PromptTemplate:
        """Return a sentiment analysis template in multiple languages."""
        return PromptTemplate(
            {
                "en": (
                    "Analyze the sentiment of the following text:\n{text}\n\n"
                    "Classify as: positive, negative, or neutral."
                ),
                "fr": (
                    "Analyser le sentiment du texte suivant:\n{text}\n\n"
                    "Classez comme: positif, nÃ©gatif ou neutre."
                ),
                "es": (
                    "Analizar el sentimiento del siguiente texto:\n{text}\n\n"
                    "Clasifique como: positivo, negativo o neutral."
                ),
                "de": (
                    "Analysieren Sie das Sentiment des folgenden Textes:\n{text}\n\n"
                    "Klassifizieren Sie als: positiv, negativ oder neutral."
                ),
            }
        )

    @staticmethod
    def summarization_template() -> PromptTemplate:
        """Return a summarization template in multiple languages."""
        return PromptTemplate(
            {
                "en": "Summarize the following text in 2-3 sentences:\n{text}",
                "fr": "RÃ©sumez le texte suivant en 2-3 phrases:\n{text}",
                "es": "Resuma el siguiente texto en 2-3 oraciones:\n{text}",
                "de": "Fassen Sie den folgenden Text in 2-3 SÃ¤tzen zusammen:\n{text}",
            }
        )

    @staticmethod
    def extraction_template() -> PromptTemplate:
        """Return a key-phrase extraction template in multiple languages."""
        return PromptTemplate(
            {
                "en": (
                    "Extract the most important key phrases from:\n{text}\n\n"
                    "Return as a comma-separated list."
                ),
                "fr": (
                    "Extrayez les phrases clÃ©s les plus importantes de:\n{text}\n\n"
                    "Retournez sous forme de liste sÃ©parÃ©e par des virgules."
                ),
                "es": (
                    "Extraiga las frases clave mÃ¡s importantes de:\n{text}\n\n"
                    "Devuelva como una lista separada por comas."
                ),
                "de": (
                    "Extrahieren Sie die wichtigsten SchlÃ¼sselphrases aus:\n{text}\n\n"
                    "Geben Sie als durch Kommas getrennte Liste zurÃ¼ck."
                ),
            }
        )
