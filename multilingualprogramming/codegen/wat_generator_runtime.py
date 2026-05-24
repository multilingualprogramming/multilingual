#
# SPDX-FileCopyrightText: 2024 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Runtime, string, and closure helpers for the WAT generator."""

from multilingualprogramming.parser.ast_nodes import (
    Assignment,
    AttributeAccess,
    BinaryOp,
    BooleanLiteral,
    BytesLiteral,
    CallExpr,
    DictLiteral,
    DictUnpackEntry,
    FStringLiteral,
    ForLoop,
    FromImportStatement,
    FunctionDef,
    Identifier,
    IfStatement,
    ImportStatement,
    LambdaExpr,
    ListComprehension,
    ListLiteral,
    LocalStatement,
    NumeralLiteral,
    ReturnStatement,
    SetComprehension,
    SetLiteral,
    StringLiteral,
    TupleLiteral,
    VariableDeclaration,
    WhileLoop,
)

from multilingualprogramming.codegen.wat_generator_support import (
    _DOM_CALLER_PARAMS,
    _LIST_NAMES,
    _SET_NAMES,
    _TUPLE_NAMES,
    _ZIP_NAMES,
    _name,
    _real_params,
)


class WATGeneratorRuntimeMixin:
    """Shared runtime-oriented lowering helpers."""

    def supports_runtime_lowering(self) -> bool:
        """Expose runtime helper availability for mixin-aware callers."""
        return True

    def _is_module_global(self, name: str) -> bool:
        """Return True when *name* should lower to a mutable module-global slot."""
        return name in getattr(self, "_module_global_names", set()) and name not in self._locals

    def _is_tracked_list_name(self, name: str) -> bool:
        """Return True when *name* refers to a tracked list-like value."""
        return (
            name in self._list_locals
            or name in getattr(self, "_module_global_list_names", set())
        )

    def _is_tracked_tuple_name(self, name: str) -> bool:
        """Return True when *name* refers to a tracked tuple-like value."""
        return (
            name in self._tuple_locals
            or name in getattr(self, "_module_global_tuple_names", set())
        )

    def _is_mutable_list_name(self, name: str) -> bool:
        """Return True when *name* can be updated through list-style methods."""
        return self._is_tracked_list_name(name) or self._is_module_global(name)

    def _emit_name_get(self, name: str, indent: str) -> bool:
        """Emit a load for *name* from local or module-global storage."""
        if name in self._locals:
            self._emit(f"{indent}local.get ${self._wat_symbol(name)}")
            return True
        if self._is_module_global(name):
            self._emit(f"{indent}global.get ${self._wat_symbol(name)}")
            return True
        return False

    def _emit_name_set(self, name: str, indent: str) -> bool:
        """Emit a store for *name* into local or module-global storage."""
        if name in self._locals:
            self._emit(f"{indent}local.set ${self._wat_symbol(name)}")
            return True
        if self._is_module_global(name):
            self._emit(f"{indent}global.set ${self._wat_symbol(name)}")
            return True
        return False

    def _gen_dom_call(self, fname: str, args, indent: str) -> None:
        """Lower a DOM builtin call to its WAT wrapper function.

        Each "str" caller param is lowered from the next argument:
          StringLiteral  -> i32.const ptr, i32.const len  (interned)
          other expr     -> gen_expr (f64 ptr), i32.trunc_f64_u, $__last_str_len
        Each "f64" caller param is lowered from the next argument as-is.
        Returns: f64 (handle or str ptr) left on stack; "" = void.
        """
        self._uses_dom = True
        caller_params = _DOM_CALLER_PARAMS.get(fname, [])
        arg_iter = iter(args)
        for pkind in caller_params:
            arg = next(arg_iter, None)
            if pkind == "str":
                if arg is None:
                    self._emit(f"{indent}i32.const 0")
                    self._emit(f"{indent}i32.const 0")
                elif isinstance(arg, StringLiteral):
                    ptr, slen = self._intern(arg.value)
                    self._emit(f"{indent}i32.const {ptr}")
                    self._emit(f"{indent}i32.const {slen}")
                else:
                    self._gen_expr(arg, indent)
                    self._emit(f"{indent}i32.trunc_f64_u")
                    self._emit(f"{indent}global.get $__last_str_len")
            elif pkind == "fn_idx":
                # Callback: register in lambda table, push table index as f64.
                if arg is None:
                    self._emit(f"{indent}f64.const 0")
                else:
                    cb_name = (
                        _name(arg)
                        if hasattr(arg, "name") or hasattr(arg, "attr")
                        else None
                    )
                    if cb_name and cb_name not in self._lambda_table:
                        self._lambda_table.append(cb_name)
                    idx = (
                        self._lambda_table.index(cb_name)
                        if cb_name and cb_name in self._lambda_table
                        else 0
                    )
                    self._emit(f"{indent}f64.const {float(idx)}  ;; callback table index")
            else:  # "f64" handle
                if arg is None:
                    self._emit(f"{indent}f64.const 0")
                else:
                    self._gen_expr(arg, indent)
        wat_fn = fname  # WAT wrapper function has the same name as the builtin
        self._emit(f"{indent}call ${wat_fn}")

    def _gen_dom_value_str(self, handle_arg, indent: str) -> None:
        """Lower ``dom_value_str(handle)`` to a heap-allocated tracked string.

        Reads the element's value into a fresh heap buffer via
        ``ml_dom_get_value`` and leaves the buffer pointer (as f64) on the
        stack with the byte length in ``$__last_str_len`` — i.e. a normal
        string value. Lets a single function read a DOM input without the
        caller managing a buffer.
        """
        self._uses_dom = True
        self._need_heap_ptr = True
        cap = 8192
        buf_local = f"__domval_{self._new_label()}_buf"
        self._locals.add(buf_local)
        sym = self._wat_symbol(buf_local)
        # Save current heap base as the result string pointer.
        self._emit(f"{indent};; dom_value_str(handle) → tracked string")
        self._emit(f"{indent}global.get $__heap_ptr")
        self._emit(f"{indent}f64.convert_i32_u")
        self._emit(f"{indent}local.set ${sym}")
        # ml_dom_get_value(handle f64, buf i32, cap i32) -> i32 bytes written
        self._gen_expr(handle_arg, indent)
        self._emit(f"{indent}local.get ${sym}")
        self._emit(f"{indent}i32.trunc_f64_u")
        self._emit(f"{indent}i32.const {cap}")
        self._emit(f"{indent}call $ml_dom_get_value")
        self._emit(f"{indent}global.set $__last_str_len")
        # Advance heap_ptr past the written bytes (rounded up to 8).
        self._emit(f"{indent}local.get ${sym}")
        self._emit(f"{indent}i32.trunc_f64_u")
        self._emit(f"{indent}global.get $__last_str_len")
        self._emit(f"{indent}i32.const 7")
        self._emit(f"{indent}i32.add")
        self._emit(f"{indent}i32.const -8")
        self._emit(f"{indent}i32.and")
        self._emit(f"{indent}i32.add")
        self._emit(f"{indent}global.set $__heap_ptr")
        # Push the result string pointer (f64).
        self._emit(f"{indent}local.get ${sym}")

    def _gen_len(self, arg_node, indent: str):
        """Emit WAT that pushes the length of a string or list variable."""
        if isinstance(arg_node, StringLiteral):
            _, byte_len = self._intern(arg_node.value)
            self._emit(f"{indent}f64.const {float(byte_len)}  ;; len of string literal")
        elif isinstance(arg_node, BytesLiteral):
            _, byte_len = self._intern(arg_node.value)
            self._emit(f"{indent}f64.const {float(byte_len)}  ;; len of bytes literal")
        elif isinstance(arg_node, Identifier):
            if arg_node.name in self._string_len_locals:
                len_local = self._string_len_locals[arg_node.name]
                self._emit(f"{indent}local.get ${self._wat_symbol(len_local)}")
            elif (
                self._is_tracked_list_name(arg_node.name)
                or self._is_tracked_tuple_name(arg_node.name)
                or arg_node.name in self._dict_key_maps
            ):
                # Load element count from the list header at offset 0.
                self._emit_name_get(arg_node.name, indent)
                self._emit(f"{indent}i32.trunc_f64_u")
                self._emit(f"{indent}f64.load  ;; list length from header")
            else:
                self._emit(
                    f"{indent}f64.const 0  "
                    f";; unsupported: len() of {arg_node.name!r} (unknown type)"
                )
        else:
            self._emit(
                f"{indent}f64.const 0  "
                f";; unsupported: len() of {type(arg_node).__name__}"
            )

    def _gen_string_len_expr(self, node, indent: str) -> bool:
        """Emit WAT that pushes a tracked UTF-8 byte length for *node*."""
        if isinstance(node, StringLiteral):
            _, byte_len = self._intern(node.value)
            self._emit(f"{indent}f64.const {float(byte_len)}")
            return True
        if isinstance(node, BytesLiteral):
            _, byte_len = self._intern(node.value)
            self._emit(f"{indent}f64.const {float(byte_len)}")
            return True
        if isinstance(node, Identifier) and node.name in self._string_len_locals:
            len_local = self._string_len_locals[node.name]
            self._emit(f"{indent}local.get ${self._wat_symbol(len_local)}")
            return True
        virtual_read = self._virtual_file_read_content(node)
        if virtual_read is not None:
            _, byte_len = self._intern(virtual_read)
            self._emit(f"{indent}f64.const {float(byte_len)}")
            return True
        if isinstance(node, BinaryOp) and node.op == "+" and self._is_string_binop(node):
            # Récursion : si l'un des opérandes n'a pas de longueur calculable
            # statiquement (FString, CallExpr, …), on renonce à l'addition et
            # on retourne False — l'appelant retombera sur `$__last_str_len`
            # rempli par l'évaluation du runtime-concat.
            start = len(self._instrs)
            if not self._gen_string_len_expr(node.left, indent):
                del self._instrs[start:]
                return False
            if not self._gen_string_len_expr(node.right, indent):
                del self._instrs[start:]
                return False
            self._emit(f"{indent}f64.add")
            return True
        return False

    def _update_string_tracking(self, name: str, value, indent: str) -> None:
        """Refresh tracked string-length metadata after storing into *name*."""
        if isinstance(value, FStringLiteral) or (
            isinstance(value, CallExpr) and _name(value.func) in self._string_return_funcs
        ):
            len_local = f"{name}_strlen"
            self._locals.add(len_local)
            self._emit(f"{indent}global.get $__last_str_len")
            self._emit(f"{indent}f64.convert_i32_u")
            self._emit(f"{indent}local.set ${self._wat_symbol(len_local)}")
            self._string_len_locals[name] = len_local
        elif self._gen_string_len_expr(value, indent):
            len_local = f"{name}_strlen"
            self._locals.add(len_local)
            self._emit(f"{indent}local.set ${self._wat_symbol(len_local)}")
            self._string_len_locals[name] = len_local
        elif self._is_string_value(value):
            # String subscript (s[i]), slice (s[a:b]), and string-valued method
            # calls leave the byte length in $__last_str_len during evaluation.
            len_local = f"{name}_strlen"
            self._locals.add(len_local)
            self._emit(f"{indent}global.get $__last_str_len")
            self._emit(f"{indent}f64.convert_i32_u")
            self._emit(f"{indent}local.set ${self._wat_symbol(len_local)}")
            self._string_len_locals[name] = len_local
        elif name in self._string_len_locals:
            del self._string_len_locals[name]

    def _update_collection_tracking(self, name: str, value) -> None:
        """Refresh tracked list/tuple metadata after storing into *name*."""
        list_names = (
            self._module_global_list_names
            if self._is_module_global(name)
            else self._list_locals
        )
        tuple_names = (
            self._module_global_tuple_names
            if self._is_module_global(name)
            else self._tuple_locals
        )
        if self._value_tracks_as_tuple(value):
            tuple_names.add(name)
            list_names.discard(name)
        elif self._value_tracks_as_list(value):
            list_names.add(name)
            tuple_names.discard(name)
        elif name in list_names:
            list_names.remove(name)
        elif name in tuple_names:
            tuple_names.remove(name)
        elements = self._resolve_static_sequence_elements(value)
        if elements is not None and (name in list_names or name in tuple_names):
            self._static_sequence_elements[name] = elements
        elif name in self._static_sequence_elements:
            del self._static_sequence_elements[name]
        if self._materialized_zip_elements_from_list_call(value) is not None:
            self._zip_pair_locals.add(name)
        elif name in self._zip_pair_locals:
            self._zip_pair_locals.remove(name)

    def _value_tracks_as_tuple(self, value) -> bool:
        """Return True when *value* should be treated as a tracked tuple."""
        if isinstance(value, TupleLiteral):
            return True
        if not isinstance(value, CallExpr):
            return False
        if _name(value.func) == "divmod" and len(value.args) == 2:
            return True
        return (
            _name(value.func) in _TUPLE_NAMES
            and len(value.args) == 1
            and isinstance(value.args[0], (ListLiteral, TupleLiteral))
        )

    def _value_tracks_as_list(self, value) -> bool:
        """Return True when *value* should be treated as a tracked list."""
        if isinstance(value, (ListLiteral, SetLiteral)):
            return True
        if self._list_repeat_operands(value) is not None:
            return True
        if self._is_materialized_sequence(value):
            return True
        if self._is_static_container_builtin(value):
            return True
        if not isinstance(value, CallExpr):
            return False
        if _name(value.func) == "sorted" and len(value.args) >= 1:
            return True
        if _name(value.func) in self._sequence_func_names:
            return True
        return self._is_materialized_list_call(value)

    @staticmethod
    def _is_materialized_sequence(value) -> bool:
        """Return True for simple one-clause comprehensions stored as sequences."""
        return (
            isinstance(value, (ListComprehension, SetComprehension))
            and len(getattr(value, "clauses", [])) == 1
            and not value.clauses[0].conditions
        )

    @staticmethod
    def _is_static_container_builtin(value) -> bool:
        """Return True for builtins that materialize a literal container input."""
        return (
            isinstance(value, CallExpr)
            and _name(value.func) in (_LIST_NAMES | _TUPLE_NAMES | _SET_NAMES)
            and len(value.args) == 1
            and isinstance(
                value.args[0],
                (ListLiteral, TupleLiteral, SetLiteral, DictLiteral),
            )
        )

    def _is_materialized_list_call(self, value) -> bool:
        """Return True when a list(...) call materializes a known sequence source."""
        return (
            isinstance(value, CallExpr)
            and _name(value.func) in _LIST_NAMES
            and len(value.args) == 1
            and isinstance(value.args[0], CallExpr)
            and (
                _name(value.args[0].func) in _ZIP_NAMES
                or _name(value.args[0].func) in self._sequence_func_names
            )
        )

    def _resolve_static_sequence_elements(self, value):
        """Return compile-time-known elements for list/tuple-like values."""
        if isinstance(value, (ListLiteral, TupleLiteral, SetLiteral)):
            return list(value.elements)
        if isinstance(value, Identifier):
            return self._static_sequence_elements.get(value.name)
        if not isinstance(value, CallExpr):
            return None
        fname = _name(value.func)
        if fname in _LIST_NAMES and len(value.args) == 1:
            arg = value.args[0]
            zip_elements = self._materialized_zip_elements(arg)
            if zip_elements is not None:
                return zip_elements
            return self._resolve_static_sequence_elements(arg)
        if fname in (_TUPLE_NAMES | _SET_NAMES) and len(value.args) == 1:
            return self._resolve_static_sequence_elements(value.args[0])
        return None

    def _materialized_zip_elements(self, value):
        """Return static tuple elements for a zip(...) call, or None."""
        if not isinstance(value, CallExpr) or _name(value.func) not in _ZIP_NAMES:
            return None
        if len(value.args) < 2:
            return None
        resolved_args = [
            self._resolve_static_sequence_elements(arg)
            for arg in value.args
        ]
        if any(elements is None for elements in resolved_args):
            return None
        zipped_len = min(len(elements) for elements in resolved_args)
        return [
            TupleLiteral([elements[index] for elements in resolved_args])
            for index in range(zipped_len)
        ]

    def _materialized_zip_elements_from_list_call(self, value):
        """Return static tuple elements for list(zip(...)), or None."""
        if (
                isinstance(value, CallExpr)
                and _name(value.func) in _LIST_NAMES
                and len(value.args) == 1
        ):
            return self._materialized_zip_elements(value.args[0])
        return None

    def _flatten_static_dict_entries(self, node):
        """Return an ordered mapping for a compile-time-resolvable DictLiteral."""
        if not isinstance(node, DictLiteral):
            return None
        flat: dict[str, object] = {}
        for entry in node.entries:
            if isinstance(entry, DictUnpackEntry):
                nested = self._flatten_static_dict_entries(entry.value)
                if nested is None:
                    return None
                flat.update(nested)
                continue
            if not (isinstance(entry, tuple) and len(entry) == 2):
                return None
            key_node, value_node = entry
            if not isinstance(key_node, StringLiteral):
                return None
            flat[key_node.value] = value_node
        return flat

    def _static_set_elements(self, node):
        """Return compile-time-deduplicated elements for a static set(...) call."""
        seq = None
        if isinstance(node, SetLiteral):
            seq = node.elements
        elif isinstance(node, (ListLiteral, TupleLiteral)):
            seq = node.elements
        if seq is None:
            return None
        result = []
        seen = set()
        for elem in seq:
            if isinstance(elem, NumeralLiteral):
                key = ("num", elem.value)
            elif isinstance(elem, StringLiteral):
                key = ("str", elem.value)
            elif isinstance(elem, BooleanLiteral):
                key = ("bool", elem.value)
            else:
                return None
            if key not in seen:
                seen.add(key)
                result.append(elem)
        return result

    def _update_int_like_tracking(self, name: str, value) -> None:
        """Track *name* as i32-shaped iff *value* is provably so (B3).

        Re-uses `_is_int_like_expr` from the expression mixin (recursive,
        already understands bitwise/shift/i32-builtin/chained `+`*). Drops
        the name from the set on re-assignment to a non-int-like value so
        stale i32 wraparound never bites a now-f64 local.
        """
        if self._is_int_like_expr(value):
            self._int_like_locals.add(name)
        elif name in self._int_like_locals:
            self._int_like_locals.discard(name)

    def _update_dict_tracking(self, name: str, value) -> None:
        """Refresh tracked static-dict metadata after storing into *name*."""
        if (isinstance(value, CallExpr)
                and _name(value.func) in _LIST_NAMES
                and len(value.args) == 1):
            value = value.args[0]
        mapping = self._flatten_static_dict_entries(value)
        if mapping is not None:
            self._dict_key_maps[name] = {key: index for index, key in enumerate(mapping)}
            return
        keys = self._static_dict_comp_keys(value)
        if keys is not None:
            self._dict_key_maps[name] = {key: index for index, key in enumerate(keys)}
        elif name in self._dict_key_maps:
            del self._dict_key_maps[name]

    def _update_assignment_tracking(self, name: str, value, indent: str) -> None:
        """Refresh side metadata after assignment-like stores into *name*."""
        self._update_string_tracking(name, value, indent)
        self._update_collection_tracking(name, value)
        self._update_dict_tracking(name, value)
        self._update_int_like_tracking(name, value)
        if isinstance(value, LambdaExpr):
            if self._lambda_table:
                self._lambda_locals[name] = self._lambda_table[-1]
        elif name in self._lambda_locals:
            del self._lambda_locals[name]
        if isinstance(value, CallExpr) and _name(value.func) in self._closure_factory_funcs:
            self._closure_locals[name] = self._closure_factory_funcs[_name(value.func)]
        elif name in self._closure_locals:
            del self._closure_locals[name]
        inferred_class = self._infer_class_name(value)
        if inferred_class:
            self._var_class_types[name] = inferred_class
        elif name in self._var_class_types:
            del self._var_class_types[name]

    def _clear_assignment_tracking(self, name: str) -> None:
        """Drop auxiliary metadata for a local after destructive-style updates."""
        if name in self._string_len_locals:
            del self._string_len_locals[name]
        if name in self._list_locals:
            self._list_locals.remove(name)
        if name in self._tuple_locals:
            self._tuple_locals.remove(name)
        if name in getattr(self, "_module_global_list_names", set()):
            self._module_global_list_names.remove(name)
        if name in getattr(self, "_module_global_tuple_names", set()):
            self._module_global_tuple_names.remove(name)
        if name in self._dict_key_maps:
            del self._dict_key_maps[name]
        if name in self._static_sequence_elements:
            del self._static_sequence_elements[name]
        if name in self._zip_pair_locals:
            self._zip_pair_locals.remove(name)
        if name in self._lambda_locals:
            del self._lambda_locals[name]
        if name in self._closure_locals:
            del self._closure_locals[name]
        if name in self._var_class_types:
            del self._var_class_types[name]

    def _resolve_virtual_file_op(self, call_expr: CallExpr):
        """Return metadata for a tracked open-handle method call, or None."""
        if not isinstance(call_expr.func, AttributeAccess):
            return None
        obj = call_expr.func.obj
        if not isinstance(obj, Identifier):
            return None
        alias = obj.name
        if alias not in self._open_aliases:
            return None
        path, mode = self._open_aliases[alias]
        return alias, path, mode, call_expr.func.attr

    def _virtual_file_read_content(self, node):
        """Return compile-time string content for a tracked file-handle read call."""
        if not isinstance(node, CallExpr):
            return None
        resolved = self._resolve_virtual_file_op(node)
        if resolved is None:
            return None
        _alias, path, mode, method = resolved
        if method != "read" or "r" not in mode:
            return None
        return self._virtual_file_contents.get(path, "")

    def _emit_last_str_len_from_f64(self, indent: str) -> None:
        """Convert a top-of-stack f64 length into $__last_str_len."""
        self._emit(f"{indent}i32.trunc_f64_u")
        self._emit(f"{indent}global.set $__last_str_len")

    def _ensure_string_format_helpers(self):
        """Emit scratch-buffer string formatting helpers once per module."""
        if self._string_format_helpers_emitted:
            return
        self._string_format_helpers_emitted = True
        mem_end = self._WASM_PAGES * 65536
        scratch = mem_end - 64
        fmt = scratch + 12
        lines = [
            "  (func $__fmt_default_tmpstr (param $v f64) (result i32 i32)",
            "    (local $neg i32)",
            "    (local $int_part i64)",
            "    local.get $v",
            "    f64.const 0",
            "    f64.lt",
            "    local.set $neg",
            "    local.get $neg",
            "    if",
            "      local.get $v",
            "      f64.neg",
            "      local.set $v",
            "    end",
            "    local.get $v",
            "    f64.trunc",
            "    i64.trunc_f64_u",
            "    local.set $int_part",
            "    local.get $int_part",
            "    call $__fmt_u64",
            "    local.get $neg",
            "    if (result i32 i32)",
            "      local.set $ml_len",
            "      local.set $ml_ptr",
            "      local.get $ml_ptr",
            "      i32.const 1",
            "      i32.sub",
            "      i32.const 45",
            "      i32.store8",
            "      local.get $ml_ptr",
            "      i32.const 1",
            "      i32.sub",
            "      local.get $ml_len",
            "      i32.const 1",
            "      i32.add",
            "    end",
            "  )",
        ]
        # Replace temp locals with declarations for valid WAT.
        lines[0] = "  (func $__fmt_default_tmpstr (param $v f64) (result i32 i32)"
        lines.insert(1, "    (local $ml_ptr i32)")
        lines.insert(2, "    (local $ml_len i32)")
        lines.insert(3, "    (local $neg i32)")
        lines.insert(4, "    (local $int_part i64)")
        lines = [
            "  (func $__fmt_default_tmpstr (param $v f64) (result f64 f64)",
            "    (local $ml_ptr i32)",
            "    (local $ml_len i32)",
            "    (local $neg i32)",
            "    (local $int_part i64)",
            "    local.get $v",
            "    f64.const 0",
            "    f64.lt",
            "    local.set $neg",
            "    local.get $neg",
            "    if",
            "      local.get $v",
            "      f64.neg",
            "      local.set $v",
            "    end",
            "    local.get $v",
            "    f64.trunc",
            "    i64.trunc_f64_u",
            "    local.set $int_part",
            "    local.get $int_part",
            "    call $__fmt_u64",
            "    local.set $ml_len",
            "    local.set $ml_ptr",
            "    local.get $neg",
            "    if",
            "      local.get $ml_ptr",
            "      i32.const 1",
            "      i32.sub",
            "      i32.const 45",
            "      i32.store8",
            "      local.get $ml_ptr",
            "      i32.const 1",
            "      i32.sub",
            "      local.set $ml_ptr",
            "      local.get $ml_len",
            "      i32.const 1",
            "      i32.add",
            "      local.set $ml_len",
            "    end",
            "    local.get $ml_ptr",
            "    f64.convert_i32_u",
            "    local.get $ml_len",
            "    f64.convert_i32_u",
            "  )",
            "  (func $__fmt_fixed1_tmpstr (param $v f64) (result f64 f64)",
            "    (local $int_part i64)",
            "    (local $frac_digit i32)",
            "    (local $ptr i32)",
            "    (local $len i32)",
            "    (local $neg i32)",
            "    (local $copy_i i32)",
            "    local.get $v",
            "    f64.const 0",
            "    f64.lt",
            "    local.set $neg",
            "    local.get $neg",
            "    if",
            "      local.get $v",
            "      f64.neg",
            "      local.set $v",
            "    end",
            "    local.get $v",
            "    f64.trunc",
            "    i64.trunc_f64_u",
            "    local.set $int_part",
            "    local.get $int_part",
            "    call $__fmt_u64",
            "    local.set $len",
            "    local.set $ptr",
            f"    i32.const {fmt}",
            "    local.set $copy_i",
            "    local.get $neg",
            "    if",
            "      local.get $copy_i",
            "      i32.const 45",
            "      i32.store8",
            "      local.get $copy_i",
            "      i32.const 1",
            "      i32.add",
            "      local.set $copy_i",
            "    end",
            "    block $copy_done",
            "      loop $copy_lp",
            "        local.get $len",
            "        i32.eqz",
            "        br_if $copy_done",
            "        local.get $copy_i",
            "        local.get $ptr",
            "        i32.load8_u",
            "        i32.store8",
            "        local.get $copy_i",
            "        i32.const 1",
            "        i32.add",
            "        local.set $copy_i",
            "        local.get $ptr",
            "        i32.const 1",
            "        i32.add",
            "        local.set $ptr",
            "        local.get $len",
            "        i32.const 1",
            "        i32.sub",
            "        local.set $len",
            "        br $copy_lp",
            "      end",
            "    end",
            "    local.get $copy_i",
            "    i32.const 46",
            "    i32.store8",
            "    local.get $copy_i",
            "    i32.const 1",
            "    i32.add",
            "    local.set $copy_i",
            "    local.get $v",
            "    local.get $v",
            "    f64.trunc",
            "    f64.sub",
            "    f64.const 10",
            "    f64.mul",
            "    f64.nearest",
            "    i32.trunc_f64_u",
            "    local.set $frac_digit",
            "    local.get $copy_i",
            "    local.get $frac_digit",
            "    i32.const 48",
            "    i32.add",
            "    i32.store8",
            f"    i32.const {fmt}",
            "    f64.convert_i32_u",
            "    local.get $neg",
            "    if (result f64)",
            "      f64.const 4",
            "    else",
            "      f64.const 3",
            "    end",
            "  )",
        ]
        self._funcs.append("\n".join(lines))

    @staticmethod
    def _parse_fixed_format_spec(spec: str):
        """Return decimal-places count if *spec* matches ``.Nf`` (N=0..9), else None."""
        import re  # pylint: disable=import-outside-toplevel
        m = re.fullmatch(r"\.(\d)f", spec)
        if m:
            return int(m.group(1))
        return None

    def _ensure_fixed_dyn_helper(self) -> str:
        """Émet (une fois) `$__fmt_fixed_dyn(v, n)` qui dispatche vers les
        helpers fixedN existants selon la valeur runtime de n (0..9). Clamp
        en dehors : n<0 → ".0f" (entier arrondi), n>9 → ".9f".

        Permet une fonction multilingual `format_fixed(v, n)` avec n variable
        au runtime — sans cela il faut une fonction par N (formatter_fixe_2/3/5/6
        comme on l'a vu côté fractales).
        """
        if getattr(self, "_string_format_fixed_dyn_emitted", False):
            return "$__fmt_fixed_dyn"
        self._string_format_fixed_dyn_emitted = True
        # On garantit que tous les helpers fixedN qu'on va appeler existent.
        self._ensure_string_format_helpers()
        for k in range(2, 10):
            self._ensure_fixedN_format_helper(k)
        lines = ["  (func $__fmt_fixed_dyn (param $v f64) (param $n i32) (result f64 f64)"]
        # Clamp inférieur : n<0 → n=0.
        lines.append("    local.get $n")
        lines.append("    i32.const 0")
        lines.append("    i32.lt_s")
        lines.append("    if")
        lines.append("      i32.const 0")
        lines.append("      local.set $n")
        lines.append("    end")
        # Clamp supérieur : n>9 → n=9.
        lines.append("    local.get $n")
        lines.append("    i32.const 9")
        lines.append("    i32.gt_s")
        lines.append("    if")
        lines.append("      i32.const 9")
        lines.append("      local.set $n")
        lines.append("    end")
        # n=0 → arrondir + helper par défaut (entier).
        lines.append("    local.get $n")
        lines.append("    i32.eqz")
        lines.append("    if (result f64 f64)")
        lines.append("      local.get $v")
        lines.append("      f64.nearest")
        lines.append("      call $__fmt_default_tmpstr")
        lines.append("    else")
        # Cascade if pour n=1..9. Compact mais lisible.
        for k in range(1, 9):
            indent = "      " + "  " * (k - 1)
            lines.append(f"{indent}local.get $n")
            lines.append(f"{indent}i32.const {k}")
            lines.append(f"{indent}i32.eq")
            lines.append(f"{indent}if (result f64 f64)")
            lines.append(f"{indent}  local.get $v")
            lines.append(f"{indent}  call $__fmt_fixed{k}_tmpstr")
            lines.append(f"{indent}else")
        # n=9 (cas par défaut au fond de la cascade)
        deepest = "      " + "  " * 8
        lines.append(f"{deepest}local.get $v")
        lines.append(f"{deepest}call $__fmt_fixed9_tmpstr")
        # Ferme chaque `else` ouvert (8 cas + le tout-extérieur n=0).
        for k in range(8, 0, -1):
            indent = "      " + "  " * (k - 1)
            lines.append(f"{indent}end")
        lines.append("    end")
        lines.append("  )")
        self._funcs.append("\n".join(lines))
        return "$__fmt_fixed_dyn"

    def _ensure_fixedN_format_helper(self, n: int) -> str:  # pylint: disable=too-many-statements
        """Emit (once) a ``$__fmt_fixedN_tmpstr`` helper for N decimal places."""
        attr = f"_string_format_fixed{n}_emitted"
        if getattr(self, attr, False):
            return f"$__fmt_fixed{n}_tmpstr"
        setattr(self, attr, True)
        if n == 1:
            # Already emitted by _ensure_string_format_helpers.
            return "$__fmt_fixed1_tmpstr"
        self._ensure_string_format_helpers()
        mem_end = self._WASM_PAGES * 65536
        scratch = mem_end - 64
        fmt = scratch + 12
        multiplier = 10 ** n
        lines = [
            f"  (func $__fmt_fixed{n}_tmpstr (param $v f64) (result f64 f64)",
            "    (local $int_part i64)",
            "    (local $frac_digits i64)",
            "    (local $ptr i32)",
            "    (local $len i32)",
            "    (local $neg i32)",
            "    (local $copy_i i32)",
            "    (local $rem i64)",
            "    (local $dig i32)",
            "    (local $j i32)",
            "    local.get $v",
            "    f64.const 0",
            "    f64.lt",
            "    local.set $neg",
            "    local.get $neg",
            "    if",
            "      local.get $v",
            "      f64.neg",
            "      local.set $v",
            "    end",
            "    local.get $v",
            "    f64.trunc",
            "    i64.trunc_f64_u",
            "    local.set $int_part",
            "    local.get $int_part",
            "    call $__fmt_u64",
            "    local.set $len",
            "    local.set $ptr",
            f"    i32.const {fmt}",
            "    local.set $copy_i",
            "    local.get $neg",
            "    if",
            "      local.get $copy_i",
            "      i32.const 45",
            "      i32.store8",
            "      local.get $copy_i",
            "      i32.const 1",
            "      i32.add",
            "      local.set $copy_i",
            "    end",
            "    block $copy_done",
            "      loop $copy_lp",
            "        local.get $len",
            "        i32.eqz",
            "        br_if $copy_done",
            "        local.get $copy_i",
            "        local.get $ptr",
            "        i32.load8_u",
            "        i32.store8",
            "        local.get $copy_i",
            "        i32.const 1",
            "        i32.add",
            "        local.set $copy_i",
            "        local.get $ptr",
            "        i32.const 1",
            "        i32.add",
            "        local.set $ptr",
            "        local.get $len",
            "        i32.const 1",
            "        i32.sub",
            "        local.set $len",
            "        br $copy_lp",
            "      end",
            "    end",
            "    ;; decimal point",
            "    local.get $copy_i",
            "    i32.const 46",
            "    i32.store8",
            "    local.get $copy_i",
            "    i32.const 1",
            "    i32.add",
            "    local.set $copy_i",
            "    ;; fractional digits",
            "    local.get $v",
            "    local.get $v",
            "    f64.trunc",
            "    f64.sub",
            f"    f64.const {float(multiplier)}",
            "    f64.mul",
            "    f64.nearest",
            "    i64.trunc_f64_u",
            "    local.set $frac_digits",
        ]
        # Emit n digits (most-significant first) via repeated div/mod.
        # We emit them into a temp buffer then copy forward.
        # Simpler: emit digits in reverse then write in order.
        # Use a digit-by-digit approach with repeated mod 10.
        # Store all N digits by computing them from high to low.
        denom = multiplier
        for _ in range(n):
            denom //= 10
            if denom == 0:
                lines += [
                    "    local.get $copy_i",
                    "    local.get $frac_digits",
                    "    i64.const 10",
                    "    i64.rem_u",
                    "    i32.wrap_i64",
                    "    i32.const 48",
                    "    i32.add",
                    "    i32.store8",
                    "    local.get $copy_i",
                    "    i32.const 1",
                    "    i32.add",
                    "    local.set $copy_i",
                ]
                break
            lines += [
                "    local.get $copy_i",
                "    local.get $frac_digits",
                f"    i64.const {denom}",
                "    i64.div_u",
                "    i64.const 10",
                "    i64.rem_u",
                "    i32.wrap_i64",
                "    i32.const 48",
                "    i32.add",
                "    i32.store8",
                "    local.get $copy_i",
                "    i32.const 1",
                "    i32.add",
                "    local.set $copy_i",
            ]
        # Compute total length = (neg ? 1 : 0) + int_part_len + 1 (dot) + n.
        # We track copy_i - fmt to get the total length.
        lines += [
            f"    i32.const {fmt}",
            "    f64.convert_i32_u",
            "    local.get $copy_i",
            f"    i32.const {fmt}",
            "    i32.sub",
            "    f64.convert_i32_u",
            "  )",
        ]
        self._funcs.append("\n".join(lines))
        return f"$__fmt_fixed{n}_tmpstr"

    def _emit_fstring_part_ptr_len(  # pylint: disable=too-many-statements
        self, part, indent: str
    ) -> bool:
        """Emit ptr/len f64 pairs for a supported f-string part."""
        if isinstance(part, str):
            offset, length = self._intern(part)
            self._emit(f"{indent}f64.const {float(offset)}")
            self._emit(f"{indent}f64.const {float(length)}")
            return True
        format_spec = getattr(part, "fstring_format_spec", "")
        if self._is_string_value(part):
            self._gen_expr(part, indent)
            self._gen_string_len_expr(part, indent)
            return True
        # Support integer format specs: d, i → truncate to int and format as integer.
        if format_spec in ("d", "i"):
            self._ensure_string_format_helpers()
            label = self._new_label()
            ptr_local = f"__fmt_ptr_{label}"
            len_local = f"__fmt_len_{label}"
            self._locals.update({ptr_local, len_local})
            self._gen_expr(part, indent)
            self._emit(f"{indent}f64.trunc  ;; truncate to int for 'd'/'i' format")
            self._emit(f"{indent}call $__fmt_default_tmpstr")
            self._emit(f"{indent}local.set ${self._wat_symbol(len_local)}")
            self._emit(f"{indent}local.set ${self._wat_symbol(ptr_local)}")
            self._emit(f"{indent}local.get ${self._wat_symbol(ptr_local)}")
            self._emit(f"{indent}local.get ${self._wat_symbol(len_local)}")
            return True
        # Support .Nf format specs (N = 0..9).
        n_decimals = self._parse_fixed_format_spec(format_spec)
        if n_decimals is not None:
            self._ensure_string_format_helpers()
            label = self._new_label()
            ptr_local = f"__fmt_ptr_{label}"
            len_local = f"__fmt_len_{label}"
            self._locals.update({ptr_local, len_local})
            self._gen_expr(part, indent)
            if n_decimals == 0:
                # Round and format as integer.
                self._emit(f"{indent}f64.nearest")
                helper = "$__fmt_default_tmpstr"
            elif n_decimals == 1:
                helper = "$__fmt_fixed1_tmpstr"
            else:
                helper = self._ensure_fixedN_format_helper(n_decimals)
            self._emit(f"{indent}call {helper}")
            self._emit(f"{indent}local.set ${self._wat_symbol(len_local)}")
            self._emit(f"{indent}local.set ${self._wat_symbol(ptr_local)}")
            self._emit(f"{indent}local.get ${self._wat_symbol(ptr_local)}")
            self._emit(f"{indent}local.get ${self._wat_symbol(len_local)}")
            return True
        if format_spec not in ("",):
            return False
        label = self._new_label()
        ptr_local = f"__fmt_ptr_{label}"
        len_local = f"__fmt_len_{label}"
        self._locals.update({ptr_local, len_local})
        self._gen_expr(part, indent)
        self._emit(f"{indent}call $__str_from_f64")
        self._emit(f"{indent}local.set ${self._wat_symbol(ptr_local)}")
        self._emit(f"{indent}global.get $__last_str_len")
        self._emit(f"{indent}f64.convert_i32_u")
        self._emit(f"{indent}local.set ${self._wat_symbol(len_local)}")
        self._emit(f"{indent}local.get ${self._wat_symbol(ptr_local)}")
        self._emit(f"{indent}local.get ${self._wat_symbol(len_local)}")
        return True

    def _gen_fstring_expr(self, node: FStringLiteral, indent: str) -> bool:
        """Lower a supported f-string by concatenating part ptr/len pairs."""
        if not node.parts:
            self._emit(f"{indent}f64.const 0")
            self._emit(f"{indent}i32.const 0")
            self._emit(f"{indent}global.set $__last_str_len")
            return True
        label = self._new_label()
        ptr_local = f"__fstr_ptr_{label}"
        len_local = f"__fstr_len_{label}"
        part_ptr = f"__fstr_part_ptr_{label}"
        part_len = f"__fstr_part_len_{label}"
        self._locals.update({ptr_local, len_local, part_ptr, part_len})
        self._ensure_str_concat_helper()
        first = True
        for part in node.parts:
            if not self._emit_fstring_part_ptr_len(part, indent):
                return False
            self._emit(f"{indent}local.set ${self._wat_symbol(part_len)}")
            self._emit(f"{indent}local.set ${self._wat_symbol(part_ptr)}")
            if first:
                self._emit(f"{indent}local.get ${self._wat_symbol(part_ptr)}")
                self._emit(f"{indent}local.set ${self._wat_symbol(ptr_local)}")
                self._emit(f"{indent}local.get ${self._wat_symbol(part_len)}")
                self._emit(f"{indent}local.set ${self._wat_symbol(len_local)}")
                first = False
            else:
                self._emit(f"{indent}local.get ${self._wat_symbol(ptr_local)}")
                self._emit(f"{indent}local.get ${self._wat_symbol(len_local)}")
                self._emit(f"{indent}local.get ${self._wat_symbol(part_ptr)}")
                self._emit(f"{indent}local.get ${self._wat_symbol(part_len)}")
                self._emit(f"{indent}call $__str_concat")
                self._emit(f"{indent}local.set ${self._wat_symbol(ptr_local)}")
                self._emit(f"{indent}local.get ${self._wat_symbol(len_local)}")
                self._emit(f"{indent}local.get ${self._wat_symbol(part_len)}")
                self._emit(f"{indent}f64.add")
                self._emit(f"{indent}local.set ${self._wat_symbol(len_local)}")
        self._emit(f"{indent}local.get ${self._wat_symbol(len_local)}")
        self._emit_last_str_len_from_f64(indent)
        self._emit(f"{indent}local.get ${self._wat_symbol(ptr_local)}")
        return True

    def _emit(self, line: str):
        self._instrs.append(line)

    def _gen_stmts(self, stmts: list, indent: str):
        for stmt in stmts:
            self._gen_stmt(stmt, indent)

    def _collect_import_aliases(self, stmts: list) -> None:
        """Record simple import aliases for known native math lowerings."""
        recognized = {"sqrt", "floor", "ceil", "fabs", "pow"}
        for stmt in stmts:
            if isinstance(stmt, ImportStatement):
                module_alias = stmt.alias or stmt.module
                self._module_aliases[module_alias] = stmt.module
            elif isinstance(stmt, FromImportStatement) and stmt.module == "math":
                for imported_name, imported_alias in stmt.names:
                    local_name = imported_alias or imported_name
                    if imported_name in recognized:
                        self._imported_call_aliases[local_name] = f"math.{imported_name}"

    def _resolve_callable_alias(self, fname: str) -> str:
        """Resolve simple imported/module-qualified aliases for builtin lowering."""
        if fname in self._imported_call_aliases:
            return self._imported_call_aliases[fname]
        if "." in fname:
            module_name, attr_name = fname.split(".", 1)
            resolved_module = self._module_aliases.get(module_name, module_name)
            return f"{resolved_module}.{attr_name}"
        return fname

    def _returns_string_like(self, func_def: FunctionDef) -> bool:
        """Best-effort check for functions that return string-like values."""
        def _stmt_returns_string(stmt):
            if isinstance(stmt, ReturnStatement) and stmt.value is not None:
                return self._is_string_value(stmt.value) or isinstance(stmt.value, FStringLiteral)
            if isinstance(stmt, IfStatement):
                else_body = stmt.else_body or []
                return any(_stmt_returns_string(inner) for inner in stmt.body + else_body)
            return False

        return any(_stmt_returns_string(stmt) for stmt in func_def.body)

    def _multi_value_return_arity(self, func_def: FunctionDef) -> int:
        """Return N≥2 if every reachable `retour` returns a TupleLiteral of arity N
        (with non-string elements) ; 1 otherwise.

        Multi-value returns lower to a WAT signature `(result f64 f64 …)` and
        `retour (a, b)` pushes N values then `return`. Heterogeneous arities or
        mixed tuple/non-tuple returns disable the optimization (function falls
        back to single-value semantics).
        """
        from multilingualprogramming.parser.ast_nodes import (  # pylint: disable=import-outside-toplevel
            TupleLiteral as _TupleLiteral,
            IfStatement as _IfStatement,
        )

        seen_arities: set[int] = set()
        has_non_tuple_return: list[bool] = [False]

        def _collect(stmt):
            if isinstance(stmt, ReturnStatement):
                if stmt.value is None:
                    has_non_tuple_return[0] = True
                    return
                if isinstance(stmt.value, _TupleLiteral):
                    # tuple de 1 élément ≡ scalaire (cas rare ; on l'ignore).
                    if len(stmt.value.elements) >= 2:
                        # Refuse les éléments string — multi-valeur ne porte que
                        # des f64 pour l'instant.
                        if any(self._is_string_value(el) for el in stmt.value.elements):
                            has_non_tuple_return[0] = True
                            return
                        seen_arities.add(len(stmt.value.elements))
                        return
                has_non_tuple_return[0] = True
                return
            if isinstance(stmt, _IfStatement):
                for inner in stmt.body + (stmt.else_body or []):
                    _collect(inner)
                return
            # Autres compounds : peuvent contenir return — descendre. (Boucles
            # sont skip-safe : un retour à l'intérieur compte aussi.)
            for attr in ("body", "else_body", "finally_body"):
                inner_body = getattr(stmt, attr, None)
                if inner_body:
                    for inner in inner_body:
                        _collect(inner)

        for stmt in func_def.body:
            _collect(stmt)

        if has_non_tuple_return[0] or len(seen_arities) != 1:
            return 1
        return next(iter(seen_arities))

    def _returns_list_like(self, func_def: FunctionDef) -> bool:
        """Best-effort check for functions that return list/tuple-like values.

        Recognizes ``retour [..]``, ``retour [expr] * n``, ``retour <local>``
        where ``<local>`` was assigned a tracked list value, and propagated
        returns from already-known list-returning callees. Used to populate
        ``_sequence_func_names`` so that the caller's ``x = func(...)`` knows
        ``x`` is a list pointer (enabling ``x[i]`` indexing).
        """
        # First pass: collect locals known to hold lists inside this function.
        list_locals = set()
        list_locals.update(self._func_param_list_names.get(_name(func_def.name), set()))

        def _track_assign(target, value):
            if not isinstance(target, Identifier):
                return
            if self._value_tracks_as_list(value):
                list_locals.add(target.name)
            elif isinstance(value, Identifier) and value.name in list_locals:
                list_locals.add(target.name)

        def _visit_for_tracking(stmt):
            if isinstance(stmt, VariableDeclaration) and isinstance(stmt.name, Identifier):
                _track_assign(stmt.name, stmt.value)
            elif isinstance(stmt, Assignment):
                _track_assign(stmt.target, stmt.value)
            elif isinstance(stmt, IfStatement):
                for inner in stmt.body + (stmt.else_body or []):
                    _visit_for_tracking(inner)
            elif isinstance(stmt, WhileLoop):
                for inner in stmt.body:
                    _visit_for_tracking(inner)
            elif isinstance(stmt, ForLoop):
                for inner in stmt.body:
                    _visit_for_tracking(inner)

        for stmt in func_def.body:
            _visit_for_tracking(stmt)

        def _stmt_returns_list(stmt):
            if isinstance(stmt, ReturnStatement) and stmt.value is not None:
                if self._value_tracks_as_list(stmt.value):
                    return True
                if isinstance(stmt.value, Identifier) and stmt.value.name in list_locals:
                    return True
                return False
            if isinstance(stmt, IfStatement):
                else_body = stmt.else_body or []
                return any(_stmt_returns_list(inner) for inner in stmt.body + else_body)
            if isinstance(stmt, WhileLoop):
                return any(_stmt_returns_list(inner) for inner in stmt.body)
            if isinstance(stmt, ForLoop):
                return any(_stmt_returns_list(inner) for inner in stmt.body)
            return False

        return any(_stmt_returns_list(stmt) for stmt in func_def.body)

    def _exception_code_for(self, value) -> int:
        """Return a small numeric code for supported exception types."""
        exc_name = ""
        if isinstance(value, CallExpr):
            exc_name = _name(value.func)
        elif isinstance(value, Identifier):
            exc_name = value.name
        mapping = {
            "ValueError": 1,
            "RuntimeError": 2,
            "TypeError": 3,
            "AssertionError": 4,
        }
        return mapping.get(exc_name, 255 if value is not None else 255)

    def _is_catch_all_handler(self, handler) -> bool:
        """Return True for bare ``except:`` or ``except Exception/BaseException:``."""
        if handler.exc_type is None:
            return True
        exc_name = ""
        if isinstance(handler.exc_type, Identifier):
            exc_name = handler.exc_type.name
        elif isinstance(handler.exc_type, CallExpr):
            exc_name = _name(handler.exc_type.func)
        return exc_name in ("Exception", "BaseException")

    def _closure_factory_spec(self, func_def: FunctionDef):
        """Return closure-factory lowering info for the supported make_counter-like shape."""
        if len(func_def.body) != 3:
            return None
        init_stmt, nested_stmt, return_stmt = func_def.body
        if not (
            isinstance(init_stmt, VariableDeclaration)
            and isinstance(nested_stmt, FunctionDef)
            and isinstance(return_stmt, ReturnStatement)
            and isinstance(return_stmt.value, Identifier)
            and _name(nested_stmt.name) == return_stmt.value.name
        ):
            return None
        if len(nested_stmt.body) != 3:
            return None
        nonlocal_stmt, assign_stmt, nested_return = nested_stmt.body
        capture_name = _name(init_stmt.name)
        if not (
            isinstance(nonlocal_stmt, LocalStatement)
            and capture_name in nonlocal_stmt.names
            and isinstance(assign_stmt, Assignment)
            and isinstance(assign_stmt.target, Identifier)
            and assign_stmt.target.name == capture_name
            and assign_stmt.op == "="
            and isinstance(nested_return, ReturnStatement)
            and isinstance(nested_return.value, Identifier)
            and nested_return.value.name == capture_name
        ):
            return None
        update_expr = assign_stmt.value
        if not (
            isinstance(update_expr, BinaryOp)
            and update_expr.op == "+"
            and isinstance(update_expr.left, Identifier)
            and update_expr.left.name == capture_name
            and isinstance(update_expr.right, NumeralLiteral)
            and float(update_expr.right.value) == 1.0
        ):
            return None
        return {
            "outer_name": _name(func_def.name),
            "nested_name": _name(nested_stmt.name),
            "capture_name": capture_name,
            "init_value": init_stmt.value,
        }

    def _emit_closure_factory_function(
        self, func_def: FunctionDef, emitted_name: str | None = None
    ) -> bool:
        """Lower a supported closure-factory function plus its nested helper."""
        spec = self._closure_factory_spec(func_def)
        if spec is None:
            return False

        outer_name = emitted_name or spec["outer_name"]
        helper_name = f"{outer_name}__{spec['nested_name']}_closure"
        self._closure_factory_funcs[outer_name] = helper_name

        saved = self._save_func_state()
        self._locals = {"env"}
        self._emit("    ;; closure step: increment captured cell 0")
        self._emit("    local.get $env")
        self._emit("    i32.trunc_f64_u")
        self._emit("    i32.const 8")
        self._emit("    i32.add")
        self._emit("    local.get $env")
        self._emit("    i32.trunc_f64_u")
        self._emit("    i32.const 8")
        self._emit("    i32.add")
        self._emit("    f64.load")
        self._emit("    f64.const 1")
        self._emit("    f64.add")
        self._emit("    local.tee $env_val")
        self._emit("    f64.store")
        self._emit("    local.get $env_val")
        self._emit("    return")
        self._locals.add("env_val")
        body_instrs = list(self._instrs)
        lines = [f'  (func ${self._wat_symbol(helper_name)} (export "{helper_name}")']
        lines.append("    (param $env f64)")
        lines.append("    (result f64)")
        lines.append("    (local $env_val f64)")
        lines.extend(body_instrs)
        lines.append("    f64.const 0  ;; implicit return")
        lines.append("  )")
        self._funcs.append("\n".join(lines))
        self._restore_func_state(saved)

        saved = self._save_func_state()
        param_names = _real_params(func_def)
        self._locals = set(param_names)
        self._need_heap_ptr = True
        self._gen_list_alloc(ListLiteral([spec["init_value"]]), "    ")
        self._emit("    return")
        body_instrs = list(self._instrs)
        self._append_wat_function(outer_name, param_names, body_instrs)
        self._restore_func_state(saved)
        return True
