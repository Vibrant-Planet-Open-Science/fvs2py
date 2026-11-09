# fvs2py
A Python wrapper of the [Forest Vegetation Simulator (FVS)](https://www.fs.usda.gov/fvs/).

This project has been designed to provide programmatic access to FVS through the [`FVS-API`](https://github.com/USDAForestService/ForestVegetationSimulator/wiki/FVS-API) from Python. It is inspired by and generally follows the pattern demonstrated by [`rFVS`](https://github.com/USDAForestService/ForestVegetationSimulator/wiki/rFVS), which loads a pre-compiled shared library of a single FVS variant and provides the user access to FVS variables and commands from a modern programming language.

Our initial focus is to replicate the functionality provided by `rFVS`.

We will then build upon the addition of new subroutines in Fortran that extend the underlying `FVS-API` and to produce corresponding wrapper functions here in `fvs2py` that will allow users access to get and set a broader suite of FVS parameters. The ultimate goal for this Python API is to allow users to run FVS, get and set simulation parameters at runtime, and to retrieve FVS output tables at runtime and in-memory without needing to interact with an external database or other output files.

## Installation

```bash
pip install fvs2py
```

fvs2py doesn't include the FVS libraries. You supply a compiled FVS variant library, either your own build or one from the [`usfs-fvs` container image](https://github.com/Vibrant-Planet-Open-Science/fvs-build/pkgs/container/usfs-fvs) (`ghcr.io/vibrant-planet-open-science/usfs-fvs`), which has every variant's library at `/usr/local/lib/FVS<variant>.so`.

## Usage

```python
from fvs2py import FVS

fvs = FVS("/path/to/FVSpn.so")
fvs.load_keyfile("name.key")
fvs.run()
fvs.summary  # pandas DataFrame
```

## Command line

fvs2py also installs an `fvs` command that works like FVS executables do. These two commands are equivalent:

```bash
FVSpn --keywordfile=name.key
fvs --lib=/path/to/FVSpn.so --keywordfile=name.key
```

Most users of `fvs2py` should primarily expect to use the Python interface. The CLI is for running FVS in a separate process, so a crash by FVS doesn't take down your program and its output can be captured.

## Development

A **dev container** is provided under [`.devcontainer/`](https://github.com/Vibrant-Planet-Open-Science/fvs2py/tree/main/.devcontainer) for VS Code. Open the repository with **Dev Containers: Reopen in Container** to get the `dev` Docker target, Python tooling, and extensions preconfigured. On first open, `postCreateCommand` runs `uv sync --frozen --extra dev` (creating a project-local `.venv` in your clone, gitignored) and installs pre-commit hooks. After pulling changes that touch the Dockerfile or lockfile, **rebuild** the dev container (or run `uv sync --extra dev` manually).

The `.venv` directory lives on your host via the bind-mounted workspace (Linux binaries from the container). You can delete it and re-run `uv sync --extra dev` to recreate.

If you don't want to use a dev container, install dev dependencies and hooks the same way before opening a pull request:

```bash
uv sync --extra dev
uv run pre-commit install
```

Run tests locally or inside the dev container:

```bash
uv run pytest .
```

Hooks run on each commit (secret scan, Ruff, mypy). Run them manually with `uv run pre-commit run --all-files`. CI runs the same checks on pull requests via the Lint workflow, and runs pytest in the `dev` Docker image via the Pytest workflow.