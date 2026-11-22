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
                           (1 = real EQDSK load via ``equnit::eq_load``)
* ``apply(eq)``         -- callable that applies all of the above

Data files:

* ``iter_taskeq.geqdsk`` -- the GEQDSK file that ``test_modelg25_geqdsk.py``
  loads with ``MODELG`` 5 and 25 (25 KB, COCOS 1, flux per radian). It is
  TASK/EQ's own output: the ``MODELG=2`` equilibrium with ``RR=6.2``,
  ``RA=2.0``, ``RB=2.4``, ``RKAP=1.7``, ``RDLT=0.33``, ``BB=5.3``, ``RIP=15``
  on the default 33 x 33 grid, written as GEQDSK by the TASK web client's
  exporter.
"""
