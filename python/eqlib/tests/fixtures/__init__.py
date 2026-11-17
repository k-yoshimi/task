"""Phase L-6 fixture package for eqlib tests.

Each ``eq_*_params.py`` module here exposes the same symbols as the
trlib fixtures so the equivalence / sweep drivers stay schema-uniform:

* ``SCALARS``           -- dict[str, float|int] of scalar params for ``eq.set_param``
* ``ARRAYS``            -- dict[str, list|dict] of 1-origin (or 0-origin
                           for ``PSIB``) array elements
* ``STRINGS``           -- dict[str, str] for ``eq.set_param_str``
* ``UNREGISTERED_KEYS`` -- list[str] of namelist keys that exist in the
                           input file but are not yet in
                           ``eq_param_registry.f90`` (skipped by ``apply``)
* ``BASELINE_NAME``     -- str, ``test_run/baselines/<name>/`` subdir
* ``MODE``              -- int, the ``eq.run(mode=...)`` argument
                           (1 = the equilibrium-file load via ``equnit::eq_load``)
* ``apply(eq)``         -- callable that applies all of the above
"""
