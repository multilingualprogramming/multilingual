# Multilingual Programming Language - WASM Infrastructure Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│               Multilingual Programming Language v0.5.x          │
│                    (WAT/WASM Infrastructure)                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴──────────────┐
                │                            │
         ┌──────▼──────┐          ┌──────────▼────────┐
         │ User Code   │          │ Standard Library  │
         │ (.multi files) │       │ (17 languages)    │
         └──────┬──────┘          └──────────┬────────┘
                │                            │
                └─────────────┬──────────────┘
                              │
                         ┌────▼─────┐
                         │ Lexer    │
                         │ (Lexer)│
                         └────┬─────┘
                              │
                         ┌────▼─────┐
                         │ Parser    │
                         │ (Parser) │
                         └────┬─────┘
                              │
                    ┌─────────▼──────────┐
                    │   AST (Abstract    │
                    │  Syntax Tree)      │
                    └─────────┬──────────┘
                              │
                ┌─────────────┴──────────────┐
                │                            │
         ┌──────▼──────────┐      ┌──────────▼────────┐
         │ Python Code     │      │   WASM Code       │
         │ Generation      │      │   Generation      │
         │ (Code Generation)       │      │ (WASM Code Generation)      │
         └──────┬──────────┘      └──────────┬────────┘
                │                            │
                │                    ┌───────▼────────┐
                │                    │ WAT Source     │
                │                    │ (Text Format)  │
                │                    └───────┬────────┘
                │                            │
                │                    ┌───────▼────────┐
                │                    │ Wasmtime/WAT   │
                │                    │ Compilation    │
                │                    └───────┬────────┘
                │                            │
                │                    ┌───────▼────────┐
                │                    │ WASM Binary    │
                │                    │ when available │
                │                    └───────┬────────┘
                │                            │
                └─────────────┬──────────────┘
                              │
                    ┌─────────▼──────────┐
                    │ Backend Selector   │
                    │ (Backend Selection)       │
                    │ Smart Auto-        │
                    │ Detection          │
                    └─────────┬──────────┘
                              │
                ┌─────────────┴──────────────┐
                │                            │
         ┌──────▼──────────┐      ┌──────────▼────────┐
         │ Python Executor │      │ WASM Loader       │
         │ (+ Fallbacks)   │      │ (WASM Bridge)      │
         │ (Python Fallbacks)    │      │ (+ Type Conv)     │
         └──────┬──────────┘      └──────────┬────────┘
                │                            │
                │              ┌─────────────┼──────────────┐
                │              │             │              │
                │         ┌────▼──┐    ┌────▼──┐    ┌─────▼──┐
                │         │Python │    │WASM   │    │Memory  │
                │         │Fallbk │    │Exec   │    │Mgmt    │
                │         │(25+   │    │Inst.  │    │(Linear)│
                │         │funcs) │    │       │    │Memory  │
                │         └────┬──┘    └────┬──┘    └────┬───┘
                │              │            │            │
                │              └─────────────┴────────────┘
                │                            │
                └─────────────┬──────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  Results / Output  │
                    └────────────────────┘
