# `trlib` API reference

This page is auto-generated from the docstrings in `python/trlib/`.
The source docstrings are the canonical reference — everything below
is extracted by `sphinx.ext.autodoc`.

## `Trlib`

In-process handle to `libtrapi.so`. One live instance per process
(the singleton boundary is enforced via `TrlibStateError`).

```{eval-rst}
.. autoclass:: trlib.Trlib
   :members:
   :special-members: __enter__, __exit__
   :show-inheritance:
```

## `TrState`

Return type of `tr_get_state`. Python dataclass mirroring
`tr_state_t` in `tr/tr_api.h`. Field descriptions come from the
`Attributes:` block of the class docstring (rendered inline via
`napoleon_use_ivar`).

```{eval-rst}
.. autoclass:: trlib.TrState
   :members:
   :show-inheritance:
```

## `TrDiagEntryPy` / `TrDiagCode`

Diagnostic entries returned by `Trlib.validate()` (PR #172).

```{eval-rst}
.. autoclass:: trlib.TrDiagEntryPy
   :members:
   :show-inheritance:

.. autoclass:: trlib.TrDiagCode
   :members:
   :undoc-members:
   :show-inheritance:
```

## Exception hierarchy

```{eval-rst}
.. autoexception:: trlib.errors.TrlibError
   :members:
.. autoexception:: trlib.errors.TrlibInitError
.. autoexception:: trlib.errors.TrlibParamError
.. autoexception:: trlib.errors.TrlibStateError
.. autoexception:: trlib.errors.TrlibRunError
.. autoexception:: trlib.errors.TrlibNotImplementedError

.. autofunction:: trlib.errors.raise_for_ierr
```
