# Using AI Keywords in WASM

**Status:** Reference guide for WAT/WASM developers  
**Updated:** 2026-05-23

---

## Overview

AI keywords (PROMPT, GENERATE, EXTRACT, CLASSIFY, THINK, STREAM, PLAN, EMBED,
TRANSCRIBE) are implemented in the **Python/Core 1 runtime** and can use the
MockProvider or optional OpenAI, Anthropic, and Ollama providers. WAT/WASM
integration is host-driven: browser or Wasmtime embeddings must provide host
imports/callbacks for model calls.

This guide explains how to integrate AI functionality when targeting WebAssembly.

---

## The Challenge

### Python (Works Out-of-Box)
```python
let response = prompt @default: "What is 2 + 2?"
print(response)  # "4"
```

The Python backend uses a MockProvider for tests and examples unless a real
provider is registered. Install `multilingualprogramming[ai]` for the OpenAI,
Anthropic, and Ollama provider SDKs.

### WASM (Requires Host Imports)
```wat
(call $prompt (i32.const 0) (i32.const 20))
```

WASM can't directly call external services. Instead, it must:
1. Define **host imports** for AI functions
2. Pass **request/response** through memory
3. Implement **host callbacks** in JavaScript/browser

---

## Solution: Host Imports

### What WASM Generates

When compiling multilingual code with AI keywords to WASM, the WAT includes calls like:

```wat
(import "env" "_prompt" (func $prompt (param i32 i32) (result i32)))
(import "env" "_generate" (func $generate (param i32 i32) (result i32)))
(import "env" "_extract" (func $extract (param i32 i32) (result i32)))
(import "env" "_classify" (func $classify (param i32 i32) (result i32)))
(import "env" "_think" (func $think (param i32 i32) (result i32)))
(import "env" "_stream" (func $stream (param i32 i32) (result i32)))
(import "env" "_plan" (func $plan (param i32 i32) (result i32)))
(import "env" "_embed" (func $embed (param i32 i32) (result i32)))
(import "env" "_transcribe" (func $transcribe (param i32 i32) (result i32)))
```

Each function:
- Takes 2 parameters: **input pointer (i32)** and **input length (i32)**
- Returns **output pointer (i32)** pointing to result in linear memory

### What You Must Provide

Implement these host functions in JavaScript:

```javascript
const hostFunctions = {
  env: {
    _prompt: (inputPtr, inputLen) => {
      const prompt = readStringFromMemory(inputPtr, inputLen);
      const response = "Mock response: " + prompt;
      return writeStringToMemory(response);
    },
    
    _generate: (inputPtr, inputLen) => {
      const spec = readStringFromMemory(inputPtr, inputLen);
      const output = "Generated: " + spec;
      return writeStringToMemory(output);
    },
    
    _extract: (inputPtr, inputLen) => {
      const text = readStringFromMemory(inputPtr, inputLen);
      // Parse and return extracted items
      return writeStringToMemory(JSON.stringify([]));
    },
    
    _classify: (inputPtr, inputLen) => {
      const text = readStringFromMemory(inputPtr, inputLen);
      return writeStringToMemory("POSITIVE");
    },
    
    // ... implement others similarly
  }
};
```

---

## Memory Layout Conventions

WASM uses linear memory to pass strings between the host and module.

### Reading from Memory

```javascript
function readStringFromMemory(ptr, len) {
  const buffer = new Uint8Array(wasmInstance.exports.memory.buffer, ptr, len);
  return new TextDecoder().decode(buffer);
}
```

### Writing to Memory

```javascript
function writeStringToMemory(str) {
  const encoder = new TextEncoder();
  const encoded = encoder.encode(str);
  const ptr = wasmInstance.exports.allocate(encoded.length);
  
  const buffer = new Uint8Array(wasmInstance.exports.memory.buffer, ptr, encoded.length);
  buffer.set(encoded);
  
  return ptr;
}
```

**Note:** Your WASM module must export an `allocate()` function to reserve memory for responses.

---

## Example: Browser Integration

### 1. Build A WAT/WASM Bundle

```bash
multilingual build-wasm-bundle examples/my_ai_program.multi \
  --lang en \
  --out-dir build/my_ai_program
```

The current CLI uses `build-wasm-bundle` for deterministic browser/WASI
artifacts.

### 2. Load and Instantiate

```javascript
const wasmModule = await fetch('my_ai_program.wasm')
  .then(r => r.arrayBuffer())
  .then(b => WebAssembly.instantiate(b, { env: hostFunctions }));

const { main, memory, allocate } = wasmModule.instance.exports;
```

### 3. Connect to Real AI Service

