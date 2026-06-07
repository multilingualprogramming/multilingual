#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Example: a cyclic-dominance ecosystem as a ``semantic-core-v1`` program.

The spatial "rock-paper-scissors" ecology -- and the wider family of cyclic
cellular automata / excitable-media models -- is, like Game of Life and the
L-system, nothing but a filling of the modality-free ⟨State, Topology, Rule,
Schedule⟩ tuple in ``multilingualprogramming.codegen.process_core``. The core
engine knows no ecology; everything specific lives here, as data. What it adds
over Game of Life are the two axes Life does not exercise:

- **State**    -- a *heterogeneous* ``{"species": k}`` per cell (a multi-valued
  field, not a boolean mask).
- **Topology** -- a 2D lattice with the Moore-8 neighbourhood.
- **Rule**     -- a rewrite rule whose clauses encode cyclic invasion: species
  ``k`` is overrun by ``(k + 1) mod n`` when enough neighbours already are it.
- **Schedule** -- *asynchronous* (cells update in sequence, each seeing the
  neighbours that already moved this tick).

``cyclic_dominance_rule`` compiles an ``n``-species cycle with an invasion
``threshold`` into generic rewrite clauses, so the *same* core stepper that runs
Conway's Life runs this ecology with no new engine code -- the universality
claim ``semantic-core-v1`` exists to make, now on the asynchronous /
multi-state axis.
"""

from __future__ import annotations

from typing import Any

from multilingualprogramming.codegen import process_core

SPECIES_FIELD = "species"


def cyclic_dominance_rule(
    species_count: int = 3,
    threshold: int = 3,
    field: str = SPECIES_FIELD,
) -> dict[str, Any]:
    """Compile an ``n``-species cyclic-invasion automaton into rewrite clauses.

    A cell of species ``k`` is taken over by species ``(k + 1) mod n`` when at
    least ``threshold`` of its eight neighbours are that successor; a cell that
    meets no threshold matches no clause and is left unchanged (the rule has no
    ``default``, so identity-on-no-match keeps it put). With three species this
    is the classic spatial rock-paper-scissors ecology.
    """
    if species_count < 2:
        raise ValueError("a cycle needs at least two species")
    enough = list(range(threshold, 9))
    clauses = [
        {
            "match": {
                "self": {field: k},
                "neighbor_count": [
                    {"field": field, "value": (k + 1) % species_count, "in": enough}
                ],
            },
            "produce": {field: (k + 1) % species_count},
        }
        for k in range(species_count)
    ]
    return process_core.rewrite_rule(clauses=clauses, default=None)


def cyclic_dominance(
    width: int,
    height: int,
    species_count: int = 3,
    threshold: int = 3,
    wrap: bool = True,
    field: str = SPECIES_FIELD,
    source_path: str = "",
) -> dict[str, Any]:
    """Assemble an asynchronous cyclic-dominance ecology on a lattice.

    The lattice is fully populated (fixed population): every cell exists for
    all time and only its species changes. The seed is a smooth diagonal mix of
    the species so invasion fronts form at once. Cells are laid out column by
    column (``x`` outer, ``y`` inner) to match the ``.multi`` authoring.
    """
    loci = [
        {"locus": [x, y], field: (x + y) % species_count}
        for x in range(width)
        for y in range(height)
    ]
    return process_core.build_process_core(
        state={"loci": loci},
        topology=process_core.lattice_topology(width, height, wrap=wrap),
        rule=cyclic_dominance_rule(species_count, threshold, field),
        schedule=process_core.asynchronous_schedule(),
        source_path=source_path,
    )


def _render(core: dict[str, Any], width: int, height: int) -> str:
    """Render a field frame as text (one glyph per species) for the demo."""
    glyphs = ".oO0#@"
    by_cell = {(x, y): v for x, y, v in process_core.field_cells(core, SPECIES_FIELD)}
    rows = [
        "".join(glyphs[by_cell.get((x, y), 0) % len(glyphs)] for x in range(width))
        for y in range(height)
    ]
    return "\n".join(rows)


def _demo() -> None:
    """Run a small ecology for a few ticks and print each frame."""
    width = height = 12
    core = cyclic_dominance(width, height)
    for tick, frame in enumerate(process_core.run(core, 4)):
        print(f"tick {tick}:")
        print(_render(frame, width, height))
        print()


if __name__ == "__main__":
    _demo()
