// SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Inverse sonic projection in the browser: observation -> semantic core.
//
// JS peer of multilingualprogramming/codegen/sonic_capture.py. Takes
// voices as they would be observed at the modality boundary (role,
// waveform, envelope, frequency, amplitude, start offset, channel --
// no opcode/name) and reconstructs a semantic-core-v0 manifest.
//
// The shared opcode ontology is fetched from ./ontology.json so this
// file and the Python inverse cannot drift apart. The parity is
// guarded by tests in tests/polymodal_equivalence_test.py.

const ONTOLOGY_KIND = "opcode-ontology-v0";
const CORE_KIND = "semantic-core-v0";

let ontologyPromise = null;

export function loadOntology(url = "./ontology.json") {
  if (!ontologyPromise) {
    ontologyPromise = fetch(url, { cache: "no-store" }).then((response) => {
      if (!response.ok) {
        throw new Error(`ontology.json ${response.status}`);
      }
      return response.json().then((data) => {
        if (data.kind !== ONTOLOGY_KIND || !Array.isArray(data.opcodes)) {
          throw new Error("invalid ontology manifest");
        }
        return data.opcodes;
      });
    });
  }
  return ontologyPromise;
}

export function _resetOntologyForTesting() {
  ontologyPromise = null;
}

function signatureOf(op) {
  return `${op.sonic.role}|${op.sonic.waveform}|${op.sonic.envelope}`;
}

export function invertibleOpcodes(opcodes) {
  const counts = new Map();
  for (const op of opcodes) {
    const sig = signatureOf(op);
    counts.set(sig, (counts.get(sig) || 0) + 1);
  }
  const invertible = new Set();
  for (const op of opcodes) {
    if (op.sonic.role === "bus") continue;
    if (counts.get(signatureOf(op)) !== 1) continue;
    invertible.add(op.code);
  }
  return invertible;
}

function opcodeFromObservation(opcodes, observed) {
  const sig = `${observed.role}|${observed.waveform}|${observed.envelope}`;
  const matches = opcodes.filter((op) => signatureOf(op) === sig);
  if (matches.length === 0) {
    throw new Error(
      `No ontology opcode matches observation ${sig} on voice index ${observed.index}`,
    );
  }
  if (matches.length > 1) {
    const names = matches.map((op) => op.name).join(", ");
    throw new Error(
      `Observation ${sig} on voice index ${observed.index} is ambiguous: matches ${names}.`,
    );
  }
  const op = matches[0];
  if (op.sonic.role === "bus") {
    throw new Error(
      `Voice index ${observed.index} resolves to bus opcode ${op.name}; intensity cannot be recovered.`,
    );
  }
  return op;
}

// Mirrors sonic_projection._voice_from_semantic_entity amplitude formula.
// Assumes signal == 0 (the seed-program convention); this is one equation
// in two unknowns and the inverse picks the documented branch.
function intensityFromAmplitude(op, amplitude) {
  if (op.sonic.role === "modulator") {
    return amplitude / 0.6;
  }
  return amplitude / 0.4;
}

export function observeVoice(voice) {
  return Object.freeze({
    index: Number(voice.index),
    role: String(voice.role),
    waveform: String(voice.waveform),
    envelope: String(voice.envelope),
    frequency_hz: Number(voice.frequency_hz),
    amplitude: Number(voice.amplitude),
    start_offset: Number(voice.start_offset),
    channel: Number(voice.channel),
  });
}

export function captureSemanticCore(
  observed,
  opcodes,
  { sourceLanguage = "en", sourcePath = "" } = {},
) {
  const entities = [];
  for (const voice of observed) {
    const op = opcodeFromObservation(opcodes, voice);
    const intensity = intensityFromAmplitude(op, voice.amplitude);
    entities.push({
      index: voice.index,
      opcode: op.code,
      name: op.name,
      intensity,
      signal: 0.0,
      phase: voice.start_offset,
      channel: voice.channel,
    });
  }
  return {
    kind: CORE_KIND,
    version: 0,
    source_language: sourceLanguage,
    source: sourcePath,
    ontology: opcodes.map(({ code, name }) => ({ code, name })),
    entities,
    relations: [],
  };
}