```

---

> **Pipeline status (v0.5.x):** Two WASM paths exist side-by-side.
>
> **WAT path (primary, production-ready):** `WATCodeGenerator` compiles the multilingual
> AST directly to WebAssembly Text (WAT). The generated WAT is compiled to binary WASM by
> `wabt` / `wat2wasm` and executed by Wasmtime. Class methods, stateful OOP instances
> (heap allocation via `$__heap_ptr`), `self.attr` field reads/writes, and instance method
> calls are fully lowered. All 17-language `complete_features_*.multi` examples compile to
> executable WASM and are validated in CI.
>
> **Rust/Cranelift path (stub, planned):** `WasmCodeGenerator.generate()` produces Rust
> intermediate code but function bodies remain stubs (`return 0`). `WasmBuildConfig.build()`
> returns `None`; Cranelift compilation is not yet implemented. No pre-built `.wasm` corpus
> binaries are shipped with the package.

---

## WASM Infrastructure: WASM Infrastructure Stack

### 1. WASM Code Generation: WASM Code Generation

**Component**: `multilingualprogramming/codegen/wasm_generator.py`

**Responsibilities**:
- Transform AST → Rust intermediate code
- Generate memory management code
- Optimize for Cranelift backend
- Export function metadata

**Key Features**:
- Rust code generation (200+ lines)
- Multi-function support
- Memory allocation (64MB)
- Panic handlers
- Metadata functions

**Output**: Rust source code ready for compilation

---

### 2. WASM Bridge: Python ↔ WASM Bridge

**Component**: `multilingualprogramming/wasm/loader.py`

**Responsibilities**:
- Load WASM binaries
- Instantiate WASM modules
- Type conversion (Python ↔ WASM)
- Memory management
- Module caching

**Key Classes**:

```python
class WasmModule:
    """Represents a loaded WASM module."""
    @staticmethod
    def load(module_path: Union[str, Path]) -> WasmModule
    def instantiate(self) -> bool
    def call(self, function_name: str, *args) -> Any
    def has_function(self, function_name: str) -> bool

class WasmModuleCache:
    """Cache loaded modules to avoid reloading."""
    def get_or_load(self, module_path: Union[str, Path]) -> Optional[WasmModule]
```

**Key Features**:
- Lazy module loading
- Module caching for performance
- Type conversion framework
- Memory buffer access
- Error handling

---

### 3. Backend Selection: Smart Backend Selector

**Component**: `multilingualprogramming/runtime/backend_selector.py`

**Responsibilities**:
- Auto-detect WASM availability
- Route function calls to correct backend
- Manage fallback logic
- Track performance statistics
- Handle errors gracefully

**Key Classes**:

```python
class Backend(Enum):
    """Available execution backends."""
    PYTHON = "python"
    WASM = "wasm"
    AUTO = "auto"

class BackendSelector:
    """Intelligent backend selection."""
    def __init__(self, prefer_backend: Backend = Backend.AUTO)
    def is_wasm_available(self) -> bool
    def call_function(self, function_name: str, *args) -> Any

class BackendRegistry:
    """Register functions for different backends."""
    def register_python(self, func_name: str, func: Callable)
    def register_wasm(self, func_name: str, wasm_path: str)
```

**Detection Algorithm**:

```
1. Check if wasmtime installed
2. Check if WASM binary exists
3. Check platform compatibility
4. Try to load WASM module
5. If any step fails → use Python fallback
```

---

### 4. Python Fallbacks: Python Fallback Implementations

**Component**: `multilingualprogramming/runtime/python_fallbacks.py`

**Responsibilities**:
- Pure Python implementations of WASM functions
- NumPy acceleration where applicable
- Function registry management
- Fallback selection

**8 Operation Classes** (25+ functions):

```python
class MatrixOperations:
    multiply(), transpose(), determinant()

class StringOperations:
    reverse(), is_palindrome(), character_frequency()

class CryptoOperations:
    simple_hash(), xor_cipher(), xor_decipher()

class DataProcessing:
    filter_data(), map_data(), reduce_data(), sort_data()

class NumericOperations:
    fibonacci(), factorial(), gcd(), lcm()

class JSONOperations:
    parse_json_simple(), stringify_json()

class SearchOperations:
    binary_search(), linear_search()

class ImageOperations:
    blur_simple()
