/*
 * test_smoke.c
 *
 * Phase L-3 smoke driver for the EQ C ABI.
 *
 * Exercises the entry points:
 *   eq_init          -> expected EQ_OK
 *   eq_get_state     -> expected EQ_OK; prints grid dimensions
 *   eq_set_param     -> L-3: real dispatch; RR=6.5 should succeed
 *   eq_set_param_str -> L-3: NEW; KNAMEQ should succeed
 *   eq_finalize      -> expected EQ_OK
 *
 * eq_run is driven through its mode contract on the defaults: -1 is
 * EQ_ERR_INVALID, 2 EQ_ERR_NOT_IMPL, 1 (the equilibrium-file load)
 * EQ_ERR_CALC_FAILED because the default MODELG=2 names no file, and
 * 0 (the Grad-Shafranov solve, no file) EQ_OK; after eq_finalize it is
 * EQ_ERR_NOT_INIT, also for -1.
 *
 * The test does NOT assert on any numerical value beyond the error
 * codes and raxis > 0 (EQCALC) and qaxis > 0 (EQCALQ) after
 * eq_run(0); the real regression story is that
 * `make eq` still produces a byte-identical binary, which is enforced
 * by the build rules in eq/Makefile (OBJ_API is not linked into
 * libeq.a).
 */
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "eq_api.h"

