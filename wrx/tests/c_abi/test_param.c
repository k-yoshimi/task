/*
 * Phase L-3: test_param
 *
 * Exercises wrx_set_param dispatch (no wrx_run required):
 *   - call wrx_init (defaults populated by wr_init Fortran)
 *   - call wrx_set_param for scalar names (RR, BB, NRAYMAX), an array
 *     subscript (PN[1], RFIN[1]), and an unknown / out-of-range name;
 *     verify the return codes.
 *   - call wrx_finalize.
 *
 * We don't assert the stored numerical values here: RR/BB/PN are not
 * part of wrx_state_t by design (see L-3 plan File Structure). The
 * test_run driver covers the wrx_run + wrx_get_state path.
 */
#include <stdio.h>
#include "wrx_api.h"

int main(void) {
    int rc;
    setvbuf(stdout, NULL, _IOLBF, 0);

    rc = wrx_init();
    if (rc != 0) { fprintf(stderr, "wrx_init -> %d\n", rc); return 10; }

    rc = wrx_set_param("RR", 3.95);
    if (rc != 0) { fprintf(stderr, "set RR -> %d\n", rc); return 11; }

    rc = wrx_set_param("BB", 3.5);
    if (rc != 0) { fprintf(stderr, "set BB -> %d\n", rc); return 12; }

    rc = wrx_set_param("NRAYMAX", 2.0);
    if (rc != 0) { fprintf(stderr, "set NRAYMAX -> %d\n", rc); return 13; }

    rc = wrx_set_param("PN[1]", 1.0);
    if (rc != 0) { fprintf(stderr, "set PN[1] -> %d\n", rc); return 14; }

    rc = wrx_set_param("RFIN[1]", 170.0e3);
    if (rc != 0) { fprintf(stderr, "set RFIN[1] -> %d\n", rc); return 15; }

    /* Array subscript out of range (idx=0) must be rejected
     * (Bugbot fix: parse_array_subscript returns idx=0 for malformed
     * subscripts which trips the idx<1 check). */
    rc = wrx_set_param("PN[0]", 0.0);
    if (rc == 0) {
        fprintf(stderr, "PN[0] (idx=0) should have been rejected\n");
        return 16;
    }

    /* Upper-bound subscript out of range (PN is NSM=100 wide). */
    rc = wrx_set_param("PN[999]", 0.0);
    if (rc == 0) {
        fprintf(stderr, "PN[999] (idx>SIZE) should have been rejected\n");
        return 17;
    }

    /* Unknown parameter name must be rejected. */
    rc = wrx_set_param("NOT_A_REAL_PARAM", 0.0);
    if (rc == 0) {
        fprintf(stderr, "unknown name should have been rejected\n");
        return 18;
    }

    /* Scalar form without subscript still works (parse_array_subscript
     * defaults idx=1 for 1-origin Fortran convention). */
    rc = wrx_set_param("Q0", 1.0);
    if (rc != 0) { fprintf(stderr, "set Q0 -> %d\n", rc); return 19; }

    rc = wrx_finalize();
    if (rc != 0) { fprintf(stderr, "wrx_finalize -> %d\n", rc); return 20; }

    printf("OK: wrx_set_param dispatch (scalar+array+rejection paths)\n");
    fflush(stdout);
    return 0;
}
