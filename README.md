# fvs2py
A Python wrapper of the [Forest Vegetation Simulator (FVS)](https://www.fs.usda.gov/fvs/).

This project has been designed to provide programmatic access to FVS through the [`FVS-API`](https://github.com/USDAForestService/ForestVegetationSimulator/wiki/FVS-API) from Python. It is inspired by and generally follows the pattern demonstrated by [`rFVS`](https://github.com/USDAForestService/ForestVegetationSimulator/wiki/rFVS), which loads a pre-compiled shared library of a single FVS variant and provides the user access to FVS variables and commands from a modern programming language.

Our initial focus is to replicate the functionality provided by `rFVS`.

We will then build upon the addition of new subroutines in Fortran that extend the underlying `FVS-API` and to produce corresponding wrapper functions here in `fvs2py` that will allow users access to get and set a broader suite of FVS parameters. The ultimate goal for this Python API is to allow users to run FVS, get and set simulation parameters at runtime, and to retrieve FVS output tables at runtime and in-memory without needing to interact with an external database or other output files.