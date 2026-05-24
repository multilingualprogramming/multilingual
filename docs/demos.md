# Demos

A short tour of Multilingual in the browser and in the repository.

## Featured demos

### Multilingual AI agent

The same agent logic written in three human languages with shared behavior.

- `examples/agent_en.multi`
- `examples/agent_fr.multi`
- `examples/agent_ja.multi`

### Memory Game

Reactive UI, async handlers, and browser interaction in Multilingual.

**[Play the Memory Game](memory-game-demo.html)**

- `examples/memory_game_en.multi`
- `examples/memory_game_fr.multi`

### Spatial dynamics

Fixed-semantic 2D research prototype for post-textual computation.

**[Open the Spatial Dynamics prototype](browser/spatial-dynamics/)**

- no textual source editor inside the workspace
- no labels rendered on the computational canvas
- fixed visual primitives with dynamic interaction laws
- source is authored in `program.multi` and built into `program.spatial.json`

```bash
multilingual spatial-build docs/browser/spatial-dynamics/program.multi \
  --out docs/browser/spatial-dynamics/program.spatial.json
```

### Sonic dynamics (polymodal projection)

The same `program.multi` rendered as a WebAudio composition rather than
a 2D scene. Demonstrates the polymodal architecture: one program, two
peer realizations sharing a modality-free semantic core.

**[Open the Sonic Dynamics prototype](browser/sonic-dynamics/)**

```bash
multilingual sonic-build docs/browser/spatial-dynamics/program.multi \
  --out docs/browser/sonic-dynamics/program.sonic.json

multilingual polymodal-build docs/browser/spatial-dynamics/program.multi \
  --out /tmp/program.semantic.json
```

See [Polymodal Computation](research/polymodal_computation.md) for the
layered design and cross-modal equivalence guarantees.

### Reactive counter

A compact reactive web app using state changes and canvas updates.

- `examples/reactive_counter.multi`

### Streaming chat

French-language example of streaming output bound to a reactive view.

- `examples/streaming_chat_fr.multi`

### Semantic search

Japanese example using semantic matching concepts.

- `examples/semantic_search_ja.multi`

### Multilingual dashboard

Combines agent-style behavior, reactive state, and UI composition.

- `examples/multilingual_dashboard.multi`

## Browser tools

- **[Open the Playground](playground.html)** for live editing and experimentation.
- **[Open the WASM Demo Hub](browser/index.html)** for precompiled browser demos.

## Useful CLI commands

```bash
multilingual ir my_program.multi
multilingual explain my_program.multi
multilingual ui-preview my_program.ml --html
multilingual run my_program.ml --mode core
```