```

**Key Features**:
- 100% Python (no external dependencies)
- NumPy-optimizable
- Identical to WASM behavior
- Comprehensive test coverage

---

### 5. WASM Corpus: Source Corpus Projects

> **Note:** The repository includes multilingual corpus source programs and tests
> that generate WAT/WASM artifacts as part of validation. Precompiled corpus
> `.wasm` binaries are not shipped with the Python package.

**Corpus: 5 Real-World Project Families** × **multiple language surfaces**

**Projects**:

1. **Matrix Operations**
   - Matrix multiplication (100×100 to 1000×1000)
   - Transpose and determinant
   - Expected speedup: **workload-dependent (benchmark for exact values)**

2. **Cryptography**
   - XOR cipher, Caesar cipher
   - Hash function, password verification
   - Projected speedup: **~workload-dependent (benchmark for exact values)**

3. **Image Processing**
   - Blur filter, edge detection
   - Histogram calculation
   - Projected speedup: **~workload-dependent (benchmark for exact values)**

4. **JSON Parsing**
   - Parse/stringify large JSON
   - Data transformation
   - Projected speedup: **~workload-dependent (benchmark for exact values)**

5. **Scientific Computing**
   - Monte Carlo simulations
   - Numerical integration
   - Projected speedup: **~workload-dependent (benchmark for exact values)**

---

### 6. Comprehensive Testing: Comprehensive Testing

**33+ Test Methods** across **5 Categories**:

1. **Correctness Tests** (12 tests)
   - Verify Python/WASM identical results

2. **Performance Benchmarks** (6 tests)
   - Measure actual speedups

3. **Fallback Tests** (5 tests)
   - Verify graceful degradation

4. **Integration Tests** (4 tests)
   - Full pipeline validation

5. **Platform Tests** (4 tests)
   - Cross-platform compatibility

---

### 7. PyPI Distribution: PyPI Distribution

**Package Structure**:

```
multilingualprogramming-0.4.0-py3-none-any.whl
├── multilingualprogramming/
│   ├── codegen/
│   │   └── wasm_generator.py (200+ lines)
│   ├── wasm/
│   │   └── loader.py (250+ lines)
│   │   # Note: no *.wasm binaries are included yet (see WASM Corpus section)
│   ├── runtime/
│   │   ├── backend_selector.py (300+ lines)
│   │   └── python_fallbacks.py (400+ lines)
│   └── ...
├── docs/
│   ├── WASM_INSTALLATION.md
│   ├── WASM_DEVELOPMENT.md
│   ├── WASM_PERFORMANCE_TUNING.md
│   ├── ARCHITECTURE_OVERVIEW.md
│   ├── TROUBLESHOOTING.md
│   └── FAQ.md
├── tests/
│   ├── wasm_corpus_test.py
│   └── wasm_comprehensive_test.py
└── pyproject.toml (WASM-enabled)
```

**Installation Options**:

```bash
pip install multilingualprogramming              # Python only
pip install multilingualprogramming[wasm]        # + wasmtime runtime
pip install multilingualprogramming[performance] # + wasmtime + NumPy
```

> **Note:** The installation size figures previously listed (50 MB / 150 MB / 250 MB) assumed a pre-built WASM binary corpus that is not yet included. Actual installed size is significantly smaller.

---

### 8. Documentation Suite: Final Documentation

**3 Documentation Files**:

1. **ARCHITECTURE_OVERVIEW.md** (this file)
   - System design
   - Component interactions
   - Data flow

2. **TROUBLESHOOTING.md**
   - Common issues
   - Debug techniques
   - Solutions

3. **FAQ.md**
   - Frequently asked questions
   - Best practices
   - Use cases

---

## WAT OOP Object Model

The `WATCodeGenerator` implements a lightweight linear-memory object model for classes.

### Stateful vs. Stateless Classes

| Kind | Definition | WAT behaviour |
|------|-----------|---------------|
| **Stateless** | No `self.attr = …` in any method | `f64.const 0` passed as `self`; no heap allocation |
| **Stateful** | At least one `self.attr = …` | Heap allocation on every constructor call; `self` carries the heap address |

### Memory Layout

```
Linear memory (WAT, 64 KB default page)
┌──────────────────────────────┐  ← offset 0
│  String data section         │  ← interned string literals (immutable)
├──────────────────────────────┤  ← HEAP_BASE = max(ceil(string_len / 8) * 8, 64)
│  Object heap                 │  ← bump-allocated instances (grows upward)
└──────────────────────────────┘  ← 65535
```

The heap pointer is a single WAT global emitted only when stateful classes exist:

```wat
(global $__heap_ptr (mut i32) (i32.const HEAP_BASE))
```

### Field Layout

Each `f64` field occupies 8 bytes. Field order is determined by first-seen
`self.attr = …` assignment, scanning `__init__` first then remaining methods.

```
base + 0   : f64  (first field)
base + 8   : f64  (second field)
...
```

### Constructor Sequence

`Counter(10)` (stateful, 1 field = 8 bytes) compiles to:

```wat
global.get $__heap_ptr      ;; advance heap pointer
i32.const 8
i32.add
global.set $__heap_ptr
global.get $__heap_ptr      ;; self = new_ptr - size
i32.const 8
i32.sub
f64.convert_i32_u           ;; self as f64
f64.const 10.0              ;; arg
call $Counter____init__
drop                        ;; discard __init__ return value
global.get $__heap_ptr      ;; push object ref
i32.const 8
i32.sub
f64.convert_i32_u
```

### Field Store / Load

`self.value = x` → `f64.store`; `self.value` → `f64.load` at the compile-time byte offset.

For full details, limitations, and a complete end-to-end example see
[docs/wat_oop_model.md](wat_oop_model.md).

---

## Data Flow Examples

### Example 1: Matrix Multiplication

```
User Code:
    result = selector.call_function("matrix_multiply", a, b)

            ↓

