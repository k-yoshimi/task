# クイックスタート notebook

以下の notebook は `tr` モジュールの end-to-end の流れを示します
(`init` → `set_params` → `validate` → `run` → `get_state` → plot).

```{note}
ビルド時には `nb_execution_mode = "off"` なので, notebook は
事前実行されたセル出力を使用します. 再実行は手動で
`jupyter nbconvert --to notebook --execute --inplace
docs/sphinx/shared/notebooks/tr-quickstart.ipynb` としてください.
```

```{toctree}
:maxdepth: 1

tr-quickstart
```
