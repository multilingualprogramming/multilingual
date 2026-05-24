# Polymodal Computation

This research track extends the post-textual direction of
[Fixed-Semantic Spatial Computation](fixed_semantic_spatial_computation.md)
into a **modality-agnostic** computational substrate.

The earlier prototype proved that 2D space can be a native computational
surface. Polymodal computation asks the next question:

> If 2D space can host a non-textual program, can the *same* program be
> rendered, perceived, and edited in any modality — visual, sonic,
> haptic, kinetic, spatial-3D — without losing its identity?

## Why "polymodal" and not "multimodal"

The repository already uses **multimodal** for image/audio/video payloads
flowing through AI calls. That meaning is about *data types*. Polymodal
computation is about *program identity*: one program, many peer
perceptual realizations.

The distinction matters because every modality in this architecture is a
peer. No modality is primary; the spatial 2D demo is one realization of
the same semantic core that the sonic WebAudio demo realizes differently.

## Layered model

| Layer | Question it answers | Concrete artifact |
|---|---|---|
| Semantic core | What primitives, with what intensities and relations? | `semantic-core-v0` manifest. Modality-free. No coordinates. No frequencies. |
| Modality projection | How is this realized in modality M? | `spatial-seed-v0`, `sonic-seed-v0`, ... — generated per-modality |
| Modality runtime | How does a perceiver experience it? | Canvas (2D), WebAudio (sonic), and others to follow |
| Modality capture (future) | How can authoring happen in this modality? | Inverse of projection — every runtime is intended to be bidirectional |

The semantic core is the canonical program. Every modality is a peer.

## The opcode ontology

A single ontology
([opcode_ontology.py](../../multilingualprogramming/codegen/opcode_ontology.py))
is the source of truth for every primitive. Each opcode entry carries a
stable integer code, a canonical name, and per-modality realization
hints:

| Layer | Field |
|---|---|
| Semantic | `code`, `name`, `description` |
| Spatial | `spatial.shape`, `spatial.color` |
| Sonic | `sonic.role`, `sonic.waveform`, `sonic.envelope` |

Adding a new primitive is one row; adding a new modality is one new
hint group. Cross-modal coherence is enforced by tests, not convention.

## What lives where

```text
multilingualprogramming/codegen/
  opcode_ontology.py     # the only source of opcode truth
  semantic_core.py       # build semantic-core-v0 manifests (modality-free)
  spatial_manifest.py    # spatial projection -> spatial-seed-v0
  sonic_projection.py    # sonic projection   -> sonic-seed-v0

docs/browser/spatial-dynamics/
  program.multi          # authored polymodal seed
  program.spatial.json   # generated spatial projection
  spatial_runtime.js     # Canvas runtime
  index.html

docs/browser/sonic-dynamics/
  program.sonic.json     # generated sonic projection of the same seed
  sonic_runtime.js       # WebAudio runtime
  index.html
```

## Building

```bash
multilingual spatial-build  docs/browser/spatial-dynamics/program.multi \
  --out docs/browser/spatial-dynamics/program.spatial.json

multilingual sonic-build    docs/browser/spatial-dynamics/program.multi \
  --out docs/browser/sonic-dynamics/program.sonic.json

multilingual polymodal-build docs/browser/spatial-dynamics/program.multi \
  --out /tmp/program.semantic.json
```

The same `program.multi` flows into every projection. That is the
architectural claim.

## The cross-modal equivalence test

The load-bearing test of this architecture lives in
[polymodal_equivalence_test.py](../../tests/polymodal_equivalence_test.py).
It loads one semantic core, projects to both the spatial and sonic
manifests, and asserts that:

- entity counts agree,
- opcode ordering agrees,
- intensity, phase, and channel are preserved by every projection,
- every projection's modality fields match the ontology's hints.

If a future modality drops, renames, or reorders entities relative to
the core, this test fails. That is what prevents the modalities from
silently drifting apart as the project grows.

## What this slice does not yet do

- **Bidirectional runtimes.** Each runtime is currently render-only;
  authoring still happens in `program.multi`. Capture (modality input
  back into the semantic core) is the next architectural step.
- **Relation richness.** The semantic core ships with an empty
  `relations` list. Containment, coupling, and pattern relations are
  follow-ups that benefit from a dedicated authoring surface, not from
  geometric inference over the existing seed.
- **Glyph-only authoring.** `.multi` still uses English-spelled
  primitive names. Once the polymodal split is real, replacing them
  with stable glyphs / numeric opcodes is incremental.
- **WASM-compiled per-modality stepping laws.** Premature until two or
  three modalities exist and their physics stabilize.

## Design test

A prototype has drifted out of polymodal computation if any of the
following hold:

- A "primary" modality emerges that the others must be defined relative to.
- A new primitive is added in one modality without an ontology entry.
- A projection adds entities that have no counterpart in the semantic core.
- Cross-modal equivalence tests are weakened or skipped to ship a feature.

The standard is stricter than "multimedia support": every modality must
be a peer expression of the same program.