int main(void) {
    int rc;
    eq_state_t state;

    printf("eq_api L-3 smoke\n");
    printf("  sizeof(eq_state_t) = %zu bytes\n", sizeof(eq_state_t));

    rc = eq_init();
    printf("  eq_init       rc=%d (expect %d=EQ_OK)\n", rc, EQ_OK);
    assert(rc == EQ_OK);

    memset(&state, 0xAA, sizeof(state));
    rc = eq_get_state(&state);
    printf("  eq_get_state  rc=%d (expect %d=EQ_OK)\n", rc, EQ_OK);
    assert(rc == EQ_OK);
    printf("    nrgmax=%d nzgmax=%d npsmax=%d\n",
           state.nrgmax, state.nzgmax, state.npsmax);
    printf("    nrmax=%d  nthmax=%d nsumax=%d\n",
           state.nrmax, state.nthmax, state.nsumax);
    printf("    raxis=%g zaxis=%g qaxis=%g psi0=%g betap=%g\n",
           state.raxis, state.zaxis, state.qaxis,
           state.psi0,  state.betap);

    rc = eq_run(-1);
    printf("  eq_run(-1)    rc=%d (expect %d=EQ_ERR_INVALID)\n",
           rc, EQ_ERR_INVALID);
    assert(rc == EQ_ERR_INVALID);

    rc = eq_run(2);
    printf("  eq_run(2)     rc=%d (expect %d=EQ_ERR_NOT_IMPL)\n",
           rc, EQ_ERR_NOT_IMPL);
    assert(rc == EQ_ERR_NOT_IMPL);

    /* Mode 1 reads the file of the format MODELG names (EQ_READ,
     * eqfile.f90); the default MODELG=2 names none. */
    rc = eq_run(1);
    printf("  eq_run(1)     rc=%d (expect %d=EQ_ERR_CALC_FAILED)\n",
           rc, EQ_ERR_CALC_FAILED);
    assert(rc == EQ_ERR_CALC_FAILED);

    /* Mode 0: the Grad-Shafranov solve (EQCALC, then EQCALQ). */
    rc = eq_run(0);
    printf("  eq_run(0)     rc=%d (expect %d=EQ_OK)\n", rc, EQ_OK);
    assert(rc == EQ_OK);

    rc = eq_get_state(&state);
    printf("  eq_get_state  rc=%d (expect %d=EQ_OK)\n", rc, EQ_OK);
    assert(rc == EQ_OK);
    printf("    raxis=%g zaxis=%g qaxis=%g psi0=%g betap=%g\n",
           state.raxis, state.zaxis, state.qaxis,
           state.psi0,  state.betap);
    assert(state.raxis > 0.0);   /* EQCALC */
    assert(state.qaxis > 0.0);   /* EQCALQ */

    /* L-3: eq_set_param now dispatches to the real registry.
     * Setting a scalar (e.g. RR=6.5) should return EQ_OK. */
    rc = eq_set_param("RR", 6.5);
    printf("  eq_set_param RR=6.5     rc=%d (expect %d=EQ_OK)\n",
           rc, EQ_OK);
    assert(rc == EQ_OK);

    rc = eq_set_param("BB", 5.3);
    printf("  eq_set_param BB=5.3     rc=%d (expect %d=EQ_OK)\n",
           rc, EQ_OK);
    assert(rc == EQ_OK);

    /* 0-origin subscript sanity for PSIB. */
    rc = eq_set_param("PSIB[0]", 2.0);
    printf("  eq_set_param PSIB[0]=2  rc=%d (expect %d=EQ_OK)\n",
           rc, EQ_OK);
    assert(rc == EQ_OK);

    rc = eq_set_param("PSIB[5]", 0.0);
    printf("  eq_set_param PSIB[5]=0  rc=%d (expect %d=EQ_OK)\n",
           rc, EQ_OK);
    assert(rc == EQ_OK);

    /* Out-of-range subscripts for both array kinds. */
    rc = eq_set_param("PSIB[6]", 1.0);
    printf("  eq_set_param PSIB[6]    rc=%d (expect %d=EQ_ERR_INVALID)\n",
           rc, EQ_ERR_INVALID);
    assert(rc == EQ_ERR_INVALID);

    rc = eq_set_param("RIPFC[0]", 1.0);
    printf("  eq_set_param RIPFC[0]   rc=%d (expect %d=EQ_ERR_INVALID)\n",
           rc, EQ_ERR_INVALID);
    assert(rc == EQ_ERR_INVALID);

    /* Unknown parameter name. */
    rc = eq_set_param("NO_SUCH_PARAM", 0.0);
    printf("  eq_set_param NO_SUCH    rc=%d (expect %d=EQ_ERR_INVALID)\n",
           rc, EQ_ERR_INVALID);
    assert(rc == EQ_ERR_INVALID);

    /* String setter (L-3). */
    rc = eq_set_param_str("KNAMEQ", "eqdata_smoke");
    printf("  eq_set_param_str KNAMEQ rc=%d (expect %d=EQ_OK)\n",
           rc, EQ_OK);
    assert(rc == EQ_OK);

    rc = eq_set_param_str("NO_SUCH_STR", "x");
    printf("  eq_set_param_str BAD    rc=%d (expect %d=EQ_ERR_INVALID)\n",
           rc, EQ_ERR_INVALID);
    assert(rc == EQ_ERR_INVALID);

    rc = eq_finalize();
    printf("  eq_finalize   rc=%d (expect %d=EQ_OK)\n", rc, EQ_OK);
    assert(rc == EQ_OK);

    /* After finalize the not-initialized contract must hold again. */
    rc = eq_run(0);
    printf("  eq_run post-fin rc=%d (expect %d=EQ_ERR_NOT_INIT)\n",
           rc, EQ_ERR_NOT_INIT);
    assert(rc == EQ_ERR_NOT_INIT);

    /* NOT_INIT comes before the check of the mode. */
    rc = eq_run(-1);
    printf("  eq_run(-1) post-fin rc=%d (expect %d=EQ_ERR_NOT_INIT)\n",
           rc, EQ_ERR_NOT_INIT);
    assert(rc == EQ_ERR_NOT_INIT);

    rc = eq_set_param("RR", 3.0);
    printf("  eq_set_param post-fin rc=%d (expect %d=EQ_ERR_NOT_INIT)\n",
           rc, EQ_ERR_NOT_INIT);
    assert(rc == EQ_ERR_NOT_INIT);

    rc = eq_set_param_str("KNAMEQ", "x");
    printf("  eq_set_param_str post-fin rc=%d (expect %d=EQ_ERR_NOT_INIT)\n",
           rc, EQ_ERR_NOT_INIT);
    assert(rc == EQ_ERR_NOT_INIT);

    /* Silence unused-variable warnings for NaN check helpers. */
    (void) isnan(0.0);

    printf("eq_api L-3 smoke: PASS\n");
    return 0;
}
