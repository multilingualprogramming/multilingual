#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Author ``semantic-core-v1`` process programs in the Multilingual language.

A v0 polymodal program is a ``.multi`` source that defines a ``seed`` list,
which :mod:`multilingualprogramming.codegen.semantic_core` turns into a
modality-free core. This module is the v1 (process-calculus) analogue: a
``.multi`` source defines a ``process`` value -- the ⟨State, Topology, Rule,
Schedule⟩ tuple assembled with the process-core builtins (``lattice_topology``,
``rewrite_rule``, ``synchronous_schedule``, ``build_process_core``, ...) -- and
this module executes it and emits the manifest.

The point is that polymodal *dynamics* are authored in the multilingual
language, in any human-language pack, exactly like static structure already
was -- never as a Python script that imports
:mod:`multilingualprogramming.codegen.process_core` directly. The engine and
stepper still live solely in ``process_core``; this module only runs the
program and hands back the data structure it built.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from typing import Any

from multilingualprogramming.codegen import process_core
from multilingualprogramming.codegen.executor import ProgramExecutor
from multilingualprogramming.codegen.runtime_builtins import make_exec_globals

PROCESS_VARIABLE = "process"


def execute_process(
    source: str,
    language: str = "en",
    source_path: str = "",
) -> dict[str, Any]:
    """Execute Multilingual source and return its ``process`` core.

    The source must assign a ``semantic-core-v1`` manifest to a top-level
    ``process`` variable (typically via ``build_process_core``). The
    manifest's ``source`` field is set to ``source_path`` so a built program
    records where it came from, mirroring the v0 ``seed`` flow.
    """
    python_source = ProgramExecutor(
        language=language,
        check_semantics=False,
    ).transpile(source)
    namespace = make_exec_globals(language)

    with contextlib.redirect_stdout(io.StringIO()):
        # Process programs are trusted Multilingual programs compiled by this
        # package, exactly like v0 polymodal seeds.
        exec(  # pylint: disable=exec-used
            compile(python_source, source_path or "<process>", "exec"), namespace
        )

    if PROCESS_VARIABLE not in namespace:
        raise ValueError("Process program must define `process`")

    core = namespace[PROCESS_VARIABLE]
    if not isinstance(core, dict):
        raise ValueError("Process `process` must be a mapping")
    if core.get("kind") != process_core.CORE_KIND:
        raise ValueError(
            f"Process `process` must be a {process_core.CORE_KIND!r} core, "
            f"got kind {core.get('kind')!r}"
        )

    core = dict(core)
    core["source"] = source_path
    return core


def build_process_core_file(
    source_path: str | Path,
    output_path: str | Path,
    language: str = "en",
) -> dict[str, Any]:
    """Build and write a ``semantic-core-v1`` manifest to disk as JSON."""
    src = Path(source_path)
    out = Path(output_path)
    core = execute_process(
        src.read_text(encoding="utf-8"),
        language=language,
        source_path=str(src),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(core, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return core
