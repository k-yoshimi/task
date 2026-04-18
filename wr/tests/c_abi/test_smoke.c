/*
 * Phase L-3 C ABI smoke test for TASK/WR.
 *
 * Goal at L-3: verify that the five wr_api entry points all return
 * WR_OK (=0) when invoked in the documented order:
 *
 *   wr_init -> wr_get_state -> wr_set_param -> wr_finalize
 *
 * Numerical correctness (does wr_run actually populate pos_pwrmax_rs?)
 * is tested in test_run.c; parameter dispatch correctness is tested in
 * test_param.c.
 */
#include <stdio.h>
#include "wr_api.h"

static int expect_ok(const char *name, int rc) {
    if (rc == WR_OK) {
        printf("OK  %-12s returned WR_OK (=%d)\n", name, rc);
        return 0;
    }
    fprintf(stderr,
            "FAIL %s returned %d, expected WR_OK (=%d)\n",
            name, rc, WR_OK);
    return 1;
}

int main(void) {
    int failures = 0;
    wr_state_t st;

    failures += expect_ok("wr_init",      wr_init());
    failures += expect_ok("wr_get_state", wr_get_state(&st));
    failures += expect_ok("wr_set_param", wr_set_param("RR", 6.2));
    failures += expect_ok("wr_finalize",  wr_finalize());

    if (failures != 0) {
        fprintf(stderr, "%d entry point(s) returned a non-OK code\n", failures);
        return 1;
    }
    printf("Phase L-3 C ABI smoke OK: 4/4 entry points returned WR_OK\n");
    return 0;
}
