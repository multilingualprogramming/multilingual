# Changelog

All notable changes to this project should be documented in this file.

The format is inspired by Keep a Changelog, and this project follows SemVer.

## [Unreleased]

### Added

#### Stochastic rewriting — the `chance` clause predicate
- **A rewrite clause can now fire probabilistically, via a new `chance(p, salt)`
  predicate** alongside `when` and `neighbor_count`. This adds the one ingredient
  the deterministic rewrite/rate rules lacked — randomness — so stochastic
  programs (Eden growth, percolation, noisy cellular automata) are expressible
  for the first time. A clause carrying `chance(p)` matches only a fraction `p`
  of the time.
- **The randomness is deterministic and byte-identical across runtimes.** There
  is no PRNG state and no seed plumbing: a roll is a pure hash of
  `(locus, step, salt)` (`_hash01`, a MurmurHash3-style 32-bit mix built from
  exact `& 0xFFFFFFFF` / `Math.imul` arithmetic so CPython and the JS port agree
  to the bit). A stochastic trajectory is therefore a reproducible function of
  the manifest, and two clauses decorrelate via different `salt`. The step index
  is threaded through `step`/`run` to the predicate so randomness varies over
  time; a deterministic rule ignores it and steps exactly as before.
- **Mirrored in the JS port** (`docs/browser/process-dynamics/process_core.js`):
  `hash01` + the `chance` branch in `clauseMatches`, with `stepIndex` threaded
  through every rewrite stepper. `tests/process_core_js_test.py` grows an Eden
  cluster under Node and asserts it matches Python cell-for-cell across the run.
- **Eden-growth example, authored in `.multi` (en + fr).**
  `examples/eden_growth.{multi,fr.multi}` grow a stochastic accretion cluster
  with a rough fractal boundary from a single seed — the first *stochastic*
  program on any axis. New `tests/process_stochastic_test.py` covers the hash
  (range, purity, uniformity, per-input sensitivity), the predicate's gating
  (`p=0` never fires, `p=1` always, `~p` on average, salt decorrelation), and
  the example (monotone growth, determinism, Tier 2, en≡fr).

#### Nonlinear rate rules — reaction-diffusion on the continuous axis
- **`rate_rule` gains a `constant` source/sink and `products` (nonlinear
  monomials) term.** A field's time-derivative was previously a *linear*
  combination of the locus's own fields (`self`) and the mean over its
  neighbours (`neighbor_mean`) — enough for diffusion and decay, but not for
  any reaction. A rate now sums four optional contributions in a fixed order:
  `self`, `neighbor_mean`, a scalar `constant`, and `products` — a list of
  monomials `{"coeff": c, "factors": [f, ...]}` each contributing
  `c · own[f0] · own[f1] · …` (factors repeat to raise a power). This reaches
  the nonlinear continuous systems the linear slice could not express:
  Gray-Scott, Lotka-Volterra predator-prey, FitzHugh-Nagumo. The terms are
  pure data — the engine still names no system. A rule that omits `constant`
  and `products` integrates **byte-for-byte** as before (they are appended only
  when present, so no existing manifest drifts).
- **Bit-identical across runtimes.** The new terms are mirrored in the JS port
  (`docs/browser/process-dynamics/process_core.js`), folding the monomial in
  the same factor order so the Python and JS continuous steppers stay
  byte-identical. `tests/process_core_js_test.py` runs Gray-Scott under Node and
  asserts both reagent fields agree float-for-float across the trajectory.
- **Gray-Scott example, authored in `.multi` (en + fr).**
  `examples/gray_scott.{multi,fr.multi}` express the canonical pattern-forming
  reaction `U + 2V -> 3V` end-to-end through the language — the first
  *nonlinear* program on the continuous axis. Both lower to a byte-identical
  core; new engine tests in `tests/process_continuous_test.py` cover the
  constant term, product monomials, term composition order, and the
  autocatalysis igniting while the field stays bounded (still Tier 1).

## [0.8.0] - 2026-06-13

### Added

#### Polymodal v1 — process calculus (dynamics over the semantic core)
- **`semantic-core-v1` = ⟨State, Topology, Rule, Schedule⟩ with one rewrite
  meta-primitive.** Where v0 described a static scene, v1 describes how a
  scene *evolves*. The stepper is modality-free and has bit-identical Python
  and JS implementations. `semantic-core-v0` remains frozen; a v0→v1
  migration projects any v0 core into a Tier-0 v1 core that round-trips the
  original entities exactly (`process_migration.py`,
  `process_static_projection.py`).
- **Process programs are authored in `.multi`, not Python.** A program
  defines a `process` variable and is compiled with the new
  `multilingual process-build` CLI — the v1 layer is a first-class citizen
  of the multilingual language rather than a set of host scripts. Builtin
  aliases for the process vocabulary ship in all 16 languages.
