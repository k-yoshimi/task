# Quickstart notebook

The notebook below walks through the end-to-end flow of the `tr`
module: `init` → `set_params` → `validate` → `run` → `get_state` →
plot.

```{note}
At build time `nb_execution_mode = "off"`, so the notebook is rendered
from pre-committed cell outputs. Re-execute manually with
`jupyter nbconvert --to notebook --execute --inplace
docs/sphinx/shared/notebooks/tr-quickstart.ipynb` before committing
source changes that should change the outputs.
```

```{toctree}
:maxdepth: 1

tr-quickstart
```
