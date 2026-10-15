"""eq_mcp.get_psi_rz returns serialisable JSON with nrg/nzg/psi_rz.

This test drives the REAL stdio transport: it spawns ``python -m eq_mcp.server``
as a subprocess and speaks JSON-RPC to it. That needs three prerequisites which
the six sibling MCP test modules all guard for and this one did not, so instead
of skipping it failed with an opaque ``MCPError: Connection closed``:

* the **client** half of the SDK (``ClientSession`` / ``stdio_client``);
* the **server** half (``mcp.server.fastmcp.FastMCP``) *inside the subprocess*.
  These are separable, which is exactly how CI failed: mcp 2.0.0 removed the
  server half while keeping the client half, so the imports below succeeded
  while the spawned server exited 2 with "Python MCP SDK (`mcp`) is not
  installed" and the client only saw the pipe close;
* a built ``eq/libeqapi.so`` for that subprocess to load.

The root fix for the CI failure is the ``mcp>=0.9,<2`` pin (this package's
pyproject and the workflow), so with a correct install the test RUNS rather
than skips. These guards exist so that an environment which is missing a
prerequisite reports which one, instead of failing opaquely.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
_MCP_ROOT = _HERE.parents[2]      # .../python/mcp-servers
_PYTHON_ROOT = _HERE.parents[3]   # .../python
_REPO_ROOT = _HERE.parents[4]     # repo root

for _extra in (str(_MCP_ROOT), str(_PYTHON_ROOT)):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)


def _resolved_so() -> Path:
    """Mirror eqlib's OWN resolution order, rather than re-deriving a narrower one.

    ``eqlib._ffi._default_lib_path`` tries MONO_LIB_PATH (priority 0, above
    EQLIB_PATH), then EQLIB_PATH, then eq/libeqapi.so, then lib/libeqapi.so.
    Re-implementing only the middle two would skip this test in layouts where
    the library is present and loadable -- a guard masking a real result.
    """
    from eqlib import _ffi  # local import: after the sys.path inserts above
    return Path(_ffi._default_lib_path())


# Client half: without it this module cannot be collected at all.
pytest.importorskip("mcp", reason="Python MCP SDK (`mcp`) not installed")

from mcp import ClientSession  # noqa: E402
from mcp import StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

# Server half: checked separately, because the SUBPROCESS is what needs it.
from eq_mcp import server as _srv  # noqa: E402


@pytest.mark.skipif(
    not _srv.MCP_AVAILABLE,
    reason=(
        "server-side MCP SDK unavailable (mcp.server.fastmcp missing; mcp 2.0 "
        "removed it — install 'mcp>=0.9,<2'), so `python -m eq_mcp.server` "
        "exits 2 and the stdio handshake cannot complete"
    ),
)
@pytest.mark.skipif(
    not _resolved_so().exists(),
    reason=f"{_resolved_so()} not built; run `make -C eq libeqapi.so`",
)
def test_get_psi_rz_via_mcp():
    async def run():
        # The parent got eq_mcp on sys.path via the inserts above; the CHILD
        # needs it on PYTHONPATH or it dies with ModuleNotFoundError and the
        # client sees the same opaque "Connection closed" this file guards
        # against. Without this the _srv.MCP_AVAILABLE guard would be checking
        # the parent while the child fails for an unrelated reason.
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "eq_mcp.server"],
            env={
                **os.environ,
                "PYTHONPATH": os.pathsep.join(
                    p for p in (
                        str(_MCP_ROOT), str(_PYTHON_ROOT),
                        os.environ.get("PYTHONPATH", ""),
                    ) if p
                ),
            },
        )
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                result = await session.call_tool("get_psi_rz", {})
                payload = json.loads(result.content[0].text)
                assert "nrg" in payload and "nzg" in payload
                assert payload["nrg"] == 33 and payload["nzg"] == 33
                assert len(payload["psi_rz"]) == 33
                assert len(payload["psi_rz"][0]) == 33
    asyncio.run(run())
