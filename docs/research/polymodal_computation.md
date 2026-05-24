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
peer. No modality is primary; the 2D spatial demo, the 1D linear strip,
the 3D volumetric scene, the sonic WebAudio composition, and the MIDI
piano roll are all realizations of the same semantic core.

## Layered model

| Layer | Question it answers | Concrete artifact |
|---|---|---|
| Semantic core | What primitives, with what intensities and relations? | `semantic-core-v0` manifest. Modality-free. No coordinates. No frequencies. Now carries derived containment relations. |
| Modality projection | How is this realized in modality M? | `linear-seed-v0`, `spatial-seed-v0`, `volumetric-seed-v0`, `sonic-seed-v0`, `midi-seed-v0` — generated per-modality |
| Modality runtime | How does a perceiver experience it? | Canvas (linear, spatial, volumetric, MIDI), WebAudio (sonic) |
| Modality capture | How can authoring happen in this modality? | Inverse of projection — sonic captures landed first (Python + browser microphone), other modalities follow |

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
| Linear (1D) | `linear.glyph`, `linear.color` |
| Spatial (2D) | `spatial.shape`, `spatial.color` |
| Volumetric (3D) | `volumetric.primitive`, `volumetric.color` |
| Sonic (WebAudio) | `sonic.role`, `sonic.waveform`, `sonic.envelope` |
| MIDI (events) | `midi.role`, `midi.pitch`, `midi.velocity` |

Adding a new primitive is one row; adding a new modality is one new
hint group. Cross-modal coherence is enforced by tests, not convention.

The vocabularies are kept disjoint by design: linear glyphs do not
include 2D shape names ("ring", "diamond", "membrane"), volumetric
primitives do not reuse 1D or 2D names, and MIDI roles
(`note`, `drum`, `cc`, `program`, `bus`) form their own taxonomy.
Tests in
[polymodal_equivalence_test.py](../../tests/polymodal_equivalence_test.py)
enforce these separations so dimensionality and modality cannot be
silently conflated.

## What lives where

```text
multilingualprogramming/codegen/
  opcode_ontology.py      # the only source of opcode truth
  semantic_core.py        # build semantic-core-v0 manifests (modality-free);
                          # derives containment relations
  linear_manifest.py      # 1D linear projection   -> linear-seed-v0
  spatial_manifest.py     # 2D spatial projection  -> spatial-seed-v0
  volumetric_manifest.py  # 3D volumetric projection -> volumetric-seed-v0
  sonic_projection.py     # sonic projection        -> sonic-seed-v0
  midi_manifest.py        # MIDI projection         -> midi-seed-v0
  sonic_capture.py        # inverse sonic projection (Python)

docs/browser/spatial-dynamics/
  program.multi           # authored polymodal seed (canonical source)
  program.spatial.json    # generated 2D projection
  ontology.json           # generated ontology sidecar
  spatial_runtime.js      # Canvas 2D runtime
  index.html

docs/browser/linear-dynamics/    # 1D peer
  program.linear.json
  ontology.json
  linear_runtime.js              # Canvas 1D timeline
  index.html

docs/browser/volumetric-dynamics/  # 3D peer
  program.volumetric.json
  ontology.json
  volumetric_runtime.js            # Canvas with hand-rolled 3D projection
  index.html

docs/browser/sonic-dynamics/       # WebAudio peer with capture
  program.sonic.json
  ontology.json
  sonic_runtime.js                 # WebAudio forward + capture wiring
  sonic_capture.js                 # inverse projection (JS)
  microphone_capture.js            # mic -> ObservedVoice pipeline
  index.html

docs/browser/midi-dynamics/        # discrete-event peer
  program.midi.json
  ontology.json
  midi_runtime.js                  # piano-roll viz + Web MIDI Out
  index.html
```

## Building

```bash
multilingual polymodal-build  docs/browser/spatial-dynamics/program.multi \
  --out /tmp/program.semantic.json

multilingual linear-build     docs/browser/spatial-dynamics/program.multi \
  --out docs/browser/linear-dynamics/program.linear.json

multilingual spatial-build    docs/browser/spatial-dynamics/program.multi \
  --out docs/browser/spatial-dynamics/program.spatial.json

multilingual volumetric-build docs/browser/spatial-dynamics/program.multi \
  --out docs/browser/volumetric-dynamics/program.volumetric.json

multilingual sonic-build      docs/browser/spatial-dynamics/program.multi \
  --out docs/browser/sonic-dynamics/program.sonic.json

multilingual midi-build       docs/browser/spatial-dynamics/program.multi \
  --out docs/browser/midi-dynamics/program.midi.json

multilingual ontology-export  --out docs/browser/spatial-dynamics/ontology.json
```

