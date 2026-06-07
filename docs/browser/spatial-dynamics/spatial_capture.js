// SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Inverse spatial projection in the browser: observation -> semantic core.
//
// JS peer of multilingualprogramming/codegen/spatial_capture.py. Takes
// 2D marks as they would be observed at the spatial authoring boundary
// (shape, color, plus widget-exposed semantic fields -- no opcode/name)
// and reconstructs a semantic-core-v0 manifest. The runtime uses this
// to satisfy the "capture path must not route through generated text"
// clause of the polymodal compatibility principle.

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
  return `${op.spatial.shape}|${op.spatial.color}`;
}

export function invertibleOpcodes(opcodes) {
  const counts = new Map();
  for (const op of opcodes) {
    const sig = signatureOf(op);
    counts.set(sig, (counts.get(sig) || 0) + 1);
  }
  const invertible = new Set();
  for (const op of opcodes) {
    if (counts.get(signatureOf(op)) !== 1) continue;
    invertible.add(op.code);
  }
  return invertible;
}

function opcodeFromObservation(opcodes, observed) {
  const sig = `${observed.shape}|${observed.color}`;
  const matches = opcodes.filter((op) => signatureOf(op) === sig);
  if (matches.length === 0) {
    throw new Error(
      `No ontology opcode matches spatial observation ${sig} on mark index ${observed.index}`,
    );
  }
  if (matches.length > 1) {
    const names = matches.map((op) => op.name).join(", ");
    throw new Error(
      `Spatial observation ${sig} on mark index ${observed.index} is ambiguous: matches ${names}.`,
    );
  }
  return matches[0];
}

export function observeMark(entity) {
  return Object.freeze({
    index: Number(entity.index),
    shape: String(entity.shape),
    color: String(entity.color),
    intensity: Number(entity.intensity),
    signal: Number(entity.signal),
    phase: Number(entity.phase),
    channel: Number(entity.channel),
    id: entity.id != null ? String(entity.id) : null,
  });
}

// Mirrors semantic_core.stable_entity_id: SHA-256 of `source_path|index`,
// keep the first 8 hex chars, prefix with "ent_". Used only when an
// observed mark has no id (a freshly authored entity).
async function stableEntityId(sourcePath, index) {
  const data = new TextEncoder().encode(`${sourcePath}|${index}`);
  const digest = await crypto.subtle.digest("SHA-256", data);
  const bytes = new Uint8Array(digest);
  let hex = "";
  for (let i = 0; i < 4; i += 1) {
    hex += bytes[i].toString(16).padStart(2, "0");
  }
  return `ent_${hex}`;
}

export async function captureSemanticCore(
  observed,
  opcodes,
  { sourceLanguage = "en", sourcePath = "" } = {},
) {
  const entities = [];
  for (const mark of observed) {
    const op = opcodeFromObservation(opcodes, mark);
    const entityId = mark.id || (await stableEntityId(sourcePath, mark.index));
    entities.push({
      id: entityId,
      index: mark.index,
      opcode: op.code,
      name: op.name,
      intensity: mark.intensity,
      signal: mark.signal,
      phase: mark.phase,
      channel: mark.channel,
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
