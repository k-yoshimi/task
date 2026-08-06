#ifndef FP_API_H
#define FP_API_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 * TASK/FP C ABI public header.
 *
 * Phase L-3 status: function symbols are present in libfpapi (built from
 * fp_api.f90) and wired to the real FPCOMM state:
 *   fp_init       -> mtx_initialize + pl_init + eq_init + ob_init +
 *                    fp_init (Fortran). Returns FP_OK.
 *   fp_set_param  -> dispatches through fp_param_registry to the
 *                    matching FPCOMM variable. ~40 namelist names
 *                    supported (see fp_param_registry.f90 for the
 *                    SELECT CASE list); unknown names return
 *                    FP_ERR_INVALID.
 *   fp_run        -> fp_prep on first call + fp_loop with NTMAX set to
 *                    the requested step count.
 *   fp_get_state  -> populates scalars + profile arrays (RNT/RWT/RTT/
 *                    RJT/RPCT/RPWT) + the volume-integrated global
 *                    scalars (TOTAL_IP ... PLASMA_VOLUME) from FPCOMM.
 *   fp_finalize   -> clears lifecycle flags. Note: FPCOMM arrays are
 *                    NOT deallocated (fp_allocate / fp_deallocate
 *                    asymmetry) so a single fp_init/fp_run/fp_finalize
 *                    per process is the supported lifecycle at L-3.
 *
 * See docs/superpowers/plans/2026-04-18-fp-library-L3-param-registry.md.
 *
 * Memory note: in C, RNT[NSAMAX][NRMAX] is row-major; in Fortran the
 * matching declaration is RNT(NRMAX, NSAMAX) (column-major). Layouts agree
 * byte-for-byte, but only RNT[0..nsamax-1][0..nrmax-1] are valid runtime
 * values (the remainder is padding up to FP_MAX_*).
 *
 * ABI note: fp_state_t only ever grows at the END of the struct, so the
 * offsets of pre-existing members are stable. Every change must be
 * mirrored in fp/fp_state.f90 and python/fplib/_ffi.py::FpStateC, and
 * libfpapi.so rebuilt (`make -C fp libfpapi.so`).
 */

#define FP_MAX_NRMAX  100
#define FP_MAX_NSAMAX 8

/* Error codes returned by every fp_* entry point. */
enum fp_error {
    FP_OK              = 0,
    FP_ERR_INVALID     = 1,  /* invalid parameter name or value     */
    FP_ERR_NOT_INIT    = 2,  /* fp_init has not been called yet     */
    FP_ERR_CALC_FAILED = 3,  /* calculation / initialization failed */
    FP_ERR_NOT_IMPL    = 4   /* reserved (was L-2 stub return)      */
};

typedef struct {
    int    nrmax;
    int    nsamax;
    int    npmax;
    int    nthmax;
    int    ntg2;
    double timefp;
    double RNT [FP_MAX_NSAMAX][FP_MAX_NRMAX];
    double RWT [FP_MAX_NSAMAX][FP_MAX_NRMAX];
    double RTT [FP_MAX_NSAMAX][FP_MAX_NRMAX];
    double RJT [FP_MAX_NSAMAX][FP_MAX_NRMAX];
    double RPCT[FP_MAX_NSAMAX][FP_MAX_NRMAX];
    double RPWT[FP_MAX_NSAMAX][FP_MAX_NRMAX];
    /* Global (volume-integrated) plasma scalars, species-summed at the
     * latest NTG1 sample. These are the quantities FP otherwise only
     * WRITEs to unit 6: the rtotal* line block (fp/fpsave.f90:305-311),
     * the W column of the per-species line (fp/fpsave.f90:252) and the
     * TVOLR banner (fp/fpprep.f90:237). Zero until the first run. */
    double TOTAL_IP;          /* total plasma current  [MA]  */
    double STORED_ENERGY;     /* stored energy         [MJ]  */
    double COLLISION_POWER;   /* total collision power [MW]  */
    double ABSORPTION_POWER;  /* total absorbed power  [MW]  */
    double ABSORPTION_WR;     /* WR (ray-tracing) part [MW]  */
    double ABSORPTION_WM;     /* WM (full-wave) part   [MW]  */
    double PLASMA_VOLUME;     /* TVOLR                 [m^3] */
} fp_state_t;

int fp_init(void);
int fp_run(int ntmax);
int fp_set_param(const char* name, double value);
int fp_set_param_str(const char* name, const char* value);
int fp_get_state(fp_state_t* state);
int fp_finalize(void);

#ifdef __cplusplus
}
#endif

#endif /* FP_API_H */
