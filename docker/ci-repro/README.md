# docker/ci-repro

Local reproduction of the GitHub Actions `ubuntu-latest` runner used by
`.github/workflows/python-tests.yml`.

## Why

After PR #135 landed the Layer-1 CI job that builds `lib<mod>api.so`
and runs pytest, a subset of tests that pass on the developer machine
SIGABRT (signal 6) in CI. Example:

```
File "python/trlib/trlib.py", line 53 in close
File "python/mcp-servers/tr_mcp/server.py", line 213 in close
File "python/mcp-servers/tr_mcp/tests/test_server.py", line 300 in test_init_run_state_finalize
Fatal Python error: Aborted
```

These are currently excluded from CI via `--deselect`. To fix them we
need a local iteration loop that matches the CI toolchain.

Key version differences:

| Component | CI (ubuntu-latest) | Dev host (typical) |
| --------- | ------------------ | ------------------ |
| gfortran  | 4:13.2.0-7ubuntu1  | 13.3.0             |
| Ubuntu    | 24.04              | 24.04              |
| Python    | 3.11.15 / 3.13.13  | varies             |

## Usage

Prerequisites: Docker installed, BPSD source cloned at `../bpsd`
relative to the repo root (`git clone https://github.com/ats-fukuyama/bpsd.git`).

Full build + run the SIGABRT-prone test:

```
./docker/ci-repro/run.sh
```

Interactive shell (iterate faster during debugging):

```
./docker/ci-repro/run.sh shell
```

Inside the container, the repo lives at
`/home/runner/work/task/task` (same path CI uses), so any log
output or gfortran backtrace references paths that match CI logs
line-for-line.

## What the workflow does

1. Builds `task-ci-repro:latest` from `Dockerfile` (Ubuntu 24.04 +
   gfortran 13.2.0 + Python 3.11 + pytest family).
2. Mounts the repo read/write and BPSD read-only.
3. Provisions `mtxp/make.mtxp` and `make.header` identically to the
   CI workflow, **plus `-fbacktrace`** in OFLAGS so any SIGABRT
   prints a Fortran stack trace.
4. Builds the full PIC chain + each `lib<mod>api.so`.
5. Runs `pytest tr_mcp::TestIntegration::test_init_run_state_finalize`
   (the canonical reproducer).
6. Writes the log to `/tmp/ci-repro.log` inside the container
   (visible in stdout).

## Expected outcomes

- **If the SIGABRT reproduces**: the `-fbacktrace` output gives the
  Fortran call stack. Use that to locate the uninit read / bounds
  violation / double-free in the source and file a one-shot fix PR.
- **If the SIGABRT does NOT reproduce**: something else in CI is
  different (kernel, CPU microarch, libc, env vars). Add diagnostic
  probes to the script, check `cat /proc/cpuinfo`, `ldd --version`,
  `env`.

## Followup

Once the root cause is fixed upstream, the corresponding test can be
removed from the `--deselect` list in `.github/workflows/python-tests.yml`
and CI gets a real Layer-1 integration tier.