- **Rule surface syntax is a free-function combinator DSL.**
  `when` / `neighbor_count` / `becomes` / `fallback` / `symbol` / `clause` /
  `rewrite` lower to `rewrite_rule` (`RULE_REWRITE`). A second rule kind,
  `rate_rule` (`RULE_RATE`), carries derivatives-as-data for continuous
  dynamics.
- **Three topologies and three schedules.** Topologies: implicit grid
  (spatial), open-population, and `graph_topology` (arbitrary node/edge
  loci via a generalized `_locus_key`). Schedules: synchronous,
  `asynchronous_schedule` (sequential in-place, identity-on-no-match), and
  `continuous_schedule(dt)` which integrates `rate_rule`s with an explicit
  Euler step (`next = field + dt·rate`). The continuous path uses a naive
  left-fold sum so CPython and JS stay bit-identical (the compensated-`sum`
  path diverged). This completes the schedule axis.
- **Tier 0–4 capability classifier.** `tierOf` / `TIER_NAMES` (Python and JS)
  grade a process by expressive power. Tier is orthogonal to invertibility:
  the SIR `network_epidemic` core classifies as Tier 4 yet
  `process_graph_projection.py` round-trips every node exactly. The tier
  line is shown on all five browser dynamics pages.
- **Example process programs (en + fr), each end-to-end through the v1
  path with a value-aware projection and a browser page.** Conway's Game of
  Life (`game_of_life.multi`), Lindenmayer L-systems
  (`lindenmayer.multi`, generative sequence rewriting), a cyclic-dominance
  ecosystem (`ecosystem.multi`, heterogeneous state + async schedule), a
  network SIR epidemic (`network_epidemic.multi`, graph topology), and heat
  diffusion (`diffusion.multi`, continuous-time, mass-conserved). Browser
  runtimes: `docs/browser/process-dynamics/` Life, L-system, ecosystem,
  graph, and diffusion pages.
- **A checked-in golden `semantic-core` fixture** plus value-aware field,
  sequence, and graph projections (`process_field_projection.py`,
  `process_sequence_projection.py`, `process_graph_projection.py`) and
  per-projection capability contracts (`process_capabilities.py`).

#### Polymodal computation — five peer modalities, relations, capture
- **Five peer modality projections of the same semantic core.** The
  polymodal architecture introduced after v0.7.0 now has five live
  peers — `linear` (1D timeline), `spatial` (2D canvas, unified under
  the semantic core; previously grandfathered), `volumetric` (3D scene
  rendered on canvas with a hand-rolled rotation and perspective, no
  WebGL/3D dependency), `sonic` (WebAudio), and `midi` (discrete
  events). Each one ships with a `multilingual <name>-build` CLI, a
  `program.<name>.json` manifest, a browser runtime under
  `docs/browser/<name>-dynamics/`, and a checked-in `ontology.json`
  sidecar generated by the new `multilingual ontology-export` CLI so
  the JS and Python sides cannot drift. The cross-modal equivalence
  test in `tests/polymodal_equivalence_test.py` now asserts entity
  count, opcode ordering, intensity/phase/channel preservation, and
  ontology-name agreement across all five peers.
- **Containment relations derived at the semantic core.** Previously
  the `relations` field on `semantic-core-v0` was always empty. Each
  `contain`-opcode entity on channel C now contains the non-`contain`
  entities on channel C, with the relation flowing through every
  projection so peers cannot silently disagree on structure. Coupling
  and temporal ordering are intentionally deferred until the source
  language gains explicit syntax.
- **Sonic round-trip — Python inverse and browser microphone capture.**
  `multilingualprogramming/codegen/sonic_capture.py` reconstructs a
  semantic core from label-stripped `ObservedVoice` records and is
  exercised by `SonicRoundTripTestSuite`. In the browser,
  `docs/browser/sonic-dynamics/sonic_capture.js` mirrors the Python
  inverse (fetching the shared ontology sidecar) and
  `microphone_capture.js` produces `ObservedVoice` records from real
  audio with a pure-vanilla DSP pipeline (spectral-flux onset
  detection, FFT peak picking, harmonic-ratio waveform classification,
  RMS envelope classification, pentatonic snapping). The sonic runtime
  gains a "capture" button that runs the pipeline and renders the
  recovered manifest.
- **Dimensionality guard vocabularies.** Linear glyph names, spatial
  shape names, and volumetric primitive names are deliberately
  disjoint (no `ring` in linear, no `dot` in volumetric, etc.), and
  tests reject accidental reuse. MIDI roles
  (`note`, `drum`, `cc`, `program`, `bus`) form a distinct
  event-oriented taxonomy.

