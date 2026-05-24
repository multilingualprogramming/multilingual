#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Capability metadata for polymodal projections.

Each projection declares which semantic fields it preserves directly,
which fields are derived or lossy, and whether it currently claims an
inverse authoring path. The metadata is intentionally descriptive: the
equivalence tests remain the enforcement layer.
"""

from __future__ import annotations

from typing import Any


def capability_contract(
    *,
    projection: str,
    preserves: list[str],
    derived: list[str] | None = None,
    lossy: list[str] | None = None,
    ambiguous: list[str] | None = None,
    inverse: str = "view-only",
) -> dict[str, Any]:
    """Return a manifest-friendly projection capability declaration."""
    return {
        "projection": projection,
        "preserves": list(preserves),
        "derived": list(derived or []),
        "lossy": list(lossy or []),
        "ambiguous": list(ambiguous or []),
        "inverse": inverse,
    }
