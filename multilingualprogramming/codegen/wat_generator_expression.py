#
# SPDX-FileCopyrightText: 2024 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Expression lowering helpers for the WAT generator."""

from multilingualprogramming.parser.ast_nodes import (
    AttributeAccess,
    BinaryOp,
    CallExpr,
    FStringLiteral,
    Identifier,
    IndexAccess,
    NumeralLiteral,
    StringLiteral,
)
from multilingualprogramming.codegen.wat_generator_support import _STR_NAMES, _name

# B3 : builtins qui produisent un f64 réinterprétable comme i32 (résultat
# garanti dans [-2^31, 2^31)). Permet à `_is_int_like_expr` de reconnaître
# un appel comme « shape i32 » et donc à `+`/`*` enchaînés d'utiliser i32 ops
# avec wraparound au lieu de f64.
_INT_LIKE_BUILTINS = frozenset({"imul32", "iadd32", "shr_u32"})

# B2 : builtins qui produisent un v128 (f64x2) sur la pile WAT. Permet à
# `_is_v128_expr` de reconnaître un appel comme « shape v128 » et donc à
# `+ - * /` enchaînés de dispatcher vers `f64x2.*` sur deux opérandes v128.
_V128_BUILTINS = frozenset({"v128_pair"})

class WATGeneratorExpressionMixin:
    """Helpers for lowering complex expressions."""

    @staticmethod
    def mixin_role() -> str:
        """Return a short description of the mixin's responsibility."""
        return "expression-lowering"

    def _gen_binop(self, node: BinaryOp, indent: str):  # noqa: C901
        op = node.op
        if op in ("==", "!=", "<", "<=", ">", ">="):
            self._gen_cmp_from_binop(node, indent)
            self._emit(f"{indent}f64.convert_i32_s")
            return
        if op in ("&", "|", "^"):
            self._emit_bitwise_binop(node, indent)
            return
        if op in ("<<", ">>"):
            self._emit_shift_binop(node, indent)
            return
        if op == "%":
            self._emit_modulo_binop(node, indent)
            return
        if op == "//":
            self._emit_floor_div_binop(node, indent)
            return
        if op == "**":
            self._emit_pow_binop(node, indent)
            return
        if op == "+" and self._is_string_binop(node):
            self._emit_string_concat_binop(node, indent)
            return
        if op == "*":
            repeat = self._list_repeat_operands(node)
            if repeat is not None:
                self._gen_list_repeat_alloc(repeat[0], repeat[1], indent)
                return
        self._emit_numeric_binop(node, indent)

    def _emit_modulo_binop(self, node: BinaryOp, indent: str):
        if isinstance(node.left, Identifier):
            tmp_name = f"__mod_left_{self._new_label()}"
            self._locals.add(tmp_name)
            self._gen_expr(node.left, indent)
            self._emit(f"{indent}local.set ${self._wat_symbol(tmp_name)}")
            self._emit(f"{indent}local.get ${self._wat_symbol(tmp_name)}")
            self._emit(f"{indent}local.get ${self._wat_symbol(tmp_name)}")
            self._gen_expr(node.right, indent)
            self._emit(f"{indent}f64.div")
            self._emit(f"{indent}f64.floor")
            self._gen_expr(node.right, indent)
            self._emit(f"{indent}f64.mul")
            self._emit(f"{indent}f64.sub")
            return
        self._emit(f"{indent};; f64 modulo")
        self._gen_expr(node.left, indent)
        self._gen_expr(node.left, indent)
        self._gen_expr(node.right, indent)
        self._emit(f"{indent}f64.div")
        self._emit(f"{indent}f64.floor")
        self._gen_expr(node.right, indent)
        self._emit(f"{indent}f64.mul")
        self._emit(f"{indent}f64.sub")

    def _emit_floor_div_binop(self, node: BinaryOp, indent: str):
        self._gen_expr(node.left, indent)
        self._gen_expr(node.right, indent)
        self._emit(f"{indent}f64.div")
        self._emit(f"{indent}f64.floor")

    def _emit_pow_binop(self, node: BinaryOp, indent: str):
        self._gen_expr(node.left, indent)
        self._gen_expr(node.right, indent)
        self._emit(f"{indent}call $pow_f64")

    def _is_string_binop(self, node: BinaryOp) -> bool:
        return self._is_string_value(node.left) and self._is_string_value(node.right)

    def _is_string_value(self, expr) -> bool:
        return (
            isinstance(expr, (StringLiteral, FStringLiteral))
            or (
                isinstance(expr, Identifier)
                and expr.name in self._string_len_locals
            )
            or (
                isinstance(expr, BinaryOp)
                and expr.op == "+"
                and self._is_string_binop(expr)
            )
            or (
                isinstance(expr, IndexAccess)
                and isinstance(expr.obj, Identifier)
                and expr.obj.name in self._string_len_locals
            )
            or (
                isinstance(expr, CallExpr)
                and (
                    _name(expr.func) == "dom_value_str"
                    or _name(expr.func) in self._string_return_funcs
                    or _name(expr.func) in _STR_NAMES
                    or (
                        isinstance(expr.func, AttributeAccess)
                        and expr.func.attr in (
                            "strip",
                            "lstrip",
                            "rstrip",
                            "upper",
                            "lower",
                            "replace",
                            "join",
                        )
                    )
                )
            )
        )

    def _emit_string_concat_binop(self, node: BinaryOp, indent: str):
        if isinstance(node.left, StringLiteral) and isinstance(node.right, StringLiteral):
            result = node.left.value + node.right.value
            offset, _ = self._intern(result)
            self._emit(f"{indent}f64.const {float(offset)}  ;; str concat (compile-time)")
            return
        self._ensure_str_concat_helper()
        self._emit(f"{indent};; str concat (runtime)")
        self._emit_string_value_with_len(node.left, indent)
        self._emit_string_value_with_len(node.right, indent)
        self._emit(f"{indent}call $__str_concat")

    def _emit_string_value_with_len(self, expr, indent: str):
        self._gen_expr(expr, indent)
        if isinstance(expr, StringLiteral):
            _, byte_len = self._intern(expr.value)
            self._emit(f"{indent}f64.const {float(byte_len)}")
            return
        if isinstance(expr, Identifier):
            len_local = self._string_len_locals[expr.name]
            self._emit(f"{indent}local.get ${self._wat_symbol(len_local)}")
            return
        if self._gen_string_len_expr(expr, indent):
            return
        # FStringLiteral, appel string-returning, OU concat imbriqué dont
        # un opérande est l'un des deux ci-dessus : l'évaluation a déjà
        # rempli `$__last_str_len` comme side-effect (f-strings via
        # _gen_fstring_expr, appels via la convention $__last_str_len,
        # `$__str_concat` qui pose len1+len2). On copie la globale.
        if isinstance(expr, (FStringLiteral, CallExpr)) or (
            isinstance(expr, BinaryOp) and expr.op == "+" and self._is_string_binop(expr)
        ):
            self._emit(f"{indent}global.get $__last_str_len")
            self._emit(f"{indent}f64.convert_i32_u")
            return
        raise ValueError(f"Unsupported string expression for WAT concat: {type(expr).__name__}")

    def _emit_numeric_binop(self, node: BinaryOp, indent: str):
        if node.op in ("+", "-", "*", "/") and self._should_use_v128_arith(node):
            self._emit_v128_arith_binop(node, indent)
            return
        if node.op in ("+", "*") and self._should_use_i32_arith(node):
            self._emit_i32_arith_binop(node, indent)
            return
        arith = {"+": "f64.add", "-": "f64.sub", "*": "f64.mul", "/": "f64.div"}
        self._gen_expr(node.left, indent)
        self._gen_expr(node.right, indent)
        self._emit(f"{indent}{arith.get(node.op, 'f64.add')}  ;; op={node.op!r}")

    # B2 ─────────────────────────────────────────────────────────────────────
    def _should_use_v128_arith(self, node: BinaryOp) -> bool:
        # Les deux côtés doivent être v128 : pas de coercition scalaire ↔ v128
        # implicite (un mélange tombe sur `f64.*` et échouera à la validation
        # WAT, ce qui pointera l'erreur à l'auteur — meilleur qu'un splat
        # silencieux qui masquerait un bug de typage).
        return self._is_v128_expr(node.left) and self._is_v128_expr(node.right)

    def _is_v128_expr(self, expr) -> bool:
        if isinstance(expr, Identifier):
            return expr.name in self._v128_locals
        if isinstance(expr, BinaryOp):
            if expr.op in ("+", "-", "*", "/"):
                return self._should_use_v128_arith(expr)
            return False
        if isinstance(expr, CallExpr):
            return _name(expr.func) in _V128_BUILTINS
        return False

    def _emit_v128_arith_binop(self, node: BinaryOp, indent: str):
        # Les deux opérandes sont v128 (vérifié par `_should_use_v128_arith`).
        # `_gen_expr` les empile en valeur v128 (via `local.get` typé v128,
        # ou via `v128_pair` qui produit un v128 sur la pile, ou via un
        # binop v128 imbriqué qui résoud ici récursivement).
        instr = {"+": "f64x2.add", "-": "f64x2.sub", "*": "f64x2.mul", "/": "f64x2.div"}[node.op]
        self._gen_expr(node.left, indent)
        self._gen_expr(node.right, indent)
        self._emit(f"{indent}{instr}  ;; SIMD f64x2 (op={node.op!r})")
    # ─────────────────────────────────────────────────────────────────────────

    def _should_use_i32_arith(self, node: BinaryOp) -> bool:
        # Require at least one side to be "earned" i32-shape (bitwise/shift,
        # i32 builtin, tracked local, nested i32-arith). Plain literal*literal
        # stays on f64 to avoid silently wrapping ordinary arithmetic.
        left_real = self._is_int_like_expr(node.left)
        right_real = self._is_int_like_expr(node.right)
        if not (left_real or right_real):
            return False
        return (
            (left_real or self._is_int_like_literal(node.left))
            and (right_real or self._is_int_like_literal(node.right))
        )

    def _is_int_like_expr(self, expr) -> bool:
        if isinstance(expr, Identifier):
            return expr.name in self._int_like_locals
        if isinstance(expr, BinaryOp):
            if expr.op in ("&", "|", "^", "<<", ">>"):
                return True
            if expr.op in ("+", "*"):
                return self._should_use_i32_arith(expr)
            return False
        if isinstance(expr, CallExpr):
            return _name(expr.func) in _INT_LIKE_BUILTINS
        return False

    @staticmethod
    def _is_int_like_literal(expr) -> bool:
        if not isinstance(expr, NumeralLiteral):
            return False
        raw = str(expr.value)
        if "." in raw or "e" in raw or "E" in raw or "j" in raw or "/" in raw:
            return False
        try:
            v = int(raw)
        except ValueError:
            return False
        return -(2**31) <= v < 2**31

    def _emit_i32_arith_binop(self, node: BinaryOp, indent: str):
        # Both operands are guaranteed to fit in i32 (either by prior bitwise
        # provenance or by being a small integer literal), so `i32.trunc_f64_s`
        # cannot trap. `i32.{add,mul}` wrap on overflow per WASM semantics.
        instr = {"+": "i32.add", "*": "i32.mul"}[node.op]
        self._gen_expr(node.left, indent)
        self._emit(f"{indent}i32.trunc_f64_s")
        self._gen_expr(node.right, indent)
        self._emit(f"{indent}i32.trunc_f64_s")
        self._emit(f"{indent}{instr}  ;; i32 wraparound (op={node.op!r})")
        self._emit(f"{indent}f64.convert_i32_s")

    def _emit_bitwise_binop(self, node: BinaryOp, indent: str):
        instr = {"&": "i32.and", "|": "i32.or", "^": "i32.xor"}[node.op]
        self._gen_expr(node.left, indent)
        self._emit(f"{indent}i32.trunc_f64_s")
        self._gen_expr(node.right, indent)
        self._emit(f"{indent}i32.trunc_f64_s")
        self._emit(f"{indent}{instr}")
        self._emit(f"{indent}f64.convert_i32_s")

    def _emit_shift_binop(self, node: BinaryOp, indent: str):
        instr = {"<<": "i32.shl", ">>": "i32.shr_s"}[node.op]
        self._gen_expr(node.left, indent)
        self._emit(f"{indent}i32.trunc_f64_s")
        self._gen_expr(node.right, indent)
        self._emit(f"{indent}i32.trunc_f64_s")
        self._emit(f"{indent}{instr}")
        self._emit(f"{indent}f64.convert_i32_s")