#### WAT/WASM backend — math accuracy
- **`math.atan` double range reduction + 12-term Taylor.** The previous implementation used
  a 6-term Taylor with only the `1/x` reduction, so `atan(1)` returned ~0.747 vs the true
  `π/4 ≈ 0.7854` (~5% error, the worst case on `|x| ≤ 1`). Now adds a second reduction
  `atan(x) = π/4 + atan((x − 1)/(x + 1))` for `x > tan(π/8) ≈ 0.4142`, so the Taylor
  argument is always in `[-tan(π/8), tan(π/8)]`. Extended to 12 terms (degrees 1..23) —
  truncation error `~ x^25/25 < 5e-12` at the boundary. Verified ~10 decimal places across
  `atan(0)`, `atan(0.5)`, `atan(1)`, `atan(10)`, `atan(1000)`, and negative arguments.
  `math.atan2` inherits the improvement directly. Regression test:
  `tests/wat_generator_wasm_execution_test.py::test_math_atan_range_reduction_precision`.

#### WAT/WASM backend — i32 wraparound builtins
- **`imul32(a, b)`, `iadd32(a, b)`, `shr_u32(a, k)`, `u32_to_f64(x)`.** The existing bitwise
  operators `& | ^ << >>` use signed-i32 conversions but stop short of multiplication
  (`*` is always `f64.mul`) and unsigned right shift (`>>` is sign-extending). These
  builtins fill the gap : `imul32` mirrors `Math.imul` (i32.mul with wraparound),
  `iadd32` adds with wraparound using an i64 intermediate (so the sum can exceed
  `[-2^31, 2^31)` before wrapping), `shr_u32` mirrors `>>>` (zero-fill right shift),
  and `u32_to_f64` reinterprets a signed-i32-as-f64 as unsigned-i32-as-f64 (maps
  negatives to `[2^31, 2^32)`). Required to port 32-bit hashes (FNV, CRC32) and PRNGs
  (mulberry32) to `.multi` source. Regression :
  `test_imul32_iadd32_shr_u32_match_js_semantics`.
- **`pow_f64` integer-exponent sign bug fixed.** The neg-flag for `pow(base, exp)` with
  integer `exp` was inverted (`neg = 0 < exp` instead of `exp < 0`), so `pow(10, -3)`
  returned 1000 and `pow(10, 3)` returned 0.001 — exactly swapped. The bug stayed
  hidden because the fractales code only ever used `**` with positive or `[0, 1]`
  exponents (interpolation). Exposed by `formatter_exponentiel` in fractales partage
  (mantissa = `x / pow(10, e)`). Regression : `test_pow_f64_negative_integer_exponent`.

#### WAT/WASM backend — language ergonomics (roadmap section C, 2026-05-23 part 2)

- **Multi-value returns (`retour (a, b, …)`).** WAT functions can now return
  N≥2 values on the stack via a `(result f64 f64 …)` signature. `retour (a, b)`
  pushes both values then `return` ; `soit x, y = f(…)` destructures via
  `local.set` in reverse order. Detected automatically per-function via
  `_multi_value_return_arity` (all `retour` statements must agree on arity).
  Eliminates the `_x`/`_y` function-pair pattern across fractales (transforms,
  landmarks, attractors). Regression: `test_multi_value_returns_tuple`.

- **String concat on FString/CallExpr RHS.** Previously `s + f"…"` and
  `s + func_call()` raised `Unsupported string expression for WAT concat`,
  forcing a temp-local refactor. Now `_emit_string_value_with_len` falls
  through to `$__last_str_len` (set by both f-string evaluation and
  string-returning calls — and by `$__str_concat` itself, so chains of
  arbitrary length work). Also fixed `_gen_string_len_expr` BinaryOp recursion
  to bail (and rollback emitted instructions) if a child returns False.
  Regression: `test_string_concat_rhs_fstring_and_call`.

- **`pow_f64` general real exponents.** Previously returned NaN for any
  non-integer exponent outside `{0, 0.5, 1, -0.5}`. Now falls back to
  `exp(b · ln(a))` for `base > 0` ; negative base with non-integer exp still
  returns NaN (no real value). Precision is bounded by `math.exp`/`math.log`
  (~1e-6 with the 2026-05-22 log fix and the new exp range reduction below).
  Regression: `test_pow_f64_general_real_exponents`.

- **`math.exp` range reduction.** Previously a 10-term Taylor applied
  directly to `x` (no reduction) — ~5% off at `|x|=5`, divergent at `|x|>20`.
  Now uses `k = round(x/ln2)`, reduces to `r ∈ [-ln2/2, ln2/2]`, applies the
  same Taylor on `r`, and multiplies by `2^k` via IEEE-754 bit-pattern
  (exponent field = `1023 + k`, mantissa 0). Accurate to ~1e-15 across the
  practical range. Enables the `pow_f64` general case above.