Backend Selector:
    WASM available? → YES
    Load module "matrix_operations.wasm"

            ↓

WASM Path:
    Call WASM function matrix_multiply(a, b)
        → Type conversion (Python list → WASM memory)
        → Execute WASM code (performance varies by workload)
        → Convert results (WASM memory → Python list)
        → Return result

Result: performance improvement depends on workload/hardware ✓


But if WASM unavailable:

Backend Selector:
    WASM available? → NO
    Use Python fallback

            ↓

Python Path:
    Call MatrixOperations.multiply(a, b)
        → Pure Python implementation
        → Maybe NumPy-accelerated
        → Return result

Result: Always works! ✓
```

---

## Performance Characteristics

### Speedup by Operation

> **Note:** Speedup is highly operation-dependent. Arithmetic-heavy loops (e.g. Mandelbrot) measure approximately **2.4×** in practice. The figures below reflect projected speedups for heavy data-parallel operations; they are not universally applicable.

| Operation | Size | Python | WASM | Speedup |
|-----------|------|--------|------|---------|
| Matrix multiply | 1000×1000 | 5.0s | 50ms | **~100x** (projected) |
| JSON parse | 10MB | 200ms | 20ms | **~10x** (projected) |
| XOR cipher | 1MB | 100ms | 1ms | **~100x** (projected) |
| Fibonacci | n=30 | 200ms | 2ms | **~100x** (projected) |
| Blur filter | 4K image | 2s | 40ms | **~50x** (projected) |

### Overhead Analysis

```
WASM Call Overhead:
  Module load: 10-50ms (cached)
  Function call: ~0.031ms (measured; Python FFI → WASM)
  Type conversion: 0.01-0.1ms per arg

Break-even point:
  Operation must be > ~0.05ms to justify WASM overhead
```

---

## Memory Architecture

### Python Memory
```
Standard Python heap management
Unlimited (system RAM limit)
Garbage collected
```

### WASM Linear Memory
```
64MB contiguous linear memory
Manually managed by WASM code
Pages: 1024 (64KB each = 64MB)
Structure:
  ┌─────────────────────┐
  │ Stack (grows up)    │  High memory
  ├─────────────────────┤
  │ Heap (grows down)   │
  ├─────────────────────┤
  │ Static data         │
  ├─────────────────────┤
  │ Reserved            │  Low memory
  └─────────────────────┘
```

---

## Integration Points

### With Python Ecosystem

```
multilingual → Python code generation
              → Standard Python execution
              → Works with existing Python tools
              → Compatible with pip, virtualenv, etc.
```

### With WASM Ecosystem

```
multilingual → WASM code generation
              → Cranelift compilation
              → Wasmtime runtime
              → Browser execution (future)
              → Serverless (future)
```

---

## Execution Model

### Two-Path Execution

```
Source Code (.multi, .ml)
    ↓
Lexer & Parser
    ↓
AST
    ├─ Path 1: Python
    │   Code Generation → Python Executor
    │   (Always works, slower)
    │
    └─ Path 2: WAT/WASM
        WAT Code Generation → WAT text → wat2wasm → WASM Binary → Wasmtime execution
        (Functional for core language + OOP; requires wasmtime + wabt)
        [Rust/Cranelift path: PLANNED — stubs only]
    ↓
