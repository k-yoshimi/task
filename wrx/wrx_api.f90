! wrx_api.f90
!
! Phase L-3: C ABI entry points for libwrxapi.so (functional layer).
!
! All five functions are now wired to the real wrcomm state:
!
!   wrx_init       -> pl_init + EQINIT + dp_init + wr_init (Fortran)
!                     populates default values for the WRX namelist
!                     (NRAYMAX=1, NSTPMAX=10000, RR/RA/BB defaults
!                     from plinit, etc.).
!   wrx_set_param  -> dispatches to wrx_param_registry::wrx_param_set
!                     which handles ~70 namelist scalars/arrays.
!   wrx_run        -> wr_prep + wr_allocate + wr_setup + wr_exec.
!                     If nstpmax_arg>0 it overrides NSTPMAX before the
!                     allocation step.
!   wrx_get_state  -> populates the wrx_state_c struct from the same set
!                     of wrcomm scalars/arrays that wrxregress.f90 dumps.
!                     Refuses (ierr=2) before wrx_run has populated the
!                     wrcomm allocations (Bugbot fix: g_run_called guard
!                     prevents reading garbage from unallocated arrays).
!   wrx_finalize   -> wr_deallocate (only if wrx_run actually allocated)
!                     and clears g_* lifecycle flags.
!
! The Fortran-side names are wrx_api_* to avoid colliding with any
! existing wrx subroutine and with the wr_api.f90 sibling (which
! uses wr_api_*); the C-side public names wrx_init, wrx_run,
! wrx_set_param, wrx_get_state, wrx_finalize are bound through
! BIND(C, NAME=...) so external callers see the spec'd wrx_*
! symbols (NOT wr_*). Verified non-collision between libwrxapi
! (wrx_*) and libwrapi (wr_*) via `nm`.
!
! See docs/superpowers/plans/2026-04-18-wrx-library-L3-param-registry.md.

MODULE wrx_api
  USE, INTRINSIC :: ISO_C_BINDING
  USE wrx_state, ONLY: wrx_state_c, WRX_MAX_NRAYMAX, WRX_MAX_NSAMAX
  USE wrcomm,    ONLY: rkind, &
       NRAYMAX, NSTPMAX, NSAMAX_WR, NSMAX, MODELG, MDLWRQ, &
       NSTPMAX_NRAY, &
       pwr_tot, pwr_nray, pwr_nsa, pwr_nsa_nray, &
       pos_pwrmax_rs_nsa, pwrmax_rs_nsa, &
       pos_pwrmax_rl_nsa, pwrmax_rl_nsa, &
       wr_allocate, wr_deallocate
  USE wrx_param_registry, ONLY: wrx_param_set
  USE plinit,  ONLY: pl_init
  USE dpinit,  ONLY: dp_init
  USE wrinit,  ONLY: wrinit_fortran => wr_init
  USE wrprep,  ONLY: wr_prep
  USE wrsetup, ONLY: wr_setup
  USE wrexec,  ONLY: wr_exec
  USE libmtx,  ONLY: mtx_initialize, mtx_finalize
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: wrx_api_init, wrx_api_run, wrx_api_get_state, &
            wrx_api_set_param, wrx_api_finalize

  ! Error codes (must match wrx_api.h enum):
  !   0 = OK
  !   1 = invalid parameter name / value
  !   2 = not initialized
  !   3 = calculation / initialization failed
  !   4 = (reserved, used in L-2 for "not implemented")
  INTEGER(C_INT), PARAMETER :: WRX_OK              = 0
  INTEGER(C_INT), PARAMETER :: WRX_ERR_INVALID     = 1
  INTEGER(C_INT), PARAMETER :: WRX_ERR_NOT_INIT    = 2
  INTEGER(C_INT), PARAMETER :: WRX_ERR_CALC_FAILED = 3

  ! Lifecycle flags (module-scope state, single instance only at L-3).
  LOGICAL, SAVE :: g_initialized = .FALSE.
  LOGICAL, SAVE :: g_run_called  = .FALSE.

  EXTERNAL EQINIT, GSOPEN, GSCLOS

