#
# SPDX-FileCopyrightText: 2024 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""
Runtime built-in functions for the multilingual programming language.

Provides a namespace dict of built-in functions that are injected into
the execution environment so that multilingual identifiers (e.g., the
Hindi word for "print") resolve to Python built-ins.
"""

import json
import sys
import asyncio
import inspect
from pathlib import Path

from multilingualprogramming.keyword.keyword_registry import KeywordRegistry
from multilingualprogramming.runtime.ai_runtime import AIRuntime
from multilingualprogramming.runtime.ai_types import ModelRef
from multilingualprogramming.runtime.multimodal_runtime import (
    AudioValue,
    DocumentValue,
    ImageValue,
    MultimodalValue,
    MultimodalPrompt,
    VideoValue,
)
from multilingualprogramming.runtime.numeric_primitives import (
    Vec2,
    ComplexScalar,
    FastRNG,
    BoundedArray,
    MinDistanceAccumulator,
)
from multilingualprogramming.runtime.reactive import ReactiveEngine, Signal, stream_to_view
from multilingualprogramming.runtime.retrieval_runtime import (
    VectorIndex,
    format_context,
    nearest,
)
from multilingualprogramming.runtime.semantic_match import semantic_match
from multilingualprogramming.runtime.tool_runtime import AgentLoop, get_registry, tool
from multilingualprogramming.runtime.memory_store import ml_memory


def _coerce_model(model):
    """Normalize model inputs to ModelRef values."""
    if isinstance(model, ModelRef):
        return model
    if model is None:
        return ModelRef("")
    return ModelRef(str(model))


def _runtime_input(prompt=""):
    """Display prompts on the real terminal even when stdout is captured."""
    if prompt and sys.stdout is not sys.__stdout__:
        visible_stdout = sys.__stdout__
        visible_stdout.write(str(prompt))
        visible_stdout.flush()
        return input()
    return input(prompt)


def _coerce_ai_payload(value):
    """Preserve multimodal payloads while normalizing plain values to text."""
    if isinstance(value, (MultimodalValue, MultimodalPrompt)):
        return value
    return str(value)


def _prompt(model, template):
    return AIRuntime.prompt(_coerce_model(model), _coerce_ai_payload(template)).content


def _generate(model, template, target_type=None):
    return AIRuntime.generate(
        _coerce_model(model),
        _coerce_ai_payload(template),
        target_type=target_type,
    )


def _think(model, template):
    return AIRuntime.think(_coerce_model(model), _coerce_ai_payload(template))


def _stream(model, template):
    return AIRuntime.stream(_coerce_model(model), _coerce_ai_payload(template))


def _embed(model, value):
    return AIRuntime.embed(_coerce_model(model), str(value))


def _extract(model, source, target_type=None):
    return AIRuntime.generate(
        _coerce_model(model),
        _coerce_ai_payload(source),
        target_type=target_type,
    )


def _classify(model, subject, *categories, target_type=None):
    prompt = f"Classify {subject!r} into one of: {', '.join(map(str, categories))}"
    return AIRuntime.generate(_coerce_model(model), prompt, target_type=target_type)


def _plan(model, goal):
    return AIRuntime.plan(_coerce_model(model), str(goal))


def _transcribe(model, source):
    return AIRuntime.transcribe(_coerce_model(model), source)


def _retrieve(index, query, *, top_k=5, min_score=0.0, model=None):
    query_value = query
    if not isinstance(query, list):
        embed_model = _coerce_model(model or "text-embedding-3-small")
        query_value = AIRuntime.embed(embed_model, str(query)).values
    return nearest(query_value, index, top_k=top_k, min_score=min_score)


def _result_propagate(value):
    """Best-effort runtime lowering for Core 1.0 result propagation."""
    if isinstance(value, tuple) and len(value) == 2:
        tag, payload = value
        if tag == "ok":
            return payload
        if tag == "err":
            raise RuntimeError(str(payload))
    if isinstance(value, dict):
        if value.get("ok") is True:
            return value.get("value")
        if value.get("ok") is False and "error" in value:
            raise RuntimeError(str(value["error"]))
    if hasattr(value, "ok") and hasattr(value, "value"):
        if value.ok:
            return value.value
        raise RuntimeError(getattr(value, "parse_error", "result propagation failed"))
    return value


def _agent_decorator(**kwargs):
    """Decorator for marking functions as agents in swarms.

    Accepts optional metadata like model. Returns a decorator that marks
    the function with agent metadata and returns it unchanged for execution.
    """
    def decorator(func):
        # Store agent metadata on the function
        func.__agent_metadata__ = kwargs
        return func
    return decorator


def _swarm_decorator(**kwargs):
    """Decorator for marking functions as swarm coordinators.

    Accepts optional metadata like agents list. Returns a decorator that marks
    the function with swarm metadata and returns it unchanged for execution.
    """
    def decorator(func):
        # Store swarm metadata on the function
        func.__swarm_metadata__ = kwargs
        return func
    return decorator


def _delegate(agent_func, *args, **kwargs):
    """Call an agent function with the given arguments.

    This is a runtime helper for swarm coordination that invokes an agent
    function with delegation semantics. In the current implementation, it
    simply calls the function directly.
    """
    return agent_func(*args, **kwargs)


def _ml_par_gather(*values):
    """Gather multiple values, handling both async and sync results.

    Executes all expressions in parallel (when possible) and returns results as tuple.
    For synchronous functions, this executes them in order and collects results.
    For coroutines, uses asyncio.gather() to run them concurrently.
    """
    # If all values are non-awaitable, just return them as-is (sequential execution)
    if all(not (inspect.iscoroutine(v) or inspect.isawaitable(v)) for v in values):
        return tuple(values)

    # If any values are coroutines, wrap all in coroutines for gather()
    async def _gather():
        async def _wrap(val):
            if inspect.iscoroutine(val) or inspect.isawaitable(val):
                return await val
            return val

        tasks = [_wrap(v) for v in values]
        return await asyncio.gather(*tasks)

    # Run the async gather
    try:
        asyncio.get_running_loop()
        # Already in async context - return the coroutine to be awaited
        return _gather()
    except RuntimeError:
        # Not in async context - run the event loop
        return asyncio.run(_gather())


def _spawn(coro):
    """Spawn a fire-and-forget coroutine task.

    Creates an asyncio task from the coroutine and returns immediately.
    The task runs concurrently in the background without awaiting completion.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop; create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if inspect.iscoroutine(coro):
        return loop.create_task(coro)
    # If already a task, return it
    return coro


