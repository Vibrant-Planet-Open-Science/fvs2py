"""Event Monitor variable access and FVS activity scheduling mixin."""

from __future__ import annotations

import ctypes as ct
from collections.abc import Callable, Iterable
from typing import Any

import numpy as np

from fvs2py.common import fvs_property
from fvs2py.constants import STR_NCYCLES
from fvs2py.enums import FvsActivity, FvsAttributeAccessor


class EventMixin:
    """Expose Event Monitor variable access and FVS activity scheduling.

    Assumes the composed class provides :meth:`FvsCore._invoke` for registry
    dispatch, ``self.keyfile`` and ``self.stop_point_code`` from
    :class:`ControlMixin`, ``self.dims`` from :class:`StandMixin`, and the
    ``_evmon_attrs`` buffer seeded by ``FVS._initialize_attributes``.
    """

    _invoke: Callable[..., Any]
    _evmon_attrs: dict[str, None]
    keyfile: str | None
    stop_point_code: int | None
    dims: dict

    @fvs_property
    def evmon_attrs(self) -> dict[str, float | None]:
        """Return current values for every tracked Event Monitor variable.

        Iterates through the canonical names seeded from
        :data:`fvs2py.constants.EVMON_ATTRS` plus any names registered via
        :meth:`set_evmon_attr`, querying FVS for each and recording
        ``None`` when FVS reports the name as not-found (``rtncode == 1``).
        This bulk-inspection view deliberately tolerates not-found names
        because the canonical list includes phase-specific variables that
        may have no value at the current stop point. For a strict
        raise-or-return contract on a single variable, use
        :meth:`get_evmon_attr`.
        """
        out: dict[str, float | None] = {}
        for name in self._evmon_attrs:
            try:
                out[name] = self.get_evmon_attr(name)
            except NameError:
                out[name] = None
        return out

    def get_evmon_attr(self, attr: str) -> float | None:
        """Return the current FVS value for a single Event Monitor variable.

        Args:
            attr: Name of the Event Monitor variable (canonical FVS name
                or one defined at runtime via a keyfile ``COMPUTE``
                statement or via :meth:`set_evmon_attr`).

        Returns:
            The variable's current value, or ``None`` if FVS has not
            advanced far enough in the current cycle for any value to be
            reported (``ncycles == 0``).

        Raises:
            NameError: If FVS does not recognize ``attr``.
            KeyError: If no keyfile has been loaded.
            RuntimeError: If the simulation has not been started.
        """
        return self._evmon_attr(attr, FvsAttributeAccessor.GET)

    def set_evmon_attr(self, attr: str, val: int | float) -> None:
        """Set the value of a single Event Monitor variable.

        If ``attr`` is not already tracked in the instance's known-names
        cache, it is registered so subsequent :attr:`evmon_attrs`
        iterations include it. The Python-side cache is not treated as
        an authoritative whitelist: FVS itself decides whether the name
        is valid and reports ``NameError`` via :func:`attr_accessor_policy`
        if it is not.

        Args:
            attr: Name of the Event Monitor variable to set.
            val: New value to assign.

        Raises:
            NameError: If FVS does not recognize ``attr``.
            KeyError: If no keyfile has been loaded.
            RuntimeError: If the simulation has not been started.
        """
        if attr not in self._evmon_attrs:
            self._evmon_attrs[attr] = None
        self._evmon_attr(attr, FvsAttributeAccessor.SET, val)

    def _evmon_attr(
        self,
        attr: str,
        action: FvsAttributeAccessor,
        val: float | None = None,
    ) -> float | None:
        """Dispatch a get or set on a single Event Monitor variable.

        Allocates a fresh single-element float64 buffer for every call
        (FVS owns the authoritative value; the buffer is transient
        working memory), runs the registered ``fvsEvmonAttr`` call, and
        returns the scalar on GET. SET calls do not return a value.
        """
        if self.keyfile is None:
            msg = "No keyfile loaded yet."
            raise KeyError(msg)
        if self.stop_point_code is None:
            msg = (
                "Simulation has not yet started and no inventory data have "
                "been loaded yet. Call `run` method."
            )
            raise RuntimeError(msg)

        if self.dims[STR_NCYCLES] == 0:
            return None

        if action == FvsAttributeAccessor.SET and val is None:
            msg = "Must provide `val` if `action` is 'set'."
            raise TypeError(msg)

        if action == FvsAttributeAccessor.SET:
            arr = np.array([val], dtype=np.float64)
        else:
            arr = np.empty(shape=(1,), dtype=np.float64)

        self._invoke(
            "fvsEvmonAttr",
            attr_name=ct.c_char_p(attr.encode()),
            nch=ct.c_int(len(attr)),
            action=ct.c_char_p(action.encode()),
            arr=arr,
        )

        if action == FvsAttributeAccessor.GET:
            return float(arr[0])
        return None

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
                per-extension activity enums (``FvsBaseActivity``,
                ``FvsFireActivity``, etc.) or a raw FVS activity code as
                an integer.
            params: Optional iterable of numeric parameters for the
                activity. ``None`` is equivalent to "no parameters"; a
                length-zero buffer is passed to FVS in that case.

        Raises:
            KeyError: If no keyfile has been loaded.
            RuntimeError: If the simulation has not been started or no
                inventory has been loaded.
            ValueError: If FVS reports a failure
                (``fvsAddActivity`` rtncode == 1).
        """
        if self.keyfile is None:
            msg = "No keyfile loaded yet."
            raise KeyError(msg)
        if self.stop_point_code is None:
            msg = "Simulation hasn't been started yet. Call `run` method."
            raise RuntimeError(msg)
        if self.dims[STR_NCYCLES] == 0:
            msg = (
                "No inventory plots loaded yet. Consider FVS.run(7, 0) to "
                "load inventory data and run configuration before "
                "simulating anything else."
            )
            raise RuntimeError(msg)

        if params is None:
            arr = np.empty(shape=(0,), dtype=np.float64)
        else:
            arr = np.array(list(params), dtype=np.float64)
            if np.isnan(arr).any():
                msg = "params may not contain NaN values."
                raise ValueError(msg)

        self._invoke(
            "fvsAddActivity",
            year=ct.c_int(int(year)),
            activity_code=ct.c_int(int(activity)),
            params=arr,
            nparams=ct.c_int(len(arr)),
        )
