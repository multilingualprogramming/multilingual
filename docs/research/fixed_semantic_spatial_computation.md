# Fixed-Semantic Spatial Computation

This research track explores a post-textual computational system for the
Multilingual Programming project. It is not a block language, flowchart system,
node editor, graphical wrapper around syntax, or natural-language prompting
interface.

The goal is a fixed-semantic, purely 2D computational environment where visual
space is the program and computation emerges from dynamic spatial interactions.

## Non-Goals

- No textual source syntax.
- No keywords.
- No identifiers.
- No prompts.
- No human-language dependency.
- No VR, AR, or 3D interaction.
- No boxes-and-arrows representation of textual programming.

## Core Claim

Multilingual currently reduces dependence on one human language by mapping many
language surfaces into shared semantics. This research direction asks a deeper
question:

> Can 2D visual space possess native computational primitives that are
> fundamentally different from textual programming abstractions?

The proposed answer is not to draw traditional programs. The proposed answer is
to define a visual-spatial substrate where fixed entities interact through
stable laws.

## Primitive Ontology

The first prototype uses fixed behavior opcodes:

| Opcode | Behavior | Meaning |
|---:|---|---|
| 1 | Emit | Produce signal over time |
| 2 | Diffuse | Equalize signal with local neighbors |
| 3 | Attract | Pull nearby entities through spatial proximity |
| 4 | Repel | Push nearby entities away |
| 5 | Stabilize | Dampen transient activation |
| 6 | Oscillate | Produce periodic signal |
| 7 | Transform | Convert nearby signal into local signal |
| 8 | Resonate | Amplify through phase alignment |
| 9 | Split | Divide activation into propagating entities |
| 10 | Merge | Combine nearby activations |
| 11 | Contain | Create a local membrane or boundary |
| 12 | Propagate | Move activation through space |

These primitives are behavioral laws, not symbolic categories. A visual element
does not stand for a variable, function, loop, or conditional. It behaves.

In Multilingual source, these behaviors are exposed as runtime primitives:

```text
emit()
diffuse()
attract()
repel()
stabilize()
oscillate()
transform()
resonate()
split()
merge()
contain()
propagate()
spatial_entity(...)
spatial_seed(...)
```

This is still an early bridge. The browser runtime animates the laws, while the
`.multi` file declares the fixed-semantic seed using Multilingual primitives.

## Spatial Semantics

Computation arises from:

- position
- distance
- containment
- local neighborhoods
- movement
- signal intensity
- oscillation phase
- boundary crossing
- activation propagation

The interface is not a source editor with a separate runtime. The interface is
the runtime state. The program is the evolving 2D structure.

## Prototype Boundary

The current implementation begins with a Multilingual seed program, a generated
JSON manifest, and a browser-native Canvas workspace:

```text
docs/browser/spatial-dynamics/
  index.html
  program.multi
  program.spatial.json
  spatial_runtime.js

multilingualprogramming/codegen/
  spatial_manifest.py
```

It intentionally avoids textual source fields such as names, identifiers,
labels, keywords, and prompts inside the visual workspace. The semantic identity
of each primitive is its fixed opcode and behavior law.

The browser workspace is the preferred prototype direction. `program.multi` is
the authored Multilingual seed artifact. `program.spatial.json` is the generated
manifest consumed by the Canvas runtime. `spatial_runtime.js` is the browser
host that animates the fixed 2D laws. The Python code is limited to the existing
compiler/CLI boundary that turns Multilingual source into a static manifest.

Build the manifest with:

```bash
multilingual spatial-build docs/browser/spatial-dynamics/program.multi \
  --out docs/browser/spatial-dynamics/program.spatial.json
```

## Relationship To The Existing Compiler

This track should not be forced into the textual AST too early.

The near-term architecture is:

```text
multilingual textual source
        -> semantic core
        -> Python / WAT / WASM

2D spatial dynamics
        -> spatial runtime
        -> optional semantic projection later
```

In the long term, stable spatial patterns may project into Core IR or compile to
WASM. But the research kernel must first prove that spatial behavior can be a
native computational grammar rather than a visualization of textual constructs.

## Early Research Milestones

1. Define the fixed primitive alphabet and preserve opcode stability.
2. Build deterministic 2D stepping rules for primitive interaction.
3. Demonstrate memory-like stabilization, gating, propagation, splitting, and
   merging without textual variables or control flow.
4. Add serialization for unlabeled spatial worlds.
5. Explore browser execution with Canvas and WebAssembly.
6. Study which spatial patterns support abstraction, reuse, and hierarchy.

## Design Test

A prototype has drifted back into traditional visual programming if it needs
boxes labeled with programming concepts, arrows representing textual control
flow, or generated source code to explain its meaning.

The standard is stricter:

> Users should shape dynamic systems, not assemble visualized instructions.
