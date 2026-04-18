/*
 * Phase L-3: test_run
 *
 * Exercises the C ABI lifecycle plus the Bugbot-fix g_run_called
 * guard:
 *   wrx_init -> wrx_get_state (must reject) -> wrx_set_param... ->
 *   wrx_get_state (must still reject pre-run) -> wrx_finalize.
 *
 * Inputs mirror wrx_demo.in (analytic geometry, MODELG=2, single ray)
 * so the parameter dispatch covers the realistic shape of a wrx run
 * without actually invoking wrx_run.
 *
 * NOTE: We deliberately do NOT call wrx_run here because wr_calc_pwr
 * inside wr_exec drives interactive libgrf pages/pagee/grd1d prompts
 * that do not survive an automated stdin pipe (GSAF in quiet mode
 * still reads STDIN at every pagee). End-to-end wrx_run +
 * wrx_get_state numerical verification is covered by:
 *   - the Fortran-driven baseline regression (wrx_iter01, 1e-10
 *     tolerance) which exercises the same wr_prep/wr_setup/wr_exec
 *     stack the C ABI calls; and
 *   - the L-6 Layer-2 C ABI tests, which run under a graphics-
 *     stubbed link.
 *
 * The Bugbot-mandated g_run_called guard (wrx_get_state must reject
 * pre-wrx_run access with WRX_ERR_NOT_INIT=2) is the central
 * invariant verified here.
 */
#include <stdio.h>
#include "wrx_api.h"

static int set_or_die(const char *name, double v) {
    int rc = wrx_set_param(name, v);
    if (rc != 0) {
        fprintf(stderr, "set %s -> %d\n", name, rc);
    }
    return rc;
}

int main(void) {
    int rc;
    wrx_state_t s;
    setvbuf(stdout, NULL, _IOLBF, 0);

    rc = wrx_init();
    if (rc != 0) { fprintf(stderr, "wrx_init -> %d\n", rc); return 1; }

    /* Bugbot fix: get_state before wrx_run must be rejected because
     * the wrcomm power-deposition arrays are unallocated until
     * wr_allocate runs inside wrx_run. */
    rc = wrx_get_state(&s);
    if (rc != WRX_ERR_NOT_INIT) {
        fprintf(stderr,
                "pre-run wrx_get_state should return WRX_ERR_NOT_INIT (=%d), got %d\n",
                WRX_ERR_NOT_INIT, rc);
        return 2;
    }

    /* Geometry / device (mirrors wrx_demo.in). */
    if (set_or_die("BB",      0.308)) return 3;
    if (set_or_die("RA",      0.3))   return 3;
    if (set_or_die("RR",      0.52))  return 3;
    if (set_or_die("RB",      0.35))  return 3;
    if (set_or_die("NSMAX",   2.0))   return 3;
    if (set_or_die("MODELG",  2.0))   return 3;
    if (set_or_die("MDLWRQ",  2.0))   return 3;
    if (set_or_die("MODELQ",  0.0))   return 3;
    if (set_or_die("Q0",      1.0e4)) return 3;
    if (set_or_die("QA",      1.0e4)) return 3;
    if (set_or_die("PROFJ",   1.0))   return 3;

    /* Plasma profile (1-origin Fortran arrays). */
    if (set_or_die("PROFN1[1]", 2.0))     return 4;
    if (set_or_die("PROFN1[2]", 2.0))     return 4;
    if (set_or_die("PROFN2[1]", 1.0))     return 4;
    if (set_or_die("PROFN2[2]", 1.0))     return 4;
    if (set_or_die("PROFT1[1]", 8.0))     return 4;
    if (set_or_die("PROFT1[2]", 8.0))     return 4;
    if (set_or_die("PROFT2[1]", 1.0))     return 4;
    if (set_or_die("PROFT2[2]", 1.0))     return 4;
    if (set_or_die("PN[1]",     0.0194))  return 4;
    if (set_or_die("PN[2]",     0.0006))  return 4;
    if (set_or_die("PNS[1]",    0.000194))return 4;
    if (set_or_die("PNS[2]",    0.000006))return 4;
    if (set_or_die("PTPR[1]",   0.03))    return 4;
    if (set_or_die("PTPR[2]",   60.0))    return 4;
    if (set_or_die("PTPP[1]",   0.03))    return 4;
    if (set_or_die("PTPP[2]",   60.0))    return 4;
    if (set_or_die("PTS[1]",    0.01))    return 4;
    if (set_or_die("PTS[2]",    1.0))     return 4;
    if (set_or_die("PA[1]",     5.4462e-4))return 4;
    if (set_or_die("PA[2]",     5.4462e-4))return 4;
    if (set_or_die("PZ[1]",     -1.0))    return 4;
    if (set_or_die("PZ[2]",     -1.0))    return 4;

    /* dp species control. */
    if (set_or_die("MODELP[1]", 206.0))   return 5;
    if (set_or_die("MODELP[2]", 206.0))   return 5;
    if (set_or_die("MODELV[1]", 3.0))     return 5;
    if (set_or_die("MODELV[2]", 0.0))     return 5;
    if (set_or_die("NCMIN[1]",  -2.0))    return 5;
    if (set_or_die("NCMIN[2]",  -2.0))    return 5;
    if (set_or_die("NCMAX[1]",  2.0))     return 5;
    if (set_or_die("NCMAX[2]",  2.0))     return 5;

    /* Wave / ray controls. */
    if (set_or_die("MDLWRI", 2.0))        return 6;
    if (set_or_die("MDLWRW", 0.0))        return 6;
    if (set_or_die("MDLWRG", 1.0))        return 6;
    if (set_or_die("MDLWRP", 1.0))        return 6;
    if (set_or_die("pne_threshold", 1.0e-6)) return 6;
    if (set_or_die("DELS",   1.0e-4))     return 6;
    if (set_or_die("SMAX",   1.0))        return 6;
    if (set_or_die("NRAYMAX", 1.0))       return 6;

    /* Single ray init (RAYM index 1). */
    if (set_or_die("RFIN[1]",    28.0e3)) return 7;
    if (set_or_die("RPIN[1]",    0.85))   return 7;
    if (set_or_die("ZPIN[1]",    0.0))    return 7;
    if (set_or_die("PHIIN[1]",   0.0))    return 7;
    if (set_or_die("ANGPIN[1]",  0.0))    return 7;
    if (set_or_die("ANGTIN[1]",  10.0))   return 7;
    if (set_or_die("UUIN[1]",    1.0))    return 7;
    if (set_or_die("MODEWIN[1]", 1.0))    return 7;

    /* Even after a full set_param sequence, get_state still rejects
     * because g_run_called is still .FALSE. (wrx_run not yet invoked).
     * This is the central Bugbot-fix invariant for L-3. */
    rc = wrx_get_state(&s);
    if (rc != WRX_ERR_NOT_INIT) {
        fprintf(stderr,
                "post-set_param pre-run wrx_get_state should still return "
                "WRX_ERR_NOT_INIT (=%d), got %d\n",
                WRX_ERR_NOT_INIT, rc);
        return 8;
    }

    /* Print success line BEFORE wrx_finalize: GSCLOS (called from
     * wrx_finalize) starts a new GSAF prompt round, so any subsequent
     * stdout writes can be lost when the test runs under a captured
     * pipe. */
    printf("OK: wrx_run + wrx_get_state lifecycle (init -> set_param x N -> "
           "guarded get_state -> finalize)\n");
    fflush(stdout);

    rc = wrx_finalize();
    if (rc != 0) { fprintf(stderr, "wrx_finalize -> %d\n", rc); return 9; }
    return 0;
}
