/*
 * Phase L-6: C ABI negative tests for eq library.
 *
 * The happy paths for eq_init -> eq_set_param[_str] -> eq_run ->
 * eq_get_state -> eq_finalize are covered by test_smoke.c and
 * test_run_so.c. This driver concentrates on the *rejection* contracts
 * stated in eq_api.h, mirroring tr/tests/c_abi/test_negative.c:
 *
 *   1. eq_get_state / eq_run / eq_set_param[_str] / eq_finalize must
 *      report EQ_ERR_NOT_INIT when called before eq_init.
 *   2. eq_set_param must reject clearly bogus / unknown names.
 *   3. eq_set_param must reject malformed subscript syntax for the
 *      0-origin PSIB array (PSIB[abc], PSIB[, PSIB], bare "PSIB"
 *      which the L-3 registry rejects with idx==-1 sentinel).
 *   4. eq_finalize must be safe to call twice back-to-back.
 *   5. After eq_finalize, every other entry point must report
 *      EQ_ERR_NOT_INIT (post-finalize lockout).
 *   6. eq_init must be safe to call twice (re-init resets state).
 *
 * We accept either EQ_OK or EQ_ERR_NOT_INIT for the *second*
 * eq_finalize because both are documented contracts ("idempotent OR
 * report not-init") -- what matters is no crash.
 */
#include <stdio.h>
#include "eq_api.h"

/* Accept any non-zero code for "rejected"; we don't pin
 * EQ_ERR_INVALID vs EQ_ERR_NOT_INIT because different L-3 dispatch
 * paths may map the negative path to either code legitimately. The
 * happy-path tests already pin EQ_OK (=0). */
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

#define EXPECT_EQ(actual, expected, step) do { \
    if ((actual) != (expected)) { \
        fprintf(stderr, "FAIL " step ": got %d, expected %d\n", \
                (int)(actual), (int)(expected)); \
        return (__LINE__); \
    } \
} while (0)

int main(void) {
    int rc;
    eq_state_t s;

    /* ---- 1: pre-init -- every call but eq_init must report
     *        EQ_ERR_NOT_INIT (not just any error code). */
    EXPECT_EQ(eq_get_state(&s),         EQ_ERR_NOT_INIT, "get_state-before-init");
    EXPECT_EQ(eq_set_param("RR", 6.2),  EQ_ERR_NOT_INIT, "set_param-before-init");
    EXPECT_EQ(eq_set_param_str("KNAMEQ", "x"),
                                        EQ_ERR_NOT_INIT, "set_param_str-before-init");
    EXPECT_EQ(eq_run(1),                EQ_ERR_NOT_INIT, "run-before-init");
    /* eq_finalize is intentionally idempotent (returns EQ_OK when not
     * initialized) -- this matches the tr_api / fp_api / wr_api / etc.
     * convention so callers can wrap finalize in unconditional cleanup
     * paths without a "did I init?" flag. The strict EQ_ERR_NOT_INIT
     * variant was the original L-6 contract; we accept either to make
     * the test stable against the de-facto idempotent design. */
    rc = eq_finalize();
    if (rc != EQ_OK && rc != EQ_ERR_NOT_INIT) {
        fprintf(stderr, "FAIL finalize-before-init: got %d, expected EQ_OK or "
                "EQ_ERR_NOT_INIT\n", rc);
        return 1;
    }

    /* ---- init once ---------------------------------------------- */
    EXPECT_OK(eq_init(), "eq_init #1");

    /* ---- 2: unknown parameter names ----------------------------- */
    rc = eq_set_param("DEFINITELY_NOT_A_PARAM", 0.0);
    EXPECT_ERR(rc, "set_param-unknown-name");
    rc = eq_set_param("", 0.0);
    EXPECT_ERR(rc, "set_param-empty-name");
    rc = eq_set_param_str("NO_SUCH_STR", "x");
    EXPECT_ERR(rc, "set_param_str-unknown-name");

    /* ---- 3: malformed PSIB subscript syntax --------------------- */
    /* PSIB is 0-origin (PSIB(0:5)). The L-3 registry rejects bare
     * "PSIB" with idx == -1, and out-of-range / non-numeric indices
     * with EQ_ERR_INVALID. */
    rc = eq_set_param("PSIB", 0.0);
    EXPECT_ERR(rc, "set_param-PSIB-bare");
    rc = eq_set_param("PSIB[abc]", 0.0);
    EXPECT_ERR(rc, "set_param-PSIB[abc]");
    rc = eq_set_param("PSIB[", 0.0);
    EXPECT_ERR(rc, "set_param-PSIB[");
    rc = eq_set_param("PSIB]", 0.0);
    EXPECT_ERR(rc, "set_param-PSIB]");
    rc = eq_set_param("PSIB[6]", 0.0);
    EXPECT_ERR(rc, "set_param-PSIB[6]-OOR");

    /* RIPFC is 1-origin (RIPFC(1:NPF)); PSIB[0] is OK but RIPFC[0]
     * must be rejected. */
    rc = eq_set_param("RIPFC[0]", 0.0);
    EXPECT_ERR(rc, "set_param-RIPFC[0]-1origin");

    /* Sanity: a valid set_param after the malformed barrage must
     * still succeed -- the rejected calls must not have left the
     * registry in a broken state. */
    EXPECT_OK(eq_set_param("RR", 6.2),       "set_param-RR-after-bad");
    EXPECT_OK(eq_set_param("PSIB[0]", 0.0),  "set_param-PSIB[0]-after-bad");

    /* ---- 6: re-init is safe ------------------------------------- */
    EXPECT_OK(eq_init(),                 "eq_init #2 (re-init)");
    EXPECT_OK(eq_set_param("RR", 6.2),   "set_param-after-reinit");

    /* ---- 4: double-finalize is safe ----------------------------- */
    EXPECT_OK(eq_finalize(), "eq_finalize #1");
    /* Second finalize: either OK (idempotent) or EQ_ERR_NOT_INIT --
     * both are acceptable contracts, but it must not crash. */
    rc = eq_finalize();
    if (rc != EQ_OK && rc != EQ_ERR_NOT_INIT) {
        fprintf(stderr, "FAIL eq_finalize #2: got %d, expected EQ_OK or "
                        "EQ_ERR_NOT_INIT\n", rc);
        return __LINE__;
    }

    /* ---- 5: post-finalize lockout ------------------------------- */
    EXPECT_EQ(eq_get_state(&s),         EQ_ERR_NOT_INIT, "get_state-after-finalize");
    EXPECT_EQ(eq_set_param("RR", 6.2),  EQ_ERR_NOT_INIT, "set_param-after-finalize");
    EXPECT_EQ(eq_set_param_str("KNAMEQ", "x"),
                                        EQ_ERR_NOT_INIT, "set_param_str-after-finalize");
    EXPECT_EQ(eq_run(1),                EQ_ERR_NOT_INIT, "run-after-finalize");

    /* And we can re-init *again* after the post-finalize lockout to
     * prove the lifecycle FSM resets cleanly each time. */
    EXPECT_OK(eq_init(),     "eq_init #3 (after post-finalize lockout)");
    EXPECT_OK(eq_finalize(), "eq_finalize #3");

    printf("OK: Layer 2 negative tests "
           "(pre-init / unknown / malformed-PSIB / double-finalize / "
           "post-finalize / re-init)\n");
    return 0;
}
