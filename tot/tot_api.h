#ifndef TOT_API_H
#define TOT_API_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 * TASK/TOT C ABI public header.
 *
 * TOT is the orchestrator: its api fans out to per-module APIs
 * (tr_init + ti_init + fp_init + wr_init, tr_run, tr_get_state + ...,
 * per-module *_set_param, *_finalize). Phase L-2 status: function
 * symbols are present in libtotapi (built from tot_api.f90); each
 * entry point is a stub returning TOT_ERR_NOT_IMPLEMENTED (=4). Real
 * composition arrives in Phase L-3+.
 *
 * Intentionally self-contained at L-2: this header does NOT include
 * tr_api.h / ti_api.h / fp_api.h / wr_api.h. That keeps the L-2 stub
 * usable even before every per-module L-2 has landed. L-3+ will either
 * include those headers and nest their state_t types, or expose the
 * composite view through a separate tot_api_compose.h.
 *
 * See docs/superpowers/specs/2026-04-17-tr-library-design.md  Section 4
 * and docs/superpowers/plans/2026-04-18-tot-library-L2-c-abi-foundation.md.
 *
 * Memory note: in C, RN[NRMAX][NSMAX] is row-major; in Fortran the
 * matching declaration is RN(NSMAX, NRMAX) (column-major). Layouts
 * agree byte-for-byte, but only RN[0..nrmax-1][0..nsmax-1] are valid
 * runtime values (the remainder is padding up to TOT_MAX_*).
 */

#define TOT_MAX_NRMAX 500
#define TOT_MAX_NSMAX 8

/*
 * tot_state_t ABI version. Bumped whenever a field is added/removed/
 * reordered in tot_state_t (i.e. whenever sizeof(tot_state_t) changes).
 * Out-of-tree binary consumers should compare TOT_STATE_ABI_VERSION at
 * compile time against any cached layout assumption and recompile when
 * it bumps. In-tree consumers (python/totlib/_ffi.py and any future
 * tot_api_check_* helpers) all rebuild from this header, so they are
 * kept in sync automatically by the build system.
 *
 * History:
 *   1 -> initial layout (Phase L-2)
 *   2 -> appended AJRFT [MA] (L-7b-i); existing field offsets preserved.
 */
#define TOT_STATE_ABI_VERSION 2

/* Error codes returned by every tot_* entry point. */
enum tot_error {
    TOT_OK              = 0,
    TOT_ERR_INVALID     = 1,  /* invalid parameter name or value        */
    TOT_ERR_NOT_INIT    = 2,  /* tot_init has not been called yet       */
    TOT_ERR_CALC_FAILED = 3,  /* per-module init / calculation failed   */
    TOT_ERR_NOT_IMPL    = 4   /* L-2 stub return: not implemented       */
};

typedef struct {
    /* ---- orchestrator presence flags (0 = absent, 1 = initialized) */
    int    tr_present;
    int    ti_present;
    int    fp_present;
    int    wr_present;

    /* ---- integrated scalar slots (aggregated from per-module state) */
    int    nt, nrmax, nsmax;
    double T, WPT, AJT, Q0, BETA0, BETAP0, BETAA, BETAN;
    double TAUE1, TAUE2, ZEFF0, ALI, RQ1;

    /* ---- integrated profile slots (TR-authoritative at L-2 scope)   */
    double RN[TOT_MAX_NRMAX][TOT_MAX_NSMAX];
    double RT[TOT_MAX_NRMAX][TOT_MAX_NSMAX];
    double AJ[TOT_MAX_NRMAX];
    double QP[TOT_MAX_NRMAX];

    /* L-7b-i: total RF + external driven current [MA]. Matches
     * tot_state.f90 end-of-struct placement; ABI v2. */
    double AJRFT;
} tot_state_t;

int tot_init(void);
int tot_run(int ntmax);
/*
 * tot_set_param / tot_set_param_str : namespaced parameter dispatch.
 *
 * Names MUST include a namespace prefix separated by ':' because the
 * tot parameter space is the union of eq / tr / fp / ti / wr / wrx.
 * Examples:
 *   tot_set_param("eq:RR",  6.2);
 *   tot_set_param("tr:DT",  0.01);
 *   tot_set_param("fp:NSMAX", 2);
 *   tot_set_param("wrx:RF", 170.0);
 * A name without ':' is rejected with TOT_ERR_INVALID.
 *
 * tot_set_param_str handles CHARACTER variables (e.g. KNAMEQ). Only
 * the `tr:` namespace is backed by a string setter in L-3; the other
 * namespaces return TOT_ERR_INVALID for string calls until their
 * per-module registries add a symmetric `_str` entry point.
 */
int tot_set_param(const char* name, double value);
int tot_set_param_str(const char* name, const char* value);
int tot_get_state(tot_state_t* state);
int tot_finalize(void);

#ifdef __cplusplus
}
#endif

#endif /* TOT_API_H */
