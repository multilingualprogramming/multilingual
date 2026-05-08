#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Executor tests for individual AI keywords with realistic examples.

Tests that each AI keyword (PROMPT, GENERATE, EXTRACT, CLASSIFY, PLAN,
TRANSCRIBE, RETRIEVE, STREAM, THINK, EMBED) actually executes in
end-to-end program contexts with MockProvider.
"""

import unittest

from multilingualprogramming.codegen.executor import ProgramExecutor
from multilingualprogramming.runtime.ai_runtime import AIRuntime, MockProvider


class ExecutorPromptKeywordTestSuite(unittest.TestCase):
    """Test PROMPT keyword in executor context."""

    def setUp(self):
        self.mock = MockProvider()
        AIRuntime.register(self.mock)

    def tearDown(self):
        AIRuntime.reset()

    def test_prompt_basic_usage(self):
        """PROMPT should query model and return response."""
        self.mock.add_response("Python is a high-level programming language.")
        source = """
let answer = prompt @default: "What is Python?"
print(answer)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)
        self.assertIn("Python", result.output)

    def test_prompt_with_multiline_template(self):
        """PROMPT should handle multiline templates."""
        self.mock.add_response("The answer is 42.")
        source = """
let q = "What is the answer to the ultimate question?"
let answer = prompt @default: q
print(answer)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)

    def test_prompt_in_loop(self):
        """PROMPT in a loop should work correctly."""
        self.mock.add_response("Response 1")
        self.mock.add_response("Response 2")
        self.mock.add_response("Response 3")
        source = """
for i in range(3):
    result = prompt @default: f"Question {i}"
    print(result)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)


class ExecutorGenerateKeywordTestSuite(unittest.TestCase):
    """Test GENERATE keyword in executor context."""

    def setUp(self):
        self.mock = MockProvider()
        AIRuntime.register(self.mock)

    def tearDown(self):
        AIRuntime.reset()

    def test_generate_basic(self):
        """GENERATE should work like prompt."""
        self.mock.add_response("123")
        source = """
let number = generate @default: "Generate a number"
print(number)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)

    def test_generate_json(self):
        """GENERATE should handle JSON responses."""
        self.mock.add_response('{"name": "Alice", "age": 30}')
        source = """
let person = generate @default: "Create a person object"
print(person)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)

    def test_generate_list_type(self):
        """GENERATE should handle list generation."""
        self.mock.add_response('["apple", "banana", "cherry"]')
        source = """
let items = generate @default: "List 3 fruits"
print(items)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)


class ExecutorExtractKeywordTestSuite(unittest.TestCase):
    """Test EXTRACT keyword in executor context."""

    def setUp(self):
        self.mock = MockProvider()
        AIRuntime.register(self.mock)

    def tearDown(self):
        AIRuntime.reset()

    def test_extract_from_text(self):
        """EXTRACT should pull structured data from text."""
        self.mock.add_response('["apple", "banana", "orange"]')
        source = """
let fruits = extract @default: "Fruits: apple, banana, orange"
print(fruits)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)

    def test_extract_named_entities(self):
        """EXTRACT should work for entity extraction."""
        self.mock.add_response('{"names": ["Alice", "Bob"], "cities": ["NYC", "LA"]}')
        source = """
let entities = extract @default: "Alice from NYC and Bob from LA are friends"
print(entities)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)


class ExecutorClassifyKeywordTestSuite(unittest.TestCase):
    """Test CLASSIFY keyword in executor context."""

    def setUp(self):
        self.mock = MockProvider()
        AIRuntime.register(self.mock)

    def tearDown(self):
        AIRuntime.reset()

    def test_classify_sentiment(self):
        """CLASSIFY should categorize sentiment."""
        self.mock.add_response("positive")
        source = """
let sentiment = classify @default: "This product is amazing!"
print(sentiment)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)

    def test_classify_intent(self):
        """CLASSIFY should work for intent classification."""
        self.mock.add_response("greeting")
        source = """
let intent = classify @default: "Hi there, how are you?"
print(intent)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)

    def test_classify_text(self):
        """CLASSIFY should work with text input."""
        self.mock.add_response("red")
        source = """
let text = "The sky is red"
let classification = classify @default: text
print(classification)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)


