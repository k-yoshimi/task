# BPSD: patched fork instead of in-repo patches

Until 2026-04-25 this directory hosted `bpsd/` with two `.patch`
files that CI applied on top of a fresh `ats-fukuyama/bpsd` clone.
Those patches now live as commits on the `develop` branch of
[`k-yoshimi/bpsd`](https://github.com/k-yoshimi/bpsd), a personal
fork of upstream.

CI (`.github/workflows/python-tests.yml`) clones the fork directly:

```bash
git clone --depth 1 --branch develop \
  https://github.com/k-yoshimi/bpsd.git ../bpsd
```

## The two patches (as fork commits)

| SHA       | Title                                                          | TASK issue |
|-----------|----------------------------------------------------------------|------------|
| 879bb7ac  | Fix species_kid out-of-bounds write in bpsd_setup_species_kdata| #140       |
| dcccf84f  | Zero-init INTENT(OUT) scalars in bpsd_get_plasmaf              | #148       |

Both patches were emailed to upstream (Fukuyama-sensei) on
2026-04-22 and are awaiting upstream merge.

## Local-dev sibling clone

The TASK module Makefiles look for `BPSD_SRC=../../bpsd` (i.e. a
sibling directory next to `task-private/`). To set up:

```bash
cd /path/to/task-private/..
git clone --branch develop https://github.com/k-yoshimi/bpsd.git
```

Or, if you already have a sibling clone of upstream:

```bash
cd ../bpsd
git remote set-url origin https://github.com/k-yoshimi/bpsd.git
git fetch origin
git checkout -B develop origin/develop
make libbpsd.a   # rebuild
```

Each `lib<mod>api.so` statically links its own copy of `bpsd_*.o`,
so when you re-point the sibling clone you must rebuild every
module's PIC bpsd objects + the `.so` itself, otherwise stale
`bpsd_*.o` from a previously-built `.so` may shadow the patched
copy at runtime (first-loaded wins under `dlopen`):

```bash
cd /path/to/task-private
for mod in tr fp ti wrx eq; do
  rm -f $mod/obj/pic/bpsd/*.o $mod/mod_pic/bpsd/*.mod
  make -C $mod bpsd_pic
  make -C $mod lib${mod}api.so
done
make -C tot libtotapi.so
```

## Sync with upstream (fork maintainer workflow)

When `ats-fukuyama/bpsd` advances or merges either patch:

```bash
cd /path/to/bpsd-fork-clone
git remote add upstream https://github.com/ats-fukuyama/bpsd.git  # once
git fetch upstream

# 1. Bring fork main to upstream main
git checkout main
git pull upstream main
git push origin main

# 2. Rebase develop onto new main (drops merged patches naturally)
git checkout develop
git rebase main
git push --force-with-lease origin develop
```

If upstream merges a patch, the corresponding commit on `develop`
becomes empty under rebase and is dropped. CI doesn't need any
change — `--branch develop` still works (just points at fewer
commits ahead of `main`). When `develop == main`, the fork is done
and can be archived.

## Recovering if the fork's `develop` branch disappears

If `k-yoshimi/bpsd@develop` is ever force-pushed away or the repo
goes private, CI will fail at the clone step. The two patches can
be reconstructed from these commits on `k-yoshimi/bpsd`:

- `879bb7ac` — species_kid OOB
- `dcccf84f` — plasmaf INTENT(OUT)

Or, if even those are gone, the original patch files are recoverable
from `git log` of this repo: see commit `feature/bpsd-fork-migration`
parent (the deletion commit) for the `.patch` file contents.
