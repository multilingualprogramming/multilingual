# pylint: disable=trailing-newlines
#

# SPDX-FileCopyrightText: 2024 John Samuel <johnsamuelwrites@gmail.com>

#

# SPDX-License-Identifier: GPL-3.0-or-later

#



"""Shared helpers for parser/codegen/executor tests."""



from multilingualprogramming.codegen.executor import ProgramExecutor

from multilingualprogramming.codegen.python_generator import PythonCodeGenerator

from multilingualprogramming.lexer.lexer import Lexer

from multilingualprogramming.parser.parser import Parser

from multilingualprogramming.runtime.ai_runtime import AIRuntime, AIProvider

from multilingualprogramming.runtime.ai_types import (

    EmbeddingVector,

    Plan,

    PromptResult,

    Reasoning,

    StreamChunk,

)





def parse_source(source, language="en"):

    """Tokenize and parse source code."""

    lexer = Lexer(source, language=language)

    tokens = lexer.tokenize()

    parser = Parser(tokens, source_language=language)

    return parser.parse()





def generate_python(source, language="en"):

    """Parse and generate Python source."""

    prog = parse_source(source, language)

    gen = PythonCodeGenerator()

    return gen.generate(prog).strip()





def execute_source(source, language="en", check_semantics=False):

    """Run the full execution pipeline."""

    executor = ProgramExecutor(language=language, check_semantics=check_semantics)

    return executor.execute(source)





class InvariantAIProvider(AIProvider):

    """Language-invariant AI provider for cross-language regression tests."""



    def prompt(self, model, template, **kwargs):

        del template, kwargs

        return PromptResult(content="mock-ai", model=model.name)



    def embed(self, model, text, **kwargs):

        del text, kwargs

        return EmbeddingVector(

            values=[0.25, 0.5, 0.75, 1.0],

            model=model.name,

            dimensions=4,

        )



    def generate(self, model, template, target_type=None, **kwargs):

        del model, template, target_type, kwargs

        return "mock-generate"



    def think(self, model, template, **kwargs):

        del template, kwargs

        return Reasoning(trace="mock-trace", conclusion="mock-think", model=model.name)



    def stream(self, model, template, **kwargs):

        del model, template, kwargs

        yield StreamChunk(content="mock-stream", is_final=True)



    def plan(self, model, goal, **kwargs):

        del model, goal, kwargs

        plan = Plan(goal="mock-goal")

        plan.add_step("mock-plan")

        return plan



    def transcribe(self, model, source, **kwargs):

        del model, source, kwargs

        return "mock-transcribe"





def register_invariant_ai_provider():

    """Register a deterministic provider for AI-native execution tests."""

    AIRuntime.register(InvariantAIProvider())

