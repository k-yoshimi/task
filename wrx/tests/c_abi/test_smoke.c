/*
 * Phase L-3 C ABI smoke test for TASK/WRX.
 *
 * Goal at L-3: verify that the four lifecycle entry points return
 * WRX_OK (=0) when invoked in the documented order:
 *
 *   wrx_init -> wrx_set_param -> wrx_finalize
 *
 * wrx_get_state is NOT exercised here because it deliberately rejects
 * pre-wrx_run access (the wrcomm power-deposition arrays are
 * unallocated until wr_allocate runs inside wrx_run). End-to-end
 * coverage of wrx_run + wrx_get_state lives in test_run.c.
 */
#include <stdio.h>
#include "wrx_api.h"

static int expect_ok(const char *name, int rc) {
    if (rc == WRX_OK) {
        printf("OK  %-13s returned WRX_OK (=%d)\n", name, rc);
        return 0;
    }
    fprintf(stderr,
            "FAIL %s returned %d, expected WRX_OK (=%d)\n",
            name, rc, WRX_OK);
    return 1;
}

int main(void) {
    int failures = 0;

    /* Line-buffer stdout so the Fortran runtime (which may share the
     * FILE* with libgrf's GSOPEN prompt) cannot swallow our progress
     * lines when the driver runs under `echo 0 | test_* > log`. */
    setvbuf(stdout, NULL, _IOLBF, 0);

    failures += expect_ok("wrx_init",      wrx_init());
    failures += expect_ok("wrx_set_param", wrx_set_param("RR", 3.95));
    failures += expect_ok("wrx_finalize",  wrx_finalize());

    if (failures != 0) {
        fprintf(stderr, "%d entry point(s) returned a non-OK code\n",
                failures);
        return 1;
    }
    printf("Phase L-3 C ABI smoke OK: 3/3 lifecycle entry points returned WRX_OK\n");
    fflush(stdout);
    return 0;
}
