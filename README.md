# fvs2py
A Python wrapper of the [Forest Vegetation Simulator (FVS)](https://www.fs.usda.gov/fvs/).

This project has been designed to provide programmatic access to FVS through the [`FVS-API`](https://github.com/USDAForestService/ForestVegetationSimulator/wiki/FVS-API) from Python. It is inspired by and generally follows the pattern demonstrated by [`rFVS`](https://github.com/USDAForestService/ForestVegetationSimulator/wiki/rFVS), which loads a pre-compiled shared library of a single FVS variant and provides the user access to FVS variables and commands from a modern programming language.

Our initial focus is to replicate the functionality provided by `rFVS`.

We will then build upon the addition of new subroutines in Fortran that extend the underlying `FVS-API` and to produce corresponding wrapper functions here in `fvs2py` that will allow users access to get and set a broader suite of FVS parameters. The ultimate goal for this Python API is to allow users to run FVS, get and set simulation parameters at runtime, and to retrieve FVS output tables at runtime and in-memory without needing to interact with an external database or other output files.

## Installation

```bash
pip install fvs2py
```

fvs2py is a wrapper, and doesn't currently ship with the FVS libraries included. You supply a compiled FVS variant library, either your own build, an official [USFS release](https://www.fs.usda.gov/fvs/software/variantinstaller.php) (currently Windows only), or one from the [`usfs-fvs` container image](https://github.com/Vibrant-Planet-Open-Science/fvs-build/pkgs/container/usfs-fvs) (`ghcr.io/vibrant-planet-open-science/usfs-fvs`), which has every variant's library at `/usr/local/lib/FVS<variant>.so`.  We're working to make updates to this package so that it can come with FVS libraries included and will keep this documentation up-to-date when those updates land.

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
FVSpn --keywordfile=name.key                        # FVS executable (PN variant)
fvs --lib=/path/to/FVSpn.so --keywordfile=name.key  # fvs2py equivalent
```

Most users of `fvs2py` should primarily expect to use the Python interface. The CLI is for running FVS in a separate process, so a crash by FVS doesn't take down your program and its output can be captured.

## Contributing

See [CONTRIBUTING.md](https://github.com/Vibrant-Planet-Open-Science/fvs2py/blob/main/CONTRIBUTING.md) for development setup, tests, and pre-commit hooks.
