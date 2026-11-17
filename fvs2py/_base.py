"""The public `FVS` class."""

from __future__ import annotations

import os
from collections.abc import Iterable

import numpy as np
import numpy.typing as npt
import pandas as pd

from fvs2py import _calls
from fvs2py._attributes import FFE, SPECIES, SVS_OBJECTS, TREES
from fvs2py._core import FvsCore
from fvs2py.constants import STR_MAXSPECIES, STR_NTREES
from fvs2py.enums import (
    FvsActivity,
    FvsExitCode,
    FvsItrnCode,
    FvsRestartCode,
    FvsStopPointCode,
)


class FVS(FvsCore):
    """Main class for interacting with FVS at runtime.

    This class is the public interface. Each member delegates to `FvsCore` (the
    loaded library and run state) or to the stateless helpers in `fvs2py._calls`
    and `fvs2py._attributes`.

    Args:
        lib_path: Path to the FVS shared library, e.g. `/usr/local/lib/FVSpn.so`.

    Raises:
        ImportError: If the library doesn't export every routine fvs2py needs.
    """

    # -- Run lifecycle ---------------------------------------------------------

    def load_keyfile(
        self,
        keywordfile: str | os.PathLike,
        *,
        check_single_stand: bool = True,
    ) -> None:
        """Set the keywordfile as a command-line argument to FVS.

        If FVS has already been started, the library is reloaded first, with a
        warning if the previous simulation hadn't finished.

        If `check_single_stand` is true (the default), the keyfile text is first
        passed to `fvs2py.keyfile.validate_single_stand`; a keyfile that
        describes zero or multiple stands raises `ValueError` before FVS is
        invoked. Callers driving multi-stand runs via `FVS.run_batch` must set
        `check_single_stand=False` to bypass the guard.

        Args:
            keywordfile: Path to the FVS keyword file.
            check_single_stand: When true (default), require the keyfile to
                define exactly one stand (one each of `STDIDENT`, `PROCESS`, and
                `STOP`).

        Raises:
            ValueError: If `check_single_stand` is true and the keyfile fails
                `fvs2py.keyfile.validate_single_stand`.
        """
        self._load_keyfile(keywordfile, check_single_stand=check_single_stand)

    def run(self, stop_point_code: int = 0, stop_point_year: int = 0) -> None:
        """Run FVS until the stand completes or a stop point is reached.

        The call stays eager: when the stand finishes (FVS reports
        `restart_code == FvsRestartCode.DONE_RUNNING_STAND`), `run` issues one
        additional `_fvs` call to flush the main output file before returning,
        so callers do not need to invoke `run` a second time just to finalize
        output. When `stop_point_code` pauses the simulation mid-cycle, no flush
        is performed and the next call to `run` resumes from the stop.

        Multi-stand keyfiles are out of scope here; use `run_batch` (and load
        the keyfile with `check_single_stand=False`) when the keyfile defines
        more than one stand.

        Args:
            stop_point_code (optional, int): when FVS should stop during a cycle:
               -1 : Stop at every stop location
                0 : Never stop
                1 : Stop just before the first call to the Event Monitor
                2 : Stop just after the first call to the Event Monitor
                3 : Stop just before the second call to the Event Monitor
                4 : Stop just after the second call to the Event Monitor
                5 : Stop after growth and mortality has been computed, but
                        prior to applying them
                6 : Stop just before the ESTAB routines are called
                7 : Stop just after input is read but before missing values
                        are imputed
            stop_point_year (optional, int): years FVS should stop, options are:
                0 or negative : Stop in every cycle
                YYYY : Stop only in the cycle that contains year YYYY

        Raises:
            RuntimeError: If no keyfile has been loaded yet.
        """
        self._run(stop_point_code, stop_point_year)

    def run_batch(
        self, stop_point_code: int = 0, stop_point_year: int = 0
    ) -> None:
        """Advance FVS one stand's worth of cycles without auto-flushing.

        Unlike `run`, this method does not follow a `DONE_RUNNING_STAND` restart
        code with a flush call. It simply returns once FVS either pauses at a
        stop point or reports the stand-done marker, leaving output
        finalization, stand-advance, and termination detection in the caller's
        hands. This is the low-level building block for driving multi-stand
        keyfiles, where the caller typically loops:

            fvs.load_keyfile(path, check_single_stand=False)
            while fvs.itrncd == FvsItrnCode.GOOD_RUNNING_STATE:
                fvs.run_batch()
                # optionally inspect per-stand outputs here
            if fvs.itrncd == FvsItrnCode.ERROR or fvs.exit_code:
                ...  # handle the failure

        The loop ends at `FINISHED_ALL_STANDS` or `ERROR`. Don't loop on
        `itrncd != FINISHED_ALL_STANDS`: after an FVS error, `itrncd` stays at
        `ERROR` and that loop never ends. Some errors (e.g. FVS can't open an
        output file) set `itrncd` to `ERROR` but leave `exit_code` at 0, so
        check both.

        Stop-point semantics are identical to `run`: pass non-zero
        `stop_point_code` / `stop_point_year` to pause mid-cycle, then call
        `run_batch` again to resume.

        Args:
            stop_point_code (optional, int): when FVS should stop during a
                cycle. See `run` for the full list of values.
            stop_point_year (optional, int): year(s) at which FVS should stop.
                See `run` for the full list of values.

        Raises:
            RuntimeError: If no keyfile has been loaded yet.
        """
        self._run_batch(stop_point_code, stop_point_year)

    def set_stop_point_codes(
        self,
        stop_point_code: int | None = None,
        stop_point_year: int | None = None,
    ) -> None:
        """Sets FVS stop point codes.

        Args:
            stop_point_code (int): Optional code for when FVS should stop during
                a cycle:
               -1 : Stop at every stop location
                0 : Never stop
                1 : Stop just before the first call to the Event Monitor
                2 : Stop just after the first call to the Event Monitor
                3 : Stop just before the second call to the Event Monitor
                4 : Stop just after the second call to the Event Monitor
                5 : Stop after growth and mortality has been computed, but
                        prior to applying them
                6 : Stop just before the ESTAB routines are called
                7 : Stop just after input is read but before missing values
                        are imputed
            stop_point_year (int): Optional, years FVS should stop, options are:
                0 or negative : Stop in every cycle
                YYYY : Stop only in the cycle that contains year YYYY

        Raises:
            ValueError: If `stop_point_code` is outside the range `[-1, 7]`, or
                if `stop_point_year` is provided without `stop_point_code`.
        """
        self._set_stop_point_codes(stop_point_code, stop_point_year)

    @property
    def stop_point_code(self) -> FvsStopPointCode | None:
        """A code used to instruct FVS when to stop during a cycle.

        -1 : Stop at every stop location.
         0 : Never stop.
         1 : Stop just before the first call to the Event Monitor.
         2 : Stop just after the first call to the Event Monitor.
         3 : Stop just before the second call to the Event Monitor.
         4 : Stop just after the second call to the Event Monitor.
         5 : Stop after growth and mortality has been computed, but prior to
                applying them.
         6 : Stop just before the ESTAB routines are called.
         7 : Stop just after input is read but before missing values are imputed
                (tree heights and crown ratios, for example) and model
                calibration (argument stptyr is ignored).

        Assigning to this property delegates to `set_stop_point_codes`,
        preserving the currently-configured `stop_point_year` (or `0` if year
        has not been set).
        """
        code = self._stop_point_code
        return None if code is None else FvsStopPointCode(code.value)

    @stop_point_code.setter
    def stop_point_code(self, value: int) -> None:
        self.set_stop_point_codes(value, self.stop_point_year or 0)

    @property
    def stop_point_year(self) -> int | None:
        """A code indicating which cycles FVS should stop at.

        0 or negative : Stop in every cycle.
        YYYY : Stop only in the cycle that contains year YYYY.

        The year only narrows `stop_point_code`; FVS never stops when
        `stop_point_code` is 0.

        Assigning to this property delegates to `set_stop_point_codes`,
        preserving the currently-configured `stop_point_code` (or `0` if code
        has not been set).
        """
        year = self._stop_point_year
        return None if year is None else year.value

    @stop_point_year.setter
    def stop_point_year(self, value: int) -> None:
        self.set_stop_point_codes(self.stop_point_code or 0, value)

    @property
    def itrncd(self) -> FvsItrnCode:
        """Returns with the current return code value in FVS.

        -1: indicates that FVS has not been started.
         0: indicates that FVS is in good running state.
         1: indicates that FVS has detected an error of some kind and should not
                be used until reset by specifying new input.
         2: indicates that FVS has finished processing all the stands; new input
                can be specified.

        Raises:
            ValueError: If FVS reports a code `FvsItrnCode` doesn't define.
        """
        return FvsItrnCode(self._invoke("fvsGetRtnCode"))

    @property
    def restart_code(self) -> FvsRestartCode:
        """A code indicating when FVS stopped.

          1: Stop was done just before the first call to the Event Monitor.
          2: Stop was done just after the first call to the Event Monitor.
          3: Stop was done just before the second call to the Event Monitor.
          4: Stop was done just after the second call to the Event Monitor.
          5: Stop was done after growth and mortality has been computed, but
                prior to applying them.
          6: Stop was done just before the ESTAB routines are called.
          7: Stop was done just after input is read but before missing values
                are imputed (tree heights and crown ratios, for example) and
                model calibration.
        100: Stop was done after a stand has been simulated but prior to
                starting a subsequent stand.

        Raises:
            ValueError: If FVS reports a code `FvsRestartCode` doesn't define.
        """
        return FvsRestartCode(self._invoke("fvsGetRestartCode"))

    @property
    def exit_code(self) -> FvsExitCode:
        """Gets the integer code returned when FVS exits.

        Possible values are:
          0 - No serious errors occurred.
          1 - Input data error.
          2 - Keyword or expression error.
          3 - Extension or group activities error.
          4 - Scratch file error.
         10 - Warning from the establishment or cover extensions.

        Raises:
            ValueError: If FVS reports a code `FvsExitCode` doesn't define.
        """
        return FvsExitCode(self._invoke("fvsGetICCode"))

    # -- Stand -----------------------------------------------------------------

    @property
    def dims(self) -> dict[str, int]:
        """Return the max dimensions of important FVS data storage."""
        return self._invoke("fvsDimSizes")

    @property
    def stand_ids(self) -> dict[str, str]:
        """Return stand identification codes.

        Raises:
            RuntimeError: If no keyfile has been loaded or `run` has not been
                called.
        """
        self._require_started()
        return _calls.stand_ids(self._invoke)

    @property
    def summary(self) -> pd.DataFrame | None:
        """Return a dataframe with FVS Summary Statistics for started cycles.

        The returned dataframe omits cycles that have not yet been initiated,
        which are identifiable where all values in that row are zero. Returns
        `None` before any cycle has started.
        """
        return _calls.summary(self._invoke)

    # -- Species ---------------------------------------------------------------

    @property
    def species(self) -> pd.DataFrame:
        """Returns species codes and attributes for all species."""
        return self.species_codes.merge(
            self.species_attrs, left_index=True, right_index=True
        )

    @property
    def species_codes(self) -> pd.DataFrame:
        """Fetch the various codes used to refer to different tree species."""
        return _calls.species_codes(self._invoke)

    @property
    def species_attrs(self) -> pd.DataFrame:
        """Returns a dataframe of species attributes.

        Fields returned are:
            spccf: CCF for each species, recomputed in FVS so setting will
                likely have no effect
            spsdi: SDI maximums for each species
            spsiteindx: Species site indices
            bfmind: Min diameter related to BFVOLUME keyword
            bftopd: Top diameter related to BFVOLUME keyword
            bfstmp: Stump height related to BFVOLUME keyword
            frmcls: Form class related to BFVOLUME keyword
            bfmeth: Volume calculation code related to BFVOLUME keyword
                (internal FVS variable methb)
            mcmind: Min diameter related to VOLUME keyword (internal FVS
                variable dbhmin)
            mctopd: Top diameter related to VOLUME keyword (internal FVS
                variable topd)
            mcstmp: Stump height related to VOLUME keyword (internal FVS
                variable stmp)
            mcmeth: Volume calculation code related to VOLUME keyword (internal
                FVS variable methc)
            baimult: Basal area increment multiplier for large trees (internal
                FVS variable xdmult)
            htgmult: Height growth multiplier for large trees (internal FVS
                variable xhmult)
            mortmult: Mortality rate multiplier (internal FVS variable xmmult)
            mortdia1: Lower diameter limit for mortality multiplier (internal
                FVS variable xmdia1)
            mortdia2: Upper diameter limit for mortality multiplier (internal
                FVS variable xmdia2)
            regdmult: Diameter growth mulitplier for regeneration (internal FVS
                variable xrdmlt)
            reghmult: Height growth multiplier for regeneration (internal FVS
                variable xrhmlt)
        """
        return SPECIES.frame(self._invoke, self.dims[STR_MAXSPECIES])

    def get_species_attr(self, attr: str) -> npt.NDArray[np.float64]:
        """Gets a single attribute for all existing species.

        Args:
            attr (str): name of species attribute to fetch

        Returns:
            a new array with the attribute's value for every species

        Raises:
            NameError: If FVS does not recognize `attr`.
        """
        return SPECIES.get(self._invoke, attr, self.dims[STR_MAXSPECIES])

    def set_species_attr(self, attr: str, arr: npt.NDArray[np.float64]) -> None:
        """Sets a single attribute for all existing species.

        Args:
            attr (str): name of species attribute to set
            arr (npt.NDArray[np.float64]): values to set, shape `(maxspecies,)`

        Raises:
            NameError: If FVS does not recognize `attr`.
            ValueError: If `arr` is not shape `(maxspecies,)`.
        """
        SPECIES.set(self._invoke, attr, arr, self.dims[STR_MAXSPECIES])

    # -- Trees -----------------------------------------------------------------

    @property
    def trees(self) -> pd.DataFrame | None:
        """Returns a dataframe of trees currently in FVS.

        Warns and returns `None` if there are no trees yet.
        """
        return _calls.trees(self._invoke)

    def get_tree_attr(self, attr: str) -> npt.NDArray[np.float64]:
        """Gets a single attribute for existing trees.

        Args:
            attr (str): name of tree attribute to fetch

        Returns:
            a new array with the attribute's value for every tree

        Raises:
            NameError: If FVS does not recognize `attr`.
        """
        return TREES.get(self._invoke, attr, _calls.ntrees(self._invoke))

    def set_tree_attr(self, attr: str, arr: npt.NDArray[np.float64]) -> None:
        """Sets a single attribute for all existing trees.

        Args:
            attr (str): name of tree attribute to set
            arr (npt.NDArray[np.float64]): values to set, shape `(ntrees,)`

        Raises:
            NameError: If FVS does not recognize `attr`.
            ValueError: If `arr` is not shape `(ntrees,)`.
        """
        TREES.set(self._invoke, attr, arr, self.dims[STR_NTREES])

    def add_trees(self, tree_df: pd.DataFrame) -> None:
        """Adds trees to an existing simulation.

        Args:
            tree_df (pd.DataFrame): trees to add. Must contain every column
                listed in `fvs2py.constants.ADD_TREES_COLS` (`dbh`, `species`,
                `ht`, `cratio`, `plot`, `tpa`), with non-null float-coercible
                values for every row. Extra columns are ignored.

        Raises:
            ValueError: If columns are missing, values are null, there isn't
                room for the new trees, or a plot or species code is out of
                range.
            RuntimeError: If no inventory plots have been loaded yet.
        """
        _calls.add_trees(self._invoke, tree_df)

    # -- Event Monitor and activities ------------------------------------------

    @property
    def evmon_attrs(self) -> dict[str, float | None]:
        """Return current values for every tracked Event Monitor variable.

        Iterates through the canonical names seeded from
        `fvs2py.constants.EVMON_ATTRS` plus any names registered via
        `set_evmon_attr`, querying FVS for each and recording `None` when FVS
        reports the name as not-found (`rtncode == 1`). This bulk-inspection
        view deliberately tolerates not-found names because the canonical list
        includes phase-specific variables that may have no value at the current
        stop point. For a strict raise-or-return contract on a single variable,
        use `get_evmon_attr`.
        """
        out: dict[str, float | None] = {}
        for name in self._evmon_names:
            try:
                out[name] = self.get_evmon_attr(name)
            except NameError:
                out[name] = None
        return out

    def get_evmon_attr(self, attr: str) -> float | None:
        """Return the current FVS value for a single Event Monitor variable.

        Args:
            attr: Name of the Event Monitor variable (canonical FVS name or one
                defined at runtime via a keyfile `COMPUTE` statement or via
                `set_evmon_attr`).

        Returns:
            The variable's current value, or `None` if FVS has not advanced far
            enough in the current cycle for any value to be reported
            (`ncycles == 0`).

        Raises:
            NameError: If FVS does not recognize `attr`.
            RuntimeError: If no keyfile has been loaded or the simulation has
                not been started.
        """
        self._require_started()
        return _calls.get_evmon(self._invoke, attr)

    def set_evmon_attr(self, attr: str, val: int | float) -> None:
        """Set the value of a single Event Monitor variable.

        If `attr` is not already tracked in the instance's known-names cache, it
        is registered so subsequent `evmon_attrs` iterations include it. The
        Python-side cache is not treated as an authoritative whitelist: FVS
        itself decides whether the name is valid and reports `NameError` if it
        is not.

        Args:
            attr: Name of the Event Monitor variable to set.
            val: New value to assign.

        Raises:
            NameError: If FVS does not recognize `attr`.
            RuntimeError: If no keyfile has been loaded or the simulation has
                not been started.
        """
        self._require_started()
        self._evmon_names.setdefault(attr)
        _calls.set_evmon(self._invoke, attr, val)

    def add_activity(
        self,
        year: int,
        activity: FvsActivity | int,
        params: Iterable[float] | None = None,
    ) -> None:
        """Schedule an FVS activity to fire in a given simulation year.

        Args:
            year: Simulation year when the activity should execute.
            activity: Activity to schedule. Accepts any member of the
                per-extension activity enums (`FvsBaseActivity`,
                `FvsFireActivity`, etc.) or a raw FVS activity code as an
                integer.
            params: Iterable of numeric parameters for the activity. `None` and
                an empty iterable both pass a length-zero buffer to FVS, which
                is only safe for activities that take no parameters (e.g.
                `FvsBaseActivity.TREELIST`). See the warning below.

        Raises:
            RuntimeError: If no keyfile has been loaded, the simulation has not
                been started, or no inventory has been loaded.
            ValueError: If `params` contains NaN, or FVS reports a failure
                (`fvsAddActivity` rtncode == 1).

        Warning:
            FVS does **not** validate the length of `params` against the chosen
            activity's documented signature. Internally, `fvsAddActivity` copies
            the caller's values into a fixed 20-wide `real(4)` buffer and hands
            the whole buffer to `opadd`, which then interprets every slot the
            keyword's schema expects. Any positions past `len(params)` contain
            **uninitialized stack memory** that `opadd` will read as if it were
            valid input. `fvsAddActivity` still returns `rtncode == 0` in this
            case, so the failure is silent: the activity may no-op, or it may be
            scheduled with nonsensical thresholds, depending on what happened to
            be on the stack at call time.

            Callers should therefore supply the full documented parameter vector
            for every activity. There are no "optional" trailing parameters from
            FVS's point of view. Consult the `FVS Keyword Reference Guide
            <https://www.fs.usda.gov/fvs/documents/gtrs/FVSKeywords.pdf>`_ for
            the field count and default values of each keyword.

            For example, `FvsBaseActivity.THINABA` takes six fields (residual
            BA, cut efficiency, min DBH, max DBH, min HT, max HT). Passing only
            a target residual basal area (`params=[80]`) will silently
            misbehave. The correct call supplies every field explicitly, e.g.
            `params=[80.0, 1.0, 0.0, 999.0, 0.0, 999.0]`.
        """
        self._require_started()
        _calls.add_activity(self._invoke, year, activity, params)

    # -- SVS and FFE -----------------------------------------------------------

    @property
    def svs_dim_sizes(self) -> dict[str, int]:
        """Current and max SVS object counts from `fvsSVSDimSizes`.

        Keys: `nsvsobjs`, `ndeadobjs`, `ncwdobjs` (current counts) and
        `mxsvsobjs`, `mxdeadobjs`, `mxcwdobjs` (capacity).
        """
        return self._invoke("fvsSVSDimSizes")

    def get_svs_obj_attr(self, attr: str) -> npt.NDArray[np.float64]:
        """Get one `fvsSVSObjData` array (length = current nsvs/ndead/ncwd)."""
        n = _calls.svs_count(self._invoke, attr)
        return SVS_OBJECTS.get(self._invoke, attr, n)

    def set_svs_obj_attr(self, attr: str, arr: npt.NDArray[np.float64]) -> None:
        """Set one `fvsSVSObjData` array; shape must match current count."""
        n = _calls.svs_count(self._invoke, attr)
        SVS_OBJECTS.set(self._invoke, attr, arr, n)

    @property
    def ffe_attrs(self) -> pd.DataFrame:
        """DataFrame of per-species `fallyrs0`..`fallyrs5` (`fvsFFEAttrs`).

        These are the Fire and Fuels Extension per-species snag crown fall-year
        vectors. FFE stand-level compute variables (e.g. `torchidx`, `crbaseht`)
        are Event Monitor variables; see `get_evmon_attr`.
        """
        return FFE.frame(self._invoke, self.dims[STR_MAXSPECIES])

    def get_ffe_attr(self, attr: str) -> npt.NDArray[np.float64]:
        """Get one `fvsFFEAttrs` fallyrs column (shape `(maxspecies,)`)."""
        return FFE.get(self._invoke, attr, self.dims[STR_MAXSPECIES])

    def set_ffe_attr(self, attr: str, arr: npt.NDArray[np.float64]) -> None:
        """Set one `fvsFFEAttrs` fallyrs column (shape `(maxspecies,)`)."""
        FFE.set(self._invoke, attr, arr, self.dims[STR_MAXSPECIES])
