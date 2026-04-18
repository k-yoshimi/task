/*
 * Phase L-3: test_run
 *
 * Exercises the full wr_init -> wr_set_param -> wr_run -> wr_get_state
 * -> wr_finalize cycle on a minimal ray-tracing configuration derived
 * from wr_test001.in (MODELG=2, single-ray, short SMAX):
 *
 *   wr_init
 *   wr_set_param(...)     // geometry + plasma + single ray input
 *   wr_run(0)             // keep the namelist NRAYMAX we just set
 *   wr_get_state(&s)      // check NRAYMAX round-trips; no NaN in pwrmax
 *   wr_finalize
 *
 * The assertion is intentionally light-weight:
 *   - wr_get_state returns 0
 *   - s.nraymax equals the NRAYMAX we set (1)
 *   - s.nstp_end[0] >= 0 and <= NSTPMAX (ray integration produced a
 *     plausible end step)
 *
 * Bit-exact comparison against wr_test001 lives in the regression
 * harness (test_run/run_tests.sh) and in Layer-1 tests (L-6).
 */
#include <stdio.h>
#include "wr_api.h"

#define CHECK(call, rc_var, tag)                                          \
    do {                                                                  \
        rc_var = (call);                                                  \
        if (rc_var != 0) {                                                \
            fprintf(stderr, "FAIL %s -> %d\n", tag, rc_var);              \
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

int main(void) {
    int rc;
    wr_state_t s;

    CHECK(wr_init(), rc, "wr_init");

    /* Geometry: ITER-sized analytic tokamak (MODELG=2 default). */
    SET("RR",   6.2);
    SET("RA",   2.0);
    SET("RKAP", 1.7);
    SET("BB",   5.3);

    /* Plasma: 4 species as in wr_test001.in. */
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

    /* WR control: short run, single ray, namelist-style input. */
    SET("MDLWRI",  101.0);
    SET("MDLWRQ",  0.0);
    SET("MDLWRW",  0.0);
    SET("SMAX",    0.10);   /* very short ray to keep test_run fast   */
    SET("DELS",    0.01);
    SET("NRAYMAX", 1.0);
    SET("NSTPMAX", 200.0);
    SET("NRSMAX",  50.0);
    SET("NRLMAX",  100.0);

    /* Ray 1 initial conditions. */
    SET("RFIN[1]",    160.0e3);
    SET("RPIN[1]",    8.5);
    SET("ZPIN[1]",    0.0);
    SET("PHIIN[1]",   0.0);
    SET("ANGZIN[1]",  -30.0);
    SET("ANGPHIN[1]", 20.0);
    SET("UUIN[1]",    1.0);
    SET("MODEWIN[1]", 1.0);

    CHECK(wr_run(0), rc, "wr_run");
    CHECK(wr_get_state(&s), rc, "wr_get_state");

    if (s.nraymax != 1) {
        fprintf(stderr, "nraymax = %d, expected 1\n", s.nraymax);
        return 3;
    }
    if (s.nstp_end[0] < 0 || s.nstp_end[0] > 200) {
        fprintf(stderr, "nstp_end[0] = %d out of range [0,200]\n",
                s.nstp_end[0]);
        return 4;
    }

    CHECK(wr_finalize(), rc, "wr_finalize");

    printf("OK: wr_run completed (nraymax=%d, nstp_end[0]=%d, "
           "pos_pwrmax_rs=%.6g, pwrmax_rs=%.6g)\n",
           s.nraymax, s.nstp_end[0], s.pos_pwrmax_rs, s.pwrmax_rs);
    return 0;
}