- **`format_fixed(v, n)` runtime builtin.** Where `f"{v:.Nf}"` requires N at
  compile time, `format_fixed(v, n)` accepts N at runtime (clamped to `[0, 9]`).
  Internally dispatches to the existing `$__fmt_fixedN_tmpstr` helpers via an
  if/else cascade in `$__fmt_fixed_dyn`. Eliminates the `formatter_fixe_2/3/5/6`
  pattern (4 near-identical functions) in fractales. Registered in
  `BUILTIN_STRING_RETURNERS` so `r = format_fixed(...)` tracks `r` as a
  string. Regression: `test_format_fixed_dynamic_n`.

- **List ABI helpers `__ml_list_count(ptr)`, `__ml_list_item(ptr, i)`.**
  Exported runtime helpers that expose the heap-backed list layout
  (header f64 at `ptr+0` = count, items at `ptr+8`, `ptr+16`, …) to host
  callers. Eliminates the `base + 8 + 8 * (2 + 2 * k)` magic-offset reads
  scattered across fractales JS code. Regression:
  `test_ml_list_count_and_item_helpers`.

- **Architectural fix: orchestrator unions state instead of resetting.**
  `_sequence_func_names` and `_string_return_funcs` are now seeded from
  `BUILTIN_LIST_RETURNERS` / `BUILTIN_STRING_RETURNERS` (frozensets in
  `wat_generator_support`) — single source of truth. Adding a new builtin
  that returns a list/string requires editing ONE constant, not also
  patching the orchestrator's reset dict. Removes the dual-init smell I
  introduced when adding `simd_mandelbrot_pair` in the prior session.

#### Deferred (need a typed IR layer)

The following items in the section-C roadmap require type information that
isn't yet tracked through expressions, and so are deferred to a future
typed-IR pass :

- **B2 — `v128`/`f64x2` source type.** A real SIMD type with operators
  `+ - * < le` lowering to `f64x2.*`. Currently scoped to one builtin
  (`simd_mandelbrot_pair`). Needs operand-type dispatch in `_emit_numeric_binop`.
- **B3 — i32 wraparound on `*` and `+` when bitwise-shaped.** Would
  eliminate `imul32`/`iadd32` builtins. Needs operand "shape" tracking.
- **B6 (full) — module-grouped manifest.** Manifest currently emits a flat
  function list. Grouping by source module name would let fractales drop
  the hand-coded `wasmMetaPanels` rebundling in `renderer.js`. Needs
  per-function module attribution through the IR.

#### WAT/WASM backend — SIMD (v128 f64x2)
- **`simd_mandelbrot_pair(cx0, cy0, cx1, cy1, max_iter)` builtin.** First WebAssembly
  SIMD-using helper in the WAT backend. Iterates two Mandelbrot pixels in parallel via
  `f64x2.mul`/`add`/`sub`, `f64x2.le`, `i64x2.add`, and `v128.bitselect` (escaped lanes
  are frozen). Returns a heap-allocated list pointer `[iter0, iter1]` (multilingual list
  convention : `f64` length header at `ptr+0`, items at `ptr+8, ptr+16`). The builtin
  is pre-registered in `_sequence_func_names` so the caller's `r = simd_mandelbrot_pair(...)`
  registers `r` as a tracked list pointer (enables `r[0]`, `r[1]`). Verified bit-equal
  (±1 iteration) to scalar across cardioid/bulb/escape cases via
  `test_simd_mandelbrot_pair_matches_scalar`. On x86-64 (SSE2) / ARM64 (NEON) hosts,
  yields ~2× speedup on the inner loop. No new v128 type at the source level — this
  is a single-purpose builtin, scoped narrowly to keep the language surface stable.

## [0.7.0] - 2026-05-23

### Added

#### WAT/WASM backend — math accuracy
- **`math.log` mantissa range reduction.** The atanh series was applied directly to `x`, so
  `log(10)` returned ~2.255 instead of 2.302585 (~2% error for arguments far from 1). Now uses
  IEEE-754 bit manipulation (`i64.reinterpret_f64`) to split `x = m·2^e`, reduces `m` further to
  `[sqrt(0.5), sqrt(2))`, and computes `log(m) + e·log(2)`. The atanh argument stays in
  `[-0.172, 0.172]` so the 5-term series converges to ~2.2e-8. Verified to ~1e-6 accuracy across
  `log(0.5)` → `log(1e10)`.

