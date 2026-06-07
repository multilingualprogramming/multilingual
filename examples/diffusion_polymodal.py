#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Example: heat diffusion as a ``semantic-core-v1`` continuous-time program.

Game of Life, the L-system and the cyclic ecology are all *discrete* rewriting:
a cell's next state is chosen from a finite set by a pattern match. Diffusion is
the first example on the **continuous** axis -- there is no "match", only a rate
of change integrated over time. It is, like the others, nothing but a filling of
the modality-free ⟨State, Topology, Rule, Schedule⟩ tuple in
``multilingualprogramming.codegen.process_core``; the core engine knows no
physics. What it exercises that the others do not:

- **State**    -- a continuous scalar ``{"u": value}`` per cell (a real field,
  not a boolean or a small integer).
- **Topology** -- a 2D lattice with the von-Neumann-4 neighbourhood (the
  standard discrete Laplacian stencil).
- **Rule**     -- a *rate* rule, not a rewrite: ``du/dt = D * (mean_nbr(u) - u)``
  expressed as the data ``self={"u": -D}, neighbor_mean={"u": D}``.
- **Schedule** -- *continuous-dt*: one explicit-Euler step ``u += dt * du/dt``
  from the previous frame.

On a toroidal lattice the mean-based stencil conserves total ``u`` exactly while
relaxing every bump toward the average -- a hot spot spreads and fades, mass
preserved. The *same* core stepper that runs Conway's Life integrates this
field with no new engine code, on the continuous-time axis ``semantic-core-v1``
was built to reach (Tier 1, fixed-population continuous dynamics).
"""

from __future__ import annotations

from typing import Any

from multilingualprogramming.codegen import process_core

FIELD = "u"


def diffusion_rule(coefficient: float = 0.2, field: str = FIELD) -> dict[str, Any]:
    """Compile the heat equation into a rate rule.

    ``du/dt = D * (mean_nbr(u) - u)`` is ``D * mean_nbr(u) - D * u``: a
    ``self`` coefficient of ``-D`` on the cell's own value and a
    ``neighbor_mean`` coefficient of ``+D`` on the mean of its neighbours. No
    system is named in the engine; the diffusion coefficient lives here as data.
    """
    return process_core.rate_rule(
        {field: {"self": {field: -coefficient}, "neighbor_mean": {field: coefficient}}}
    )


def diffusion_field(
    width: int,
    height: int,
    coefficient: float = 0.2,
    dt: float = 1.0,
    field: str = FIELD,
    source_path: str = "",
) -> dict[str, Any]:
    """Assemble a continuous-time diffusion field on a toroidal lattice.

    The lattice is fully populated (fixed population): every cell exists for all
    time and only its continuous value moves. A single hot cell at the centre
    (value ``1.0``) seeds a bump that spreads while total mass is conserved.
    Cells are laid out column by column (``x`` outer, ``y`` inner) to match the
    ``.multi`` authoring, and the centre uses integer division so the seed lands
    on a lattice cell.
    """
    cx = width // 2
    cy = height // 2
    loci = [
        {"locus": [x, y], field: 1.0 if x == cx and y == cy else 0.0}
        for x in range(width)
        for y in range(height)
    ]
    return process_core.build_process_core(
        state={"loci": loci},
        topology=process_core.lattice_topology(
            width, height, True, process_core.NEIGHBORHOOD_VONNEUMANN4
        ),
        rule=diffusion_rule(coefficient, field),
        schedule=process_core.continuous_schedule(dt),
        source_path=source_path,
    )


def _render(core: dict[str, Any], width: int, height: int) -> str:
    """Render a field frame as text (a glyph ramp by value) for the demo."""
    ramp = " .:-=+*#%@"
    by_cell = {(x, y): v for x, y, v in process_core.field_cells(core, FIELD)}
    peak = max((v for v in by_cell.values()), default=0.0) or 1.0
    rows = [
        "".join(
            ramp[min(len(ramp) - 1, int(by_cell.get((x, y), 0.0) / peak * (len(ramp) - 1)))]
            for x in range(width)
        )
        for y in range(height)
    ]
    return "\n".join(rows)


def _demo() -> None:
    """Run a small diffusion field for a few ticks and print each frame."""
    width = height = 11
    core = diffusion_field(width, height)
    for tick, frame in enumerate(process_core.run(core, 6)):
        mass = sum(v for _, _, v in process_core.field_cells(frame, FIELD))
        print(f"tick {tick} (mass {mass:.4f}):")
        print(_render(frame, width, height))
        print()


if __name__ == "__main__":
    _demo()
