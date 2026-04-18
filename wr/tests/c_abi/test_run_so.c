/*
 * Phase L-4: test_run_so
 *
 * dlopen libwrapi.so, dlsym the 5 C ABI entry points, and exercise the
 * full init -> set_param -> run -> get_state -> finalize cycle. This
 * proves the shared object is loadable, has the expected external
 * symbols, and that the Fortran-side lifecycle works when driven from
 * a C binary that never saw libwr.a.
 *
 * Usage:
 *   WRLIB_PATH=/path/to/libwrapi.so ./test_run_so   (WRLIB_PATH optional,
 *                                                    defaults to ./libwrapi.so)
 *
 * Return values mirror test_run.c so debugging is easy:
 *   0 = OK
 *   1..8 = step that failed (same numbering as test_run.c)
 *   90 = dlopen failed
 *   91 = dlsym failed (one of the 5 entry points missing)
 *
 * Mirrors tr/tests/c_abi/test_run_so.c (Phase L-4, PR #35).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <dlfcn.h>

#include "wr_api.h"

typedef int  (*wr_init_fn)(void);
typedef int  (*wr_run_fn)(int);
typedef int  (*wr_set_param_fn)(const char *, double);
typedef int  (*wr_get_state_fn)(wr_state_t *);
typedef int  (*wr_finalize_fn)(void);

#define SET(fn, name, val)                                                \
    do {                                                                  \
        int _rc = (fn)((name), (val));                                    \
        if (_rc != 0) {                                                   \
            fprintf(stderr, "FAIL set %s=%g -> %d\n", (name), (val), _rc);\
            dlclose(h);                                                   \
            return 2;                                                     \
        }                                                                 \
    } while (0)

int main(void) {
    const char *path = getenv("WRLIB_PATH");
    if (!path || !*path) path = "./libwrapi.so";

    /* RTLD_LAZY: libwrapi.so legitimately has unresolved references to
     * graphics symbols (pagee_, r2w2b_, ...) emitted by EQ/PL routines
     * that are unreachable from the C ABI happy path. With RTLD_NOW the
     * dynamic loader would refuse to load the .so even though we never
     * call those routines. RTLD_LAZY defers resolution until the first
     * call, which never happens for graphics from a Python wrapper. */
    void *h = dlopen(path, RTLD_LAZY);
    if (!h) {
        fprintf(stderr, "dlopen(%s) failed: %s\n", path, dlerror());
        return 90;
    }

    wr_init_fn       f_init       = (wr_init_fn)       dlsym(h, "wr_init");
    wr_run_fn        f_run        = (wr_run_fn)        dlsym(h, "wr_run");
    wr_set_param_fn  f_set_param  = (wr_set_param_fn)  dlsym(h, "wr_set_param");
    wr_get_state_fn  f_get_state  = (wr_get_state_fn)  dlsym(h, "wr_get_state");
    wr_finalize_fn   f_finalize   = (wr_finalize_fn)   dlsym(h, "wr_finalize");
    if (!f_init || !f_run || !f_set_param || !f_get_state || !f_finalize) {
        fprintf(stderr,
                "dlsym missing one of wr_{init,run,set_param,get_state,finalize}:"
                " init=%p run=%p set=%p get=%p fin=%p\n",
                (void*)f_init, (void*)f_run, (void*)f_set_param,
                (void*)f_get_state, (void*)f_finalize);
        dlclose(h);
        return 91;
    }

    /* Mirror the test_run.c cycle so the .so is proven to be a drop-in
     * replacement for the static libwr.a link path. */
    int rc;
    wr_state_t s;

    rc = f_init();
    if (rc != 0) { fprintf(stderr, "FAIL wr_init -> %d\n", rc); dlclose(h); return 1; }

    /* Geometry: ITER-sized analytic tokamak (MODELG=2 default). */
    SET(f_set_param, "RR",   6.2);
    SET(f_set_param, "RA",   2.0);
    SET(f_set_param, "RKAP", 1.7);
    SET(f_set_param, "BB",   5.3);

    /* Plasma: 4 species as in wr_test001.in. */
    SET(f_set_param, "NSMAX",  4.0);
    SET(f_set_param, "PA[1]",  1.0);  SET(f_set_param, "PA[2]",  2.0);
    SET(f_set_param, "PA[3]",  3.0);  SET(f_set_param, "PA[4]",  4.0);
    SET(f_set_param, "PZ[1]", -1.0);  SET(f_set_param, "PZ[2]",  1.0);
    SET(f_set_param, "PZ[3]",  1.0);  SET(f_set_param, "PZ[4]",  2.0);
    SET(f_set_param, "PN[1]",  0.9);  SET(f_set_param, "PN[2]",  0.40);
    SET(f_set_param, "PN[3]",  0.40); SET(f_set_param, "PN[4]",  0.05);
    SET(f_set_param, "PNS[1]", 0.03); SET(f_set_param, "PNS[2]", 0.0133);
    SET(f_set_param, "PNS[3]", 0.0133); SET(f_set_param, "PNS[4]", 0.0017);
    SET(f_set_param, "PTPR[1]", 35.0); SET(f_set_param, "PTPR[2]", 35.0);
    SET(f_set_param, "PTPR[3]", 35.0); SET(f_set_param, "PTPR[4]", 35.0);
    SET(f_set_param, "PTPP[1]", 35.0); SET(f_set_param, "PTPP[2]", 35.0);
    SET(f_set_param, "PTPP[3]", 35.0); SET(f_set_param, "PTPP[4]", 35.0);
    SET(f_set_param, "PTS[1]",  1.0);  SET(f_set_param, "PTS[2]",  1.0);
    SET(f_set_param, "PTS[3]",  1.0);  SET(f_set_param, "PTS[4]",  1.0);
    SET(f_set_param, "MODELP[1]", 4.0); SET(f_set_param, "MODELP[2]", 4.0);
    SET(f_set_param, "MODELP[3]", 4.0); SET(f_set_param, "MODELP[4]", 4.0);
    SET(f_set_param, "PROFN1", 3.7);
    SET(f_set_param, "PROFN2", 2.7);

    /* WR control: short run, single ray, namelist-style input. */
    SET(f_set_param, "MDLWRI",  101.0);
    SET(f_set_param, "MDLWRQ",  0.0);
    SET(f_set_param, "MDLWRW",  0.0);
    SET(f_set_param, "SMAX",    0.10);
    SET(f_set_param, "DELS",    0.01);
    SET(f_set_param, "NRAYMAX", 1.0);
    SET(f_set_param, "NSTPMAX", 200.0);
    SET(f_set_param, "NRSMAX",  50.0);
    SET(f_set_param, "NRLMAX",  100.0);

    /* Ray 1 initial conditions. */
    SET(f_set_param, "RFIN[1]",    160.0e3);
    SET(f_set_param, "RPIN[1]",    8.5);
    SET(f_set_param, "ZPIN[1]",    0.0);
    SET(f_set_param, "PHIIN[1]",   0.0);
    SET(f_set_param, "ANGZIN[1]",  -30.0);
    SET(f_set_param, "ANGPHIN[1]", 20.0);
    SET(f_set_param, "UUIN[1]",    1.0);
    SET(f_set_param, "MODEWIN[1]", 1.0);

    rc = f_run(0);
    if (rc != 0) { fprintf(stderr, "FAIL wr_run -> %d\n", rc); dlclose(h); return 5; }

    rc = f_get_state(&s);
    if (rc != 0) { fprintf(stderr, "FAIL wr_get_state -> %d\n", rc); dlclose(h); return 6; }

    if (s.nraymax != 1) {
        fprintf(stderr, "nraymax = %d, expected 1\n", s.nraymax);
        dlclose(h);
        return 7;
    }
    if (s.nstp_end[0] < 0 || s.nstp_end[0] > 200) {
        fprintf(stderr, "nstp_end[0] = %d out of range [0,200]\n",
                s.nstp_end[0]);
        dlclose(h);
        return 7;
    }

    rc = f_finalize();
    if (rc != 0) { fprintf(stderr, "FAIL wr_finalize -> %d\n", rc); dlclose(h); return 8; }

    printf("OK: dlopen(%s) + wr_init/run/get_state/finalize cycle"
           " (nraymax=%d, nstp_end[0]=%d, pos_pwrmax_rs=%.6g, pwrmax_rs=%.6g)\n",
           path, s.nraymax, s.nstp_end[0], s.pos_pwrmax_rs, s.pwrmax_rs);

    dlclose(h);
    return 0;
}
