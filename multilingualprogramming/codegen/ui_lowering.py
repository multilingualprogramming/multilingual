#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Lower reactive Core IR into a self-contained HTML/JavaScript preview."""

# pylint: disable=too-many-return-statements,too-many-branches
# pylint: disable=too-many-instance-attributes,too-many-locals,too-many-statements

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from multilingualprogramming.core.ir_nodes import (
    IRAwaitExpr,
    IRAttributeAccess,
    IRBinaryOp,
    IRBooleanOp,
    IRBreakStatement,
    IRCallExpr,
    IRCanvasBlock,
    IRClassDecl,
    IRCompareOp,
    IRConditionalExpr,
    IRContinueStatement,
    IRDelStatement,
    IRDictLiteral,
    IRExprStatement,
    IRForLoop,
    IRFunction,
    IRIdentifier,
    IRIfStatement,
    IRImportStatement,
    IRIndexAccess,
    IRLiteral,
    IRListLiteral,
    IRNode,
    IRObserveBinding,
    IROnChange,
    IRProgram,
    IRRaiseStatement,
    IRRenderBlock,
    IRReturnStatement,
    IRSetLiteral,
    IRSliceExpr,
    IRTryStatement,
    IRTupleLiteral,
    IRUIElement,
    IRUnaryOp,
    IRViewBinding,
    IRWhileLoop,
)

_USM_DIR = Path(__file__).parent.parent / "resources" / "usm"
with (_USM_DIR / "builtins_aliases.json").open(encoding="utf-8") as _f:
    _BUILTINS_ALIASES: dict = json.load(_f)["aliases"]
with (_USM_DIR / "keywords.json").open(encoding="utf-8") as _f:
    _KEYWORDS: dict = json.load(_f)["categories"]


def _builtin_aliases_for(canonical: str) -> frozenset[str]:
    names = {canonical}
    for lang_aliases in _BUILTINS_ALIASES.get(canonical, {}).values():
        names.update(lang_aliases)
    return frozenset(names)


def _keyword_aliases_for(category: str, concept: str) -> frozenset[str]:
    names: set[str] = set()
    entry = _KEYWORDS.get(category, {}).get(concept, {})
    for surface in entry.values():
        if isinstance(surface, str):
            names.add(surface)
            names.add(surface.lower())
        elif isinstance(surface, list):
            for item in surface:
                if isinstance(item, str):
                    names.add(item)
                    names.add(item.lower())
    return frozenset(names)


_RANGE_NAMES = _builtin_aliases_for("range")
_STR_NAMES = _builtin_aliases_for("str")
_LIST_NAMES = _builtin_aliases_for("list")
_NUMBER_NAMES = (
    _builtin_aliases_for("number")
    | _builtin_aliases_for("int")
    | _builtin_aliases_for("float")
)
_TRUE_NAMES = _keyword_aliases_for("logical", "TRUE")
_FALSE_NAMES = _keyword_aliases_for("logical", "FALSE")
_NONE_NAMES = _keyword_aliases_for("logical", "NONE")


@dataclass
class UILoweringResult:
    """Output of the UI lowering pass."""

    html: str = ""
    js: str = ""
    diagnostics: list[str] = field(default_factory=list)
    js_signals: list[str] = field(default_factory=list)
    js_handlers: list[str] = field(default_factory=list)
    js_bindings: list[str] = field(default_factory=list)

    def emit_html(self) -> str:
        """Return the generated HTML document."""
        return self.html

    def emit_js(self) -> str:
        """Return the generated JavaScript bundle."""
        return self.js


