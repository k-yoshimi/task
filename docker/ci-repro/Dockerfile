# Ubuntu 24.04 + gfortran 13.2.0 — reproduces the GitHub Actions
# ubuntu-latest runner used by .github/workflows/python-tests.yml.
#
# Purpose: some tests that SIGABRT in CI do NOT reproduce on the host
# (host gfortran 13.3.0). This image pins the exact CI toolchain so
# the crash can be inspected locally with gdb / fbacktrace.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        gfortran gcc make git \
        python3.11 python3.11-venv python3-pip \
        ca-certificates gdb \
    && rm -rf /var/lib/apt/lists/*

# Verify the gfortran version matches what CI installs
# (Ubuntu 24.04 ships gfortran 4:13.2.0-7ubuntu1).
RUN gfortran --version | head -1 \
    && python3.11 --version

# pytest and friends — same pins as python-tests.yml
RUN python3.11 -m pip install --no-cache-dir --break-system-packages \
        pytest pytest-mock pytest-subtests pytest-forked tomli

# Match the CI layout exactly: repo is mounted at /home/runner/work/task/task.
WORKDIR /home/runner/work/task/task

# Default to an interactive shell so `docker run -it` drops you in.
# The run.sh wrapper overrides this with the actual build/test command.
CMD ["/bin/bash"]
