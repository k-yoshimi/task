# `eqlib` API リファレンス

本ページは `python/eqlib/` のドキュメンテーション文字列 (docstring)
から `sphinx.ext.autodoc` で自動抽出したものです. ソースコードの
docstring が一次情報で, ここに反映されます.

## `Eq`

`libeqapi.so` への in-process ハンドル. 1 プロセス 1 インスタンス
(シングルトン境界は `EqlibError` で強制). `eq.run()` は時間ステップ
数ではなく `mode` を取る点に注意.

```{eval-rst}
.. autoclass:: eqlib.Eq
   :members:
   :special-members: __enter__, __exit__
   :show-inheritance:
```

## `EqState`

`eq_get_state` の返り値. `eq_state_t` C 構造体と対応する Python
dataclass. フィールド記述は docstring の `Attributes:` ブロックが
`napoleon_use_ivar` で inline 展開されます.

```{eval-rst}
.. autoclass:: eqlib.EqState
   :members:
   :show-inheritance:
```

## `EqDiagEntryPy` / `EqDiagCode`

`Eq.validate()` が返す診断エントリ (PR #164 / #165).

```{eval-rst}
.. autoclass:: eqlib.EqDiagEntryPy
   :members:
   :show-inheritance:

.. autoclass:: eqlib.EqDiagCode
   :members:
   :undoc-members:
   :show-inheritance:
```

## 例外階層

```{eval-rst}
.. autoexception:: eqlib.errors.EqlibError
   :members:
.. autoexception:: eqlib.errors.EqlibInitError
.. autoexception:: eqlib.errors.EqlibInvalidParamError
.. autoexception:: eqlib.errors.EqlibNotInitializedError
.. autoexception:: eqlib.errors.EqlibCalculationFailedError
.. autoexception:: eqlib.errors.EqlibNotImplementedError

.. autofunction:: eqlib.errors.raise_for_rc
.. autofunction:: eqlib.errors.raise_for_ierr
```

### 旧 camelCase エイリアス

`python/eqlib/errors.py` は初期 API ドラフトに対して書かれた呼び出し側
コードとの互換のため, 例外クラスを `EqLib*` (L-ib 大文字) 名でも
re-export しています:

- `EqLibError` ≡ `EqlibError`
- `EqLibInvalidParam` ≡ `EqlibInvalidParamError`
- `EqLibNotInitialized` ≡ `EqlibNotInitializedError`
- `EqLibCalculationFailed` ≡ `EqlibCalculationFailedError`
- `EqLibNotImplemented` ≡ `EqlibNotImplementedError`

新規コードは `Eqlib*` の正準名を使用してください. エイリアス側は
module 属性として残りますが個別にはドキュメント化されていません.
