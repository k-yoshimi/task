/*
 * Phase L-3: test_param
 *
 * Exercises wr_set_param and wr_get_state together:
 *   - wr_set_param without wr_init -> WR_ERR_NOT_INIT (=2)
 *   - call wr_init (populates WRCOMM defaults via wr_init Fortran).
 *   - call wr_set_param for scalar names (RR, BB), an array subscript
 *     (PN[1], RFIN[1], MODEWIN[1]), and unknown / out-of-range names;
 *     verify the return codes.
 *   - call wr_get_state and check that NRAYMAX / NRSMAX / NRLMAX come
 *     back > 0 (proof that the WRCOMM defaults set by wr_init are
 *     readable).
 *   - call wr_finalize.
 */
#include <stdio.h>
#include "wr_api.h"

int main(void) {
    int rc;
    wr_state_t s;

    /* Pre-init: set_param should reject with NOT_INIT. */
    rc = wr_set_param("RR", 6.2);
    if (rc != WR_ERR_NOT_INIT) {
        fprintf(stderr, "pre-init wr_set_param -> %d, want %d\n",
                rc, WR_ERR_NOT_INIT);
        return 9;
    }

    rc = wr_init();
    if (rc != 0) { fprintf(stderr, "wr_init -> %d\n", rc); return 10; }

    rc = wr_set_param("RR", 6.2);
    if (rc != 0) { fprintf(stderr, "set RR -> %d\n", rc); return 11; }

    rc = wr_set_param("BB", 5.3);
    if (rc != 0) { fprintf(stderr, "set BB -> %d\n", rc); return 12; }

    rc = wr_set_param("NSMAX", 2.0);
    if (rc != 0) { fprintf(stderr, "set NSMAX -> %d\n", rc); return 13; }

    rc = wr_set_param("PN[1]", 1.0);
    if (rc != 0) { fprintf(stderr, "set PN[1] -> %d\n", rc); return 14; }

    rc = wr_set_param("NRAYMAX", 1.0);
    if (rc != 0) { fprintf(stderr, "set NRAYMAX -> %d\n", rc); return 15; }

    rc = wr_set_param("RFIN[1]", 160.0e3);
    if (rc != 0) { fprintf(stderr, "set RFIN[1] -> %d\n", rc); return 16; }

    rc = wr_set_param("MODEWIN[1]", 1.0);
    if (rc != 0) { fprintf(stderr, "set MODEWIN[1] -> %d\n", rc); return 17; }

    /* Array subscript out of range must be rejected. */
    rc = wr_set_param("PN[0]", 0.0);
    if (rc != WR_ERR_INVALID) {
        fprintf(stderr, "PN[0] should return WR_ERR_INVALID, got %d\n", rc);
        return 18;
    }
    rc = wr_set_param("PN[999]", 0.0);
    if (rc != WR_ERR_INVALID) {
        fprintf(stderr, "PN[999] should return WR_ERR_INVALID, got %d\n", rc);
        return 19;
    }

    /* Unknown parameter must be rejected. */
    rc = wr_set_param("NOT_A_REAL_PARAM", 0.0);
    if (rc != WR_ERR_INVALID) {
        fprintf(stderr, "unknown name should return WR_ERR_INVALID, got %d\n", rc);
        return 20;
    }

    /* get_state must succeed after init. */
    rc = wr_get_state(&s);
    if (rc != 0) { fprintf(stderr, "wr_get_state -> %d\n", rc); return 21; }

    if (s.nraymax <= 0 || s.nrsmax <= 0 || s.nrlmax <= 0) {
        fprintf(stderr, "bad state: nraymax=%d nrsmax=%d nrlmax=%d\n",
                s.nraymax, s.nrsmax, s.nrlmax);
        return 22;
    }

    rc = wr_finalize();
    if (rc != 0) { fprintf(stderr, "wr_finalize -> %d\n", rc); return 23; }

    printf("OK: wr_set_param + wr_get_state "
           "(nraymax=%d nrsmax=%d nrlmax=%d)\n",
           s.nraymax, s.nrsmax, s.nrlmax);
    return 0;
}
