/*
 * Phase L-6: C ABI negative tests for TASK/WRX.
 *
 * The happy paths for wrx_init -> wrx_set_param -> wrx_run ->
 * wrx_get_state -> wrx_finalize are covered by test_smoke.c,
 * test_param.c, test_run.c and test_run_so.c. This driver concentrates
 * on the *rejection* contracts stated in wrx_api.h:
 *
 *   1. wrx_get_state / wrx_run / wrx_set_param must report a non-zero
 *      error code when called before wrx_init or after wrx_finalize.
 *   2. wrx_set_param must reject clearly bogus names.
 *   3. wrx_set_param must reject out-of-range array subscripts.
 *   4. wrx_set_param must reject malformed subscript syntax.
 *   5. wrx_init must be safe to call again after wrx_finalize
 *      (re-init).
 *   6. wrx_finalize must be safe to call twice back-to-back
 *      (idempotent).
 *
 * We deliberately do NOT call wrx_run here -- wr_calc_pwr (called from
 * wr_exec via SRCS_CORE's wrcalpwr.f90) invokes the real libgrf grd1d
 * module procedure, which cannot be stubbed at link time, and the
 * whole graphics path is best-avoided in automated test drivers. The
 * run-path reject behaviour is exercised at pre-init and post-finalize
 * via wrx_run(1) returning non-zero -- that only needs symbol-level
 * reachability, not a successful call.
 *
 * Each failure returns a distinct exit code (the __LINE__ of the check
 * that tripped) so regressions point at the exact contract that
 * slipped.
 */
#include <stdio.h>
#include "wrx_api.h"

/* Accept any non-zero code for "rejected"; we don't pin
 * WRX_ERR_INVALID vs WRX_ERR_NOT_INIT vs WRX_ERR_NOT_IMPL because
 * different error paths inside wrx_api.f90 may map the negative case
 * to either legitimately. The happy-path tests (test_smoke.c /
 * test_param.c / test_run_so.c) already pin WRX_OK (=0). */
#define EXPECT_ERR(rc, step) do { \
    if ((rc) == 0) { \
        fprintf(stderr, "FAIL " step ": expected non-zero rc, got 0\n"); \
        return (__LINE__); \
    } \
} while (0)

#define EXPECT_OK(rc, step) do { \
    if ((rc) != 0) { \
        fprintf(stderr, "FAIL " step ": expected 0, got %d\n", (rc)); \
        return (__LINE__); \
    } \
} while (0)

int main(void) {
    int rc;
    /* wrx_state_t is ~70KB; stack-allocating risks overflow on threads
     * or under valgrind's main-stack tracker. BSS (static) is pre-zeroed
     * and size-independent. */
    static wrx_state_t s;

    /* Line-buffer stdout so the Fortran runtime (which may share the
     * FILE* with libgrf's GSOPEN prompt) cannot swallow progress
     * lines when the driver runs under `printf '0\nc\n' | test_* >
     * log`. */
    setvbuf(stdout, NULL, _IOLBF, 0);

    /* ---- 1: calls before init must be rejected ------------------ */
    rc = wrx_get_state(&s);
    EXPECT_ERR(rc, "get_state-before-init");
    rc = wrx_run(1);
    EXPECT_ERR(rc, "run-before-init");
    rc = wrx_set_param("RR", 6.2);
    EXPECT_ERR(rc, "set_param-before-init");

    /* ---- init once ---------------------------------------------- */
    EXPECT_OK(wrx_init(), "wrx_init #1");

    /* ---- 2: unknown parameter names ----------------------------- */
    rc = wrx_set_param("DEFINITELY_NOT_A_PARAM", 0.0);
    EXPECT_ERR(rc, "set_param-unknown-name");

    /* Empty name is also invalid. */
    rc = wrx_set_param("", 0.0);
    EXPECT_ERR(rc, "set_param-empty-name");

    /* ---- 3: malformed subscript syntax -------------------------- */
    rc = wrx_set_param("PN[", 1.0);
    EXPECT_ERR(rc, "set_param-PN[");
    rc = wrx_set_param("PN]", 1.0);
    EXPECT_ERR(rc, "set_param-PN]");
    rc = wrx_set_param("PN[abc]", 1.0);
    EXPECT_ERR(rc, "set_param-PN[abc]");

    /* ---- 4: out-of-range array subscripts ----------------------- */
    rc = wrx_set_param("PN[99999]", 1.0);
    EXPECT_ERR(rc, "set_param-PN[99999]");

    /* ---- 5: double finalize is idempotent ----------------------- */
    EXPECT_OK(wrx_finalize(), "wrx_finalize #1");
    /* Second finalize: must be idempotent (either OK or a specific
     * error code; we accept *anything* that doesn't crash -- note the
     * (void) cast). The contract is "safe to call twice" not "returns
     * OK twice". */
    (void) wrx_finalize();

    /* ---- 6: post-finalize: operations on closed state are rejected - */
    rc = wrx_get_state(&s);
    EXPECT_ERR(rc, "get_state-after-finalize");
    rc = wrx_run(1);
    EXPECT_ERR(rc, "run-after-finalize");

    /* ---- 7: re-init after finalize succeeds --------------------- */
    EXPECT_OK(wrx_init(), "wrx_init #2 (re-init after finalize)");
    /* After re-init, a normal set_param still works. */
    EXPECT_OK(wrx_set_param("RR", 6.2),
              "set_param-after-reinit");
    EXPECT_OK(wrx_finalize(), "wrx_finalize #2");

    printf("OK: Layer 2 negative tests "
           "(init/finalize/name/subscript/reinit)\n");
    fflush(stdout);
    return 0;
}