Backend Selector
    (Auto-detect best path)
    ├─ WASM available → Use WASM (2–typically faster depending on operation on suitable workloads)
    └─ Else → Use Python (always works)
    ↓
Execution
    (Transparent to user)
    ↓
Results (identical)
```

---

## Quality Assurance

### Testing Strategy

```
Correctness:
  ✓ Python and WASM produce identical results
  ✓ Type conversions work correctly
  ✓ Edge cases handled
  ✓ 12 correctness tests

Performance:
  ✓ WASM faster than Python for many compute-heavy workloads (benchmark-dependent)
  ✓ No unexpected slowdowns
  ✓ Overhead quantified
  ✓ 6 performance benchmarks

Reliability:
  ✓ Fallback works without WASM
  ✓ Graceful degradation
  ✓ Error handling tested
  ✓ 5 fallback tests

Integration:
  ✓ Full pipelines work
  ✓ Component interaction tested
  ✓ 4 integration tests

Platform:
  ✓ Windows, Linux, macOS
  ✓ 32-bit and 64-bit
  ✓ Python 3.12+
  ✓ 4 platform tests
```

---

## Key Design Decisions

### 1. Why Two Backends?

**Python**: Always works, easy to debug
**WASM**: Fast for compute-intensive work

**Solution**: Automatic selection, transparent to user

### 2. Why Fallbacks?

WASM requires:
- Compilation (time)
- External runtime (wasmtime)
- Platform support

**Solution**: Pure Python fallback, always available

### 3. Why Module Caching?

WASM module load is expensive (10-50ms)

**Solution**: Cache modules after first load

### 4. Why 25+ Fallback Functions?

Ensure correct behavior even without WASM

**Solution**: Comprehensive Python implementations

### 5. Why NumPy Optimization?

Fallback path should be as fast as possible

**Solution**: NumPy-accelerate where applicable

---

## Future Enhancements (Advanced Features)

### Short Term
- [ ] Browser-based WASM execution
- [ ] Parallel execution (multiple WASM modules)
- [ ] JIT compilation (compile at runtime)

### Medium Term
- [ ] GPU acceleration (WASM SIMD)
- [ ] Distributed computing
- [ ] Cloud deployment templates

### Long Term
- [ ] Quantum computing support
- [ ] Hardware accelerators
- [ ] Custom WASM targets

---

## Compliance & Standards

### Supported Standards
- ✅ WebAssembly 1.0 (W3C)
- ✅ Python 3.12+ (PEP 8)
- ✅ GPL-3.0-or-later (licensing)

### Compatibility Matrix

| Component | Windows | Linux | macOS | BSD |
|-----------|---------|-------|-------|-----|
| Python | ✅ | ✅ | ✅ | ✅ |
| WASM | ✅ | ✅ | ✅ | ⚠️ |
| NumPy | ✅ | ✅ | ✅ | ⚠️ |

---

## Resources

### Documentation
- [WASM Installation](./WASM_INSTALLATION.md)
- [WASM Development](./WASM_DEVELOPMENT.md)
- [Performance Tuning](./WASM_PERFORMANCE_TUNING.md)

### External References
- [WebAssembly Spec](https://webassembly.org/)
- [Cranelift Compiler](https://docs.rs/cranelift/)
- [Wasmtime Runtime](https://docs.wasmtime.dev/)

---

## Summary

The WAT/WASM infrastructure delivers a **2-path execution model** with **transparent backend selection**:

- ✅ **Always works** (Python fallback)
- ✅ **WAT path production-ready** (core language + OOP fully lowered; all 17 languages validated)
- ✅ **No code changes required** (automatic selection)
- ✅ **Cross-platform** (Windows/Linux/macOS)
- ✅ **Stability-focused** (1787 tests, comprehensive docs)

---

**Version**: v0.5.x (updated March 2026)
**Status**: WAT path stable; Rust/Cranelift path planned.
**Architecture**: Stable & Extensible
