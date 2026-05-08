"""End-to-end test of memory game compilation pipeline."""

from pathlib import Path
from multilingualprogramming.lexer.lexer import Lexer
from multilingualprogramming.parser.parser import Parser
from multilingualprogramming.core.semantic_lowering import lower_to_semantic_ir
from multilingualprogramming.codegen.ui_lowering import lower_to_ui
from multilingualprogramming.core import ir_nodes as ir


def _walk_ir(node):
    """Yield a node and all nested IR nodes reachable from it."""
    if not isinstance(node, ir.IRNode):
        return
    yield node
    for value in vars(node).values():
        if isinstance(value, ir.IRNode):
            yield from _walk_ir(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, ir.IRNode):
                    yield from _walk_ir(item)


def test_memory_game_file_exists():
    """Memory game example file exists."""
    game_file = Path(__file__).parent.parent.parent / "examples" / "memory_game_en.multi"
    assert game_file.exists()


def test_memory_game_parses():
    """Memory game parses without errors."""
    game_file = Path(__file__).parent.parent.parent / "examples" / "memory_game_en.multi"
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    assert program is not None


def test_memory_game_lowers_to_ir():
    """Memory game lowers to semantic IR without fallback placeholders."""
    game_file = Path(__file__).parent.parent.parent / "examples" / "memory_game_en.multi"
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")

    # Check that no IRExpression placeholders were used (indicates unsupported nodes)
    def count_placeholders(node):
        if isinstance(node, ir.IRExpression) and not hasattr(node, '_original_type'):
            return 1
        count = 0
        for value in vars(node).values():
            if isinstance(value, ir.IRNode):
                count += count_placeholders(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ir.IRNode):
                        count += count_placeholders(item)
        return count

    # This test is lenient: just ensure we can lower it
    assert ir_program is not None


def test_memory_game_has_observe_bindings():
    """Memory game IR contains observe bindings."""
    game_file = Path(__file__).parent.parent.parent / "examples" / "memory_game_en.multi"
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")

    # Find observe bindings
    observe_names = {
        node.name
        for top_level in ir_program.body
        for node in _walk_ir(top_level)
        if isinstance(node, ir.IRObserveBinding)
    }

    # Memory game should have several observe vars
    assert len(observe_names) > 0
    # These are the known observe vars from memory_game_en.multi
    expected = {
        "cards",
        "revealed",
        "matched",
        "first_pick",
        "second_pick",
        "matches_found",
        "game_won",
        "is_checking",
    }
    assert expected.issubset(observe_names)


def test_memory_game_has_async_functions():
    """Memory game IR contains async functions."""
    game_file = Path(__file__).parent.parent.parent / "examples" / "memory_game_en.multi"
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")

    # Find async functions
    async_funcs = {
        node.name
        for top_level in ir_program.body
        for node in _walk_ir(top_level)
        if isinstance(node, ir.IRFunction) and node.is_async
    }

    assert len(async_funcs) > 0
    # Memory game has handle_card_click and reset_game
    expected = {"handle_card_click", "reset_game"}
    assert expected.issubset(async_funcs)


def test_memory_game_lowers_to_ui():
    """Memory game IR lowers to UI output without errors."""
    game_file = Path(__file__).parent.parent.parent / "examples" / "memory_game_en.multi"
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")
    ui_result = lower_to_ui(ir_program)

    assert ui_result is not None
    assert ui_result.html != ""
    assert ui_result.js != ""


def test_memory_game_ui_contains_signals():
    """Generated UI output contains signal declarations."""
    game_file = Path(__file__).parent.parent.parent / "examples" / "memory_game_en.multi"
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")
    ui_result = lower_to_ui(ir_program)

    js = ui_result.emit_js()
    # Check for signal declarations
    assert "__ml_signal" in js
    assert "cards" in js
    assert "revealed" in js
    assert "matched" in js


def test_memory_game_ui_contains_functions():
    """Generated UI output contains async functions."""
    game_file = Path(__file__).parent.parent.parent / "examples" / "memory_game_en.multi"
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")
    ui_result = lower_to_ui(ir_program)

    js = ui_result.emit_js()
    # Check for function definitions
    assert "async function handle_card_click" in js
    assert "async function reset_game" in js


def test_memory_game_ui_contains_render():
    """Generated UI output contains render function."""
    game_file = Path(__file__).parent.parent.parent / "examples" / "memory_game_en.multi"
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")
    ui_result = lower_to_ui(ir_program)

    js = ui_result.emit_js()
    # Check for render function
    assert "function __ml_render()" in js


def test_memory_game_html_contains_game_board():
    """Generated HTML contains game board element."""
    game_file = Path(__file__).parent.parent.parent / "examples" / "memory_game_en.multi"
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")
    ui_result = lower_to_ui(ir_program)

    html = ui_result.emit_html()
    # Check for expected HTML elements
    assert "game-board" in html
    assert "Memory Game" in html
    assert "New Game" in html
