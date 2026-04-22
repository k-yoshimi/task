#!/usr/bin/env bash
# apply-bpsd-patches.sh — local-dev mirror of the CI BPSD patch step.
#
# Applies every patch in docs/external-patches/bpsd/ to the sibling
# ../bpsd clone, then forces a full rebuild of every libXapi.so so
# the patched bpsd_*.o is picked up by ALL of them (not just the one
# you happen to rebuild). See docs/external-patches/bpsd/README.md
# for the symbol-shadowing rationale.
#
# Idempotent: re-running on an already-patched tree exits cleanly
# (each `git apply` is gated on `--check` first).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BPSD_DIR="${BPSD_DIR:-$REPO_ROOT/../bpsd}"
PATCH_DIR="$REPO_ROOT/docs/external-patches/bpsd"

if [ ! -d "$BPSD_DIR" ]; then
    echo "ERROR: BPSD checkout not found at $BPSD_DIR" >&2
    echo "       Set BPSD_DIR=/path/to/bpsd or clone:" >&2
    echo "       git clone https://github.com/ats-fukuyama/bpsd $BPSD_DIR" >&2
    exit 1
fi

echo "=== applying BPSD patches in $PATCH_DIR to $BPSD_DIR ==="
shopt -s nullglob
applied_any=0
for patch in "$PATCH_DIR"/*.patch; do
    name="$(basename "$patch")"
    if git -C "$BPSD_DIR" apply --check "$patch" 2>/dev/null; then
        git -C "$BPSD_DIR" apply --verbose "$patch"
        echo "  applied: $name"
        applied_any=1
    elif git -C "$BPSD_DIR" apply --reverse --check "$patch" 2>/dev/null; then
        echo "  already-applied: $name"
    else
        echo "  ERROR: $name failed --check (neither apply nor reverse-apply works)" >&2
        echo "  → resolve manually: git -C $BPSD_DIR apply --verbose --reject $patch" >&2
        exit 1
    fi
done

echo "=== rebuilding libbpsd.a ==="
make -C "$BPSD_DIR" libbpsd.a >/dev/null

echo "=== rebuilding ALL libXapi.so (per-mod bpsd_*.o is statically linked) ==="
for mod in tr fp ti wrx eq; do
    rm -f "$REPO_ROOT/$mod/obj/pic/bpsd"/*.o \
          "$REPO_ROOT/$mod/mod_pic/bpsd"/*.mod 2>/dev/null || true
    echo "  $mod: bpsd_pic + lib${mod}api.so"
    make -C "$REPO_ROOT/$mod" bpsd_pic >/dev/null
    make -C "$REPO_ROOT/$mod" "lib${mod}api.so" >/dev/null
done
make -C "$REPO_ROOT/tot" libtotapi.so >/dev/null

echo "=== done ==="
[ "$applied_any" = "1" ] && echo "  patches newly applied: yes" \
                         || echo "  patches were already applied"