#### WAT/WASM backend — list-return propagation
- **User functions returning lists are now tracked at the call site.** A function whose body
  returns a list literal (`retour [a, b]`), a list-repeat (`retour [0]*n`), a tracked-list local,
  or another list-returning call is detected by `_returns_list_like` and registered in
  `_sequence_func_names`. The caller's `x = func(...)` therefore makes `x` a tracked list, so
  `x[i]` indexing lowers correctly (previously fell back to `f64.const 0 ;; unsupported:
  IndexAccess on non-list`). Unblocks pure-`.multi` Dekker arithmetic (`two_sum`/`two_product`
  returning `[hi, lo]`) and other helpers that return small fixed-shape lists.

#### WAT/WASM backend — host-side helpers
- **`__ml_str_alloc(len)` exported** (companion to `__ml_str_len`): JS calls this to allocate a
  length-prefixed string buffer for host→wasm string passing. Writes the byte length as a
  4-byte header and returns the pointer to the bytes (header at `ptr-4`). Used by the fractales
  L-système main-canvas migration to pass axiom/rules as real string args.

#### WAT/WASM backend — string operations
- **Length-prefixed string parameters (cross-function string passing)**: string values carry no
  length in their f64 pointer, so passing a string as a function argument previously lost its byte
  length in the callee. Parameters annotated as strings (`s: str` / `s: chaîne`, normalized to the
  identifier `str`) are now passed as **length-prefixed buffers**: the caller copies the argument
  via the new `$__str_make_headered` helper, which writes the byte length as a 4-byte header at
  `ptr - 4`, and the callee recovers it into a tracked `<name>_strlen` local at its prologue. This
  makes `len(s)`, indexing (`s[i]`), slicing (`s[a:b]`), char comparison (`s[i] == "F"`), and
  concatenation work on a string received as an argument — enabling multi-function string APIs.
  String-annotated parameters are also excluded from list-like inference so `s[i]` lowers as a
  string subscript rather than a stride-8 list load. Data offset `0` is now reserved (8 bytes) so
  no interned string can alias the null/None sentinel pointer. `$__str_concat` now maintains
  `$__last_str_len = len1 + len2`, so concatenation results are self-describing for callers.
- **String content equality (`==` / `!=`)**: comparisons where both operands are string-valued
  now lower to a new `$__str_eq` WAT helper that compares UTF-8 byte ranges, instead of comparing
  heap pointers. This makes `s[i] == "F"`, `slice == literal`, and string-valued method results
  compare by content. Variables bound to a string subscript/slice/method result (`ch = s[i]`) now
  retain string-length tracking, so equality on them compares content too.
- **`str(x)` number-to-string conversion**: `str(42)` → `"42"`, `str(3.14)` → `"3.14"` via new
  `$__str_from_f64` WAT helper. Correctly formats integers without a decimal point and floats with
  up to 6 significant decimal digits (trailing zeros trimmed). String and string-variable arguments
  pass through unchanged.
- **F-string numeric interpolation**: `f"{x}"` where `x` is a numeric `f64` variable now calls
  `$__str_from_f64`, producing correct float output (`f"{3.14}"` → `"3.14"` rather than `"3"`).
- **String method `.upper()` / `.lower()`**: ASCII case conversion, returns heap-allocated copy.
- **String method `.startswith(prefix)` / `.endswith(suffix)`**: Returns `0.0` / `1.0`.
- **String method `.count(needle)`**: Counts non-overlapping occurrences; returns f64.
- **String method `.replace(old, new)`**: Replaces all occurrences; returns heap-allocated copy.
- **`str()` recognized as string-valued**: `_is_string_value` updated so `str(x)` composes
  correctly inside f-strings and string concatenation.

#### WAT/WASM backend — math
- **`math.sin` / `math.cos` / `math.tan`**: Horner-polynomial approximations (6-term).
- **`math.exp`**: 10-term Horner polynomial for e^x.
- **`math.log` / `math.log2` / `math.log10`**: atanh-series natural log; scaled for base 2/10.
- **`math.atan` / `math.atan2`**: 6-term series with |x|>1 identity; quadrant-adjusted atan2.
- **`math.trunc` / `math.hypot` / `math.degrees` / `math.radians`**: Inline WAT lowering.
- **`math.pi` / `math.e` / `math.tau` / `math.inf` / `math.nan`**: Emitted as `f64.const` literals.

#### WAT/WASM backend — strings
- **`ord(s)` builtin**: returns the first UTF-8 byte of a string as an `f64`
  (`i32.load8_u` at the string pointer). Enables storing characters as numeric
  codes — e.g. on an `f64` stack for iterative/DFS string algorithms.

