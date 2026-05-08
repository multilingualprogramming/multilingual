"""Test ReactiveList signal implementation."""

import pytest
from multilingualprogramming.runtime.reactive import ReactiveList, ReactiveEngine


def test_reactive_list_get():
    """ReactiveList.get() returns defensive copy."""
    initial = [1, 2, 3]
    rl = ReactiveList("test", initial)
    result = rl.get()
    assert result == [1, 2, 3]
    # Ensure it's a copy, not the same object
    result.append(4)
    assert rl.get() == [1, 2, 3]


def test_reactive_list_set():
    """ReactiveList.set() replaces entire list."""
    rl = ReactiveList("test", [1, 2, 3])
    rl.set([4, 5, 6])
    assert rl.get() == [4, 5, 6]


def test_reactive_list_set_index():
    """ReactiveList.set_index() mutates at index."""
    rl = ReactiveList("test", [1, 2, 3])
    rl.set_index(1, 99)
    assert rl.get() == [1, 99, 3]


def test_reactive_list_getitem():
    """ReactiveList.__getitem__() reads element."""
    rl = ReactiveList("test", [10, 20, 30])
    assert rl[0] == 10
    assert rl[2] == 30


def test_reactive_list_setitem():
    """ReactiveList.__setitem__() mutates element."""
    rl = ReactiveList("test", [10, 20, 30])
    rl[1] = 25
    assert rl.get() == [10, 25, 30]


def test_reactive_list_on_change():
    """ReactiveList.on_change() registers handler."""
    rl = ReactiveList("test", [1, 2])
    called = []

    def handler(new_list):
        called.append(new_list)

    rl.on_change(handler)
    rl.set([3, 4])
    assert called == [[3, 4]]

    rl.set_index(0, 5)
    assert called == [[3, 4], [5, 4]]


def test_reactive_engine_declare_list():
    """ReactiveEngine.declare() returns ReactiveList for list initial."""
    engine = ReactiveEngine()
    sig = engine.declare("items", [1, 2, 3])
    assert isinstance(sig, ReactiveList)
    assert sig.get() == [1, 2, 3]


def test_reactive_engine_declare_scalar():
    """ReactiveEngine.declare() returns Signal for scalar initial."""
    from multilingualprogramming.runtime.reactive import Signal

    engine = ReactiveEngine()
    sig = engine.declare("count", 42)
    assert isinstance(sig, Signal)
    assert sig.get() == 42


def test_reactive_engine_idempotent():
    """ReactiveEngine.declare() is idempotent."""
    engine = ReactiveEngine()
    sig1 = engine.declare("items", [1, 2])
    sig2 = engine.declare("items", [3, 4])  # Should return same instance
    assert sig1 is sig2
    assert sig2.get() == [1, 2]  # Original value preserved


def test_reactive_list_multiple_handlers():
    """Multiple handlers on same signal all receive updates."""
    rl = ReactiveList("test", [1])
    calls1 = []
    calls2 = []

    rl.on_change(lambda v: calls1.append(v))
    rl.on_change(lambda v: calls2.append(v))

    rl.set([2, 3])

    assert calls1 == [[2, 3]]
    assert calls2 == [[2, 3]]
