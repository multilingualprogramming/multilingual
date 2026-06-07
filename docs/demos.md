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
a 2D scene. The browser runtime also exposes a microphone-capture path
that runs the inverse sonic projection in real time
(audio → `ObservedVoice` records → `semantic-core-v0`).

**[Open the Sonic Dynamics prototype](browser/sonic-dynamics/)**

```bash
multilingual sonic-build docs/browser/spatial-dynamics/program.multi \
  --out docs/browser/sonic-dynamics/program.sonic.json
```

### Linear dynamics (1D polymodal projection)

The same `program.multi` rendered as a one-dimensional timeline strip.
Each entity becomes a positioned mark along a single axis; channel
drives the vertical lane.

**[Open the Linear Dynamics prototype](browser/linear-dynamics/)**

```bash
multilingual linear-build docs/browser/spatial-dynamics/program.multi \
  --out docs/browser/linear-dynamics/program.linear.json
```

### Volumetric dynamics (3D polymodal projection)

The same `program.multi` rendered as a rotating three-dimensional
scene using canvas 2D with a hand-rolled rotation and perspective —
no WebGL or 3D library required.

**[Open the Volumetric Dynamics prototype](browser/volumetric-dynamics/)**

```bash
multilingual volumetric-build docs/browser/spatial-dynamics/program.multi \
  --out docs/browser/volumetric-dynamics/program.volumetric.json
```

### MIDI dynamics (discrete-event polymodal projection)

The same `program.multi` rendered as a flat list of MIDI events
visualized as a piano roll. An optional "Web MIDI Out" button forwards
the events to a connected synthesizer. Exists to falsify the claim
that the ontology only maps cleanly to continuous-shape modalities.

**[Open the MIDI Dynamics prototype](browser/midi-dynamics/)**

```bash
multilingual midi-build docs/browser/spatial-dynamics/program.multi \
  --out docs/browser/midi-dynamics/program.midi.json
```

### Semantic core and shared ontology

Every projection above is derived from the same modality-free semantic
core. The ontology sidecar is exported separately so browser runtimes
fetch the same opcode table the Python projections use.

```bash
multilingual polymodal-build docs/browser/spatial-dynamics/program.multi \
  --out /tmp/program.semantic.json

multilingual ontology-export \
  --out docs/browser/spatial-dynamics/ontology.json
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
