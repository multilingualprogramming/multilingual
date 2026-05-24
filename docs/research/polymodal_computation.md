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
Text is one of those authoring surfaces for polymodal programs, but it
is not the only one and it is not required to be the interchange format
between modalities.

## Compatibility principle

Polymodal computation must not break the existing textual Multilingual
language. The safe boundary is:

```text
text .multi
spatial edits
sonic capture
MIDI capture
3D edits
haptic / kinetic input
        |
        v
semantic-core-vN
        |
        v
text projection / WAT / Python / modality projections
```

The textual language keeps its parser, AST, language packs, Python
backend, WAT/WASM backend, and compatibility tests. Polymodal
computation is an additional semantic profile layered beside the
current language, not a replacement for source syntax.

This distinction is load-bearing:

- **Compatibility belongs to the textual language.** Existing `.multi`
  and `.ml` programs should continue to parse, transpile, execute, and
  compile as before.
- **Equivalence belongs to the semantic core.** A polymodal program is
  equivalent across surfaces only to the extent that each surface
  preserves the declared semantic facts of `semantic-core-vN`.
- **Text regeneration is optional.** A spatial or sonic capture should
  reconstruct the semantic core directly; generated text may be useful
  for inspection, teaching, or archival purposes, but it should not be
  the authority through which every modality must pass.

Not every Multilingual program needs to be polymodal. The project can
support a broad language and a stricter polymodal profile:

```text
Multilingual language
  includes ordinary textual programs
  includes Python/WAT-compatible programs
  includes polymodal seed programs
```

Only programs in the polymodal profile are required to satisfy
cross-modal equivalence. This protects existing source compatibility
while letting the research track evolve quickly.

## Semantic versioning of program identity

The semantic core must be versioned aggressively. A `semantic-core-v0`
manifest should always mean what it meant when it was emitted. If a
future `semantic-core-v1` adds explicit coupling, temporal ordering,
stable entity IDs, richer relation kinds, or perceptual capability
metadata, old manifests should be handled by explicit migration:

```text
semantic-core-v0 -> semantic-core-v1
```

The migration may enrich or annotate old programs, but it must not
silently reinterpret old fields. This gives the project two kinds of
stability at once: textual source compatibility for existing
Multilingual programs, and manifest compatibility for polymodal
programs.

As editing becomes bidirectional, entity identity should move from
index-only ordering toward stable IDs:

```json
{
  "id": "ent_7f3a",
  "index": 0,
  "opcode": 6,
  "intensity": 0.8,
  "signal": 0.4,
  "phase": 0.25,
  "channel": 2
}
```

Indexes remain useful for deterministic ordering and compact manifests.
Stable IDs preserve identity when a user drags, deletes, records,
inserts, groups, or reorders entities in a non-textual surface.

## Perceptual capability contracts

Every modality should declare what it preserves, what it loses, and
what it cannot disambiguate. Equivalence should be checked against that
contract rather than assumed.

```json
{
  "projection": "sonic-seed-v0",
  "preserves": ["opcode", "intensity", "phase", "channel"],
  "lossy": ["signal"],
  "ambiguous": ["diffuse/stabilize/resonate", "attract/repel"]
}
```

This makes room for several equivalence levels:

| Level | Meaning |
|---|---|
| Exact-equivalent | The modality can recover the declared semantic facts exactly. |
| Behavior-equivalent | The modality preserves behavior even if presentation details differ. |
| Lossy-equivalent | The modality preserves a documented subset and marks the rest as lost. |
| Ambiguous-by-design | The modality cannot distinguish some semantic identities and says so. |
| View-only | The modality renders the program but does not claim inverse recovery. |
| Non-invertible | The modality is useful as output, but not as an authoring surface. |

The sonic round-trip already follows this discipline: opcodes whose
`(role, waveform, envelope)` tuple is unique are invertible, while
shared signatures are excluded from the invertible subset instead of
pretending to be lossless. Future MIDI, spatial, volumetric, haptic,
and kinetic capture paths should make the same kind of declaration.

## The opcode ontology

A single ontology
([opcode_ontology.py](../_generated/multilingualprogramming/codegen/opcode_ontology.py))
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
[polymodal_equivalence_test.py](../_generated/tests/polymodal_equivalence_test.py)
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
  midi_capture.py         # inverse MIDI projection (Python)

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
  midi_capture.js                  # inverse projection (JS)
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
[polymodal_equivalence_test.py](../_generated/tests/polymodal_equivalence_test.py).
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