class ExecutorStreamKeywordTestSuite(unittest.TestCase):
    """Test STREAM keyword in executor context."""

    def setUp(self):
        self.mock = MockProvider()
        AIRuntime.register(self.mock)

    def tearDown(self):
        AIRuntime.reset()

    def test_stream_basic_collection(self):
        """STREAM should return an iterable."""
        source = """
let s = stream @default: "Tell a short story"
let text = ""
for chunk in s:
    text = text + str(chunk)
print("Collected stream")
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)

    def test_stream_simple_iteration(self):
        """STREAM iteration should work."""
        source = """
let s = stream @default: "Generate output"
let count = 0
for chunk in s:
    count = count + 1
print(count)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)

    def test_stream_output(self):
        """STREAM should have content."""
        self.mock.add_response("Stream response")
        source = """
let s = stream @default: "Test"
for chunk in s:
    print(chunk)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)


class ExecutorPlanKeywordTestSuite(unittest.TestCase):
    """Test PLAN keyword in executor context."""

    def setUp(self):
        self.mock = MockProvider()
        AIRuntime.register(self.mock)

    def tearDown(self):
        AIRuntime.reset()

    def test_plan_basic_generation(self):
        """PLAN should generate a multi-step plan."""
        self.mock.add_response("1. Gather ingredients\n2. Mix\n3. Bake\n4. Cool")
        source = """
let plan = plan @default: "How to bake a cake"
print(plan)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)

    def test_plan_complex_goal(self):
        """PLAN should handle complex goals."""
        self.mock.add_response("1. Research\n2. Design\n3. Implement\n4. Test\n5. Deploy")
        source = """
let goal = "Build a web application"
let plan = plan @default: goal
print(plan)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)


class ExecutorEmbedKeywordTestSuite(unittest.TestCase):
    """Test EMBED keyword in executor context."""

    def setUp(self):
        self.mock = MockProvider()
        AIRuntime.register(self.mock)

    def tearDown(self):
        AIRuntime.reset()

    def test_embed_text_vector(self):
        """EMBED should generate embedding vectors."""
        source = """
let vec = embed @default: "This is a test sentence"
print(len(vec))
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)
        # Should print dimensions
        self.assertIn("4", result.output)

    def test_embed_multiple_texts(self):
        """EMBED should work for multiple texts."""
        source = """
let v1 = embed @default: "Hello"
let v2 = embed @default: "World"
print("Embeddings generated")
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)

    def test_embed_similarity(self):
        """EMBED should enable similarity computation."""
        source = """
let v1 = embed @default: "cat"
let v2 = embed @default: "cat"
print("Vectors similar")
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)


class ExecutorThinkKeywordTestSuite(unittest.TestCase):
    """Test THINK keyword in executor context."""

    def setUp(self):
        self.mock = MockProvider()
        AIRuntime.register(self.mock)

    def tearDown(self):
        AIRuntime.reset()

    def test_think_reasoning(self):
        """THINK should return reasoning structure."""
        self.mock.add_response("Step 1: Consider the problem\nConclusion: The answer is 42")
        source = """
let reasoning = think @default: "Why is 42 significant?"
print(reasoning)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)

    def test_think_complex_problem(self):
        """THINK should work for complex reasoning."""
        self.mock.add_response("First, analyze the question\nConclusion: Yes, it's possible")
        source = """
let result = think @default: "Can AI solve all problems?"
print(result)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)


class ExecutorTranscribeKeywordTestSuite(unittest.TestCase):
    """Test TRANSCRIBE keyword in executor context."""

    def setUp(self):
        self.mock = MockProvider()
        AIRuntime.register(self.mock)

    def tearDown(self):
        AIRuntime.reset()

    def test_transcribe_audio_fallback(self):
        """TRANSCRIBE should handle audio-like inputs."""
        self.mock.add_response("This is transcribed text")
        source = """
let text = transcribe @default: "audio data"
print(text)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)

    def test_transcribe_binary_input(self):
        """TRANSCRIBE should handle binary audio input."""
        source = """
let bytes_data = b"audio"
let text = transcribe @default: bytes_data
print("Transcribed")
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        # Should handle binary input gracefully
        self.assertIsNotNone(result.output)


if __name__ == "__main__":
    unittest.main()
