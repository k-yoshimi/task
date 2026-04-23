# `trlib` API リファレンス

本ページは `python/trlib/` のドキュメンテーション文字列 (docstring)
から `sphinx.ext.autodoc` で自動抽出したものです. ソースコードの
docstring が一次情報で, ここに反映されます.

## `Trlib`

`libtrapi.so` への in-process ハンドル. 1 プロセス 1 インスタンス
(シングルトン境界は `TrlibStateError` で強制).

```{eval-rst}
.. autoclass:: trlib.Trlib
   :members:
   :special-members: __enter__, __exit__
   :show-inheritance:
```

## `TrState`

`tr_get_state` の返り値. `tr_state_t` C 構造体と対応する Python dataclass.
フィールド記述は docstring の `Attributes:` ブロックが
`napoleon_use_ivar` で inline 展開されます.

```{eval-rst}
.. autoclass:: trlib.TrState
   :members:
   :show-inheritance:
```

## `TrDiagEntryPy` / `TrDiagCode`

`Trlib.validate()` が返す診断エントリ (PR #172).

```{eval-rst}
.. autoclass:: trlib.TrDiagEntryPy
   :members:
   :show-inheritance:

.. autoclass:: trlib.TrDiagCode
   :members:
   :undoc-members:
   :show-inheritance:
```

## 例外階層

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
