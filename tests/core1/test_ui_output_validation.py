"""Validate generated UI output HTML/CSS/JS quality."""

from pathlib import Path
from multilingualprogramming.lexer.lexer import Lexer
from multilingualprogramming.parser.parser import Parser
from multilingualprogramming.core.semantic_lowering import lower_to_semantic_ir
from multilingualprogramming.codegen.ui_lowering import lower_to_ui


def test_memory_game_html_has_required_structure():
    """Generated HTML has all required structural elements."""
    game_file = Path("examples/memory_game_en.multi")
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")
    ui_result = lower_to_ui(ir_program)
    html = ui_result.emit_html()

    # Check doctype
    assert html.startswith("<!DOCTYPE html>")

    # Check head section
    assert "<head>" in html
    assert '<meta charset="UTF-8">' in html
    assert "<title>" in html
    assert "</head>" in html

    # Check body
    assert "<body>" in html
    assert '</body>' in html

    # Check root container for render block
    assert 'id="__ml_root"' in html


def test_memory_game_html_has_css_styling():
    """Generated HTML includes CSS for game styling."""
    game_file = Path("examples/memory_game_en.multi")
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")
    ui_result = lower_to_ui(ir_program)
    html = ui_result.emit_html()

    # Check for stylesheet
    assert "<style>" in html
    assert "</style>" in html

    # Check for critical CSS classes
    assert ".memory-game" in html
    assert ".game-board" in html
    assert ".card" in html
    assert ".status" in html
    assert ".reset-btn" in html

    # Check for grid layout
    assert "grid" in html or "display" in html
    assert "grid-template-columns" in html or "repeat(4" in html


def test_memory_game_js_has_required_functions():
    """Generated JS has all required signal and function declarations."""
    game_file = Path("examples/memory_game_en.multi")
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")
    ui_result = lower_to_ui(ir_program)
    js = ui_result.emit_js()

    # Check for signal declarations
    assert "__ml_signals['cards']" in js
    assert "__ml_signals['revealed']" in js
    assert "__ml_signals['matched']" in js

    # Check for async functions
    assert "async function handle_card_click" in js
    assert "async function reset_game" in js

    # Check for render function
    assert "function __ml_render()" in js


def test_memory_game_js_no_undefined_calls():
    """Generated JS does not contain calls to undefined functions."""
    game_file = Path("examples/memory_game_en.multi")
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")
    ui_result = lower_to_ui(ir_program)
    js = ui_result.emit_js()

    # Should not call memory_game() as a function (it's not in JS context)
    assert "memory_game()" not in js

    # Should not have undefined class references
    assert "class undefined" not in js


def test_memory_game_js_has_render_initialization():
    """Generated JS initializes render on page load."""
    game_file = Path("examples/memory_game_en.multi")
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")
    ui_result = lower_to_ui(ir_program)
    js = ui_result.emit_js()

    # Check for initialization
    assert "__ml_render()" in js


def test_memory_game_js_signal_change_bindings():
    """Generated JS binds signal changes to re-render."""
    game_file = Path("examples/memory_game_en.multi")
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")
    ui_result = lower_to_ui(ir_program)
    js = ui_result.emit_js()

    # Check that signals are wired to re-render
    assert ".on_change" in js or "on_change" in js
    assert "_engine.on_change" in js or ".on_change(() => __ml_render())" in js


def test_memory_game_js_has_reactive_runtime():
    """Generated JS includes ReactiveSignal and ReactiveList classes."""
    game_file = Path("examples/memory_game_en.multi")
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")
    ui_result = lower_to_ui(ir_program)
    js = ui_result.emit_js()

    # Check for reactive runtime
    assert "class ReactiveSignal" in js
    assert "class ReactiveList" in js
    assert "class ReactiveEngine" in js
    assert "function __ml_signal" in js


def test_memory_game_js_for_loop_structure():
    """Generated JS has correct for-loop structure for game board."""
    game_file = Path("examples/memory_game_en.multi")
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")
    ui_result = lower_to_ui(ir_program)
    js = ui_result.emit_js()

    # Check for loop iterations 0-7
    assert "for (let i = 0; i < 8" in js

    # Check that button elements are created inside loop
    assert "document.createElement('button')" in js

    # Status and reset button should appear after the loop
    lines = js.split('\n')
    for_loop_line = None
    status_div_line = None
    reset_button_line = None

    for i, line in enumerate(lines):
        if "for (let i = 0; i < 8" in line:
            for_loop_line = i
        if 'className = \'status\'' in line:
            status_div_line = i
        if 'className = \'reset-btn\'' in line:
            reset_button_line = i

    if for_loop_line and status_div_line:
        # Status div should be after for loop
        assert status_div_line > for_loop_line


def test_memory_game_html_valid_utf8():
    """Generated HTML is valid UTF-8 and encodes properly."""
    game_file = Path("examples/memory_game_en.multi")
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")
    ui_result = lower_to_ui(ir_program)
    html = ui_result.emit_html()

    # Should be valid UTF-8 and encodable without errors
    html.encode('utf-8')

    # Should contain the game title
    assert "Memory" in html and "Game" in html


def test_memory_game_js_event_handlers():
    """Generated JS has event handlers for card clicks."""
    game_file = Path("examples/memory_game_en.multi")
    source = game_file.read_text()
    lexer = Lexer(source, lang="en")
    tokens = lexer.tokenize()
    parser = Parser(tokens, lang="en")
    program = parser.parse()
    ir_program = lower_to_semantic_ir(program, lang="en")
    ui_result = lower_to_ui(ir_program)
    js = ui_result.emit_js()

    # Check for event handler attachment
    assert "addEventListener('click'" in js
    assert "handle_card_click" in js

    # Check for reset button handler
    assert "reset_game" in js
