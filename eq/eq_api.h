#ifndef EQ_API_H
#define EQ_API_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 * TASK/EQ C ABI public header.
 *
 * Phase L-3 status:
 *   - eq_init / eq_finalize / eq_get_state : EQ_OK.
 *   - eq_set_param : real SELECT CASE dispatch (eq_param_registry.f90,
 *                    ~60 names covering /EQ/ namelist scalars + PSIB[0..5]
 *                    + RIPFC/RPFC/ZPFC/WPFC[1..10]).
 *   - eq_set_param_str : NEW in L-3. Covers KNAMEQ/KNAMWR/KNAMWM/
 *                    KNAMFP/KNAMFO/KNAMPF/KNAMEQ2 (CHARACTER(LEN=80)).
 *   - eq_run(1) : real EQDSK load via equnit::eq_load using the current
 *                 MODELG + KNAMEQ. eq_run(0) and other modes still
 *                 return EQ_ERR_NOT_IMPL pending L-4.
 *   - eq_save   : NEW in Task 1.1. Writes TASK-internal binary to KNAMEQ.
 *                 Returns EQ_OK unconditionally; caller must verify file.
 *
 * Memory note: every array in eq_state_t is fixed-size (max-capacity).
 * Valid runtime slots are 1..nrmax / 1..npsmax / 1..nrgmax / etc.;
 * the remainder is zero-padded by eq_get_state before return.
 *
 * PSIB indexing note: PSIB is 0-origin (0..5) because the underlying
 * Fortran declaration is REAL(8) :: PSIB(0:5). All other 1D array
 * parameters (RIPFC/RPFC/ZPFC/WPFC) are 1-origin.
 */

#define EQ_MAX_NRGM 513
#define EQ_MAX_NZGM 513
#define EQ_MAX_NPSM 513
#define EQ_MAX_NRM  1001
#define EQ_MAX_NTHM 2049
#define EQ_MAX_NSUM 1343

/* Error codes returned by every eq_* entry point. */
enum eq_error {
    EQ_OK              = 0,
    EQ_ERR_INVALID     = 1,  /* invalid parameter name or value     */
    EQ_ERR_NOT_INIT    = 2,  /* eq_init has not been called yet     */
    EQ_ERR_CALC_FAILED = 3,  /* calculation / initialization failed */
    EQ_ERR_NOT_IMPL    = 4   /* L-2 stub return: not implemented    */
};

/*
 * IMPORTANT: This struct must match eq_state.f90::eq_state_c byte-for-byte.
 * Field names, order, and types must stay in sync — both sides are
 * INTEGER(C_INT) / int and REAL(C_DOUBLE) / double, so natural alignment
 * agrees on every supported target. If you add/remove/reorder a field
 * here, update eq_state.f90 in the same commit (and vice versa).
 */
typedef struct eq_state_t {
    /* grid counters (NRGMAX/NZGMAX/NPSMAX/NRMAX/NTHMAX/NSUMAX) */
    int    nrgmax;
    int    nzgmax;
    int    npsmax;
    int    nrmax;
    int    nthmax;
    int    nsumax;
    /* secondary grid counters (NRVMAX volume grid; NSGMAX/NTGMAX
     * orthogonal curvilinear PSI(s,t) grid) needed for MODELG=3
     * Layer 1 baseline metrics. */
    int    nrvmax;
    int    nsgmax;
    int    ntgmax;
    /* plasma scalars */
    double raxis;
    double zaxis;
    double psi0;
    double psipa;
    double psita;
    double qaxis;
    double qsurf;
    double betat;
    double betap;
    double pvol;
    double raave;
    double ripx;
    /* 1D profiles (sampled at 1..npsmax) */
    double psips[EQ_MAX_NPSM];
    double ppps[EQ_MAX_NPSM];
    double ttps[EQ_MAX_NPSM];
    double qqps[EQ_MAX_NPSM];
    /* R / Z grid coordinates */
    double rg[EQ_MAX_NRGM];
    double zg[EQ_MAX_NZGM];
    /* Per-NR flux-surface profile arrays (1..nrmax). Mirror the 7
     * columns written by eqregress.f (PSIP/PSIT/PPS/TTS/QPS/VPS/RST)
     * for Phase 0 baseline regression. Only the first nrmax entries
     * carry valid runtime data; the rest is zero-padded. */
    double profile_psip[EQ_MAX_NRM];
    double profile_psit[EQ_MAX_NRM];
    double profile_pps[EQ_MAX_NRM];
    double profile_tts[EQ_MAX_NRM];
    double profile_qps[EQ_MAX_NRM];
    double profile_vps[EQ_MAX_NRM];
    double profile_rst[EQ_MAX_NRM];
} eq_state_t;

int eq_init(void);
int eq_run(int mode);
int eq_set_param(const char* name, double value);
/* Set a string-valued parameter. Supported names:
 *   KNAMEQ, KNAMEQ2, KNAMWR, KNAMWM, KNAMFP, KNAMFO, KNAMPF
 * All are CHARACTER(LEN=80) on the Fortran side. */
int eq_set_param_str(const char* name, const char* value);
int eq_get_state(eq_state_t* state);
int eq_finalize(void);

/*
 * Issue #143: pre-run parameter validation API. Pilot module = eq.
 *
 * Diagnostic categories. Wider numeric range than eq_error so the
 * code field never collides with eq_error in callers that aggregate.
 */
enum eq_diag_code {
    EQ_DIAG_OUT_OF_RANGE           = 1,
    EQ_DIAG_INCONSISTENT_PAIR      = 2,
    EQ_DIAG_OUT_OF_RANGE_AFTER_DEP = 3,
    EQ_DIAG_FILE_MISSING           = 4,
    EQ_DIAG_MISSING_REQUIRED       = 5,
};

#define EQ_DIAG_PARAM_LEN 64
#define EQ_DIAG_MSG_LEN   128

/*
 * Single diagnostic record. param[] and msg[] are NUL-terminated
 * Fortran-padded strings (the Fortran side fills them via TRIM and
 * appends C_NULL_CHAR). Must match eq_state.f90::eq_diag_entry_c
 * byte-for-byte.
 */
typedef struct {
    char param[EQ_DIAG_PARAM_LEN];
    int  code;
    char msg[EQ_DIAG_MSG_LEN];
} eq_diag_entry_t;

/*
 * Run cross-parameter validation against the current eq state and
 * fill diag[0..ndiag-1] with up to diag_cap diagnostics.
 *
 *   diag      : OUT — caller-allocated diagnostic array
 *   diag_cap  : IN  — capacity of diag (entries beyond ndiag are
 *                     left untouched)
 *   ndiag_out : OUT — number of diagnostics actually produced
 *                     (0..diag_cap)
 *
 * Return values:
 *   EQ_OK           — no diagnostics produced (ndiag_out == 0)
 *   EQ_ERR_INVALID  — one or more diagnostics produced (ndiag_out > 0)
 *   EQ_ERR_NOT_INIT — eq_init has not been called yet
 *
 * The validation is read-only: it does not modify any eq state.
 * Caller workflow: validate → fix any reported issues → validate again
 * → run.
 */
int eq_validate(eq_diag_entry_t* diag, int diag_cap, int* ndiag_out);

/* Write current EQ state to KNAMEQ binary; returns EQ_OK unconditionally.
   Caller MUST verify file existence afterward (see Task 1.2 Python wrapper). */
int eq_save(void);

#ifdef __cplusplus
}
#endif

#endif /* EQ_API_H */
