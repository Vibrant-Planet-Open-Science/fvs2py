# fvs2py
A Python wrapper of the [Forest Vegetation Simulator (FVS)](https://www.fs.usda.gov/fvs/).

This project has been designed to provide programmatic access to FVS through the [`FVS-API`](https://github.com/USDAForestService/ForestVegetationSimulator/wiki/FVS-API) from Python. It is inspired by and generally follows the pattern demonstrated by [`rFVS`](https://github.com/USDAForestService/ForestVegetationSimulator/wiki/rFVS), which loads a pre-compiled shared library of a single FVS variant and provides the user access to FVS variables and commands from a modern programming language.

Our initial focus is to replicate the functionality provided by `rFVS`.

We will then build upon the addition of new subroutines in Fortran that extend the underlying `FVS-API` and to produce corresponding wrapper functions here in `fvs2py` that will allow users access to get and set a broader suite of FVS parameters. The ultimate goal for this Python API is to allow users to run FVS, get and set simulation parameters at runtime, and to retrieve FVS output tables at runtime and in-memory without needing to interact with an external database or other output files.

## Installation

```bash
pip install 'fvs2py[runtime]'
```

The `runtime` extra installs [fvs-runtime](https://pypi.org/project/fvs-runtime/), which has the shared libraries of the 22 US variants the USFS builds from Fortran, for Linux, macOS and Windows.

If you omit the `runtime` extra and just do `pip install fvs2py` you will get the fvs2py package installed without any of the FVS shared libraries (use this only if you intend to build your own libraries that follow the same [FVS-API](https://github.com/USDAForestService/ForestVegetationSimulator/wiki/FVS-API) that fvs2py expects). We strongly recommend using `pip install 'fvs2py[runtime]'` unless you are building or customizing FVS variants yourself.

## Usage

```python
from fvs2py import FVS

fvs = FVS("pn")  # or FVS(lib_path="/path/to/FVSpn.so")
fvs.load_keyfile("name.key")
fvs.run()
fvs.summary  # pandas DataFrame
fvs.version     # "2027.1.1 (USDAForestService)"
fvs.build_info  # dict: Version, Org, Remote, Branch, Commit, Date
```

### Reading output tables in memory

With `memory_tables=True`, FVS keeps its output database (the tables a keyfile's `DATABASE` block requests with `DSNOut`) in memory instead of writing a `.db` file, and you read the tables straight into DataFrames:

```python
fvs = FVS("pn", memory_tables=True)
fvs.load_keyfile("name.key")
fvs.run()
fvs.table_names                     # ["FVS_Cases", "FVS_Summary2", ...]
fvs.get_table("FVS_Summary2")       # pandas DataFrame, columns in table order
```

## Command Line Interface (CLI)

fvs2py also installs an `fvs` command that works like FVS executables do. These commands are equivalent:

```bash
FVSpn --keywordfile=name.key                        # original FVS executable (PN variant)
fvs --variant=pn --keywordfile=name.key             # fvs2py equivalent
fvs --lib=/path/to/FVSpn.so --keywordfile=name.key  # fvs2py with your own library
```

Most users of `fvs2py` should primarily expect to use the Python interface. The CLI is for running FVS in a separate process to handle any crashes and catch outputs if FVS breaks.

## Contributing

See [CONTRIBUTING.md](https://github.com/Vibrant-Planet-Open-Science/fvs2py/blob/main/CONTRIBUTING.md) for development setup, tests, and pre-commit hooks.
