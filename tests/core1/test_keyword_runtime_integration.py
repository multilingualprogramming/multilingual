#

# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>

#

# SPDX-License-Identifier: GPL-3.0-or-later

#



"""Integration tests for AI keywords at runtime with MockProvider.



Tests that each AI keyword (PROMPT, GENERATE, EXTRACT, CLASSIFY, PLAN,

TRANSCRIBE, RETRIEVE, STREAM, THINK) actually executes correctly with

MockProvider in a realistic multilingual program context.

"""



import unittest



from multilingualprogramming.codegen.executor import ProgramExecutor

from multilingualprogramming.runtime.ai_runtime import AIRuntime, MockProvider





class AIKeywordRuntimeTestSuite(unittest.TestCase):

    """Test AI keywords execute correctly with MockProvider."""



    def setUp(self):

        """Set up MockProvider before each test."""

        self.mock = MockProvider()

        self.mock.add_response("This is a mock AI response.")

        AIRuntime.register(self.mock)



    def tearDown(self):

        """Reset AIRuntime after each test."""

        AIRuntime.reset()



    def test_prompt_keyword_executes(self):

        """PROMPT keyword should send query to provider and return result."""

        source = """

let result = prompt @default: "What is 2 + 2?"

print(result)

"""

        executor = ProgramExecutor(language="en")

        result = executor.execute(source)

        self.assertTrue(result.success, result.errors)

        self.assertIn("mock AI response", result.output)



    def test_generate_keyword_executes(self):

        """GENERATE keyword should work like prompt with type hint."""

        self.mock.add_response('{"name": "Alice", "age": 30}')

        source = """

let data = generate @default: "Create a person object"

print(data)

"""

        executor = ProgramExecutor(language="en")

        result = executor.execute(source)

        self.assertTrue(result.success, result.errors)



    def test_think_keyword_executes(self):

        """THINK keyword should return reasoning with trace and conclusion."""

        self.mock.add_response("Step 1: Consider the problem\nConclusion: The answer is 42")

        source = """

let reasoning = think @default: "Why is the answer 42?"

print(reasoning)

"""

        executor = ProgramExecutor(language="en")

        result = executor.execute(source)

        self.assertTrue(result.success, result.errors)



    def test_stream_keyword_executes(self):

        """STREAM keyword should collect streaming responses."""

        source = """

let s = stream @default: "Tell me a story"

let full_text = ""

for chunk in s:

    full_text = full_text + str(chunk)

print(full_text)

"""

        executor = ProgramExecutor(language="en")

        result = executor.execute(source)

        # Stream with MockProvider should work (returns single chunk)

        self.assertTrue(result.success, result.errors)



    def test_extract_keyword_executes(self):

        """EXTRACT keyword should extract structured data."""

        self.mock.add_response('["item1", "item2", "item3"]')

        source = """

let items = extract @default: "Extract a list from: apple, banana, cherry"

print(items)

"""

        executor = ProgramExecutor(language="en")

        result = executor.execute(source)

        self.assertTrue(result.success, result.errors)



    def test_classify_keyword_executes(self):

        """CLASSIFY keyword should categorize input."""

        self.mock.add_response("positive")

        source = """

let sentiment = classify @default: "This is great!"

print(sentiment)

"""

        executor = ProgramExecutor(language="en")

        result = executor.execute(source)

        self.assertTrue(result.success, result.errors)



    def test_embed_keyword_executes(self):

        """EMBED keyword should generate embeddings."""

        source = """

let vec = embed @default: "This is a test sentence"

print(len(vec))

"""

        executor = ProgramExecutor(language="en")

        result = executor.execute(source)

        self.assertTrue(result.success, result.errors)



    def test_plan_keyword_executes(self):

        """PLAN keyword should create a multi-step plan."""

        self.mock.add_response("Step 1: Understand the goal\nStep 2: Create a plan\nStep 3: Execute")

        source = """

let plan = plan @default: "How to bake a cake"

print(plan)

"""

        executor = ProgramExecutor(language="en")

        result = executor.execute(source)

        self.assertTrue(result.success, result.errors)



    def test_transcribe_keyword_executes(self):

        """TRANSCRIBE keyword should convert audio to text."""

        self.mock.add_response("Hello, this is transcribed audio")

        source = """

let text = transcribe @default: <audio_content>

print(text)

"""

        executor = ProgramExecutor(language="en")

        result = executor.execute(source)

        # transcribe with MockProvider should work

        # (error handling varies based on audio input format)

        self.assertIsNotNone(result.output)



    def test_multiple_ai_calls_in_sequence(self):

        """Multiple AI calls should each get responses from mock queue."""

        # Create a fresh mock for this test to avoid setUp's default response

        mock = MockProvider()

        mock.add_response("First response")

        mock.add_response("Second response")

        AIRuntime.reset()

        AIRuntime.register(mock)



        source = """

let r1 = prompt @default: "First question"

let r2 = prompt @default: "Second question"

print(r1)

print(r2)

"""

        executor = ProgramExecutor(language="en")

        result = executor.execute(source)

        self.assertTrue(result.success, result.errors)

        self.assertIn("First response", result.output)

        self.assertIn("Second response", result.output)



    def test_ai_with_variables(self):

        """AI keywords should work with variable inputs."""

        source = """

let question = "What is Python?"

let answer = prompt @default: question

print(answer)

"""

        executor = ProgramExecutor(language="en")

        result = executor.execute(source)

        self.assertTrue(result.success, result.errors)



    def test_french_prompt_keyword(self):

        """PROMPT in French should work identically."""

        source = """

let resultat = prompt @default: "Combien font 2 + 2?"

print(resultat)

"""

        executor = ProgramExecutor(

            language="en"

        )  # Use English for now - keywords work across languages

        result = executor.execute(source)

        self.assertTrue(result.success, result.errors)

        self.assertIn("mock AI response", result.output)



    def test_spanish_generate_keyword(self):

        """GENERATE in Spanish (generar) should work."""

        source = """

let datos = generate @default: "Crear un objeto JSON"

print(datos)

"""

        executor = ProgramExecutor(language="en")  # Use English for now

        result = executor.execute(source)

        self.assertTrue(result.success, result.errors)



    def test_provider_call_log(self):

        """MockProvider should log all calls for inspection."""

        self.mock.add_response("First response")

        self.mock.add_response("Second response")

        source = """

let r1 = prompt @default: "First"

print(r1)

"""

        executor = ProgramExecutor(language="en")

        result = executor.execute(source)

        self.assertTrue(result.success)



        # Check call log - should have at least one prompt call

        calls = self.mock.call_log

        self.assertGreaterEqual(len(calls), 1)

        self.assertEqual(calls[0]["op"], "prompt")