def _channel(capacity=0):
    """Create a channel for inter-task communication.

    Parameters:
        capacity: Maximum buffered items (0 = unbounded)

    Returns:
        A Channel[T] instance with send(), receive(), and close() methods.
    """
    from multilingualprogramming.runtime.channel import Channel
    return Channel(capacity=capacity)


def _on_change(signal_or_name, handler=None):
    """Register a change handler on a signal.

    Can be used as:
    - signal.on_change(handler) — register handler directly
    - on_change(signal_name) — decorator factory (if ReactiveEngine available)
    """
    if handler is not None:
        # Direct call: signal.on_change(handler)
        return signal_or_name.on_change(handler)

    # Decorator factory pattern (for future use with engine)
    def decorator(fn):
        if hasattr(signal_or_name, 'on_change'):
            signal_or_name.on_change(fn)
        return fn
    return decorator


def _canvas(name="", children=None, bindings=None):
    """Create a canvas node for UI rendering.

    Parameters:
        name: Canvas element identifier
        children: List of child CanvasNodes or values
        bindings: Dict mapping slot names to Signal values

    Returns:
        A CanvasNode instance.
    """
    from multilingualprogramming.runtime.reactive import CanvasNode
    return CanvasNode(name=name, children=children, bindings=bindings)


def _render(canvas_or_dict):
    """Render a canvas to its dictionary representation.

    Converts a CanvasNode (or already-dict) to a plain dict suitable for
    serialization or JavaScript code generation.

    Returns:
        A dict with 'name', 'bindings', and 'children' keys.
    """
    if hasattr(canvas_or_dict, 'to_dict'):
        return canvas_or_dict.to_dict()
    # Already a dict
    return canvas_or_dict


def _bind(canvas_or_node, slot_name, signal):
    """Bind a signal to a named slot on a canvas node.

    When the signal changes, the canvas node is notified (for live updates).

    Parameters:
        canvas_or_node: CanvasNode instance
        slot_name: Name of the slot to bind
        signal: Signal instance to observe
    """
    if hasattr(canvas_or_node, 'bind'):
        canvas_or_node.bind(slot_name, signal)
    return canvas_or_node


