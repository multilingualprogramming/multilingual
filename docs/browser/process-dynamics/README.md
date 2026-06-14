# Process Dynamics — semantic-core-v1 browser demos

Five browser pages, each animating one modality-free
⟨State, Topology, Rule, Schedule⟩ program. Every page is driven by the **one
shared stepper** ([`process_core.js`](process_core.js), a faithful port of
`multilingualprogramming/codegen/process_core.py`) and projects the same
trajectory into a canvas **and** sound at once. The status line shows the
program's expressiveness tier, read straight from the manifest's axes.

| Page | Axis it exercises | Tier |
|------|-------------------|------|
| [index.html](index.html) — Game of Life | synchronous lattice rewriting | 2 |
| [lsystem.html](lsystem.html) — Lindenmayer algae | generative sequence rewriting | 3 |
| [ecosystem.html](ecosystem.html) — cyclic-dominance ecology | asynchronous multi-state field | 1 |
| [graph.html](graph.html) — SIR network contagion | graph topology | 4 |
| [diffusion.html](diffusion.html) — heat equation | continuous-time rate rule | 1 |
| [gray_scott.html](gray_scott.html) — Gray-Scott reaction-diffusion | nonlinear continuous rate rule (`products`) | 1 |
| [eden.html](eden.html) — Eden growth | stochastic synchronous rewriting (`chance`) | 2 |

Each `program.*.v1.json` is generated from the matching program in
[`examples/`](../../../examples) (`*.multi`) via the build CLI; they are checked
in so the pages need no build step.

## Run the demos

These are ES-module pages that `fetch()` their manifest, so they must be served
over HTTP (opening the file directly will not work). From the repository root:

```sh
python3 -m http.server 8000 --directory docs/browser
```

Then open <http://localhost:8000/> and click **Open Process Dynamics**, or jump
straight to a page, e.g. <http://localhost:8000/process-dynamics/diffusion.html>.
Once on any page, the nav strip at the top hops between all five. Click
**Sound: off** to toggle audio (browsers require a click before playing audio).

## Test them

The *logic* of every page is covered by the automated suite — you do not need a
browser to know the engine is correct. From the repository root:

```sh
python3 -m pytest tests/process_core_js_test.py
```

This runs `process_core.js` **under Node** and asserts, for every demo, that:

- its checked-in manifest still matches a fresh build of the `.multi` program
  (no drift), and
- its trajectory is byte-identical to the Python engine's, frame for frame
  (the diffusion page is checked float-for-float), and
- the page loads its runtime as a module and the runtime imports the one shared
  stepper (no page rolls its own).

So a green suite means every page's data and engine path is verified; serving
the pages is only to *see and hear* the result.
