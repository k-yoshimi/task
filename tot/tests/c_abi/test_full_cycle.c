/*
 * Phase L-6: full-cycle C ABI driver for the tot orchestrator.
 *
 * Drives a complete init -> set_param -> run -> get_state -> finalize
 * cycle directly through the static-link C ABI surface (i.e. without
 * dlopen — that path is covered by test_run_so.c). Asserts OK at every
 * step and validates the TR-authoritative state slots that the L-6
 * fan-out aggregates from tr_api_get_state.
 *
 * Mirrors the per-module L-6 happy-path drivers
 * (tr/tests/c_abi/test_run.c, fp/tests/c_abi/test_run.c,
 * wrx/tests/c_abi/test_run.c) so the orchestrator surface is pinned at
 * the same depth as the per-module surfaces.
 *
 * Return values:
 *   0     = OK
 *   1..7  = step that failed (see EXPECT_OK / EXPECT_TRUE macros)
 */
#include <stdio.h>
#include "tot_api.h"

#define EXPECT_OK(rc, step) do { \
    int _rc = (rc); \
    if (_rc != TOT_OK) { \
        fprintf(stderr, "FAIL " step ": expected TOT_OK (0), got %d\n", _rc); \
        return (__LINE__); \
    } \
} while (0)

#define EXPECT_TRUE(cond, step) do { \
    if (!(cond)) { \
        fprintf(stderr, "FAIL " step ": condition false: " #cond "\n"); \
        return (__LINE__); \
    } \
} while (0)

int main(void) {
    tot_state_t s;

    /* ---- 1: init ---- */
    EXPECT_OK(tot_init(), "tot_init");

    /* ---- 2: set_param: tr DT (transport time step) ---- */
    EXPECT_OK(tot_set_param("tr:DT", 0.001), "tot_set_param tr:DT");

    /* ---- 3: idempotent re-init ---- */
    EXPECT_OK(tot_init(), "tot_init #2 (idempotent)");

    /* ---- 4: run zero steps (smoke; proves the fan-out path is alive
     *        without invoking the inner trcalc loop body) ---- */
    EXPECT_OK(tot_run(0), "tot_run(0)");

    /* ---- 5: get_state — TR-authoritative slots must be populated
     *        with the default-sized grid (NRMAX=50, NSMAX=2 from
     *        trinit.f90 defaults). ---- */
    EXPECT_OK(tot_get_state(&s), "tot_get_state");
    EXPECT_TRUE(s.tr_present == 1, "tr_present == 1 after init");
    EXPECT_TRUE(s.nrmax > 0, "nrmax > 0 after init");
    EXPECT_TRUE(s.nsmax > 0, "nsmax > 0 after init");

    /* ---- 6: a non-zero run step (advance one transport step). ---- */
    EXPECT_OK(tot_run(1), "tot_run(1)");
    EXPECT_OK(tot_get_state(&s), "tot_get_state #2");
    EXPECT_TRUE(s.nt >= 1, "nt advanced after tot_run(1)");

    /* ---- 7: finalize + idempotent double-finalize ---- */
    EXPECT_OK(tot_finalize(), "tot_finalize");
    EXPECT_OK(tot_finalize(), "tot_finalize #2 (idempotent)");

    /* ---- 8: re-init after finalize must succeed (heap-reuse smoke). ---- */
    EXPECT_OK(tot_init(),     "tot_init after finalize (heap reuse)");
    EXPECT_OK(tot_finalize(), "tot_finalize #3");

    printf("OK: tot full-cycle (init/set_param/run/get_state/finalize"
           " + idempotent + heap-reuse)\n");
    return 0;
}
