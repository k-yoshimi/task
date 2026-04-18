! wr_api.f90
!
! Phase L-3: C ABI entry points for libwrapi (functional layer).
!
! All five functions are now wired to the real WRCOMM state:
!
!   wr_init       -> pl_init + EQINIT + dp_init + wr_init (Fortran).
!                    Lifecycle flag g_initialized is set; WR arrays are
!                    not allocated until the first wr_run (so that
!                    NRAYMAX / NSTPMAX may be tuned via wr_set_param
!                    between init and run).
!   wr_set_param  -> dispatches to wr_param_registry::wr_param_set which
!                    handles ~80 namelist scalars/arrays.
!   wr_run        -> wr_allocate + wr_setup + wr_exec, optionally with
!                    NRAYMAX overridden by the nray_request argument
!                    (>0).
!   wr_get_state  -> populates the wr_state_c struct with NRAYMAX /
!                    NRSMAX / NRLMAX, the global pwrmax_* scalars, the
!                    per-ray peak-power scalars and the radial profiles
!                    (pos_nrs / pwr_nrs and pos_nrl / pwr_nrl).
!                    Bound-checked against WR_MAX_*; ALLOCATED() guards
!                    on WRCOMM arrays mean a partially-initialized state
!                    yields zero-padded fields rather than a crash.
!   wr_finalize   -> wr_deallocate (only if WR arrays were allocated)
!                    and clears g_* flags.
!
! The Fortran-side names are wr_api_* to avoid colliding with the
! existing SUBROUTINE wr_init in wrinit.f90; the C-side public names
! wr_init, wr_run, wr_set_param, wr_get_state, wr_finalize are bound
! through BIND(C, NAME=...) so external callers see the spec'd symbols.
!
! See docs/superpowers/plans/2026-04-18-wr-library-L3-param-registry.md.
! Mirrors tr/tr_api.f90 (Phase L-3, PR #33).

MODULE wr_api
  USE, INTRINSIC :: ISO_C_BINDING
  USE wr_state, ONLY: wr_state_c, &
                      WR_MAX_NRAYMAX, WR_MAX_NRSMAX, WR_MAX_NRLMAX, &
                      WR_MAX_NRAY_EQ
  USE wrcomm,   ONLY: rkind, &
       NRAYMAX, NSTPMAX, NRSMAX, NRLMAX, NEQ, &
       NSTPMAX_NRAY, RAYS, &
       pos_nrs, pwr_nrs, pos_nrl, pwr_nrl, &
       pos_pwrmax_rs, pwrmax_rs, pos_pwrmax_rl, pwrmax_rl, &
       pos_pwrmax_rs_nray, pwrmax_rs_nray, &
       pos_pwrmax_rl_nray, pwrmax_rl_nray, &
       wr_allocate, wr_deallocate, wr_reset_alloc_state
  USE wr_param_registry, ONLY: wr_param_set
  USE plinit,            ONLY: pl_init
  USE dpinit,            ONLY: dp_init
  USE wrinit,            ONLY: wrinit_fortran => wr_init
  USE wrsetup,           ONLY: wr_setup
  USE wrexec,            ONLY: wr_exec
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: wr_api_init, wr_api_run, wr_api_get_state, &
            wr_api_set_param, wr_api_finalize

  ! Error codes (must match wr_api.h enum):
  !   0 = OK
  !   1 = invalid parameter name / value / index
  !   2 = not initialized
  !   3 = calculation / initialization failed
  !   4 = (reserved, used in L-2 for "not implemented")
  INTEGER(C_INT), PARAMETER :: WR_OK              = 0
  INTEGER(C_INT), PARAMETER :: WR_ERR_INVALID     = 1
  INTEGER(C_INT), PARAMETER :: WR_ERR_NOT_INIT    = 2
  INTEGER(C_INT), PARAMETER :: WR_ERR_CALC_FAILED = 3

  ! Lifecycle flags (module-scope state, single instance only at L-3).
  LOGICAL, SAVE :: g_initialized = .FALSE.
  LOGICAL, SAVE :: g_allocated   = .FALSE.

  EXTERNAL :: EQINIT

CONTAINS

  !-------------------------------------------------------------------
  ! wr_init : populate namelist defaults across the pl/eq/dp/wr stack.
  !
  ! WR arrays are NOT allocated here (deferred to wr_run) so callers can
  ! tune NRAYMAX / NSTPMAX via wr_set_param before the first run.
  !-------------------------------------------------------------------
  FUNCTION wr_api_init() RESULT(ierr) BIND(C, NAME="wr_init")
    INTEGER(C_INT) :: ierr

    IF (g_initialized) THEN
       ! Idempotent: already initialized, just return OK.
       ierr = WR_OK
       RETURN
    END IF

    ! Belt-and-suspenders: if a previous lifecycle left WRCOMM arrays
    ! allocated (e.g. caller crashed before wr_finalize), free them and
    ! reset the wr_allocate SAVE state so this cycle starts clean.
    ! Safe to call even on a fresh process (wr_deallocate is now
    ! ALLOCATED()-guarded; wr_reset_alloc_state is a pure flag reset).
    CALL wr_deallocate
    CALL wr_reset_alloc_state

    ! Match the trmain.f90 / wrmain.f90 init order:
    ! pl_init -> EQINIT -> dp_init -> wr_init (Fortran).
    CALL pl_init
    CALL EQINIT
    CALL dp_init
    CALL wrinit_fortran

    g_initialized = .TRUE.
    g_allocated   = .FALSE.
    ierr = WR_OK
  END FUNCTION wr_api_init

  !-------------------------------------------------------------------
  ! wr_set_param : dispatch to the parameter registry.
  !-------------------------------------------------------------------
  FUNCTION wr_api_set_param(name, value) RESULT(ierr) BIND(C, NAME="wr_set_param")
    CHARACTER(KIND=C_CHAR), DIMENSION(*), INTENT(IN) :: name
    REAL(C_DOUBLE), VALUE,                INTENT(IN) :: value
    INTEGER(C_INT) :: ierr
    CHARACTER(LEN=64) :: fname
    INTEGER :: i

    IF (.NOT. g_initialized) THEN
       ierr = WR_ERR_NOT_INIT
       RETURN
    END IF

    ! Convert C string (NUL-terminated) to Fortran string.
    fname = ' '
    DO i = 1, LEN(fname)
       IF (name(i) == C_NULL_CHAR) EXIT
       fname(i:i) = name(i)
    END DO

    IF (wr_param_set(TRIM(fname), value) /= 0) THEN
       ierr = WR_ERR_INVALID
    ELSE
       ierr = WR_OK
    END IF
  END FUNCTION wr_api_set_param

  !-------------------------------------------------------------------
  ! wr_run : allocate-if-needed, set up rays, and run wr_exec.
  !
  ! nray_request > 0 overrides the namelist NRAYMAX before allocation.
  ! nray_request <= 0 keeps whatever NRAYMAX was set via init / set_param.
  !-------------------------------------------------------------------
  FUNCTION wr_api_run(nray_request) RESULT(ierr) BIND(C, NAME="wr_run")
    INTEGER(C_INT), VALUE, INTENT(IN) :: nray_request
    INTEGER(C_INT) :: ierr
    INTEGER :: setup_ierr, exec_ierr, nstat

    IF (.NOT. g_initialized) THEN
       ierr = WR_ERR_NOT_INIT
       RETURN
    END IF

    IF (nray_request > 0) NRAYMAX = nray_request

    CALL wr_allocate
    g_allocated = .TRUE.

    CALL wr_setup(setup_ierr)
    IF (setup_ierr /= 0) THEN
       ierr = WR_ERR_CALC_FAILED
       RETURN
    END IF

    CALL wr_exec(nstat, exec_ierr)
    IF (exec_ierr /= 0) THEN
       ierr = WR_ERR_CALC_FAILED
       RETURN
    END IF

    ierr = WR_OK
  END FUNCTION wr_api_run

  !-------------------------------------------------------------------
  ! wr_get_state : populate the C-visible state struct from WRCOMM.
  !
  ! All ALLOCATABLE arrays are guarded with ALLOCATED() so a
  ! partially-initialized state (init without run, or wr_allocate that
  ! failed midway) yields zero-padded fields rather than a segfault.
  !-------------------------------------------------------------------
  FUNCTION wr_api_get_state(state) RESULT(ierr) BIND(C, NAME="wr_get_state")
    TYPE(wr_state_c), INTENT(OUT) :: state
    INTEGER(C_INT) :: ierr
    INTEGER :: nray, nrs, nrl, i, n

    ! Always zero the struct so callers never see uninitialized memory.
    state%nraymax = 0
    state%nrsmax  = 0
    state%nrlmax  = 0
    state%pos_pwrmax_rs      = 0.0_C_DOUBLE
    state%pwrmax_rs          = 0.0_C_DOUBLE
    state%pos_pwrmax_rl      = 0.0_C_DOUBLE
    state%pwrmax_rl          = 0.0_C_DOUBLE
    state%nstp_end           = 0
    state%pos_pwrmax_rs_nray = 0.0_C_DOUBLE
    state%pwrmax_rs_nray     = 0.0_C_DOUBLE
    state%pos_pwrmax_rl_nray = 0.0_C_DOUBLE
    state%pwrmax_rl_nray     = 0.0_C_DOUBLE
    state%rays_end           = 0.0_C_DOUBLE
    state%pos_nrs            = 0.0_C_DOUBLE
    state%pwr_nrs            = 0.0_C_DOUBLE
    state%pos_nrl            = 0.0_C_DOUBLE
    state%pwr_nrl            = 0.0_C_DOUBLE

    IF (.NOT. g_initialized) THEN
       ierr = WR_ERR_NOT_INIT
       RETURN
    END IF

    IF (NRAYMAX > WR_MAX_NRAYMAX .OR. &
        NRSMAX  > WR_MAX_NRSMAX  .OR. &
        NRLMAX  > WR_MAX_NRLMAX) THEN
       ! Refuse rather than silently truncate: the static layout cannot
       ! hold the requested grid, the caller must rebuild libwrapi with
       ! larger WR_MAX_* constants.
       ierr = WR_ERR_CALC_FAILED
       RETURN
    END IF

    state%nraymax       = NRAYMAX
    state%nrsmax        = NRSMAX
    state%nrlmax        = NRLMAX
    state%pos_pwrmax_rs = pos_pwrmax_rs
    state%pwrmax_rs     = pwrmax_rs
    state%pos_pwrmax_rl = pos_pwrmax_rl
    state%pwrmax_rl     = pwrmax_rl

    ! Per-ray scalars and end-state RAYS(0:NEQ, end, j).
    IF (ALLOCATED(NSTPMAX_NRAY)) THEN
       n = MIN(NRAYMAX, SIZE(NSTPMAX_NRAY))
       DO nray = 1, n
          state%nstp_end(nray) = NSTPMAX_NRAY(nray)
       END DO
    END IF
    IF (ALLOCATED(pos_pwrmax_rs_nray)) THEN
       n = MIN(NRAYMAX, SIZE(pos_pwrmax_rs_nray))
       DO nray = 1, n
          state%pos_pwrmax_rs_nray(nray) = pos_pwrmax_rs_nray(nray)
       END DO
    END IF
    IF (ALLOCATED(pwrmax_rs_nray)) THEN
       n = MIN(NRAYMAX, SIZE(pwrmax_rs_nray))
       DO nray = 1, n
          state%pwrmax_rs_nray(nray) = pwrmax_rs_nray(nray)
       END DO
    END IF
    IF (ALLOCATED(pos_pwrmax_rl_nray)) THEN
       n = MIN(NRAYMAX, SIZE(pos_pwrmax_rl_nray))
       DO nray = 1, n
          state%pos_pwrmax_rl_nray(nray) = pos_pwrmax_rl_nray(nray)
       END DO
    END IF
    IF (ALLOCATED(pwrmax_rl_nray)) THEN
       n = MIN(NRAYMAX, SIZE(pwrmax_rl_nray))
       DO nray = 1, n
          state%pwrmax_rl_nray(nray) = pwrmax_rl_nray(nray)
       END DO
    END IF

    ! End-state RAYS(0:NEQ, NSTP_END, NRAY).
    ! Fortran column-major rays_end(NRAY_EQ, NRAYMAX) matches C
    ! row-major rays_end[NRAYMAX][NRAY_EQ] byte-for-byte.
    IF (ALLOCATED(NSTPMAX_NRAY) .AND. ALLOCATED(RAYS)) THEN
       n = MIN(NRAYMAX, SIZE(NSTPMAX_NRAY))
       DO nray = 1, n
          IF (NSTPMAX_NRAY(nray) < 0 .OR. &
              NSTPMAX_NRAY(nray) > NSTPMAX) CYCLE
          DO i = 0, NEQ
             ! state index 1..NEQ+1 (1-origin) <- RAYS(0:NEQ)
             state%rays_end(i + 1, nray) = RAYS(i, NSTPMAX_NRAY(nray), nray)
          END DO
       END DO
    END IF

    ! Profiles: minor-radius and major-radius binned absorbed power.
    IF (ALLOCATED(pos_nrs) .AND. ALLOCATED(pwr_nrs)) THEN
       n = MIN(NRSMAX, SIZE(pos_nrs), SIZE(pwr_nrs))
       DO nrs = 1, n
          state%pos_nrs(nrs) = pos_nrs(nrs)
          state%pwr_nrs(nrs) = pwr_nrs(nrs)
       END DO
    END IF
    IF (ALLOCATED(pos_nrl) .AND. ALLOCATED(pwr_nrl)) THEN
       n = MIN(NRLMAX, SIZE(pos_nrl), SIZE(pwr_nrl))
       DO nrl = 1, n
          state%pos_nrl(nrl) = pos_nrl(nrl)
          state%pwr_nrl(nrl) = pwr_nrl(nrl)
       END DO
    END IF

    ierr = WR_OK
  END FUNCTION wr_api_get_state

  !-------------------------------------------------------------------
  ! wr_finalize : release WRCOMM arrays and clear lifecycle flags.
  !-------------------------------------------------------------------
  FUNCTION wr_api_finalize() RESULT(ierr) BIND(C, NAME="wr_finalize")
    INTEGER(C_INT) :: ierr

    IF (.NOT. g_initialized) THEN
       ! Idempotent: nothing to free, but not an error either.
       ierr = WR_OK
       RETURN
    END IF

    IF (g_allocated) THEN
       CALL wr_deallocate
       g_allocated = .FALSE.
    END IF

    ! Reset the wr_allocate SAVE state machine so a subsequent
    ! wr_init + wr_run cycle starts clean. Without this, the next
    ! wr_allocate would jump into its "already initialized" branch and
    ! double-free the just-deallocated arrays (Bugbot HIGH, PR #36).
    CALL wr_reset_alloc_state

    g_initialized = .FALSE.
    ierr = WR_OK
  END FUNCTION wr_api_finalize

END MODULE wr_api