#### WAT/WASM backend — list allocation
- **Runtime-sized list repeat `[elem] * n`**: a single-element list literal multiplied by a
  runtime count now allocates an `n`-length list (layout `[length_f64, elem0, ...]`) filled with
  the repeated element, instead of falling through to numeric multiplication. The result is tracked
  as a list, so `buf[i] = ...`, `buf[i]`, and `len(buf)` work — enabling O(n) buffer fills
  (e.g. two-pass count-then-write) rather than O(n²) `append` chains under the bump allocator.
  Recognised in either operand order (`[0.0] * n` or `n * [0.0]`).

#### WAT/WASM backend — list mutation
- **`list.append(x)`**: `$__list_append` allocates a new block with `count+1` slots, copies
  existing data, appends the element, and updates the local variable.
- **`list.pop()`**: `$__list_pop` decrements the count in-place and returns the last element;
  works in both statement and expression contexts.
- **`list.extend(other)`**: `$__list_extend` merges two lists into a new heap block.
- **`list(existing_list)`**: Produces a shallow copy when called with an existing list local.

#### WAT/WASM backend — iteration
- **`enumerate(lst)` in `for` loops**: `for i, x in enumerate(lst)` lowers to a counted list
  loop that unpacks the two-element tuple target `(i, x)` via `_emit_sequence_len_setup` /
  `_emit_sequence_value_load`.
- **`list(map(fn, lst))`**: Applies a known WAT function to every element of a list local;
  produces a new list of the same length.
- **`list(filter(fn, lst))`**: Keeps elements where `fn` returns a truthy value; count updated
  after the loop.

#### WAT/WASM backend — dict methods
- **`dict.values()`**: Returns the dict pointer itself (dicts are stored as f64 value lists).
- **`dict.keys()`**: Allocates a new list of interned string pointers for each compile-time key.
- **`dict.items()`**: Allocates an outer list of 2-element `[key_ptr, val]` tuple pairs.
- **`dict.get(key)` / `dict.get(key, default)`**: Compile-time string-literal key lookup;
  returns the element f64, the default expression, or `0.0` if the key is absent.

#### WAT/WASM backend — OOP / type checking
- **`isinstance(obj, ClassName)`**: Emits a type-tag check at `obj_ptr - 8` against the
  compile-time class ID from `_class_ids`. Returns `1.0` (true) or `0.0` (false) as f64.
- **OOP state reset fix**: `_static_method_names`, `_property_getters`, `_class_ids`, and
  `_dispatch_func_names` are now reset between `generate()` calls, eliminating stale OOP
  state that could corrupt subsequent compilations in the same generator instance.

#### WAT/WASM backend — DOM
- **`dom_on(handle, event, callback)`**: Registers a WAT function-table callback for a DOM
  event. The generated module exports `__dom_dispatch(idx)` which JS calls on the event;
  `ml_dom_on` host import added to the DOM bridge.

#### WAT/WASM backend — JSON
- **`json.dumps(list)`**: Encodes a tracked f64 list as a JSON array string
  (`[n1,n2,...]`) using a new `$__json_encode_list` WAT helper.

#### WAT/WASM backend — generators
- **`yield from range(n)`**: Now materializes correctly via Shape 1b in `_simple_generator_spec`.

### Fixed
- **`math.sin` / `math.cos` returned wrong values** (two bugs): (1) both helpers began with an
  uncompensated `x += pi` phase shift, so they computed `sin(x+pi) = -sin(x)` and
  `cos(x+pi) = -cos(x)` — e.g. `math.cos(0.0)` returned `-1.0`; (2) range reduction used
  `floor(x/2pi)` (reducing to `[0, 2pi)`), so angles in `(3pi/2, 2pi)` and negative angles got a
  spurious double reflection with the wrong sign — e.g. `math.cos(-60deg)` returned `-0.5` instead
  of `+0.5`. Fixed by removing the phase shift and reducing to `[-pi, pi]` via
  `floor(x/2pi + 0.5)` so a single reflection suffices. Now `cos(0)=1`, `sin(pi/2)≈1`,
  `cos(4pi)=1`, `cos(-60deg)=cos(300deg)=0.5`, `cos(240deg)=-0.5`. `math.tan` (defined as
  `sin/cos`) is corrected transitively.
- **F-string float formatting**: Default `{x}` interpolation previously truncated floats to
  their integer part; now delegates to `$__str_from_f64` for correct output.
- **`math.atan` WAT stack error**: The conditional negation inside `if` without a declared
  result type caused a WASM validation failure; fixed by saving the result to `(local $r f64)`.
- **`$__json_encode_list` copy-index clobbering**: Inner copy loop used `$i` (element index)
  as its write pointer, corrupting output after the first element; fixed with a separate `$ci`.

## [0.6.0] - 2026-03-09