class UILoweringPass:
    """Lower an IR program to a browser preview bundle."""

    def __init__(self) -> None:
        self._result = UILoweringResult()
        self._signal_names: set[str] = set()
        self._has_render_root = False
        self._canvas_names: list[str] = []
        self._functions: list[str] = []
        self._module_parts: list[str] = []
        self._ui_function_names: set[str] = set()
        self._render_function = ""
        self._local_scopes: list[set[str]] = []

    def lower(
        self,
        program: IRProgram,
        modules: dict[str, IRProgram] | None = None,
    ) -> UILoweringResult:
        """Lower an IRProgram to UI output."""
        preamble = self._emit_preamble()
        self._lower_imported_modules(modules or {})
        self._local_scopes.append(set())
        for node in program.body:
            self._lower_node(node)
        self._local_scopes.pop()

        self._wire_render_updates()

        js_parts = [preamble]
        js_parts.extend(self._module_parts)
        js_parts.extend(self._result.js_signals)
        js_parts.extend(self._functions)
        js_parts.extend(self._result.js_handlers)
        js_parts.extend(self._result.js_bindings)
        if self._render_function:
            js_parts.append(self._render_function)
            js_parts.append("if (typeof __ml_render === 'function') {\n  __ml_render();\n}")

        self._result.js = "\n\n".join(part for part in js_parts if part)
        self._result.html = self._emit_html()
        return self._result

    def _lower_imported_modules(self, modules: dict[str, IRProgram]) -> None:
        for module_name, module_program in modules.items():
            module_pass = UILoweringPass()
            module_result = module_pass.lower(module_program)
            module_parts = []
            module_parts.extend(module_result.js_signals)
            module_parts.extend(module_pass._functions)  # pylint: disable=protected-access
            module_parts.extend(module_result.js_handlers)
            module_parts.extend(module_result.js_bindings)
            module_js = "\n\n".join(part for part in module_parts if part)

            if "unsupported" in module_js or "null /*" in module_js:
                self._result.diagnostics.append(
                    f"Skipped UI module {module_name}: unsupported lowering output"
                )
                continue

            exported_names = [
                node.name
                for node in module_program.body
                if isinstance(node, (IRClassDecl, IRFunction))
            ]
            if not exported_names:
                continue

            namespace_js = self._namespace_assignment_js(module_name, exported_names)
            wrapped_js = "\n\n".join([module_js, namespace_js])
            self._module_parts.append(f"(() => {{\n{wrapped_js}\n}})();")

    def _namespace_assignment_js(self, module_name: str, names: list[str]) -> str:
        parts = module_name.split(".")
        lines = ["window." + parts[0] + " = window." + parts[0] + " || {};"]
        current = "window." + parts[0]
        for part in parts[1:]:
            current = current + "." + part
            lines.append(f"{current} = {current} || {{}};")
        exports = ", ".join(f"{name}: {name}" for name in names)
        lines.append(f"Object.assign({current}, {{{exports}}});")
        return "\n".join(lines)

    def _lower_node(self, node: IRNode) -> None:
        """Lower one node, descending into wrapper functions when useful."""
        if isinstance(node, IRObserveBinding):
            self._lower_observe(node)
            return
        if isinstance(node, IROnChange):
            self._lower_on_change(node)
            return
        if isinstance(node, IRCanvasBlock):
            self._lower_canvas(node)
            return
        if isinstance(node, IRClassDecl):
            self._lower_class(node)
            return
        if isinstance(node, IRViewBinding):
            self._lower_view_binding(node)
            return
        if isinstance(node, IRRenderBlock):
            self._lower_render_block(node)
            return
        if isinstance(node, IRFunction):
            if self._is_ui_entry_function(node):
                self._ui_function_names.add(node.name)
                for child in node.body:
                    self._lower_node(child)
                return
            self._lower_function(node)
            if not node.is_async:
                self._ui_function_names.add(node.name)
                for child in node.body:
                    self._lower_node(child)
            return
        if hasattr(node, "target") and hasattr(node, "value"):
            self._functions.append(self._assignment_to_js(node, 0))

    def _is_ui_entry_function(self, node: IRFunction) -> bool:
        """Return True for functions that serve as reactive UI entry containers."""
        effects = getattr(node, "effects", None)
        if effects is None or not hasattr(effects, "names"):
            return False
        return "ui" in effects.names()

    def _emit_preamble(self) -> str:
        return """// Generated by Multilingual UI lowering
class ReactiveSignal {
  constructor(value) {
    this._value = value;
    this._handlers = [];
  }
  get() { return this._value; }
  set(value) {
    this._value = value;
    for (const handler of this._handlers) {
      handler(value);
    }
  }
  on_change(handler) {
    this._handlers.push(handler);
  }
}

class ReactiveList {
  constructor(value) {
    this._value = Array.from(value || []);
    this._handlers = [];
  }
  get() { return this._value.slice(); }
  set(value) {
    this._value = Array.from(value || []);
    this._notify();
  }
  setIndex(index, value) {
    this._value[index] = value;
    this._notify();
  }
  on_change(handler) {
    this._handlers.push(handler);
  }
  _notify() {
    const snapshot = this.get();
    for (const handler of this._handlers) {
      handler(snapshot);
    }
  }
}

class ReactiveEngine {
  constructor() {
    this.signals = {};
  }
  declare(name, initial) {
    if (!this.signals[name]) {
      this.signals[name] = __ml_signal(initial);
    }
    return this.signals[name];
  }
  get(name) {
    return this.signals[name];
  }
  on_change(name) {
    return (handler) => {
      this.declare(name, null).on_change(handler);
      return handler;
    };
  }
}

function __ml_signal(initial) {
  return Array.isArray(initial) ? new ReactiveList(initial) : new ReactiveSignal(initial);
}

function streamToView(source, target) {
  if (!source || !target || typeof source.on_change !== 'function') {
    return;
  }
  source.on_change((value) => {
    target.textContent = value == null ? '' : String(value);
  });
}

function intervalle(...args) {
  let start = 0;
  let stop = 0;
  let step = 1;
  if (args.length === 1) {
    stop = Number(args[0] ?? 0);
  } else if (args.length >= 2) {
    start = Number(args[0] ?? 0);
    stop = Number(args[1] ?? 0);
    step = Number(args[2] ?? 1);
  }
  if (!Number.isFinite(step) || step === 0) {
    step = 1;
  }
  const result = [];
  if (step > 0) {
    for (let i = start; i < stop; i += step) {
      result.push(i);
    }
  } else {
    for (let i = start; i > stop; i += step) {
      result.push(i);
    }
  }
  return result;
}

function __ml_contains(container, item) {
  if (container instanceof Set) {
    return container.has(item);
  }
  if (Array.isArray(container) || typeof container === 'string') {
    return container.includes(item);
  }
  if (container && typeof container === 'object') {
    return item in container;
  }
  return false;
}

function __ml_add(container, item) {
  if (container instanceof Set) {
    container.add(item);
    return container;
  }
  if (Array.isArray(container)) {
    container.push(item);
    return container;
  }
  return container;
}

function __ml_extend(container, values) {
  for (const value of values || []) {
    __ml_add(container, value);
  }
  return container;
}

function __ml_slice(start, stop, step) {
  return { start, stop, step };
}

const _engine = new ReactiveEngine();
const __ml_signals = _engine.signals;"""

    def _lower_observe(self, node: IRObserveBinding) -> None:
        self._signal_names.add(node.name)
        value = self._expr_to_js(node.value)
        self._result.js_signals.append(
            f"__ml_signals['{node.name}'] = _engine.declare('{node.name}', {value});"
        )

    def _lower_on_change(self, node: IROnChange) -> None:
        signal_name = self._signal_name(node.signal) or self._expr_to_js(node.signal)
        body = "\n".join(self._stmt_to_js(stmt, 1) for stmt in (node.body or []))
        if not body:
            body = "  return undefined;"
        self._result.js_handlers.append(
            f"_engine.on_change('{signal_name}')((value) => {{\n{body}\n}});"
        )

    def _lower_canvas(self, node: IRCanvasBlock) -> None:
        self._canvas_names.append(node.name or "canvas")

    def _lower_view_binding(self, node: IRViewBinding) -> None:
        signal_name = self._signal_name(node.signal)
        target_name = self._identifier_name(node.target) or self._expr_to_js(node.target)
        if signal_name:
            self._result.js_bindings.append(
                "streamToView("
                f"_engine.get('{signal_name}'), document.getElementById('{target_name}')"
                ");"
            )

    def _lower_function(self, node: IRFunction) -> None:
        keyword = "async function" if node.is_async else "function"
        params = ", ".join(self._param_to_js(param) for param in (node.parameters or []))
        self._local_scopes.append({param.name for param in (node.parameters or [])})
        body = "\n".join(self._stmt_to_js(stmt, 1) for stmt in (node.body or []))
        self._local_scopes.pop()
        self._functions.append(f"{keyword} {node.name}({params}) {{\n{body}\n}}")

    def _lower_class(self, node: IRClassDecl) -> None:
        lines = [f"class {node.name} {{"]
        for child in node.body or []:
            if not isinstance(child, IRFunction):
                continue
            name = "constructor" if child.name == "__init__" else child.name
            keyword = "async " if child.is_async else ""
            params = ", ".join(self._param_to_js(param) for param in (child.parameters or []))
            self._local_scopes.append({param.name for param in (child.parameters or [])})
            body = "\n".join(self._stmt_to_js(stmt, 2) for stmt in (child.body or []))
            self._local_scopes.pop()
            lines.append(f"  {keyword}{name}({params}) {{")
            if body:
                lines.append(body)
            lines.append("  }")
        lines.append("}")
        self._functions.append("\n".join(lines))

    def _param_to_js(self, param) -> str:
        if getattr(param, "default", None) is None:
            return param.name
        return f"{param.name} = {self._expr_to_js(param.default)}"

    def _lower_render_block(self, node: IRRenderBlock) -> None:
        self._has_render_root = True
        lines = [
            "function __ml_render() {",
            "  const __root = document.getElementById('__ml_root');",
            "  if (!__root) {",
            "    return;",
            "  }",
            "  __root.innerHTML = '';",
        ]
        if node.root is not None:
            lines.extend(self._element_to_js(node.root, "__root", 1))
        lines.append("}")
        self._render_function = "\n".join(lines)

    def _wire_render_updates(self) -> None:
        if not self._render_function:
            return
        for name in sorted(self._signal_names):
            self._result.js_handlers.append(
                f"_engine.on_change('{name}')(() => __ml_render());"
            )

    def _emit_html(self) -> str:
        canvas_html = "\n".join(
            f'    <div id="{name}" class="ml-canvas"></div>'
            for name in self._canvas_names
        )
        root_html = '    <div id="__ml_root"></div>' if self._has_render_root else ""
        title = (
            "Memory Game - Multilingual"
            if self._has_render_root
            else "Multilingual UI Preview"
        )
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{
      margin: 0;
      padding: 24px;
      font-family: system-ui, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .ml-canvas {{
      min-height: 48px;
      border: 1px dashed #8aa;
      padding: 12px;
      margin-bottom: 12px;
    }}
    .memory-game {{
      background: white;
      border-radius: 12px;
      padding: 32px;
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
      max-width: 600px;
    }}
    .memory-game h1 {{
      text-align: center;
      color: #333;
      margin-top: 0;
      margin-bottom: 24px;
      font-size: 28px;
    }}
    .game-board {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin-bottom: 24px;
      padding: 16px;
      background: #f5f5f5;
      border-radius: 8px;
    }}
    .card {{
      aspect-ratio: 1;
      padding: 0;
      border: 2px solid #ddd;
      background: #fff;
      color: #333;
      font-size: 32px;
      font-weight: bold;
      cursor: pointer;
      border-radius: 6px;
      transition: all 0.2s ease;
    }}
    .card:hover {{
      transform: scale(1.05);
      box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    }}
    .card:disabled {{
      opacity: 0.6;
      cursor: not-allowed;
    }}
    .card.revealed {{
      background: #e3f2fd;
      border-color: #2196f3;
      color: #1976d2;
    }}
    .card.matched {{
      background: #c8e6c9;
      border-color: #4caf50;
      color: #2e7d32;
    }}
    .status {{
      text-align: center;
      margin-bottom: 16px;
    }}
    .status p {{
      margin: 8px 0;
      color: #555;
      font-size: 16px;
    }}
    .reset-btn {{
      display: block;
      width: 100%;
      padding: 12px;
      margin-top: 8px;
      background: #667eea;
      color: white;
      border: none;
      border-radius: 6px;
      font-size: 16px;
      font-weight: bold;
      cursor: pointer;
      transition: background 0.2s ease;
    }}
    .reset-btn:hover {{
      background: #764ba2;
    }}
  </style>
