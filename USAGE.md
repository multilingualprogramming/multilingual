## Usage

The project provides several independent modules.

## Related Docs

- Quick start: [README.md](README.md)
- Detailed reference: [docs/reference.md](docs/reference.md)

## Numerals

```python
from multilingualprogramming.numeral.mp_numeral import MPNumeral

num1 = MPNumeral("VII")
num2 = MPNumeral("III")
print(num1 + num2)  # X
```

## Keywords

```python
from multilingualprogramming.keyword.keyword_registry import KeywordRegistry

registry = KeywordRegistry()
print(registry.get_keyword("COND_IF", "fr"))  # si
```

## Date/Time

```python
from multilingualprogramming.datetime.mp_date import MPDate

d = MPDate.from_string("15-Janvier-2024")
print(d.to_string("en"))
```

## Lexer

```python
from multilingualprogramming.lexer.lexer import Lexer

lexer = Lexer("if x > 5:\n    print(x)", language="en")
tokens = lexer.tokenize()
print(tokens)
```

## Execute a Program

```python
from multilingualprogramming import ProgramExecutor

result = ProgramExecutor(language="en").execute("""\
def add(a, b):
    return a + b
print(add(2, 3))
""")

print(result.success)  # True
print(result.output)   # 5
```

`ProgramExecutor` enables `.multi` and `.ml` module imports automatically during execution.

## CLI Essentials

```bash
multilingual --version
multilingual run hello.multi --lang en
multilingual run hello.multi --show-backend
multilingual run hello.multi --mode core
multilingual compile hello.multi --lang en
multilingual smoke --all
multilingual ir hello.multi --format json
multilingual explain hello.multi
```

Backend and artifact helpers:

```bash
multilingual repl --show-python --show-wat --show-rust
multilingual wat-abi hello.multi --lang en
multilingual wat-host-shim hello.multi --lang en
multilingual wat-renderer-template hello.multi --lang en
multilingual build-wasm-bundle hello.multi --out-dir build/wasm
multilingual build-browser-module hello.multi --lang en --export describe,build_manifest --out build/browser_module.mjs
multilingual build-ui-bundle examples/memory_game_en.multi --out-dir build/ui
multilingual ui-preview examples/memory_game_en.multi --html
```

`build-browser-module` emits a browser-native ES module for JSON-compatible
Multilingual programs. It is intended for rich dictionaries/lists/strings that
do not fit the narrow scalar WASM ABI yet:

```bash
python -m multilingualprogramming build-browser-module app.multi \
  --lang en \
  --export describe,build_manifest \
  --out public/generated/app/browser_module.mjs
```

The generated module can be loaded with a normal browser dynamic import:

```js
const app = await import("./generated/app/browser_module.mjs");
const manifest = app.build_manifest({ name: "demo", items: [1, 2, 3] });
```

## Optional Extras

```bash
pip install "multilingualprogramming[wasm]"
pip install "multilingualprogramming[ai]"
pip install "multilingualprogramming[performance]"
pip install "multilingualprogramming[all]"
```

The `ai` extra installs provider SDKs for OpenAI, Anthropic, and Ollama.

## Enable `.multi` Imports In Plain Python

```python
from multilingualprogramming import enable_multilingual_imports

enable_multilingual_imports()

import my_module  # loads my_module.multi (or my_module.ml) when present on sys.path
```

## Parse and Inspect AST

```python
from multilingualprogramming import Lexer, Parser, ASTPrinter

source = """\
def square(x):
    return x * x
"""

tokens = Lexer(source, language="en").tokenize()
ast = Parser(tokens, source_language="en").parse()
print(ASTPrinter().print(ast))
```

## Core 1 Runtime APIs

```python
from multilingualprogramming.runtime import (
    AIRuntime,
    AnthropicProvider,
    OpenAIProvider,
    OllamaProvider,
    InferenceCache,
    ModelRegistry,
    ReactiveEngine,
    Channel,
)
```

Provider SDKs are optional. Install `multilingualprogramming[ai]` before
constructing the concrete OpenAI, Anthropic, or Ollama providers.

## Run Examples

```bash
python -m examples.arithmetic
python -m examples.numeral_extended
python -m examples.keywords
python -m examples.datetime_example
python -m examples.lexer_example
python -m examples.parser_example
python -m examples.ast_example
python -m examples.multilingual_parser_example
python -m examples.codegen_example
python -m examples.multilingual_codegen_example
python -m examples.semantic_example
python -m examples.executor_example
```
