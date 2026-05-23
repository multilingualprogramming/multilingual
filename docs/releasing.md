# Releasing

This project publishes to PyPI via GitHub Actions trusted publishing.

## Preconditions

1. PyPI trusted publisher configured for this repository/workflow.
2. GitHub environment `pypi` exists and is allowed to run release jobs.
3. Branch protection requires CI checks listed in `CONTRIBUTING.md`.

## Release Checklist

1. Update `multilingualprogramming/version.py` with the new version.
2. Add release notes to `CHANGELOG.md` and `RELEASE.md` under a new version heading.
3. Review user-facing docs for stale version numbers, install extras, CLI flags, and backend claims.
4. Run local checks:
```bash
python3 -m multilingualprogramming --version
python3 -m multilingualprogramming smoke --all
python3 -m pytest -q
```
5. Build and validate release artifacts:
```bash
python3 -m build
python3 -m twine check dist/*
```
Current optional extras are:
- `wasm` — Wasmtime runtime
- `ai` — OpenAI, Anthropic, and Ollama providers
- `performance` — Wasmtime plus NumPy
- `all` — WASM, performance, and AI dependencies
6. Push changes to `main`.
7. Create and push a version tag:
```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```
8. Verify workflow `Release to PyPI` succeeds.
9. Confirm package availability on PyPI.

## Post-release

1. Create a GitHub release for tag `vX.Y.Z`.
2. Move changelog placeholders under `Unreleased` as needed.