The same `program.multi` flows into every projection. That is the
architectural claim.

## The cross-modal equivalence test

The load-bearing test of this architecture lives in
[polymodal_equivalence_test.py](../../tests/polymodal_equivalence_test.py).
It loads one semantic core, projects to all five peer manifests, and
asserts that:

- entity counts agree across every projection,
- opcode ordering agrees,
- intensity, phase, and channel are preserved by every projection
  (translated as needed: position for linear, z for volumetric,
  start_offset for MIDI, etc.),
- every projection's modality fields match the ontology's hints,
- structural relations derived at the semantic core flow through to
  every projection that exposes them.

If a future modality drops, renames, or reorders entities relative to
the core, this test fails. That is what prevents the modalities from
silently drifting apart as the project grows.

## Relations

The semantic core records structural relations between entities so the
peer projections share a single source of truth for structure (not just
for entity fields). Currently inferred:

- **Containment.** Each `contain`-opcode entity on channel C contains
  every non-`contain` entity on channel C. Multiple containers on the
  same channel produce overlapping containments. Lonely `contain`
  entities (no other entities on their channel) emit no relation —
  empty membranes are not load-bearing structure.

Coupling and temporal ordering are deferred until the source language
gains explicit syntactic surface for them: inferring those from raw
structure risks codifying arbitrary heuristics that become hard to
change.

## Sonic round-trip (current bidirectional path)

Sonic was the first modality to land a bidirectional path:

- **Python inverse** in
  [sonic_capture.py](../../multilingualprogramming/codegen/sonic_capture.py)
  takes label-stripped `ObservedVoice` records (the fields a real audio
  analyzer could recover: role, waveform, envelope, frequency,
  amplitude, start offset, channel) and reconstructs a
  `semantic-core-v0` manifest.
- **JS inverse** in
  [sonic_capture.js](../../docs/browser/sonic-dynamics/sonic_capture.js)
  mirrors the Python module and fetches the shared
  [ontology.json](../../docs/browser/sonic-dynamics/ontology.json)
  sidecar so it cannot drift.
- **Microphone pipeline** in
  [microphone_capture.js](../../docs/browser/sonic-dynamics/microphone_capture.js)
  produces `ObservedVoice` records from real audio using vanilla DSP:
  spectral-flux onset detection, FFT peak picking for pitch,
  harmonic-ratio waveform classification, RMS-history envelope
  classification, snapping to the same pentatonic scale used by the
  forward projection.

The round-trip test in
[`SonicRoundTripTestSuite`](../../tests/polymodal_equivalence_test.py)
asserts that the *invertible subset* of opcodes (those whose
`(role, waveform, envelope)` tuple is unique in the ontology) recovers
its semantic identity under
`core -> sonic -> observed -> captured-core`. Opcodes that share a
sonic signature (split/merge, attract/repel, diffuse/stabilize/resonate)
are explicitly excluded from the invertible set — ambiguous-by-design
rather than silently lossy.

## Open work

- **Bidirectional MIDI capture.** Web MIDI In can produce the same
  `MidiEvent`-shaped records that the forward projection emits; the
  inverse mirroring the sonic pattern is the natural next step.
- **Authoring surfaces inside the runtimes.** Every runtime is still
  fundamentally view-only (sonic has microphone capture but the spatial
  / linear / volumetric / MIDI runtimes do not yet edit the manifest).
- **Coupling and temporal-ordering relations.** Waiting for explicit
  source syntax.
- **Glyph-only authoring.** `.multi` still uses English-spelled
  primitive names. Once the polymodal split is real, replacing them
  with stable glyphs / numeric opcodes is incremental.

## Design test

A prototype has drifted out of polymodal computation if any of the
following hold:

- A "primary" modality emerges that the others must be defined relative to.
- A new primitive is added in one modality without an ontology entry.
- A projection adds entities that have no counterpart in the semantic core.
- Cross-modal equivalence tests are weakened or skipped to ship a feature.
- A modality's hint vocabulary silently reuses names from another
  dimensionality (e.g., 1D glyphs reaching for 2D shape names),
  collapsing the distinction the peer projections are meant to preserve.

The standard is stricter than "multimedia support": every modality must
be a peer expression of the same program.
