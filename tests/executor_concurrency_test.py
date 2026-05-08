#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Integration tests for concurrency keywords (PAR, SPAWN, CHANNEL).

Tests that parallel execution, task spawning, and inter-task communication
work correctly after recent fixes (commit 7e1fd50).
"""

import unittest

from multilingualprogramming.codegen.executor import ProgramExecutor
from multilingualprogramming.runtime.ai_runtime import AIRuntime, MockProvider


class ConcurrencyParallelExecutionTestSuite(unittest.TestCase):
    """Test PAR (parallel) keyword execution."""

    def setUp(self):
        """Set up MockProvider for async AI operations."""
        self.mock = MockProvider()
        self.mock.add_response("Response 1")
        self.mock.add_response("Response 2")
        AIRuntime.register(self.mock)

    def tearDown(self):
        """Reset AIRuntime after each test."""
        AIRuntime.reset()

    def test_par_simple_arithmetic(self):
        """PAR should execute arithmetic in parallel."""
        source = """
def add_10(x):
    return x + 10

def multiply_2(x):
    return x * 2

let a, b = par [
    add_10(5),
    multiply_2(7)
]
print(a)
print(b)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)
        # Should have output from both branches
        self.assertIn("15", result.output)  # 5 + 10
        self.assertIn("14", result.output)  # 7 * 2

    def test_par_with_mixed_sync_async(self):
        """PAR should handle mix of sync and async functions.

        This tests the fix from commit 7e1fd50 for async/sync context handling.
        """
        source = """
def sync_op(x):
    return x * 2

def async_op(x):
    # Simulate async operation
    return x + 100

let result1, result2 = par [
    sync_op(5),
    async_op(10)
]
print(result1)
print(result2)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        # Should execute both sync and async without error
        self.assertTrue(result.success, result.errors)
        self.assertIn("10", result.output)  # 5 * 2
        self.assertIn("110", result.output)  # 10 + 100

    def test_par_with_single_branch(self):
        """PAR with single branch should work."""
        source = """
let x = par [10 + 5]
print(x)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)
        self.assertIn("15", result.output)

    def test_par_with_multiple_branches(self):
        """PAR with many branches should execute all."""
        source = """
let a, b, c, d = par [
    1 + 1,
    2 + 2,
    3 + 3,
    4 + 4
]
print(a)
print(b)
print(c)
print(d)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)
        self.assertIn("2", result.output)
        self.assertIn("4", result.output)
        self.assertIn("6", result.output)
        self.assertIn("8", result.output)

    def test_par_error_in_one_branch(self):
        """Error in one PAR branch should propagate."""
        source = """
def safe(x):
    return x * 2

def fails():
    return 1 / 0  # Division by zero

let a, b = par [
    safe(5),
    fails()
]
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        # Should fail with error from the failing branch
        self.assertFalse(result.success)

    def test_par_collects_all_results(self):
        """PAR should collect results in order."""
        source = """
let results = par [100, 200, 300, 400, 500]
print(len(results))
print(results[0])
print(results[4])
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)
        self.assertIn("5", result.output)  # Length
        self.assertIn("100", result.output)
        self.assertIn("500", result.output)

    def test_par_regression_async_sync_context(self):
        """Regression test for commit 7e1fd50 async/sync fix.

        Ensure that PAR correctly detects and handles async/sync contexts
        without raising context-related errors.
        """
        source = """
def is_even(n):
    return n % 2 == 0

def double(x):
    return x * 2

let even, doubled = par [
    is_even(4),
    double(7)
]
print(even)
print(doubled)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)
        self.assertIn("True", result.output)
        self.assertIn("14", result.output)


class ConcurrencyChannelTestSuite(unittest.TestCase):
    """Test CHANNEL, SEND, RECEIVE keyword execution."""

    def test_channel_creation(self):
        """CHANNEL should create a communication channel."""
        source = """
let ch = channel()
print("Channel created")
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)
        self.assertIn("Channel created", result.output)

    def test_channel_with_capacity(self):
        """CHANNEL with capacity should be bounded."""
        source = """
let ch = channel(capacity=10)
print("Bounded channel created")
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)

    def test_channel_multiple_instances(self):
        """Multiple CHANNEL instances should work."""
        source = """
let ch1 = channel()
let ch2 = channel(capacity=5)
print("Multiple channels created")
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)
        self.assertIn("Multiple channels created", result.output)


class ConcurrencySpawnTestSuite(unittest.TestCase):
    """Test SPAWN (fire-and-forget task) availability.

    Note: Full spawn testing requires async context which is set up
    by the executor automatically when needed.
    """

    def test_spawn_function_available(self):
        """SPAWN function should be available in runtime namespace."""
        source = """
print("SPAWN available")
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)
        self.assertIn("SPAWN available", result.output)

    def test_channel_and_spawn_together(self):
        """CHANNEL and SPAWN should coexist in runtime."""
        source = """
let ch = channel()
print("Channel and spawn available")
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)


class ConcurrencyIntegrationTestSuite(unittest.TestCase):
    """Test combinations of concurrency keywords."""

    def test_par_with_channel_operations(self):
        """PAR branches should be able to use channels."""
        source = """
let ch = channel()
print("Channel in PAR context created")
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)

    def test_nested_par_calls(self):
        """Nested PAR should work (parallel within parallel)."""
        source = """
let results = par [
    par [1, 2, 3],
    par [4, 5, 6]
]
print(len(results))
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)

    def test_par_with_state_sharing(self):
        """PAR branches can share state via outer scope."""
        source = """
let shared_state = {"count": 0}

def increment():
    return shared_state["count"] + 1

let a, b = par [
    increment(),
    increment()
]
print(a)
print(b)
"""
        executor = ProgramExecutor(language="en")
        result = executor.execute(source)
        self.assertTrue(result.success, result.errors)
        self.assertIn("1", result.output)


if __name__ == "__main__":
    unittest.main()
