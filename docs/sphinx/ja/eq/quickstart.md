# クイックスタート notebook

以下の notebook は `eq` モジュールの end-to-end の流れを示します
(`init` → `set_params` → `validate` → `run(mode=1)` → `get_state` →
ψ-面プロット).

```{note}
ビルド時には `nb_execution_mode = "off"` なので, notebook は事前実行
されたセル出力を使用します. 再実行は手動で
`jupyter nbconvert --to notebook --execute --inplace
docs/sphinx/shared/notebooks/eq-quickstart.ipynb` としてください.
```

```{toctree}
:maxdepth: 1

eq-quickstart
```