CONTAINS

  !-------------------------------------------------------------------
  ! wrx_init : populate default namelist values via the standard stack
  ! used by wrmain.f90 (pl_init -> EQINIT -> dp_init -> wr_init).
  ! Allocation of wrcomm arrays happens inside wrx_run via wr_allocate
  ! (because the array sizes depend on NRAYMAX/NSTPMAX which the caller
  ! may set between init and run via wrx_set_param).
  !-------------------------------------------------------------------
  FUNCTION wrx_api_init() RESULT(ierr) BIND(C, NAME="wrx_init")
    INTEGER(C_INT) :: ierr

    IF (g_initialized) THEN
       ierr = WRX_OK   ! idempotent
       RETURN
    END IF

    ! wr_calc_pwr and friends rely on the commpi globals (nrank, nsize)
    ! being populated; mtx_initialize does this and is harmless when
    ! run outside MPI (libmtxnompi.f90 sets nrank=0, nsize=1).
    CALL mtx_initialize

    ! wr_calc_pwr (inside wr_exec) calls libgrf pages/pagee/grd1d which
    ! require GSOPEN. Mirror wrmain.f90 startup so the C ABI works
    ! without a caller needing to pre-open the graphics subsystem.
    CALL GSOPEN

    CALL pl_init
    CALL EQINIT
    CALL dp_init
    CALL wrinit_fortran

    g_initialized = .TRUE.
    g_run_called  = .FALSE.
    ierr = WRX_OK
  END FUNCTION wrx_api_init

  !-------------------------------------------------------------------
  ! wrx_set_param : dispatch to the parameter registry.
  !-------------------------------------------------------------------
  FUNCTION wrx_api_set_param(name, value) RESULT(ierr) &
       BIND(C, NAME="wrx_set_param")
    CHARACTER(KIND=C_CHAR), DIMENSION(*), INTENT(IN) :: name
    REAL(C_DOUBLE), VALUE,                INTENT(IN) :: value
    INTEGER(C_INT) :: ierr
    CHARACTER(LEN=64) :: fname
    INTEGER :: i

    IF (.NOT. g_initialized) THEN
       ierr = WRX_ERR_NOT_INIT
       RETURN
    END IF

    ! Convert C string (NUL-terminated) to Fortran string.
    fname = ' '
    DO i = 1, LEN(fname)
       IF (name(i) == C_NULL_CHAR) EXIT
       fname(i:i) = name(i)
    END DO

    IF (wrx_param_set(TRIM(fname), REAL(value, KIND=rkind)) /= 0) THEN
       ierr = WRX_ERR_INVALID
    ELSE
       ierr = WRX_OK
    END IF
  END FUNCTION wrx_api_set_param

  !-------------------------------------------------------------------
  ! wrx_run : run wr_prep -> wr_allocate -> wr_setup -> wr_exec once.
  !
  ! NOTE: dummy arg is nstpmax_arg (not nstpmax) to avoid case-
  ! insensitive collision with the wrcomm global NSTPMAX imported above.
  ! BIND(C, NAME="wrx_run") keeps the external C symbol as wrx_run.
  !
  ! nstpmax_arg > 0 overrides the namelist NSTPMAX before allocation;
  ! nstpmax_arg <= 0 keeps whatever wrx_set_param("NSTPMAX", ...) or
  ! wr_init defaulted.
  !-------------------------------------------------------------------
  FUNCTION wrx_api_run(nstpmax_arg) RESULT(ierr) BIND(C, NAME="wrx_run")
    INTEGER(C_INT), VALUE, INTENT(IN) :: nstpmax_arg
    INTEGER(C_INT) :: ierr
    INTEGER :: nstat, ierr_local

    IF (.NOT. g_initialized) THEN
       ierr = WRX_ERR_NOT_INIT
       RETURN
    END IF

    IF (nstpmax_arg > 0) NSTPMAX = nstpmax_arg

    CALL wr_prep(ierr_local)
    IF (ierr_local /= 0) THEN
       ierr = WRX_ERR_CALC_FAILED
       RETURN
    END IF

    CALL wr_allocate

    CALL wr_setup(ierr_local)
    IF (ierr_local /= 0) THEN
       ierr = WRX_ERR_CALC_FAILED
       RETURN
    END IF

    CALL wr_exec(nstat, ierr_local)
    IF (ierr_local /= 0) THEN
       ierr = WRX_ERR_CALC_FAILED
       RETURN
    END IF

    g_run_called = .TRUE.
    ierr = WRX_OK
  END FUNCTION wrx_api_run

  !-------------------------------------------------------------------
  ! wrx_get_state : populate the C-visible state struct.
  !
  ! Bugbot fix: explicitly reject when wrx_run has not been called yet,
  ! because the wrcomm power-deposition arrays (pwr_nray, pwr_nsa,
  ! NSTPMAX_NRAY, ...) are unallocated until wr_allocate runs inside
  ! wrx_run; reading them via UBOUND/SIZE in this function would
  ! seg-fault.
  !-------------------------------------------------------------------
  FUNCTION wrx_api_get_state(state) RESULT(ierr) BIND(C, NAME="wrx_get_state")
    TYPE(wrx_state_c), INTENT(OUT) :: state
    INTEGER(C_INT) :: ierr
    INTEGER :: nray, nsa, n_r, n_s

    ! Always zero the struct so callers never see uninitialized memory.
    state%nraymax           = 0
    state%nstpmax           = 0
    state%nsamax            = 0
    state%nsmax             = 0
    state%modelg            = 0
    state%mdlwrq            = 0
    state%pwr_tot           = 0.0_C_DOUBLE
    state%nstpmax_nray      = 0
    state%pwr_nray          = 0.0_C_DOUBLE
    state%pwr_nsa           = 0.0_C_DOUBLE
    state%pwr_nsa_nray      = 0.0_C_DOUBLE
    state%pos_pwrmax_rs_nsa = 0.0_C_DOUBLE
    state%pwrmax_rs_nsa     = 0.0_C_DOUBLE
    state%pos_pwrmax_rl_nsa = 0.0_C_DOUBLE
    state%pwrmax_rl_nsa     = 0.0_C_DOUBLE

    IF (.NOT. g_initialized) THEN
       ierr = WRX_ERR_NOT_INIT
       RETURN
    END IF

    IF (.NOT. g_run_called) THEN
       ! pwr_nray, pwr_nsa, NSTPMAX_NRAY, ... are populated by
       ! wr_allocate + wr_exec inside wrx_run. Without wrx_run these
       ! are unallocated -> we cannot read them. Reject explicitly
       ! using NOT_INIT (same code as the lifecycle-guard pattern
       ! everywhere else in this module).
       ierr = WRX_ERR_NOT_INIT
       RETURN
    END IF

    IF (NRAYMAX > WRX_MAX_NRAYMAX .OR. NSAMAX_WR > WRX_MAX_NSAMAX) THEN
       ! Static layout cannot hold the requested grid; caller needs to
       ! rebuild libwrxapi with larger WRX_MAX_* constants.
       ierr = WRX_ERR_CALC_FAILED
       RETURN
    END IF

    n_r = MIN(NRAYMAX, WRX_MAX_NRAYMAX)
    n_s = MIN(NSAMAX_WR, WRX_MAX_NSAMAX)

    state%nraymax = NRAYMAX
    state%nstpmax = NSTPMAX
    state%nsamax  = NSAMAX_WR
    state%nsmax   = NSMAX
    state%modelg  = MODELG
    state%mdlwrq  = MDLWRQ
    state%pwr_tot = pwr_tot

    DO nray = 1, n_r
       state%nstpmax_nray(nray) = NSTPMAX_NRAY(nray)
       state%pwr_nray(nray)     = pwr_nray(nray)
    END DO
    DO nsa = 1, n_s
       state%pwr_nsa(nsa)            = pwr_nsa(nsa)
       state%pos_pwrmax_rs_nsa(nsa)  = pos_pwrmax_rs_nsa(nsa)
       state%pwrmax_rs_nsa(nsa)      = pwrmax_rs_nsa(nsa)
       state%pos_pwrmax_rl_nsa(nsa)  = pos_pwrmax_rl_nsa(nsa)
       state%pwrmax_rl_nsa(nsa)      = pwrmax_rl_nsa(nsa)
    END DO
    DO nray = 1, n_r
       DO nsa = 1, n_s
          state%pwr_nsa_nray(nsa, nray) = pwr_nsa_nray(nsa, nray)
       END DO
    END DO

    ierr = WRX_OK
  END FUNCTION wrx_api_get_state

  !-------------------------------------------------------------------
  ! wrx_finalize : release wrcomm arrays and clear lifecycle flags.
  !
  ! wr_deallocate calls bare DEALLOCATE on every array; calling it
  ! before wr_allocate seg-faults. Guard with g_run_called and the
  ! ALLOCATED(pwr_nray) canary (pwr_nray is the first array touched
  ! by wr_allocate, so it tracks the allocation lifecycle reliably).
  !-------------------------------------------------------------------
  FUNCTION wrx_api_finalize() RESULT(ierr) BIND(C, NAME="wrx_finalize")
    INTEGER(C_INT) :: ierr

    IF (.NOT. g_initialized) THEN
       ierr = WRX_OK   ! idempotent: nothing to free
       RETURN
    END IF

    IF (g_run_called .AND. ALLOCATED(pwr_nray)) THEN
       CALL wr_deallocate
    END IF

    ! Close the graphics subsystem (opened by wrx_api_init); pair
    ! with the mtx_finalize below to mirror wrmain.f90 shutdown.
    CALL GSCLOS

    ! Balance the mtx_initialize done in wrx_api_init (libmtxnompi is
    ! a no-op here, but MPI backends require the shutdown call).
    CALL mtx_finalize

    g_run_called  = .FALSE.
    g_initialized = .FALSE.
    ierr = WRX_OK
  END FUNCTION wrx_api_finalize

END MODULE wrx_api