</head>
<body>
{canvas_html}
{root_html}
  <script>
{self._result.js}
  </script>
</body>
</html>
"""

    def _stmt_to_js(self, stmt: IRNode, indent: int) -> str:
        pad = "  " * indent
        if isinstance(stmt, IRReturnStatement):
            if stmt.value is None:
                return f"{pad}return;"
            return f"{pad}return {self._expr_to_js(stmt.value)};"
        if isinstance(stmt, IRRaiseStatement):
            if stmt.value is None:
                return f"{pad}throw new Error();"
            return f"{pad}throw {self._expr_to_js(stmt.value)};"
        if isinstance(stmt, IRBreakStatement):
            return f"{pad}break;"
        if isinstance(stmt, IRContinueStatement):
            return f"{pad}continue;"
        if isinstance(stmt, IRImportStatement):
            return ""
        if isinstance(stmt, IRDelStatement):
            return f"{pad}delete {self._expr_to_js(stmt.target)};"
        if isinstance(stmt, IRIfStatement):
            return self._if_to_js(stmt, indent)
        if isinstance(stmt, IRForLoop):
            return self._for_to_js(stmt, indent)
        if isinstance(stmt, IRWhileLoop):
            return self._while_to_js(stmt, indent)
        if isinstance(stmt, IRTryStatement):
            return self._try_to_js(stmt, indent)
        if isinstance(stmt, IRExprStatement):
            return f"{pad}{self._expr_to_js(stmt.expression)};"
        if isinstance(stmt, IRCallExpr):
            return f"{pad}{self._expr_to_js(stmt)};"
        if isinstance(stmt, IRAwaitExpr):
            return f"{pad}{self._expr_to_js(stmt)};"
        if hasattr(stmt, "target") and hasattr(stmt, "value"):
            return self._assignment_to_js(stmt, indent)
        return f"{pad}// unsupported {type(stmt).__name__}"

    def _assignment_to_js(self, stmt: IRNode, indent: int) -> str:
        pad = "  " * indent
        target = getattr(stmt, "target", None)
        value = getattr(stmt, "value", None)
        if isinstance(target, IRIndexAccess):
            signal_name = self._signal_name(target.obj)
            index = self._expr_to_js(target.index)
            rendered = self._expr_to_js(value)
            if signal_name and signal_name in self._signal_names:
                return (
                    f"{pad}_engine.get('{signal_name}').setIndex({index}, {rendered});"
                )
            obj = self._expr_to_js(target.obj)
            return f"{pad}{obj}[{index}] = {rendered};"
        if isinstance(target, IRIdentifier):
            rendered = self._expr_to_js(value)
            if target.name in self._signal_names:
                return f"{pad}_engine.get('{target.name}').set({rendered});"
            if self._local_scopes and target.name not in self._local_scopes[-1]:
                self._local_scopes[-1].add(target.name)
                return f"{pad}var {target.name} = {rendered};"
            return f"{pad}{target.name} = {rendered};"
        rendered_target = self._expr_to_js(target)
        rendered_value = self._expr_to_js(value)
        return f"{pad}{rendered_target} = {rendered_value};"

    def _if_to_js(self, node: IRIfStatement, indent: int) -> str:
        pad = "  " * indent
        lines = [f"{pad}if ({self._expr_to_js(node.condition)}) {{"]
        lines.extend(self._stmt_to_js(stmt, indent + 1) for stmt in (node.body or []))
        lines.append(f"{pad}}}")
        for clause in (node.elif_clauses or []):
            lines.append(f"{pad}else if ({self._expr_to_js(clause.condition)}) {{")
            lines.extend(
                self._stmt_to_js(stmt, indent + 1) for stmt in (clause.body or [])
            )
            lines.append(f"{pad}}}")
        if node.else_body:
            lines.append(f"{pad}else {{")
            lines.extend(
                self._stmt_to_js(stmt, indent + 1) for stmt in (node.else_body or [])
            )
            lines.append(f"{pad}}}")
        return "\n".join(lines)

    def _try_to_js(self, node: IRTryStatement, indent: int) -> str:
        pad = "  " * indent
        lines = [f"{pad}try {{"]
        lines.extend(self._stmt_to_js(stmt, indent + 1) for stmt in (node.body or []))
        if not node.body:
            lines.append(f"{pad}  return undefined;")
        lines.append(f"{pad}}}")

        handler = node.handlers[0] if node.handlers else None
        error_name = self._exception_handler_name(handler)
        lines[-1] += f" catch ({error_name}) {{"
        handler_body = getattr(handler, "body", []) if handler else []
        lines.extend(self._stmt_to_js(stmt, indent + 1) for stmt in handler_body)
        lines.append(f"{pad}}}")

        if node.finally_body:
            lines[-1] += " finally {"
            lines.extend(self._stmt_to_js(stmt, indent + 1) for stmt in node.finally_body)
            lines.append(f"{pad}}}")
        return "\n".join(lines)

    def _exception_handler_name(self, handler: IRNode | None) -> str:
        if handler is None:
            return "error"
        explicit_name = getattr(handler, "name", None)
        if explicit_name:
            return explicit_name
        exc_type = getattr(handler, "exc_type", None)
        if isinstance(exc_type, IRIdentifier) and not exc_type.name[:1].isupper():
            return exc_type.name
        return "error"

    def _for_to_js(self, node: IRForLoop, indent: int) -> str:
        pad = "  " * indent
        target = self._loop_target_to_js(node.target) or "i"
        iterable = node.iterable
        if isinstance(iterable, IRCallExpr) and self._call_name(iterable.func) == "range":
            args = iterable.args or []
            if len(args) == 1:
                start, stop, step = "0", self._expr_to_js(args[0]), "1"
            elif len(args) == 2:
                start = self._expr_to_js(args[0])
                stop = self._expr_to_js(args[1])
                step = "1"
            else:
                start = self._expr_to_js(args[0])
                stop = self._expr_to_js(args[1])
                step = self._expr_to_js(args[2])
            lines = [
                f"{pad}for (let {target} = {start}; {target} < {stop}; {target} += {step}) {{"
            ]
            lines.extend(self._stmt_to_js(stmt, indent + 1) for stmt in (node.body or []))
            lines.append(f"{pad}}}")
            return "\n".join(lines)
        iterable_js = self._expr_to_js(iterable)
        lines = [f"{pad}for (const {target} of {iterable_js}) {{"]
        lines.extend(self._stmt_to_js(stmt, indent + 1) for stmt in (node.body or []))
        lines.append(f"{pad}}}")
        return "\n".join(lines)

    def _loop_target_to_js(self, target: IRNode | None) -> str | None:
        if isinstance(target, IRIdentifier):
            return target.name
        if isinstance(target, IRTupleLiteral):
            names = [self._identifier_name(element) for element in target.elements]
            if all(names):
                return "[" + ", ".join(name for name in names if name) + "]"
        return None

    def _while_to_js(self, node: IRWhileLoop, indent: int) -> str:
        pad = "  " * indent
        lines = [f"{pad}while ({self._expr_to_js(node.condition)}) {{"]
        lines.extend(self._stmt_to_js(stmt, indent + 1) for stmt in (node.body or []))
        lines.append(f"{pad}}}")
        return "\n".join(lines)

    def _element_to_js(self, elem: IRUIElement, parent_var: str, indent: int) -> list[str]:
        pad = "  " * indent
        lines: list[str] = []
        if elem.condition is not None:
            lines.append(f"{pad}if ({self._expr_to_js(elem.condition)}) {{")
            lines.extend(self._element_to_js_unconditional(elem, parent_var, indent + 1))
            lines.append(f"{pad}}}")
            return lines
        return self._element_to_js_unconditional(elem, parent_var, indent)

    def _element_to_js_unconditional(
        self, elem: IRUIElement, parent_var: str, indent: int
    ) -> list[str]:
        pad = "  " * indent
        var_name = f"__el_{abs(id(elem))}"
        lines = [f"{pad}const {var_name} = document.createElement('{elem.tag or 'div'}');"]

        for attr in (elem.attributes or []):
            value = self._expr_to_js(attr.value)
            if attr.name == "class" and not attr.is_class_binding:
                lines.append(f"{pad}{var_name}.className = {value};")
            elif attr.is_class_binding:
                class_name = attr.name.split(":", 1)[1] if ":" in attr.name else attr.name
                lines.append(
                    f"{pad}if ({value}) {{ {var_name}.classList.add('{class_name}'); }}"
                )
            elif attr.name == "disabled":
                lines.append(f"{pad}{var_name}.disabled = {value};")
            elif attr.is_event_handler:
                lines.append(
                    f"{pad}{var_name}.addEventListener('click', async () => {{ {value}; }});"
                )
            else:
                lines.append(f"{pad}{var_name}.setAttribute('{attr.name}', {value});")

        if elem.text_content is not None:
            lines.append(f"{pad}{var_name}.textContent = {self._expr_to_js(elem.text_content)};")

        for child in (elem.children or []):
            lines.extend(self._render_child(child, var_name, indent))

        lines.append(f"{pad}{parent_var}.appendChild({var_name});")
        return lines

    def _render_child(self, child: IRNode, parent_var: str, indent: int) -> list[str]:
        pad = "  " * indent
        if isinstance(child, IRUIElement):
            return self._element_to_js(child, parent_var, indent)
        if isinstance(child, IRForLoop):
            return [self._for_render_to_js(child, parent_var, indent)]
        if isinstance(child, IRIfStatement):
            return [self._if_render_to_js(child, parent_var, indent)]
        if isinstance(child, IRExprStatement):
            if isinstance(child.expression, IRCallExpr):
                if self._call_name(child.expression.func) in self._ui_function_names:
                    return []
            value = self._expr_to_js(child.expression)
            return [f"{pad}{parent_var}.appendChild(document.createTextNode(String({value})));"]
        if isinstance(child, (IRLiteral, IRCallExpr, IRIdentifier, IRBinaryOp, IRConditionalExpr)):
            value = self._expr_to_js(child)
            return [f"{pad}{parent_var}.appendChild(document.createTextNode(String({value})));"]
        return [f"{pad}// unsupported child {type(child).__name__}"]

    def _if_render_to_js(self, node: IRIfStatement, parent_var: str, indent: int) -> str:
        pad = "  " * indent
        lines = [f"{pad}if ({self._expr_to_js(node.condition)}) {{"]
        for stmt in (node.body or []):
            lines.extend(self._render_child(stmt, parent_var, indent + 1))
        lines.append(f"{pad}}}")
        for clause in (node.elif_clauses or []):
            lines.append(f"{pad}else if ({self._expr_to_js(clause.condition)}) {{")
            for stmt in (clause.body or []):
                lines.extend(self._render_child(stmt, parent_var, indent + 1))
            lines.append(f"{pad}}}")
        if node.else_body:
            lines.append(f"{pad}else {{")
            for stmt in (node.else_body or []):
                lines.extend(self._render_child(stmt, parent_var, indent + 1))
            lines.append(f"{pad}}}")
        return "\n".join(lines)

    def _for_render_to_js(self, node: IRForLoop, parent_var: str, indent: int) -> str:
        pad = "  " * indent
        target = self._identifier_name(node.target) or "i"
        iterable = node.iterable
        lines: list[str] = []
        if isinstance(iterable, IRCallExpr) and self._call_name(iterable.func) == "range":
            args = iterable.args or []
            if len(args) == 1:
                start, stop, step = "0", self._expr_to_js(args[0]), "1"
            elif len(args) == 2:
                start = self._expr_to_js(args[0])
                stop = self._expr_to_js(args[1])
                step = "1"
            else:
                start = self._expr_to_js(args[0])
                stop = self._expr_to_js(args[1])
                step = self._expr_to_js(args[2])
            lines.append(
                f"{pad}for (let {target} = {start}; {target} < {stop}; {target} += {step}) {{"
            )
        else:
            iterable_js = self._expr_to_js(iterable)
            lines.append(f"{pad}for (const {target} of {iterable_js}) {{")
        for stmt in (node.body or []):
            lines.extend(self._render_child(stmt, parent_var, indent + 1))
        lines.append(f"{pad}}}")
        return "\n".join(lines)

    def _expr_to_js(self, node: IRNode | None) -> str:
        if node is None:
            return "null"
        if isinstance(node, IRLiteral):
            if node.kind == "string":
                return repr(str(node.value))
            if node.kind == "bool":
                return "true" if bool(node.value) else "false"
            if node.kind == "none":
                return "null"
            return str(node.value)
        if isinstance(node, IRListLiteral):
            return "[" + ", ".join(self._expr_to_js(item) for item in node.elements) + "]"
        if isinstance(node, IRSetLiteral):
            return "new Set([" + ", ".join(self._expr_to_js(item) for item in node.elements) + "])"
        if isinstance(node, IRDictLiteral):
            entries = []
            for entry in node.entries:
                if isinstance(entry, tuple) and len(entry) == 2:
                    key, value = entry
                    rendered_key = self._expr_to_js(key)
                    rendered_value = self._expr_to_js(value)
                    entries.append(f"[{rendered_key}]: {rendered_value}")
            return "{" + ", ".join(entries) + "}"
        if isinstance(node, IRIdentifier):
            if node.name == "self":
                return "this"
            if node.name in _TRUE_NAMES:
                return "true"
            if node.name in _FALSE_NAMES:
                return "false"
            if node.name in _NONE_NAMES:
                return "null"
            if node.name in self._signal_names:
                return f"_engine.get('{node.name}').get()"
            return node.name
        if isinstance(node, IRIndexAccess):
            if isinstance(node.index, IRSliceExpr):
                start = (
                    self._expr_to_js(node.index.start)
                    if node.index.start is not None
                    else "undefined"
                )
                stop = (
                    self._expr_to_js(node.index.stop)
                    if node.index.stop is not None
                    else "undefined"
                )
                return f"{self._expr_to_js(node.obj)}.slice({start}, {stop})"
            return f"{self._expr_to_js(node.obj)}[{self._expr_to_js(node.index)}]"
        if isinstance(node, IRSliceExpr):
            start = self._expr_to_js(node.start) if node.start is not None else "undefined"
            stop = self._expr_to_js(node.stop) if node.stop is not None else "undefined"
            if node.step is not None:
                return f"__ml_slice({start}, {stop}, {self._expr_to_js(node.step)})"
            return f"__ml_slice({start}, {stop})"
        if isinstance(node, IRAttributeAccess):
            return f"{self._expr_to_js(node.obj)}.{node.attr}"
        if isinstance(node, IRBinaryOp):
            return f"({self._expr_to_js(node.left)} {node.op} {self._expr_to_js(node.right)})"
        if isinstance(node, IRBooleanOp):
            op_name = str(node.op).lower()
            op = " && " if op_name in ("and", "et", "&&") else " || "
            return "(" + op.join(self._expr_to_js(value) for value in node.values) + ")"
        if isinstance(node, IRCompareOp):
            left = self._expr_to_js(node.left)
            parts: list[str] = []
            current_left = left
            for op, right in node.comparators:
                right_js = self._expr_to_js(right)
                if op in ("in", "dans"):
                    parts.append(f"__ml_contains({right_js}, {current_left})")
                elif op in ("not in", "non dans"):
                    parts.append(f"(!__ml_contains({right_js}, {current_left}))")
                elif op in ("is", "est"):
                    parts.append(f"({current_left} === {right_js})")
                elif op in ("is not", "n'est pas", "nest pas"):
                    parts.append(f"({current_left} !== {right_js})")
                else:
                    parts.append(f"({current_left} {op} {right_js})")
                current_left = right_js
            return " && ".join(parts) if parts else left
        if isinstance(node, IRUnaryOp):
            if node.op in ("NOT", "not", "!"):
                return f"(!{self._expr_to_js(node.operand)})"
            return f"({node.op}{self._expr_to_js(node.operand)})"
        if isinstance(node, IRConditionalExpr):
            return (
                f"({self._expr_to_js(node.condition)}"
                f" ? {self._expr_to_js(node.true_expr)}"
                f" : {self._expr_to_js(node.false_expr)})"
            )
        if isinstance(node, IRCallExpr):
            call_name = self._call_name(node.func)
            args = ", ".join(self._expr_to_js(arg) for arg in (node.args or []))
            localized_method = self._localized_method_call_to_js(node)
            if localized_method is not None:
                return localized_method
            if call_name in _STR_NAMES:
                return f"String({args})"
            if call_name in _LIST_NAMES:
                return f"Array.from({args})" if args else "[]"
            if call_name in _NUMBER_NAMES:
                return f"Number({args})"
            if call_name in _RANGE_NAMES:
                return f"intervalle({args})"
            if call_name == "Exception":
                return f"new Error({args})"
            if call_name == "json.dumps":
                return f"JSON.stringify({args})"
            if call_name == "len":
                return f"({self._expr_to_js(node.args[0])}).length" if node.args else "0"
            if call_name == "asyncio.sleep":
                delay = self._expr_to_js(node.args[0]) if node.args else "0"
                return f"new Promise((resolve) => setTimeout(resolve, {delay} * 1000))"
            func_js = self._expr_to_js(node.func)
            constructor_name = call_name.rsplit(".", 1)[-1] if call_name else ""
            if constructor_name[:1].isupper():
                return f"new {func_js}({args})"
            return f"{func_js}({args})"
        if isinstance(node, IRAwaitExpr):
            return f"await {self._expr_to_js(node.value)}"
        return f"null /* {type(node).__name__} */"

    def _localized_method_call_to_js(self, node: IRCallExpr) -> str | None:
        if not isinstance(node.func, IRAttributeAccess):
            return None

        obj = self._expr_to_js(node.func.obj)
        attr = node.func.attr
        args = [self._expr_to_js(arg) for arg in (node.args or [])]

        if attr in {"obtenir", "get"}:
            key = args[0] if args else "undefined"
            default = args[1] if len(args) > 1 else "undefined"
            return f"(({obj})?.[{key}] ?? {default})"
        if attr in {"ajouter", "append"}:
            value = args[0] if args else "undefined"
            return f"__ml_add({obj}, {value})"
        if attr in {"etendre", "extend"}:
            values = args[0] if args else "[]"
            return f"__ml_extend({obj}, {values})"
        if attr in {"minuscule", "lower"}:
            return f"String({obj}).toLowerCase()"
        if attr in {"remplacer", "replace"}:
            return f"{obj}.replace({', '.join(args)})"
        if attr in {"joindre", "join"}:
            values = args[0] if args else "[]"
            return f"({values}).join({obj})"
        if attr == "items":
            return f"Object.entries({obj})"
        if attr == "keys":
            return f"Object.keys({obj})"
        if attr == "pop" and args and args[0] == "0":
            return f"{obj}.shift()"
        return None

    def _identifier_name(self, node: IRNode | None) -> str | None:
        return node.name if isinstance(node, IRIdentifier) else None

    def _signal_name(self, node: IRNode | None) -> str | None:
        if isinstance(node, IRIdentifier):
            return node.name
        return None

    def _call_name(self, node: IRNode | None) -> str | None:
        if isinstance(node, IRIdentifier):
            return node.name
        if isinstance(node, IRAttributeAccess):
            base = self._call_name(node.obj)
            if base:
                return f"{base}.{node.attr}"
        return None


def lower_to_ui(
    program: IRProgram,
    modules: dict[str, IRProgram] | None = None,
) -> UILoweringResult:
    """Lower an IRProgram to a browser preview bundle."""
    return UILoweringPass().lower(program, modules=modules)
