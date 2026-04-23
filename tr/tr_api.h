#ifndef TR_API_H
#define TR_API_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 * TASK/TR C ABI public header.
 *
 * Phase L-2 status: function symbols are present in libtrapi (built from
 * tr_api.f90); each entry point is a stub returning TR_ERR_NOT_IMPLEMENTED
 * (=4). Real bodies arrive in Phase L-3.
 *
 * See docs/superpowers/specs/2026-04-17-tr-library-design.md  Section 4.2.
 *
 * Memory note: in C, RN[NRMAX][NSMAX] is row-major; in Fortran the
 * matching declaration is RN(NSMAX, NRMAX) (column-major). Layouts agree
 * byte-for-byte, but only RN[0..nrmax-1][0..nsmax-1] are valid runtime
 * values (the remainder is padding up to TR_MAX_*).
 */

#define TR_MAX_NRMAX 500
#define TR_MAX_NSMAX 8

/* Error codes returned by every tr_* entry point. */
enum tr_error {
    TR_OK              = 0,
    TR_ERR_INVALID     = 1,  /* invalid parameter name or value     */
    TR_ERR_NOT_INIT    = 2,  /* tr_init has not been called yet     */
    TR_ERR_CALC_FAILED = 3,  /* calculation / initialization failed */
    TR_ERR_NOT_IMPL    = 4   /* L-2 stub return: not implemented    */
};

typedef struct {
    int    nt, nrmax, nsmax;
    double T, WPT, AJT, Q0, BETA0, BETAP0, BETAA, BETAN;
    double TAUE1, TAUE2, ZEFF0, ALI, RQ1;
    double RN[TR_MAX_NRMAX][TR_MAX_NSMAX];
    double RT[TR_MAX_NRMAX][TR_MAX_NSMAX];
    double AJ[TR_MAX_NRMAX];
    double QP[TR_MAX_NRMAX];
} tr_state_t;

/*
 * Issue #143 pre-run parameter validation API.
 *
 * Read-only cross-parameter consistency check. Call after tr_init and
 * any tr_set_param / tr_set_param_str, before tr_run. Must NOT modify
 * any tr state.
 */
enum tr_diag_code {
    TR_DIAG_OUT_OF_RANGE           = 1,
    TR_DIAG_INCONSISTENT_PAIR      = 2,
    TR_DIAG_OUT_OF_RANGE_AFTER_DEP = 3,
    TR_DIAG_FILE_MISSING           = 4,
    TR_DIAG_MISSING_REQUIRED       = 5
};

#define TR_DIAG_PARAM_LEN 64
#define TR_DIAG_MSG_LEN   128

/*
 * One diagnostic entry. Matches tr_state.f90::tr_diag_entry_c byte-for-byte.
 * param / msg are C_NULL_CHAR-padded on write (Fortran zero-fills then
 * overwrites with TRIM of the source + appends C_NULL_CHAR).
 */
typedef struct tr_diag_entry {
    char param[TR_DIAG_PARAM_LEN];
    int  code;
    char msg[TR_DIAG_MSG_LEN];
} tr_diag_entry_t;

int tr_init(void);
int tr_run(int ntmax);
int tr_set_param(const char* name, double value);
int tr_set_param_str(const char* name, const char* value);
int tr_get_state(tr_state_t* state);
int tr_finalize(void);

/*
 * Return codes:
 *   TR_OK           (0): *ndiag_out == 0; state validates cleanly
 *   TR_ERR_INVALID  (1): *ndiag_out >= 1; diagnostics are the payload
 *   TR_ERR_NOT_INIT (2): library not initialized
 * Caller workflow: validate -> fix any reported issues -> validate again
 * -> tr_run. The function does NOT mutate tr state.
 */
int tr_validate(tr_diag_entry_t* diag, int diag_cap, int* ndiag_out);

#ifdef __cplusplus
}
#endif

#endif /* TR_API_H */
