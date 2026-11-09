# Contributing

## Reporting issues

Open an issue at [fvs2py issues](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues) and include:

- your fvs2py version (`pip show fvs2py`)
- the FVS variant and where the library came from: your own build, or the `usfs-fvs` image tag
- a minimal keyword file that reproduces the problem, if you can share one
- the full traceback, or the FVS error output from the `.out` file

If FVS itself gives the wrong result (the same behavior happens when you run the variant's executable, e.g. `FVSpn`, directly), report it to the [Forest Vegetation Simulator project](https://github.com/USDAForestService/ForestVegetationSimulator/issues). Problems with the `usfs-fvs` container image belong in [fvs-build](https://github.com/Vibrant-Planet-Open-Science/fvs-build/issues).

## Development environment

A **dev container** is provided under [`.devcontainer/`](.devcontainer/) for VS Code. Open the repository with **Dev Containers: Reopen in Container** to get the `dev` Docker target, Python tooling, and extensions preconfigured. On first open, `postCreateCommand` runs `uv sync --frozen --extra dev` (creating a project-local `.venv` in your clone, gitignored) and installs pre-commit hooks. After pulling changes that touch the Dockerfile or lockfile, **rebuild** the dev container (or run `uv sync --extra dev` manually).

The `.venv` directory lives on your host via the bind-mounted workspace (Linux binaries from the container). You can delete it and re-run `uv sync --extra dev` to recreate.

If you don't want to use a dev container, install dev dependencies and hooks the same way before opening a pull request:

```bash
uv sync --extra dev
uv run pre-commit install
```

## Tests

Run tests locally or inside the dev container:

```bash
uv run pytest .
```

## Checks

Hooks run on each commit (secret scan, Ruff, mypy). Run them manually with `uv run pre-commit run --all-files`. CI runs the same checks on pull requests via the Lint workflow, and runs pytest in the `dev` Docker image via the Pytest workflow.

## Style

Ruff and mypy enforce most of the style. Beyond what they check:

- Docstrings follow the [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
- Mark code in docstrings with single backticks (`` `itrncd` ``). Don't use reST roles (`:func:`) or double backticks.

## Commit messages and PR titles

Pull requests are squash-merged, and the PR title becomes the commit message on `main`. [release-please](https://github.com/googleapis/release-please) reads those messages to write the changelog and choose the next version, so PR titles must follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <lowercase, present-tense summary>
```

For example, `feat: adds fvs CLI entry point` or `docs: fixes run_batch loop example`.

| Type | Changelog section | Release |
| --- | --- | --- |
| `feat` | Features | yes |
| `fix` | Bug Fixes | yes |
| `perf` | Performance Improvements | yes |
| `docs` | Documentation | yes |
| `build` | Build System | yes |
| `refactor` | Code Refactoring | yes |
| `ci`, `test`, `chore` | hidden | no |

Mark a breaking change with `!` after the type (`feat!: ...`) and describe it in a `BREAKING CHANGE:` footer. While fvs2py is below 1.0, a breaking change bumps the minor version and everything else that releases bumps the patch version.