### Added
- **WAT/WASM OOP object model**: Stateful classes (those with `self.attr = …` assignments)
  now use a linear-memory bump allocator in generated WAT. Each field is an `f64` stored at
  a compile-time-computed byte offset. Object pointers are carried as `f64` values and
  converted at field-access sites via `i32.trunc_f64_u` / `f64.convert_i32_u`.
- **Heap-pointer global**: `(global $__heap_ptr (mut i32) …)` is emitted only when at least
  one stateful class is present; `HEAP_BASE` is aligned to 8 bytes after the string data section.
- **`self.attr` store/load lowering**: Attribute writes (`self.x = val`) compile to `f64.store`;
  attribute reads (`self.x`) compile to `f64.load`. Compound assignments (`self.x += delta`)
  use a temporary `f64` local to avoid address recomputation issues.
- **External `obj.attr` reads**: `obj.attr` outside the class body lowers to `f64.load` when
  the variable's class is statically known from local assignments.
- **Stateful instance method calls**: Instance method calls (`obj.method(…)`) pass the actual
  heap address as `self` (as `f64`) for stateful classes; stateless classes keep the old
  `f64.const 0` behavior.
- **Inheritance and method resolution in WAT/WASM**: Subclass hierarchies are now resolved
  at WAT-emit time; inherited methods are dispatched to the correct parent-class WAT export.
- **`with` statement lowering in WAT**: Context-manager blocks (`with expr as var`) lower to
  WAT with enter/exit call sequences.
- **`try/except` lowering in WAT**: Try-except blocks compile to WAT control-flow blocks,
  providing structured exception handling in the WASM backend.
- **`lambda` lowering in WAT**: Lambda expressions lower to anonymous WAT functions with
  captured parameters forwarded as explicit arguments.
- **`match/case` lowering in WAT**: Structural pattern-matching statements lower to WAT
  `if/else` chains using equality comparisons.
- **`async/await` lowering in WAT**: Async function definitions and `await` expressions lower
  to synchronous WAT equivalents with stub scheduling hooks.
- **`@property` setter/getter in WAT**: Property descriptors (`@property`, `@x.setter`) lower
  to distinct WAT getter/setter exports following the established class-method mangling scheme.
- **Bytes literals in WAT**: `b"..."` byte-string literals are stored in the WAT data section
  and referenced by pointer/length pairs.
- **WAT generation organized by themes**: The WAT backend code is now split into focused
  modules by language construct theme (control flow, OOP, literals, builtins) for maintainability.
- **`TupleLiteral` code generation fix**: Tuple literals now wrap generated elements in
  parentheses, producing correctly parenthesized WAT output.
- **Updated builtin aliases**: Expanded localized builtin alias coverage across supported languages.
- **New WAT OOP tests** in `tests/wat_generator_test.py`:
  - `WATOopObjectModelTestSuite` — 6 WAT pattern tests (no wasmtime required).
  - 3 new execution tests in `WATClassWasmExecutionTestSuite`: single-field counter get,
    increment-then-get, and two independent instances.
- **`docs/wat_oop_model.md`**: Reference document covering the object model design, memory
  layout, field layout rules, constructor sequence, store/load patterns, limitations, and a
  full end-to-end WAT example.
- **`AGENTS.md`**: Agent guidance document for AI-assisted development workflows in this repository.

### Changed
- Stateless classes (no `self.attr` assignments) are unaffected and keep the `f64.const 0`
  self path — no existing tests are broken.
- WAT backend source split into themed sub-modules for clarity and maintainability.

### Fixed
- `TupleLiteral` code generation now wraps output in parentheses (previously emitted bare elements).
- Various WAT backend correctness fixes surfaced during gap-filling and test stabilization.

## v0.5.1
- Update documentation

## v0.5.0

### Added
- **Class lowering in WAT backend**: Top-level `ClassDef` methods now lower to standalone WAT exports with deterministic mangled names.
- **Constructor and method call lowering**:
  - `ClassName(...)` lowers to class `__init__` in WAT with implicit `self` handling.
  - `Class.method(...)` lowers to mangled class method exports.
  - `obj = Class(...); obj.method(...)` lowers via lightweight local class-type tracking.
- **Executable WASM validation for complete features**:
  - New test `tests/complete_features_wasm_execution_test.py` compiles every `examples/complete_features_*.multi` from WAT to binary WASM, materializes `.wat/.wasm` artifacts, instantiates modules, and executes `__main`.
- **CI workflow gate for complete-feature WASM execution**:
  - `.github/workflows/wasm-backends-test.yml` now runs the new complete-feature WAT/WASM execution test on primary WASM jobs.

### Changed
- **WAT symbol emission now Unicode-safe**:
  - Function, parameter, and local identifiers are sanitized to valid WAT symbols while preserving original export names.
  - Fixes WAT→WASM compilation failures for non-Latin identifiers in multilingual examples.
