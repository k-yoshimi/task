#!/bin/bash
# Reproduce the CI build + run the SIGABRT-prone tests inside a
# Ubuntu 24.04 + gfortran 13.2.0 container that matches the GitHub
# Actions ubuntu-latest runner.
#
# Usage:
#   ./docker/ci-repro/run.sh          # full build + pytest
#   ./docker/ci-repro/run.sh shell    # drop into interactive shell
#
# On first run Docker builds the image (~200 MB). Subsequent runs
# reuse the image and just remount the repo.

set -euo pipefail

# Repo root = parent of docker/ci-repro/
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

# BPSD is expected at ../bpsd (sibling to the repo), matching the
# BPSD_SRC=../../bpsd path used by every module Makefile. Resolve it
# via `realpath` so symlinked layouts (e.g. /home/... -> /data/...) work.
BPSD_HOST="$(realpath "$REPO_ROOT/../bpsd" 2>/dev/null || true)"
if [[ -z "$BPSD_HOST" || ! -d "$BPSD_HOST" ]]; then
    echo "BPSD source not found at $REPO_ROOT/../bpsd." >&2
    echo "Clone it: git clone https://github.com/ats-fukuyama/bpsd.git $REPO_ROOT/../bpsd" >&2
    exit 1
fi

IMAGE=task-ci-repro:latest
echo "==> Building Docker image ($IMAGE)"
docker build -t "$IMAGE" -f docker/ci-repro/Dockerfile docker/ci-repro

# Match the CI path layout: /home/runner/work/task/task is the repo,
# and BPSD sits at a sibling so BPSD_SRC=../../bpsd resolves correctly.
RUN_ARGS=(
    --rm
    -v "$REPO_ROOT:/home/runner/work/task/task"
    -v "$BPSD_HOST:/home/runner/work/task/bpsd"
    -w /home/runner/work/task/task
)

if [[ "${1:-}" == "shell" ]]; then
    exec docker run -it "${RUN_ARGS[@]}" "$IMAGE" /bin/bash
fi

exec docker run "${RUN_ARGS[@]}" "$IMAGE" /bin/bash -c '
set -euo pipefail

echo "==> Host env"
gfortran --version | head -1
python3.11 --version
uname -a
ldd --version | head -1
cat /proc/cpuinfo | grep "^model name" | head -1 || true

echo ""
echo "==> Provision mtxp/make.mtxp from nompi template"
cp mtxp/make.mtxp.nompi mtxp/make.mtxp

echo ""
echo "==> Provision make.header (CI-equivalent, plus -fbacktrace for the debug OFLAGS)"
# Same content as the python-tests.yml `make.header` heredoc.
cat > make.header <<"HEADER_EOF"
LAPACK = nolapack.f
LIBLA =
MODLA95 =
MDSPLUS = nomdsplus.f
MDSLIB =
MF77 = mpif77
MF90 = mpif90
MF95 = mpif90
MFC  = $(MF90)

GFLIBS=
# Release flags + -fbacktrace so any SIGABRT prints a Fortran stack.
OFLAGS = -g -O3 -m64 -std=legacy -fbacktrace
DFLAGS = -g -m64 -fbounds-check -ffpe-trap=invalid,zero,overflow -fbacktrace -fcheck=all -std=legacy
FCFIXED = gfortran -ffixed-form
FCFREE = gfortran -ffree-form
MOD = mod
MODDIR = -Jmod
LD=ld
LDFLAGS=-r -o
FPP=
HEADER_EOF

echo ""
echo "==> Build PIC support libs (bpsd, lib, mtxp, pl, eq, dp, ob, adf11, adpost)"
make -C /home/runner/work/task/bpsd libbpsd.a
make -C lib libtask_pic.a libgrf_pic.a libmds_pic.a
make -C mtxp libmtxnompi_pic.o libmtxbnd_pic.o
make -C tr bpsd_pic
make -C pl libpl_noeq_pic
make -C eq libeq_pic.a
make -C pl libpl_pic.a
make -C dp libdp_pic.a
make -C ob libob_pic.a
make -C open-adas/adf11/adf11-lib lib-adf11_pic.a || true
make -C adpost lib-adpost_pic.a || true

echo ""
echo "==> Build lib<mod>api.so"
for mod in tr fp ti wr wrx eq tot; do
    echo "--- $mod ---"
    if [[ "$mod" != "tot" ]]; then
        make -C "$mod" bpsd_pic
    fi
    make -C "$mod" "lib${mod}api.so"
done

echo ""
echo "==> Run the SIGABRT-prone test with full Fortran backtrace"
export PYTHONPATH=python
export PYTHONDONTWRITEBYTECODE=1
python3.11 -m pytest \
    python/mcp-servers/tr_mcp/tests/test_server.py::TestIntegration::test_init_run_state_finalize \
    -v --tb=short 2>&1 | tee /tmp/ci-repro.log

echo ""
echo "==> Test exit: $?"
'