```javascript
hostFunctions.env._prompt = async (inputPtr, inputLen) => {
  const prompt = readStringFromMemory(inputPtr, inputLen);
  
  // Call your AI service (Ollama, Claude, etc.)
  const response = await fetch('/api/prompt', {
    method: 'POST',
    body: JSON.stringify({ prompt })
  }).then(r => r.json());
  
  return writeStringToMemory(response.text);
};
```

---

## Complete Working Example

### Multilingual Code (`ai_demo.multi`)
```multilingual
let question = "What is machine learning?"
let answer = prompt @default: question
print("Q:", question)
print("A:", answer)
```

### Build WAT/WASM Artifacts
```bash
multilingual build-wasm-bundle ai_demo.multi --lang en --out-dir build/ai_demo
```

### JavaScript Host (`ai_demo.html`)
```html
<!DOCTYPE html>
<html>
<head><title>WASM AI Demo</title></head>
<body>
  <div id="output"></div>
  <script>
    // Memory utilities
    function readStringFromMemory(ptr, len) {
      const buffer = new Uint8Array(memory.buffer, ptr, len);
      return new TextDecoder().decode(buffer);
    }
    
    function writeStringToMemory(str) {
      const encoded = new TextEncoder().encode(str);
      const ptr = allocate(encoded.length);
      const buffer = new Uint8Array(memory.buffer, ptr, encoded.length);
      buffer.set(encoded);
      return ptr;
    }
    
    // Host functions
    const hostFunctions = {
      env: {
        _prompt: (inputPtr, inputLen) => {
          const prompt = readStringFromMemory(inputPtr, inputLen);
          const response = `Processed: "${prompt}"`;
          return writeStringToMemory(response);
        },
        _generate: (inputPtr, inputLen) => {
          return writeStringToMemory("Generated output");
        },
        _extract: (inputPtr, inputLen) => {
          return writeStringToMemory("[]");
        },
        _classify: (inputPtr, inputLen) => {
          return writeStringToMemory("NEUTRAL");
        },
        // ... other AI functions
      }
    };
    
    // Load and run
    let memory, allocate, main;
    
    WebAssembly.instantiateStreaming(
      fetch('ai_demo.wasm'),
      hostFunctions
    ).then(({ instance }) => {
      memory = instance.exports.memory;
      allocate = instance.exports.allocate;
      main = instance.exports.main;
      
      // Execute main
      main();
    });
  </script>
</body>
</html>
```

---

## API Reference

| Keyword | Purpose | Input Format | Output Format |
|---------|---------|--------------|---------------|
| `prompt` | Ask a question | Plain text | Plain text |
| `generate` | Create content | Specification | Generated text |
| `extract` | Parse data | Unstructured text | JSON array |
| `classify` | Categorize | Text | Category label |
| `think` | Reason through | Problem | Reasoning steps |
| `stream` | Stream response | Query | Iterator/stream |
| `plan` | Create steps | Goal | List of steps |
| `embed` | Get vector | Text | Float array |
| `transcribe` | Audio→text | Audio data | Transcribed text |

---

## Migration Path

### Phase 1 (Current)
- ✅ Mock implementations (for testing)
- ✅ Dummy host imports

### Phase 2 (v0.9.0)
- Plan: Real AI service integration
- Plan: Caching layer for embeddings
- Plan: Streaming support

### Phase 3 (v1.0.0)
- Plan: Native WASI AI module
- Plan: Hardware acceleration for embeddings
- Plan: Multi-provider support (OpenAI, Anthropic, Ollama)

---

## Troubleshooting

### Error: Undefined host import `_prompt`
**Cause:** Host function not provided  
**Fix:** Add `_prompt` to your `hostFunctions.env` object

### Error: Invalid pointer in `readStringFromMemory`
**Cause:** WASM module didn't allocate memory properly  
**Fix:** Ensure WASM module exports `allocate()` function

### Responses are truncated or garbled
**Cause:** Memory write overflow  
**Fix:** Increase buffer size or use dynamic allocation

---

## Best Practices

1. **Always check buffer bounds** before reading/writing
2. **Implement timeout handling** for external AI calls
3. **Cache embeddings** to avoid redundant computation
4. **Use separate host functions** for different AI services
5. **Test with mock implementations first**, then swap in real services

---

## See Also

- [WASM Architecture Overview](WASM_ARCHITECTURE_OVERVIEW.md)
- [Release Notes](CHANGELOG.md)
- [Frontend Contracts](frontend_contracts.md)

---

## Contributing

To improve this guide or add new AI integrations:

1. Create a pull request with your improvements
2. Include working example code
3. Document any new host import signatures
4. Add test cases for new functionality

---

**Generated:** 2026-05-08  
**Maintainer:** Multilingual Programming Team  
**License:** GPL-3.0-or-later