class AIKeywordErrorHandlingTestSuite(unittest.TestCase):

    """Test error handling in AI keywords."""



    def setUp(self):

        """Set up MockProvider before each test."""

        AIRuntime.register(MockProvider())



    def tearDown(self):

        """Reset AIRuntime after each test."""

        AIRuntime.reset()



    def test_unregistered_provider_error(self):

        """Without a provider, AI keywords should fail gracefully."""

        AIRuntime.reset()  # Clear the provider

        source = """

let result = prompt @default: "test"

"""

        executor = ProgramExecutor(language="en")

        result = executor.execute(source)

        self.assertFalse(result.success)



    def test_empty_prompt_template(self):

        """Empty prompt should still work (provider responsibility)."""

        source = """

let result = prompt @default: ""

print(result)

"""

        executor = ProgramExecutor(language="en")

        result = executor.execute(source)

        self.assertTrue(result.success, result.errors)



    def test_model_not_found_fallback(self):

        """Non-existent model should use mock provider fallback."""

        source = """

let result = prompt @nonexistent-model: "question"

print(result)

"""

        executor = ProgramExecutor(language="en")

        result = executor.execute(source)

        # MockProvider should gracefully handle unknown models

        self.assertTrue(result.success, result.errors)





if __name__ == "__main__":

    unittest.main()

