/*
 * Phase L-4: test_run_so (wrx)
 *
 * dlopen libwrxapi.so, dlsym the 5 C ABI entry points, and exercise the
 * lifecycle (init -> set_param x N -> guarded get_state -> finalize).
 * This proves the shared object is loadable, has the expected external
 * symbols, and that the Fortran-side lifecycle works when driven from
 * a C binary that never saw libwr.a.
 *
 * Usage:
 *   WRXLIB_PATH=/path/to/libwrxapi.so ./test_run_so
 *   (WRXLIB_PATH optional, defaults to ./libwrxapi.so)
 *
 * Return values mirror tests/c_abi/test_run.c so debugging is easy:
 *   0  = OK
 *   1..8 = step that failed (same numbering as test_run.c)
 *   90 = dlopen failed
 *   91 = dlsym failed (one of the 5 entry points missing)
 *
 * NOTE: Mirrors wrx/tests/c_abi/test_run.c (not wr/tests/c_abi/
 * test_run_so.c). Like the static test_run.c, we deliberately skip
 * wrx_run here because wr_calc_pwr (called from wr_exec via SRCS_CORE's
 * wrcalpwr.f90) invokes the real libgrf grd1d module procedure, which
 * cannot be stubbed at link time (module procedures resolve at compile
 * time, not at link time). End-to-end wrx_run + wrx_get_state
 * numerical verification is covered by the Fortran-driven baseline
 * regression (wrx_iter01, 1e-10 tolerance) which exercises the same
 * wr_prep/wr_setup/wr_exec stack the C ABI would call.
 *
 * The Bugbot-mandated g_run_called guard (wrx_get_state must reject
 * pre-wrx_run access with WRX_ERR_NOT_INIT=2) is verified here via the
 * dlopen path.
 *
 * Mirrors wr/tests/c_abi/test_run_so.c (Phase L-4, PR #42) structure
 * (dlopen/dlsym/dlclose scaffolding) but with the wrx-specific
 * lifecycle (skip wrx_run per above).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>

#include "wrx_api.h"

typedef int  (*wrx_init_fn)(void);
typedef int  (*wrx_run_fn)(int);
typedef int  (*wrx_set_param_fn)(const char *, double);
typedef int  (*wrx_get_state_fn)(wrx_state_t *);
typedef int  (*wrx_finalize_fn)(void);

#define SET(fn, name, val)                                                \
    do {                                                                  \
        int _rc = (fn)((name), (val));                                    \
        if (_rc != 0) {                                                   \
            fprintf(stderr, "FAIL set %s=%g -> %d\n", (name), (val), _rc);\
            dlclose(h);                                                   \
            return 3;                                                     \
        }                                                                 \
    } while (0)

int main(void) {
    const char *path = getenv("WRXLIB_PATH");
    if (!path || !*path) path = "./libwrxapi.so";

    /* RTLD_LAZY: libwrxapi.so may contain unresolved references to any
     * graphics symbols not covered by wrx_graphics_stubs.f90 that are
     * only reached through pathological eq/pl code paths. The C ABI
     * happy path never calls those, so defer resolution to first
     * call. RTLD_NOW would refuse to load the .so even though we never
     * touch the missing routines. */
    void *h = dlopen(path, RTLD_LAZY);
    if (!h) {
        fprintf(stderr, "dlopen(%s) failed: %s\n", path, dlerror());
        return 90;
    }

    wrx_init_fn       f_init       = (wrx_init_fn)       dlsym(h, "wrx_init");
    wrx_run_fn        f_run        = (wrx_run_fn)        dlsym(h, "wrx_run");
    wrx_set_param_fn  f_set_param  = (wrx_set_param_fn)  dlsym(h, "wrx_set_param");
    wrx_get_state_fn  f_get_state  = (wrx_get_state_fn)  dlsym(h, "wrx_get_state");
    wrx_finalize_fn   f_finalize   = (wrx_finalize_fn)   dlsym(h, "wrx_finalize");
    if (!f_init || !f_run || !f_set_param || !f_get_state || !f_finalize) {
        fprintf(stderr,
                "dlsym missing one of wrx_{init,run,set_param,get_state,finalize}:"
                " init=%p run=%p set=%p get=%p fin=%p\n",
                (void*)f_init, (void*)f_run, (void*)f_set_param,
                (void*)f_get_state, (void*)f_finalize);
        dlclose(h);
        return 91;
    }

    int rc;
    /* wrx_state_t is ~70KB; stack-allocating risks overflow on threads
     * or under valgrind's main-stack tracker. BSS (static) is pre-zeroed
     * and size-independent. */
    static wrx_state_t s;
    setvbuf(stdout, NULL, _IOLBF, 0);

    rc = f_init();
    if (rc != 0) { fprintf(stderr, "FAIL wrx_init -> %d\n", rc); dlclose(h); return 1; }

    /* Pre-set_param get_state must reject because g_run_called=.FALSE. */
    rc = f_get_state(&s);
    if (rc != WRX_ERR_NOT_INIT) {
        fprintf(stderr,
                "pre-run wrx_get_state should return WRX_ERR_NOT_INIT (=%d), got %d\n",
                WRX_ERR_NOT_INIT, rc);
        dlclose(h);
        return 2;
    }

    /* Parameters mirror tests/c_abi/test_run.c (wrx_demo.in: analytic
     * geometry, MODELG=2, single ray). */
    SET(f_set_param, "BB",      0.308);
    SET(f_set_param, "RA",      0.3);
    SET(f_set_param, "RR",      0.52);
    SET(f_set_param, "RB",      0.35);
    SET(f_set_param, "NSMAX",   2.0);
    SET(f_set_param, "MODELG",  2.0);
    SET(f_set_param, "MDLWRQ",  2.0);
    SET(f_set_param, "MODELQ",  0.0);
    SET(f_set_param, "Q0",      1.0e4);
    SET(f_set_param, "QA",      1.0e4);
    SET(f_set_param, "PROFJ",   1.0);

    SET(f_set_param, "PROFN1[1]", 2.0);
    SET(f_set_param, "PROFN1[2]", 2.0);
    SET(f_set_param, "PROFN2[1]", 1.0);
    SET(f_set_param, "PROFN2[2]", 1.0);
    SET(f_set_param, "PROFT1[1]", 8.0);
    SET(f_set_param, "PROFT1[2]", 8.0);
    SET(f_set_param, "PROFT2[1]", 1.0);
    SET(f_set_param, "PROFT2[2]", 1.0);
    SET(f_set_param, "PN[1]",     0.0194);
    SET(f_set_param, "PN[2]",     0.0006);
    SET(f_set_param, "PNS[1]",    0.000194);
    SET(f_set_param, "PNS[2]",    0.000006);
    SET(f_set_param, "PTPR[1]",   0.03);
    SET(f_set_param, "PTPR[2]",   60.0);
    SET(f_set_param, "PTPP[1]",   0.03);
    SET(f_set_param, "PTPP[2]",   60.0);
    SET(f_set_param, "PTS[1]",    0.01);
    SET(f_set_param, "PTS[2]",    1.0);
    SET(f_set_param, "PA[1]",     5.4462e-4);
    SET(f_set_param, "PA[2]",     5.4462e-4);
    SET(f_set_param, "PZ[1]",     -1.0);
    SET(f_set_param, "PZ[2]",     -1.0);

    SET(f_set_param, "MODELP[1]", 206.0);
    SET(f_set_param, "MODELP[2]", 206.0);
    SET(f_set_param, "MODELV[1]", 3.0);
    SET(f_set_param, "MODELV[2]", 0.0);
    SET(f_set_param, "NCMIN[1]",  -2.0);
    SET(f_set_param, "NCMIN[2]",  -2.0);
    SET(f_set_param, "NCMAX[1]",  2.0);
    SET(f_set_param, "NCMAX[2]",  2.0);

    SET(f_set_param, "MDLWRI", 2.0);
    SET(f_set_param, "MDLWRW", 0.0);
    SET(f_set_param, "MDLWRG", 1.0);
    SET(f_set_param, "MDLWRP", 1.0);
    SET(f_set_param, "pne_threshold", 1.0e-6);
    SET(f_set_param, "DELS",   1.0e-4);
    SET(f_set_param, "SMAX",   1.0);
    SET(f_set_param, "NRAYMAX", 1.0);

    /* Single ray init (RAYM index 1). */
    SET(f_set_param, "RFIN[1]",    28.0e3);
    SET(f_set_param, "RPIN[1]",    0.85);
    SET(f_set_param, "ZPIN[1]",    0.0);
    SET(f_set_param, "PHIIN[1]",   0.0);
    SET(f_set_param, "ANGPIN[1]",  0.0);
    SET(f_set_param, "ANGTIN[1]",  10.0);
    SET(f_set_param, "UUIN[1]",    1.0);
    SET(f_set_param, "MODEWIN[1]", 1.0);

    /* Post-set_param pre-run get_state must still reject (g_run_called
     * still .FALSE.). This is the central Bugbot-fix invariant for L-3
     * re-verified via the dlopen path. */
    rc = f_get_state(&s);
    if (rc != WRX_ERR_NOT_INIT) {
        fprintf(stderr,
                "post-set_param pre-run wrx_get_state should still return "
                "WRX_ERR_NOT_INIT (=%d), got %d\n",
                WRX_ERR_NOT_INIT, rc);
        dlclose(h);
        return 7;
    }

    /* Silence unused-variable warning for f_run: referenced via dlsym
     * existence check, deliberately not invoked (see header comment). */
    (void)f_run;

    /* Print success line BEFORE dlclose so captured pipes do not lose it. */
    printf("OK: dlopen(%s) + wrx_init/set_param/guarded-get_state/finalize"
           " lifecycle verified through shared library\n", path);
    fflush(stdout);

    rc = f_finalize();
    if (rc != 0) { fprintf(stderr, "FAIL wrx_finalize -> %d\n", rc); dlclose(h); return 8; }

    dlclose(h);
    return 0;
}
