# Releasing to PyPI

The package is published as
[`my-better-isabelle-prover`](https://pypi.org/project/my-better-isabelle-prover/).
There is no CI: a release is built and uploaded **by hand** from a clean checkout.

> [!IMPORTANT]
> A PyPI version number can be used only once. A wrong file uploaded under
> `X.Y.Z` cannot be replaced — only yanked, and the fix must go out as a new
> version. Everything below happens *before* `twine upload`, on purpose.

## Prerequisites

```bash
pip install build twine
```

Uploading needs a PyPI API token. There is no `~/.pypirc` on the development
machine — the token lives in `~/secret.sh` (untracked, outside the repository),
which exports `TWINE_PASSWORD`:

```bash
source ~/secret.sh                    # sets TWINE_PASSWORD (also PYPI_API_KEY, UV_PUBLISH_TOKEN)
export TWINE_USERNAME=__token__       # NOT set by secret.sh — twine needs it for a token upload
```

Do this in the same shell as the upload. Note the repository's own `./secret.sh`
is a *different* file (LLM and R2 keys) and holds no PyPI credentials.

## Version numbering

The version lives in **two** files and they must agree:

| File | What it feeds |
|------|---------------|
| `pyproject.toml` (`version = `) | the distribution metadata — what PyPI sees |
| `my_better_isabelle_prover/__init__.py` (`__version__ = `) | what `import my_better_isabelle_prover` reports |

Nothing reads `__version__` at runtime, so a mismatch breaks no test and shows up
only after users have the wrong number — check both. (This is not hypothetical:
0.3.0's bump landed in a feature commit that touched `pyproject.toml` alone,
leaving `__init__.py` behind at 0.2.0.)

While the project is `0.x`, a **breaking change bumps the MINOR** — including
behavioural breaks, not just API ones. Making `patch` apply only the `user`
category by default (it used to apply everything) is what made 0.3.0 a minor
rather than a patch release.

## Procedure

```bash
# 1. Bump both version files, then commit and push. The commit is named after the
#    release, and the tree must be clean and in sync with origin/main before it.
git commit -am "Release X.Y.Z"
git push origin main

# 2. Tag the exact commit that will be built.
git tag -a vX.Y.Z -m "Release X.Y.Z"
git push origin vX.Y.Z

# 3. Build from a clean tree — stale build/ and *.egg-info/ directories are what
#    make a wheel ship yesterday's files.
rm -rf dist build my_better_isabelle_prover.egg-info
python -m build
twine check dist/*

# 4. Inspect the wheel before it becomes permanent (see the checklist below).
python -m zipfile -l dist/my_better_isabelle_prover-X.Y.Z-py3-none-any.whl

# 5. Upload ONLY this version. `dist/` also holds every previous release's
#    artifacts; `twine upload dist/*` would try to re-upload them, PyPI would
#    reject the duplicates with a 400, and the whole command aborts.
source ~/secret.sh                    # TWINE_PASSWORD
export TWINE_USERNAME=__token__
twine upload dist/my_better_isabelle_prover-X.Y.Z*

# 6. Verify from PyPI, not from the working tree (see the trap below).
python3 -m venv /tmp/verify && env -u PYTHONPATH /tmp/verify/bin/pip install \
    "my-better-isabelle-prover==X.Y.Z"
env -u PYTHONPATH /tmp/verify/bin/my-better-isabelle status
```

## What to check in the wheel

The patches are **package data**, not code, so they are included by the globs in
`pyproject.toml`'s `[tool.setuptools.package-data]` — and anything the globs miss
is dropped silently. A wheel that imports fine can still be useless because it
carries no patches. Before uploading, confirm the listing contains:

- every `patches/<version>/<feature>/*.patch` for the versions being shipped,
- `patches/categories.toml` — without it *every* command exits `3`,
- `AGENTS.md` (a symlink in the source tree; the build inlines its content), which
  the `help` command prints.

When adding a new *kind* of file under `patches/`, extend the `package-data` list
in the same commit. `order.txt` (documented in [develop.md](develop.md)) is **not
covered by the current globs** — the day a version needs one, add it there, or the
feature apply order will be right in git and wrong in the wheel.

## The verification trap

The development checkout is on `PYTHONPATH`, so a plain
`pip install && my-better-isabelle ...` inside a fresh venv can still import the
**source tree** and report success for a wheel that never worked. Prefix the
verification commands with `env -u PYTHONPATH` (as in step 6) and confirm the
version you get back is the one you just released.