- **WASM execution test runtime bounded**:
  - Added Wasmtime fuel metering in complete-feature execution tests to prevent long CI hangs while still validating instantiation and execution.

### Fixed
- **WAT/WASM class regressions**:
  - Fixed incorrect argument mapping for implicit `self` in constructor/instance lowering that could leave stack values and produce invalid WASM.
- **Tooling quality**:
  - Updated test/config and corpus fixtures to remove warning noise and stabilize CI signal.
- **Release docs**:
  - Documented PyPI file-name immutability and the correct recovery path for `HTTP 400 File already exists` uploads.

## [0.4.0]
### Added
- **WATCodeGenerator**: New backend compiling the multilingual AST directly to WebAssembly Text (WAT); fully tested via `tests/complete_features_wat_test.py` across all 17 languages.
- **Playground WAT/WASM tab**: Interactive playground now shows generated WAT source and executes it in the browser via wabt.js + native `WebAssembly.instantiate()`.
- **Playground Rust/Wasmtime tab**: Playground shows generated Rust/Wasmtime bridge scaffold alongside the WAT view for local compilation workflows.
- **REPL `:wat` command**: Toggles display of generated WAT code before execution (alias `:wasm`).
- **REPL `:rust` command**: Toggles display of generated Rust/Wasmtime bridge code before execution (alias `:wasmtime`).
- **CLI `--show-wat` / `--show-rust` flags**: Startup equivalents of `:wat` and `:rust` for the `repl` subcommand.
- **Python 3.12 feature completion**: All 17 `complete_features_XX.multi` example files updated with the full checklist — numeric literals (hex/octal/binary/scientific), augmented assignments, bitwise operators, chained assignment, type annotations, ternary expressions, default/variadic params, lambdas, list/dict/generator/nested/filtered comprehensions, `try/except/else`, exception chaining, multiple `except` handlers, `match/case/default`, decorators, multiple inheritance, `@staticmethod` / `@classmethod` / `@property`, and docstrings.
- **New CLI tests**: `language_completeness_cli_test.py` and `operators_cli_test.py`.
- **WASM Backend**: WebAssembly compilation target with significant performance gains on compute-intensive operations (benchmark-dependent).
- **Python ↔ WASM Bridge**: Type conversion and memory management for seamless interop between Python and WASM.
- **Smart Backend Selector**: Auto-detection and transparent routing between WASM and Python fallback execution paths.
- **Python Fallback Implementations**: 25+ pure Python implementations for guaranteed compatibility across all platforms.
- **WASM Corpus Projects**: 20 multilingual example projects (matrix operations, cryptography, image processing, JSON parsing, scientific computing) in 4 languages each.
- **Comprehensive Test Suite**: 33+ tests covering correctness, performance, fallback mechanisms, integration, and platform compatibility.
- **PyPI Distribution Infrastructure**: Complete packaging for PyPI with optional WASM dependencies and Python 3.12+ support.
- **Documentation Suite**: WASM architecture overview, installation guides, performance tuning, troubleshooting, and FAQ.

### Changed
- CLI `multilingual run <file>.ml` correctly handles `.ml` file execution.
- **Python Version Support**: 3.12+ (advanced features).
- **Performance Profile**: CPU-bound operations can execute substantially faster via WASM backend (benchmark-dependent).
- **Dependency Model**: WASM support now optional via `[wasm]` extra; numpy support optional via `[performance]`.

### Fixed
- Broken relative links in `docs/reference.md` and `docs/fr/programmation.md` (`../CHANGELOG.md`, `../USAGE.md`, `../examples/README.md`).
- Variable name clashes in Spanish (`y` = AND keyword) and Danish/Swedish (`i` = IN keyword) comprehension examples.
- Complete multilingual support for WASM infrastructure across all 17 languages.
- All 1671 tests passing, 2 skipped (WASM Rust compile, requires `rustc` wasm32 target).

## [0.3.0] - 2026-02-22

### Added
- Complete feature examples (`examples/complete_features_XX.multi`) for all 17 supported languages.
- Verified feature parity across all languages with comprehensive test coverage.

### Changed
- Enhanced language coverage from 12 to 17 supported languages with complete examples.
- Test suite expanded with integrated complete feature validation for all languages.

### Fixed
- Zero regressions; all 85 tests passing.

## [0.2.0] - 2026-02-21

### Added
- Advanced language feature support across parser/codegen/runtime tests.
- Expanded localized built-in alias coverage and compatibility fixtures.
- Python 3.12+ packaging baseline with 3.12/3.13/3.14 CI verification.

### Changed
- Test module naming migrated away from milestone-oriented file names.
- Example programs refreshed to include newer feature coverage.
