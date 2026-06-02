#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Example: Game of Life as a ``semantic-core-v1`` program.

Conway's Game of
Life -- and the whole family of outer-totalistic cellular automata -- is
nothing but a filling of the modality-free ⟨State, Topology, Rule,
Schedule⟩ tuple defined in
``multilingualprogramming.codegen.process_core``. The core engine knows
nothing about Life; everything specific to it lives here, as data:

- **State**    -- one ``{"alive": 0|1}`` field per lattice cell.
- **Topology** -- a 2D lattice with the Moore-8 neighbourhood.
- **Rule**     -- a rewrite rule whose clauses encode birth/survival.
- **Schedule** -- synchronous (every cell updates from the previous frame).

``life_like_rule`` is a small standard-library helper that compiles a
``B<birth>/S<survival>`` specification into generic rewrite clauses, so the
*same* core stepper runs Conway's Life (``B3/S23``), Seeds (``B2/S``),
HighLife (``B36/S23``), and so on with no new engine code -- which is the
universality claim ``semantic-core-v1`` exists to make.
"""

from __future__ import annotations

from typing import Any, Iterable

from multilingualprogramming.codegen import process_core

ALIVE_FIELD = "alive"


def life_like_rule(
    birth: Iterable[int] = (3,),
    survival: Iterable[int] = (2, 3),
    field: str = ALIVE_FIELD,
) -> dict[str, Any]:
    """Compile a ``B<birth>/S<survival>`` automaton into rewrite clauses.

    A dead cell becomes alive when its live-neighbour count is in
    ``birth``; a live cell stays alive when its count is in ``survival``;
    otherwise the produced state is dead. Conway's Game of Life is
    ``life_like_rule(birth=(3,), survival=(2, 3))``.
    """
    birth = sorted({int(n) for n in birth})
    survival = sorted({int(n) for n in survival})
    return process_core.rewrite_rule(
        clauses=[
            {
                "match": {
                    "self": {field: 0},
                    "neighbor_count": [{"field": field, "value": 1, "in": birth}],
                },
                "produce": {field: 1},
            },
            {
                "match": {
                    "self": {field: 1},
                    "neighbor_count": [{"field": field, "value": 1, "in": survival}],
                },
                "produce": {field: 1},
            },
        ],
        default={field: 0},
    )


def cellular_lattice(
    width: int,
    height: int,
    live_cells: Iterable[tuple[int, int]],
    rule: dict[str, Any],
    wrap: bool = True,
    field: str = ALIVE_FIELD,
    source_path: str = "",
) -> dict[str, Any]:
    """Assemble a synchronous lattice program from a rule and live cells."""
    live = {(int(x), int(y)) for x, y in live_cells}
    for x, y in live:
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(f"live cell ({x}, {y}) is outside the lattice")
    loci = [
        {"locus": [x, y], field: 1 if (x, y) in live else 0}
        for y in range(height)
        for x in range(width)
    ]
    return process_core.build_process_core(
        state={"loci": loci},
        topology=process_core.lattice_topology(width, height, wrap=wrap),
        rule=rule,
        schedule=process_core.synchronous_schedule(),
        source_path=source_path,
    )


def game_of_life(
    width: int,
    height: int,
    live_cells: Iterable[tuple[int, int]],
    wrap: bool = True,
    source_path: str = "",
) -> dict[str, Any]:
    """Build a Conway's Game of Life program as a ``semantic-core-v1`` manifest."""
    return cellular_lattice(
        width,
        height,
        live_cells,
        rule=life_like_rule(birth=(3,), survival=(2, 3)),
        wrap=wrap,
        source_path=source_path,
    )


# A handful of canonical Life patterns, as live-cell coordinate lists.
BLINKER = [(1, 1), (2, 1), (3, 1)]
BLOCK = [(1, 1), (2, 1), (1, 2), (2, 2)]
GLIDER = [(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)]


def _render(core: dict[str, Any]) -> str:
    """Render a lattice frame as text for the demo below."""
    topology = core["topology"]
    width, height = topology["width"], topology["height"]
    live = set(process_core.active_cells(core, ALIVE_FIELD))
    rows = [
        "".join("#" if (x, y) in live else "." for x in range(width))
        for y in range(height)
    ]
    return "\n".join(rows)


def _demo() -> None:
    """Run a glider for a few generations and print each frame."""
    core = game_of_life(8, 8, GLIDER, wrap=True)
    for generation, frame in enumerate(process_core.run(core, 4)):
        print(f"generation {generation}:")
        print(_render(frame))
        print()


if __name__ == "__main__":
    _demo()