class RuntimeBuiltins:
    """
    Builds a dict of built-in names that should be available at runtime.

    For a given source language, the keyword used for PRINT, INPUT, and
    type keywords are mapped to the corresponding Python built-ins.

    Usage:
        builtins = RuntimeBuiltins("fr").namespace()
        # {'afficher': <built-in function print>,
        #  'saisir':   <built-in function input>, ...}

    The returned dict is intended to be merged into the exec() globals
    so that transpiled code can call built-in functions by their
    multilingual names.
    """

    # Mapping from USM concept ID to the Python built-in object
    _CONCEPT_TO_BUILTIN = {
        "PRINT": print,
        "INPUT": _runtime_input,
        "TYPE_INT": int,
        "TYPE_FLOAT": float,
        "TYPE_STR": str,
        "TYPE_BOOL": bool,
        "TYPE_LIST": list,
        "TYPE_DICT": dict,
    }

    # Additional Python built-ins available in every language
    _UNIVERSAL_BUILTINS = {
        "len": len,
        "range": range,
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "sorted": sorted,
        "reversed": reversed,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "filter": filter,
        "isinstance": isinstance,
        "type": type,
        "hasattr": hasattr,
        "getattr": getattr,
        "setattr": setattr,
        "repr": repr,
        "round": round,
        "open": open,
        "iter": iter,
        "next": next,
        "any": any,
        "all": all,
        "chr": chr,
        "ord": ord,
        "hex": hex,
        "oct": oct,
        "bin": bin,
        "id": id,
        "hash": hash,
        "callable": callable,
        "dir": dir,
        "vars": vars,
        "super": super,
        "property": property,
        "staticmethod": staticmethod,
        "classmethod": classmethod,
        "print": print,
        "input": _runtime_input,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "frozenset": frozenset,
        "bytes": bytes,
        "bytearray": bytearray,
        "memoryview": memoryview,
        "object": object,
        "Exception": Exception,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "KeyError": KeyError,
        "IndexError": IndexError,
        "AttributeError": AttributeError,
        "RuntimeError": RuntimeError,
        "StopIteration": StopIteration,
        "ZeroDivisionError": ZeroDivisionError,
        "FileNotFoundError": FileNotFoundError,
        "IOError": IOError,
        "OSError": OSError,
        "ImportError": ImportError,
        "NotImplementedError": NotImplementedError,
        "True": True,
        "False": False,
        "None": None,
        # Additional built-in functions
        "pow": pow,
        "divmod": divmod,
        "complex": complex,
        "format": format,
        "ascii": ascii,
        "breakpoint": breakpoint,
        "compile": compile,
        "eval": eval,
        "exec": exec,
        "globals": globals,
        "locals": locals,
        "issubclass": issubclass,
        "delattr": delattr,
        "slice": slice,
        # Additional exception types
        "ArithmeticError": ArithmeticError,
        "AssertionError": AssertionError,
        "BufferError": BufferError,
        "EOFError": EOFError,
        "FloatingPointError": FloatingPointError,
        "GeneratorExit": GeneratorExit,
        "LookupError": LookupError,
        "NameError": NameError,
        "OverflowError": OverflowError,
        "PermissionError": PermissionError,
        "RecursionError": RecursionError,
        "ReferenceError": ReferenceError,
        "SyntaxError": SyntaxError,
        "SystemError": SystemError,
        "SystemExit": SystemExit,
        "TimeoutError": TimeoutError,
        "UnicodeError": UnicodeError,
        "UnicodeDecodeError": UnicodeDecodeError,
        "UnicodeEncodeError": UnicodeEncodeError,
        "Warning": Warning,
        "DeprecationWarning": DeprecationWarning,
        "UserWarning": UserWarning,
        "FutureWarning": FutureWarning,
        "ResourceWarning": ResourceWarning,
        "ConnectionError": ConnectionError,
        "BrokenPipeError": BrokenPipeError,
        "BlockingIOError": BlockingIOError,
        "ChildProcessError": ChildProcessError,
        "ConnectionAbortedError": ConnectionAbortedError,
        "ConnectionRefusedError": ConnectionRefusedError,
        "ConnectionResetError": ConnectionResetError,
        "FileExistsError": FileExistsError,
        "InterruptedError": InterruptedError,
        "IsADirectoryError": IsADirectoryError,
        "NotADirectoryError": NotADirectoryError,
        "ProcessLookupError": ProcessLookupError,
        "StopAsyncIteration": StopAsyncIteration,
        "UnboundLocalError": UnboundLocalError,
        # Base exception classes
        "BaseException": BaseException,
        "KeyboardInterrupt": KeyboardInterrupt,
        # Additional exception types (Python 3.12)
        "ModuleNotFoundError": ModuleNotFoundError,
        "IndentationError": IndentationError,
        "TabError": TabError,
        "UnicodeTranslateError": UnicodeTranslateError,
        "ExceptionGroup": ExceptionGroup,
        "BaseExceptionGroup": BaseExceptionGroup,
        # Additional warning types
        "BytesWarning": BytesWarning,
        "EncodingWarning": EncodingWarning,
        "ImportWarning": ImportWarning,
        "PendingDeprecationWarning": PendingDeprecationWarning,
        "RuntimeWarning": RuntimeWarning,
        "SyntaxWarning": SyntaxWarning,
        "UnicodeWarning": UnicodeWarning,
        # Async built-in functions (Python 3.10+)
        "aiter": aiter,
        "anext": anext,
        # Numeric helpers for fractal/geometry workloads
        "Vec2": Vec2,
        "ComplexScalar": ComplexScalar,
        "FastRNG": FastRNG,
        "BoundedArray": BoundedArray,
        "MinDistanceAccumulator": MinDistanceAccumulator,
        "AIRuntime": AIRuntime,
        "ModelRef": ModelRef,
        "prompt": _prompt,
        "requete": _prompt,
        "requête": _prompt,
        "pregunte": _prompt,
        "pregunta": _prompt,
        "generate": _generate,
        "generar": _generate,
        "generer": _generate,
        "générer": _generate,
        "think": _think,
        "pensar": _think,
        "penser": _think,
        "stream": _stream,
        "flux": _stream,
        "flujo": _stream,
        "embed": _embed,
        "incrustacion": _embed,
        "incorporer": _embed,
        "extract": _extract,
        "extraire": _extract,
        "extraer": _extract,
        "classify": _classify,
        "clasificar": _classify,
        "classer": _classify,
        "plan": _plan,
        "planificar": _plan,
        "planifier": _plan,
        "transcribe": _transcribe,
        "transcribir": _transcribe,
        "transcrire": _transcribe,
        "retrieve": _retrieve,
        "__ml_result_propagate": _result_propagate,
        "semantic_match": semantic_match,
        "VectorIndex": VectorIndex,
        "nearest": nearest,
        "format_context": format_context,
        "ReactiveEngine": ReactiveEngine,
        "Signal": Signal,
        "stream_to_view": stream_to_view,
        "ImageValue": ImageValue,
        "AudioValue": AudioValue,
        "VideoValue": VideoValue,
        "DocumentValue": DocumentValue,
        "MultimodalPrompt": MultimodalPrompt,
        "AgentLoop": AgentLoop,
        "tool": tool,
        "agent": _agent_decorator,
        "swarm": _swarm_decorator,
        "delegate": _delegate,
        "deleguer": _delegate,
        "get_tool_registry": get_registry,
        "memory": ml_memory,
        "memoire": ml_memory,
        "_ml_par_gather": _ml_par_gather,
        # Concurrency keywords
        "spawn": _spawn,
        "launch": _spawn,
        "lancer": _spawn,
        "channel": _channel,
        "canal": _channel,
        # Reactive & UI keywords
        "on": _on_change,
        "on_change": _on_change,
        "onchange": _on_change,
        "canvas": _canvas,
        "render": _render,
        "afficher": _render,
        "mostrar": _render,
        "bind": _bind,
        "lier": _bind,
        "vincular": _bind,
        "CanvasNode": _canvas,
        "Channel": _channel,
    }

    # Non-callable special values available in exec() namespace
    _SPECIAL_VALUES = {
        "Ellipsis": Ellipsis,
        "NotImplemented": NotImplemented,
    }

    _BUILTIN_ALIAS_CATALOG = None

    def __init__(self, source_language="en"):
        self._language = source_language
        self._registry = KeywordRegistry()

    @classmethod
    def _load_builtin_alias_catalog(cls):
        """Load localized built-in aliases from resources."""
        if cls._BUILTIN_ALIAS_CATALOG is not None:
            return cls._BUILTIN_ALIAS_CATALOG

        path = (
            Path(__file__).resolve().parent.parent
            / "resources" / "usm" / "builtins_aliases.json"
        )
        with open(path, "r", encoding="utf-8-sig") as handle:
            cls._BUILTIN_ALIAS_CATALOG = json.load(handle)
        return cls._BUILTIN_ALIAS_CATALOG

    @classmethod
    def _localized_builtin_aliases(cls, language):
        """Return alias->builtin map for a given language."""
        catalog = cls._load_builtin_alias_catalog()
        aliases = {}
        for canonical, by_language in catalog.get("aliases", {}).items():
            if canonical == "input":
                builtin_obj = input
            else:
                builtin_obj = cls._UNIVERSAL_BUILTINS.get(canonical)
            if builtin_obj is None or not isinstance(by_language, dict):
                continue
            for alias in by_language.get(language, []):
                aliases[alias] = builtin_obj
        return aliases

    def namespace(self):
        """
        Return a dict mapping multilingual names to Python built-ins.

        Includes:
        1. Language-specific keyword mappings (PRINT -> afficher, etc.)
        2. Universal Python built-ins (len, range, abs, etc.)
        """
        ns = dict(self._UNIVERSAL_BUILTINS)
        ns.update(self._SPECIAL_VALUES)

        # Add language-specific mappings (all variants, not only canonical).
        concept_map = self._registry.get_concept_map()
        for concept, builtin_obj in self._CONCEPT_TO_BUILTIN.items():
            try:
                translations = concept_map[concept]
                keyword_value = translations.get(self._language)
                if keyword_value is None:
                    continue
                keywords = (
                    keyword_value if isinstance(keyword_value, list)
                    else [keyword_value]
                )
                for keyword in keywords:
                    if keyword not in ns:
                        ns[keyword] = builtin_obj
            except Exception:
                pass  # Skip if concept not found for this language
        for alias, builtin_obj in self._localized_builtin_aliases(
            self._language
        ).items():
            # Keep canonical names stable if an alias collides.
            if alias not in ns:
                ns[alias] = builtin_obj

        return ns

    @classmethod
    def all_languages_namespace(cls):
        """
        Return a namespace containing built-in mappings for ALL supported
        languages simultaneously. Useful for multi-language environments.
        """
        ns = dict(cls._UNIVERSAL_BUILTINS)
        registry = KeywordRegistry()

        concept_map = registry.get_concept_map()
        for lang in registry.get_supported_languages():
            for concept, builtin_obj in cls._CONCEPT_TO_BUILTIN.items():
                try:
                    translations = concept_map[concept]
                    keyword_value = translations.get(lang)
                    if keyword_value is None:
                        continue
                    keywords = (
                        keyword_value if isinstance(keyword_value, list)
                        else [keyword_value]
                    )
                    for keyword in keywords:
                        if keyword not in ns:
                            ns[keyword] = builtin_obj
                except Exception:
                    pass
            for alias, builtin_obj in cls._localized_builtin_aliases(
                lang
            ).items():
                # Keep canonical names stable if an alias collides.
                if alias not in ns:
                    ns[alias] = builtin_obj

        return ns


def make_exec_globals(language="en", extra=None):
    """Return a ready-to-use globals dict for exec() with localized builtins.

    Convenience wrapper for users who transpile multilingual source to Python
    and then call exec() directly (rather than via ProgramExecutor).

    Args:
        language: Source language code (e.g., "en", "fr", "hi"). Determines
                  which localized builtin names (afficher, longueur, ...) are
                  added on top of the universal Python builtins.
        extra:    Optional dict of additional names to merge in. Keys from
                  *extra* take precedence over the builtins namespace.

    Returns:
        dict suitable for use as the globals argument to exec().

    Example::

        python_src = ProgramExecutor(language="fr").transpile(french_source)
        g = make_exec_globals("fr")
        exec(python_src, g)
        # g now contains any names defined by the executed code.
    """
    ns = RuntimeBuiltins(language).namespace()
    # Required by Python's import machinery when exec'd code uses imports.
    ns.setdefault("__name__", "__main__")
    ns.setdefault("__package__", None)
    ns.setdefault("__spec__", None)
    if extra:
        ns.update(extra)
    return ns
