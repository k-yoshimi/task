/*
 * Phase L-3: test_reinit
 *
 * Regression test for Bugbot HIGH on PR #36: calling wr_finalize then
 * wr_init + wr_run again previously caused a double-free crash because
 * wr_allocate's local SAVE flags (INIT, NRAYMAX_SAVE, NSTPMAX_SAVE)
 * were not reset by wr_deallocate. After the fix, wr_api_finalize calls
 * wr_reset_alloc_state in wrcomm and wr_api_init re-arms by calling
 * wr_deallocate (now ALLOCATED()-guarded) defensively.
 *
 * The test runs two full init -> run -> finalize cycles back-to-back,
 * potentially with different NRAYMAX between cycles to also exercise
 * the "shape changed across cycles" path. A clean exit (return 0)
 * means no double-free crash occurred and both cycles produced a
 * plausible nstp_end.
 */
#include <stdio.h>
#include "wr_api.h"

#define CHECK(call, tag)                                                  \
    do {                                                                  \
        int _rc = (call);                                                 \
        if (_rc != 0) {                                                   \
            fprintf(stderr, "FAIL %s -> %d\n", (tag), _rc);               \
            return 1;                                                     \
        }                                                                 \
    } while (0)

#define SET(name, val)                                                    \
    do {                                                                  \
        int _rc = wr_set_param((name), (val));                            \
        if (_rc != 0) {                                                   \
            fprintf(stderr, "FAIL set %s=%g -> %d\n", (name), (val), _rc);\
            return 2;                                                     \
        }                                                                 \
    } while (0)

/* Apply the wr_test001-derived single-ray configuration to the current
 * (already-init'd) WR state. Pulled out of test_run.c so we can reuse
 * it across reinit cycles. */
static int configure_single_ray(double nraymax_d) {
    SET("RR",   6.2);
    SET("RA",   2.0);
    SET("RKAP", 1.7);
    SET("BB",   5.3);

    SET("NSMAX",  4.0);
    SET("PA[1]",  1.0);     SET("PA[2]",  2.0);
    SET("PA[3]",  3.0);     SET("PA[4]",  4.0);
    SET("PZ[1]", -1.0);     SET("PZ[2]",  1.0);
    SET("PZ[3]",  1.0);     SET("PZ[4]",  2.0);
    SET("PN[1]",  0.9);     SET("PN[2]",  0.40);
    SET("PN[3]",  0.40);    SET("PN[4]",  0.05);
    SET("PNS[1]", 0.03);    SET("PNS[2]", 0.0133);
    SET("PNS[3]", 0.0133);  SET("PNS[4]", 0.0017);
    SET("PTPR[1]", 35.0);   SET("PTPR[2]", 35.0);
    SET("PTPR[3]", 35.0);   SET("PTPR[4]", 35.0);
    SET("PTPP[1]", 35.0);   SET("PTPP[2]", 35.0);
    SET("PTPP[3]", 35.0);   SET("PTPP[4]", 35.0);
    SET("PTS[1]",  1.0);    SET("PTS[2]",  1.0);
    SET("PTS[3]",  1.0);    SET("PTS[4]",  1.0);
    SET("MODELP[1]", 4.0);  SET("MODELP[2]", 4.0);
    SET("MODELP[3]", 4.0);  SET("MODELP[4]", 4.0);
    SET("PROFN1", 3.7);
    SET("PROFN2", 2.7);

    SET("MDLWRI",  101.0);
    SET("MDLWRQ",  0.0);
    SET("MDLWRW",  0.0);
    SET("SMAX",    0.10);
    SET("DELS",    0.01);
    SET("NRAYMAX", nraymax_d);
    SET("NSTPMAX", 200.0);
    SET("NRSMAX",  50.0);
    SET("NRLMAX",  100.0);

    SET("RFIN[1]",    160.0e3);
    SET("RPIN[1]",    8.5);
    SET("ZPIN[1]",    0.0);
    SET("PHIIN[1]",   0.0);
    SET("ANGZIN[1]",  -30.0);
    SET("ANGPHIN[1]", 20.0);
    SET("UUIN[1]",    1.0);
    SET("MODEWIN[1]", 1.0);
    return 0;
}

static int run_one_cycle(int cycle, double nraymax_d) {
    wr_state_t s;
    int rc;

    CHECK(wr_init(), "wr_init");

    rc = configure_single_ray(nraymax_d);
    if (rc != 0) return rc;

    CHECK(wr_run(0), "wr_run");
    CHECK(wr_get_state(&s), "wr_get_state");

    if (s.nraymax != (int) nraymax_d) {
        fprintf(stderr,
                "cycle %d: nraymax = %d, expected %d\n",
                cycle, s.nraymax, (int) nraymax_d);
        return 3;
    }
    if (s.nstp_end[0] < 0 || s.nstp_end[0] > 200) {
        fprintf(stderr,
                "cycle %d: nstp_end[0] = %d out of range [0,200]\n",
                cycle, s.nstp_end[0]);
        return 4;
    }

    CHECK(wr_finalize(), "wr_finalize");
    printf("OK  cycle %d: nraymax=%d, nstp_end[0]=%d, "
           "pos_pwrmax_rs=%.6g\n",
           cycle, s.nraymax, s.nstp_end[0], s.pos_pwrmax_rs);
    return 0;
}

int main(void) {
    /* Cycle 1: same shape as test_run.c (NRAYMAX=1). */
    if (run_one_cycle(1, 1.0) != 0) return 10;

    /* Cycle 2: identical shape - exercises the "shape unchanged"
     * fast path in wr_allocate after wr_reset_alloc_state. */
    if (run_one_cycle(2, 1.0) != 0) return 20;

    /* Cycle 3: identical shape again to make sure we don't accumulate
     * stale state across more than two cycles. */
    if (run_one_cycle(3, 1.0) != 0) return 30;

    printf("Phase L-3 reinit OK: 3 init->run->finalize cycles "
           "completed with no double-free\n");
    return 0;
}
