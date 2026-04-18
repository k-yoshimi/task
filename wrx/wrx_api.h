#ifndef WRX_API_H
#define WRX_API_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 * TASK/WRX library C ABI public header.
 *
 * Phase L-3 status: all five entry points wired to the real wrcomm
 * stack (pl_init/EQINIT/dp_init/wr_init in wrx_init; ~70 namelist
 * parameters dispatched via wrx_param_registry in wrx_set_param;
 * wr_prep+wr_allocate+wr_setup+wr_exec in wrx_run; wrcomm scalars
 * and 1-D/2-D power-deposition arrays copied into wrx_state_t in
 * wrx_get_state; wr_deallocate guarded by g_run_called in
 * wrx_finalize). WRX_ERR_NOT_IMPL is preserved for backward
 * compatibility but is no longer returned by any entry point.
 *
 * See docs/superpowers/plans/2026-04-18-wrx-library-L3-param-registry.md
 * and docs/superpowers/plans/2026-04-18-wrx-library-L2-c-abi-foundation.md.
 *
 * Upper bounds for the fixed-size state struct:
 *   WRX_MAX_NRAYMAX = 100  (matches NRAYM in wrcomm_parm)
 *   WRX_MAX_NSAMAX  = 8    (matches NSM in pl/plcomm)
 * Actual runtime nraymax/nsamax must be <= these.
 *
 * Memory note: in C, pwr_nsa_nray[NRAYMAX][NSAMAX] is row-major; in
 * Fortran the matching declaration is pwr_nsa_nray(NSAMAX, NRAYMAX)
 * (column-major). The two layouts agree byte-for-byte, but only
 * [0..nraymax-1][0..nsamax-1] carry valid runtime values (the rest is
 * padding up to WRX_MAX_*).
 */

#define WRX_MAX_NRAYMAX 100
#define WRX_MAX_NSAMAX  8

/* Error codes returned by every wrx_* entry point. */
enum wrx_error {
    WRX_OK              = 0,
    WRX_ERR_INVALID     = 1,  /* invalid parameter name or value     */
    WRX_ERR_NOT_INIT    = 2,  /* wrx_init has not been called yet    */
    WRX_ERR_CALC_FAILED = 3,  /* calculation / initialization failed */
    WRX_ERR_NOT_IMPL    = 4   /* L-2 stub return: not implemented    */
};

typedef struct {
    int    nraymax;
    int    nstpmax;
    int    nsamax;
    int    nsmax;
    int    modelg;
    int    mdlwrq;
    double pwr_tot;
    int    nstpmax_nray[WRX_MAX_NRAYMAX];
    double pwr_nray[WRX_MAX_NRAYMAX];
    double pwr_nsa[WRX_MAX_NSAMAX];
    double pwr_nsa_nray[WRX_MAX_NRAYMAX][WRX_MAX_NSAMAX];
    double pos_pwrmax_rs_nsa[WRX_MAX_NSAMAX];
    double pwrmax_rs_nsa[WRX_MAX_NSAMAX];
    double pos_pwrmax_rl_nsa[WRX_MAX_NSAMAX];
    double pwrmax_rl_nsa[WRX_MAX_NSAMAX];
} wrx_state_t;

int wrx_init(void);
int wrx_run(int nstpmax);
int wrx_set_param(const char* name, double value);
int wrx_get_state(wrx_state_t* state);
int wrx_finalize(void);

#ifdef __cplusplus
}
#endif

#endif /* WRX_API_H */