Future relation kinds should become first-class semantic facts rather
than projection heuristics:

- **Coupling.** Entity A modulates or depends on entity B.
- **Inhibition.** Entity A suppresses entity B when a threshold is met.
- **Temporal ordering.** Entity A precedes, triggers, or schedules
  entity B.
- **Synchronization.** Entities share phase, clock, pulse, or cadence.
- **Routing.** Signals move through explicit paths or channels.
- **Causality.** A relation records that one event or state transition
  produces another.

These relations should enter the semantic core through explicit
authoring surfaces or language syntax, not through hidden inference.
Once present in `semantic-core-vN`, every peer modality can decide how
to expose them: as spatial force, sonic modulation, MIDI routing,
volumetric structure, haptic resistance, or textual declarations.

## Sonic round-trip (current bidirectional path)

Sonic was the first modality to land a bidirectional path:

- **Python inverse** in
  [sonic_capture.py](../_generated/multilingualprogramming/codegen/sonic_capture.py)
  takes label-stripped `ObservedVoice` records (the fields a real audio
  analyzer could recover: role, waveform, envelope, frequency,
  amplitude, start offset, channel) and reconstructs a
  `semantic-core-v0` manifest.
- **JS inverse** in
  [sonic_capture.js](../browser/sonic-dynamics/sonic_capture.js)
  mirrors the Python module and fetches the shared
  [ontology.json](../browser/sonic-dynamics/ontology.json)
  sidecar so it cannot drift.
- **Microphone pipeline** in
  [microphone_capture.js](../browser/sonic-dynamics/microphone_capture.js)
  produces `ObservedVoice` records from real audio using vanilla DSP:
  spectral-flux onset detection, FFT peak picking for pitch,
  harmonic-ratio waveform classification, RMS-history envelope
  classification, snapping to the same pentatonic scale used by the
  forward projection.

The round-trip test in
[`SonicRoundTripTestSuite`](../_generated/tests/polymodal_equivalence_test.py)
asserts that the *invertible subset* of opcodes (those whose
`(role, waveform, envelope)` tuple is unique in the ontology) recovers
its semantic identity under
`core -> sonic -> observed -> captured-core`. Opcodes that share a
sonic signature (split/merge, attract/repel, diffuse/stabilize/resonate)
are explicitly excluded from the invertible set — ambiguous-by-design
rather than silently lossy.

## MIDI round-trip (current bidirectional path)

MIDI is the second modality with an inverse path. Its observation
surface is deliberately discrete: role, pitch, velocity, channel, start
offset, and index. The Python inverse in
[midi_capture.py](../_generated/multilingualprogramming/codegen/midi_capture.py)
and the JS inverse in
[midi_capture.js](../browser/midi-dynamics/midi_capture.js)
recover semantic identity from `(role, pitch)` using the shared
ontology.

MIDI capture is intentionally partial:

- `bus` events are silent routing markers and are not recoverable as
  authoring input.
- `program` events currently have zero base velocity, so intensity
  cannot be recovered.
- events clipped to MIDI velocity 127 are rejected because the original
  intensity may have exceeded the representable range.

The MIDI round-trip tests assert that the unclipped, invertible subset
recovers opcode, name, phase, channel, and approximate intensity under
`core -> MIDI -> observed -> captured-core`.

## Long-term authoring model

The long-term environment should be a live polymodal workspace rather
than a source editor with previews. A user should be able to edit the
same program through several peer surfaces:

- draw or move entities in 2D space,
- hear and modify the sonic projection,
- record or edit MIDI events,
- manipulate a volumetric scene,
- use touch, gesture, or haptic input,
- inspect the semantic core as a diagnostic view,
- optionally project the core back into textual Multilingual.

The shared state should be the semantic core:

```text
semantic-core-vN
  <-> spatial runtime
  <-> sonic runtime
  <-> MIDI runtime
  <-> volumetric runtime
  <-> haptic / kinetic runtimes
  <-> textual projection
```

This is different from a conventional IDE. The text surface is a peer
interface for programs that choose to expose one, not the sovereign
representation that every other modality must imitate.

## Research milestones

The next milestones should preserve compatibility while making the
polymodal claim stronger:

1. **Browser MIDI input wiring.** The Python/JS MIDI inverse exists;
   the runtime still needs Web MIDI In capture that feeds observed
   events into it.
