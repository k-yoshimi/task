/*
 * Phase L-4: test_run_so
 *
 * dlopen libtrapi.so, dlsym the 5 C ABI entry points, and exercise the
 * full init -> set_param -> run -> get_state -> finalize cycle. This
 * proves the shared object is loadable, has the expected external
 * symbols, and that the Fortran-side lifecycle works when driven from
 * a C binary that never saw libtr2.a.
 *
 * Usage:
 *   TRLIB_PATH=/path/to/libtrapi.so ./test_run_so   (TRLIB_PATH optional,
 *                                                    defaults to ./libtrapi.so)
 *
 * Return values mirror test_run.c so debugging is easy:
 *   0 = OK
 *   1..8 = step that failed (same numbering as test_run.c)
 *   90 = dlopen failed
 *   91 = dlsym failed (one of the 5 entry points missing)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <dlfcn.h>

#include "tr_api.h"

typedef int  (*tr_init_fn)(void);
typedef int  (*tr_run_fn)(int);
typedef int  (*tr_set_param_fn)(const char *, double);
typedef int  (*tr_get_state_fn)(tr_state_t *);
typedef int  (*tr_finalize_fn)(void);

int main(void) {
    const char *path = getenv("TRLIB_PATH");
    if (!path || !*path) path = "./libtrapi.so";

    /* RTLD_LAZY: libtrapi.so legitimately has unresolved references to
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

    tr_init_fn       f_init       = (tr_init_fn)       dlsym(h, "tr_init");
    tr_run_fn        f_run        = (tr_run_fn)        dlsym(h, "tr_run");
    tr_set_param_fn  f_set_param  = (tr_set_param_fn)  dlsym(h, "tr_set_param");
    tr_get_state_fn  f_get_state  = (tr_get_state_fn)  dlsym(h, "tr_get_state");
    tr_finalize_fn   f_finalize   = (tr_finalize_fn)   dlsym(h, "tr_finalize");
    if (!f_init || !f_run || !f_set_param || !f_get_state || !f_finalize) {
        fprintf(stderr,
                "dlsym missing one of tr_{init,run,set_param,get_state,finalize}:"
                " init=%p run=%p set=%p get=%p fin=%p\n",
                (void*)f_init, (void*)f_run, (void*)f_set_param,
                (void*)f_get_state, (void*)f_finalize);
        dlclose(h);
        return 91;
    }

    /* Mirror the test_run.c cycle so the .so is proven to be a drop-in
     * replacement for the static libtr2.a link path. */
    int rc;
    tr_state_t s0, s1;
    const double dt   = 0.01;
    const int    nstp = 5;

    rc = f_init();                      if (rc != 0) { dlclose(h); return 1; }
    rc = f_set_param("DT", dt);         if (rc != 0) { dlclose(h); return 2; }
    rc = f_set_param("NTSTEP", 1);      if (rc != 0) { dlclose(h); return 3; }
    rc = f_get_state(&s0);              if (rc != 0) { dlclose(h); return 4; }
    rc = f_run(nstp);                   if (rc != 0) { dlclose(h); return 5; }
    rc = f_get_state(&s1);              if (rc != 0) { dlclose(h); return 6; }

    double dT       = s1.T - s0.T;
    double expected = nstp * dt;
    if (fabs(dT - expected) > 1e-6) {
        fprintf(stderr,
                "expected T to advance by %g (nstp=%d * dt=%g), got %g\n",
                expected, nstp, dt, dT);
        dlclose(h);
        return 7;
    }

    rc = f_finalize();                  if (rc != 0) { dlclose(h); return 8; }

    printf("OK: dlopen(%s) + init/run/get_state/finalize cycle"
           " advanced T by %g (expected ~%g, nstp=%d)\n",
           path, dT, expected, nstp);

    dlclose(h);
    return 0;
}
