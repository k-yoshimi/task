# Quickstart notebook

The notebook below walks through the end-to-end flow of the `eq`
module: `init` → `set_params` → `validate` → `run(mode=1)` →
`get_state` → plot the ψ grid.

```{note}
At build time `nb_execution_mode = "off"`, so the notebook is rendered
from pre-committed cell outputs. Re-execute manually with
`jupyter nbconvert --to notebook --execute --inplace
docs/sphinx/shared/notebooks/eq-quickstart.ipynb` before committing
source changes that should change the outputs.
```

```{toctree}
:maxdepth: 1

eq-quickstart
```
