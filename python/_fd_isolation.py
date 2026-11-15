"""Keep Fortran output off the JSON-RPC pipe of a stdio MCP server.

Fortran ``WRITE(6,...)`` goes to OS fd 1, which for a stdio MCP server is
also the pipe its JSON-RPC answers travel on. One diagnostic line from the
library and the client logs "Failed to parse JSONRPC message from server";
in the worst case the session drops with "Connection closed".

:func:`install` moves the pipe to a descriptor of its own and gives fd 1
to stderr:

1. ``dup(1)`` saves the pipe; ``dup2(2, 1)`` points fd 1 at stderr, so the
   library's output lands in the server's log.
2. ``sys.stdout`` is rebuilt on the saved descriptor. The MCP SDK wraps
   ``sys.stdout.buffer`` in a ``TextIOWrapper`` of its own and flushes
   after every message; the line buffering asked for here only matters
   for Python-side ``print()``.

fd 0 is left as it is: the client's requests arrive on it. The saved
descriptor is never 0, 1 or 2, also when one of them is closed.

Call it from a server's ``main()`` just before the stdio server is built,
never at import time (#227 item 1): an import by pytest, by an embedding
application or by tot_mcp (which imports its siblings for their parameter
registries) must not change the host process's fd 1 and ``sys.stdout``.

The module sits beside the library wrappers, in ``<repo>/python/`` (like
``_runtime_mode``): every server puts that directory on ``sys.path`` for
its wrapper, so the module is found wherever the wrapper is. One flag for
the whole process: the servers share the module, so a second server's
``main()`` in the same process does not ``dup`` the redirected fd 1 and take
stderr for the pipe.

Two descriptor layouts need more than the two calls above:

* **fd 2 is closed.** ``dup(1)`` returns the lowest free descriptor, which
  is then 2, and ``dup2(2, 1)`` copies the pipe back onto fd 1. fd 2 is
  opened on ``os.devnull`` first, and ``sys.stderr``, which Python left at
  ``None``, is given that descriptor: a ``print(..., file=sys.stderr)`` or
  a traceback would otherwise be written to ``sys.stdout``, the pipe.
  (A ``sys.stderr`` of ``None`` beside an open fd 2 is given fd 2 for the
  same reason.)
  (A file that the process itself opened in between, and that took the
  number 2, is not told apart from a stderr; no server does that.)
* **fd 1 and fd 2 are the same file** (the host started the server with
  stderr merged into stdout, ``2>&1``, or on one pseudo-terminal).
  Pointing fd 1 at fd 2 changes nothing, so fd 1 goes to ``os.devnull``
  and one line on stderr says that what is written to fd 1 is discarded.
  "The same file" is read from ``fstat`` (``st_dev``, ``st_ino``). Where
  that gives no identity (an inode number of 0: Windows for a pipe or a
  console, some sockets) the two are taken for different files, so a
  merged stream is not recognised there and fd 1 goes to fd 2 as usual.

Nothing is changed until everything is prepared. The one call that
changes fd 1 is a ``dup2``, which does it or fails; a failure up to and
including it leaves fd 1, ``sys.stdout`` and the flag as they were and
closes the descriptors opened on the way, and nothing after it can fail.
(A closed fd 2 that was repaired, together with its ``sys.stderr``, stays
repaired when a later step fails; a repair that fails itself is undone.)
"""
from __future__ import annotations

import errno
import os
import sys

_INSTALLED = False
# The stream that was sys.stdout. Kept for the life of the process: a
# wrapper that owns fd 1 would close the descriptor when collected.
_PREVIOUS_STDOUT = None

_SAME_FILE_WARNING = (
    "warning: stdout and stderr of this MCP server are the same file; "
    "what the library writes to fd 1 (Fortran unit 6) is discarded to keep it "
    "off the JSON-RPC stream (give the server a stderr of its own to see it)\n"
)


def installed() -> bool:
    """True once :func:`install` has run in this process."""
    return _INSTALLED


def _close_quietly(fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        pass


def _same_file(fd_a: int, fd_b: int) -> bool:
    a, b = os.fstat(fd_a), os.fstat(fd_b)
    return a.st_ino != 0 and (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino)


def _dup_above_stderr(fd: int) -> int:
    """A duplicate of ``fd`` that is not 0, 1 or 2, whichever of them is free."""
    low = []
    try:
        while True:
            new = os.dup(fd)
            if new > 2:
                return new
            low.append(new)
    finally:
        for held in low:
            _close_quietly(held)


def _repair_fd2() -> None:
    """Open fd 2 on the null device if it is closed, and give Python a
    ``sys.stderr`` if it has none.

    Both or neither: a failure closes the descriptor this call opened, so
    that the next call starts from a closed fd 2 again.
    """
    try:
        os.fstat(2)
        opened = False
    except OSError as exc:
        if exc.errno != errno.EBADF:
            # fd 2 is there but cannot be looked at: not ours to replace
            raise
        null = os.open(os.devnull, os.O_WRONLY)
        if null != 2:
            try:
                os.dup2(null, 2)
            finally:
                _close_quietly(null)
        opened = True
    try:
        if opened:
            os.set_inheritable(2, True)     # as dup2 leaves it, for a child process
        if sys.stderr is None:
            sys.stderr = open(2, "w", buffering=1, encoding="utf-8",
                              errors="backslashreplace", closefd=False)
    except BaseException:
        if opened:
            _close_quietly(2)
        raise


def install() -> None:
    """Give fd 1 to stderr and rebuild ``sys.stdout`` on the saved pipe.

    Idempotent, and process-wide: the first call does the work for every
    server that shares this module.
    """
    global _INSTALLED, _PREVIOUS_STDOUT
    if _INSTALLED:
        return
    previous = sys.stdout
    if previous is not None:
        try:
            previous.flush()        # what Python buffered still belongs to the pipe
        except Exception:           # a host's stream of its own: best effort
            pass
    _repair_fd2()
    pipe_fd = _dup_above_stderr(1)
    null = None
    try:
        # closefd=False: this function owns pipe_fd until the redirect is done,
        # whatever the stream's construction does when it fails half-way.
        new_stdout = os.fdopen(pipe_fd, "w", buffering=1, encoding="utf-8", closefd=False)
        discard = _same_file(1, 2)
        if discard:
            null = os.open(os.devnull, os.O_WRONLY)
        os.dup2(null if discard else 2, 1)
    except BaseException:
        if null is not None:
            _close_quietly(null)
        _close_quietly(pipe_fd)
        raise
    # fd 1 is redirected: nothing after this point may fail.
    if null is not None:
        _close_quietly(null)
    _PREVIOUS_STDOUT = previous
    sys.stdout = new_stdout
    _INSTALLED = True
    if discard:
        try:
            os.write(2, _SAME_FILE_WARNING.encode("utf-8"))
        except OSError:
            pass