2. **Stable identity.** Add optional entity IDs to the semantic core and
   preserve them through every projection.
3. **Richer capability enforcement.** Projection manifests now declare
   capability metadata; future tests should use those contracts to
   drive exact, lossy, and view-only round-trip expectations.
4. **Golden manifests.** Store versioned fixture manifests for the
   semantic core and every projection, then require old fixtures to load
   identically or migrate explicitly.
5. **Spatial authoring.** Let the 2D runtime edit a manifest and recover
   semantic-core identity without routing changes through generated
   text.
6. **Live synchronized runtime.** Keep spatial, sonic, MIDI, and
   semantic-core views synchronized as one program state changes.
7. **Explicit relation syntax.** Add coupling and temporal-ordering
   relations only when the source language or authoring surfaces can
   express them deliberately.
8. **Pattern recognition.** Recognize stable dynamic structures such as
   gates, memory loops, oscillator networks, membranes, routers,
   attractor basins, and feedback circuits as higher-level semantic
   patterns.

The strongest near-term proof is:

> Two independent authoring modalities can modify the same semantic
> core, and equivalence tests prove that the declared semantic identity
> survives.

## Potential applications

Polymodal computation has applications wherever computation needs to be
understood, authored, or controlled through more than one human sensory
or cognitive channel.

| Area | Why polymodal computation matters |
|---|---|
| Accessibility | Blind, deaf, motor-impaired, and neurodiverse programmers can use peer authoring surfaces instead of accessibility layers added after the fact. |
| Education | Learners can encounter computation as rhythm, movement, containment, propagation, resonance, and transformation before syntax. |
| Creative coding | One semantic program can become animation, sound, MIDI, spatial sculpture, or live performance state. |
| Scientific simulation | Diffusion, attraction, repulsion, stabilization, oscillation, propagation, and containment map naturally onto dynamic systems. |
| Robotics | Spatial, kinetic, and haptic modalities can express target seeking, obstacle avoidance, damping, gait, routing, and boundary constraints. |
| Music as computation | MIDI and sonic capture let executable structure be played, heard, recovered, and transformed. |
| Collaborative tools | Different collaborators can use different modalities while sharing one semantic program. |
| AI agent debugging | Goals, constraints, uncertainty, conflicts, tool calls, and plan propagation can become perceptible structures. |
| Digital twins | Industrial, building, transport, and distributed systems can be inspected as synchronized spatial, sonic, and semantic state. |

The project should avoid framing these as visualizations of ordinary
programs. The more interesting claim is that computation can have
multiple native perceptual forms while keeping one semantic identity.

## Open work

- **Browser MIDI input wiring.** The Python and JS inverse projections
  now exist; the browser runtime still needs a live Web MIDI In capture
  button and recovered-core panel.
- **Authoring surfaces inside the runtimes.** Every runtime is still
  fundamentally view-only (sonic has microphone capture but the spatial
  / linear / volumetric / MIDI runtimes do not yet edit the manifest).
- **Coupling and temporal-ordering relations.** Waiting for explicit
  source syntax.
- **Glyph-only authoring.** `.multi` still uses English-spelled
  primitive names. Once the polymodal split is real, replacing them
  with stable glyphs / numeric opcodes is incremental.
- **Compatibility profiles.** The textual language and the polymodal
  profile should remain distinct so ordinary `.multi` programs do not
  inherit cross-modal obligations.
- **Perceptual contract enforcement.** Projection metadata now marks
  lossy, ambiguous, and partial-inverse surfaces; tests should
  increasingly derive their expectations from those declarations.

## Design test

A prototype has drifted out of polymodal computation if any of the
following hold:

- A "primary" modality emerges that the others must be defined relative to.
- A new primitive is added in one modality without an ontology entry.
- A projection adds entities that have no counterpart in the semantic core.
- Cross-modal equivalence tests are weakened or skipped to ship a feature.
- A polymodal feature changes the behavior of ordinary textual programs
  outside the polymodal profile.
- A capture path routes through generated text as the only way to
  recover semantic identity.
- A lossy or ambiguous projection claims exact equivalence.
- A modality's hint vocabulary silently reuses names from another
  dimensionality (e.g., 1D glyphs reaching for 2D shape names),
  collapsing the distinction the peer projections are meant to preserve.

The standard is stricter than "multimedia support": every modality must
be a peer expression of the same program.
