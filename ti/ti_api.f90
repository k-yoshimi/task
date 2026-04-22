! ti_api.f90
!
! Phase L-3: C ABI entry points for libtiapi (functional layer).
!
! All five functions are now wired to the real TICOMM state:
!
!   ti_init       -> pl_init + eq_init + ti_init (Fortran) + allocate_ticomm
!                    populates TICOMM default values including NRMAX=50,
!                    NSMAX=2 (from pl_init), DT=0.01, NTSTEP=1, etc.
!   ti_set_param  -> dispatches to ti_param_registry::ti_param_set which
!                    handles ~35 namelist scalars/arrays. Clears g_prepared
!                    so profile-affecting changes pick up on the next run.
!   ti_run        -> ti_prep (first call only) + ti_exec with NTMAX set to
!                    the requested step count; NTMAX is restored after the
!                    loop.
!   ti_get_state  -> populates the ti_state_c struct from the TICOMM
!                    scalars / profile arrays (ZEFF, BETA, BETAP, etc.).
!   ti_finalize   -> deallocate_ticomm + clears g_* flags.
!
! The Fortran-side names are ti_api_* to avoid colliding with the existing
! SUBROUTINE ti_init in tiinit.f90 (and friends); the C-side public names
! ti_init, ti_run, ti_set_param, ti_get_state, ti_finalize are bound
! through BIND(C, NAME=...) so external callers see the spec'd symbols.
!
! See docs/superpowers/specs/2026-04-17-tr-library-design.md §4 and
! docs/superpowers/plans/2026-04-18-ti-library-L3-param-registry.md.

MODULE ti_api
  USE, INTRINSIC :: ISO_C_BINDING
  USE ti_state, ONLY: ti_state_c, TI_MAX_NRMAX, TI_MAX_NSA_MAX
  USE ticomm,   ONLY: rkind, &
       NRMAX, NSMAX, NT, T, NTMAX, &
       nsa_max, &
       residual_loop_max, icount_loop_max, icount_mat_max, &
       RNA, RTA, RUA, RBP, RQP, RJP, ZEFF, BETA, BETAP, &
       allocate_ticomm, deallocate_ticomm
  USE ti_param_registry, ONLY: ti_param_set
  USE plinit,            ONLY: pl_init
  USE equnit,            ONLY: eq_init
  USE tiinit,            ONLY: tiinit_fortran => ti_init
  USE tiprep,            ONLY: ti_prep
  USE tiexec,            ONLY: ti_exec
  USE libmtx,            ONLY: mtx_initialize, mtx_finalize
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: ti_api_init, ti_api_run, ti_api_get_state, &
            ti_api_set_param, ti_api_finalize

  ! Error codes (must match ti_api.h enum):
  !   0 = OK
  !   1 = invalid parameter name / value
  !   2 = not initialized
  !   3 = calculation / initialization failed
  !   4 = (reserved, used in L-2 for "not implemented")
  INTEGER(C_INT), PARAMETER :: TI_OK              = 0
  INTEGER(C_INT), PARAMETER :: TI_ERR_INVALID     = 1
  INTEGER(C_INT), PARAMETER :: TI_ERR_NOT_INIT    = 2
  INTEGER(C_INT), PARAMETER :: TI_ERR_CALC_FAILED = 3

  ! Lifecycle flags (module-scope state, single instance only at L-3).
  LOGICAL, SAVE :: g_initialized = .FALSE.
  LOGICAL, SAVE :: g_prepared    = .FALSE.

CONTAINS

  !-------------------------------------------------------------------
  ! ti_init : allocate TICOMM and populate default parameter values.
  !-------------------------------------------------------------------
  FUNCTION ti_api_init() RESULT(ierr) BIND(C, NAME="ti_init")
    INTEGER(C_INT) :: ierr
    INTEGER :: alloc_ierr

    IF (g_initialized) THEN
       ! Idempotent: already initialized, just return OK.
       ierr = TI_OK
       RETURN
    END IF

    ! libmtxnompi globals (nrank, nsize) must be populated before any
    ! mtx_allgather_real8 call (libmtxnompi.f90:704). Without this,
    ! `nsize` reads as garbage and `vtot(ndata*nsize)` becomes a
    ! negative-bound array → "Index '1' above upper bound of -888800"
    ! Fortran runtime error during run(). Mirrors wrx_api.f90:99 +
    ! fp_api.f90:86. Harmless under nompi (sets nrank=0, nsize=1).
    CALL mtx_initialize

    ! Mirror timain.f90:28 — open the scratch unit that lib/libkio.f90
    ! hard-codes (WRITE(7)/REWIND(7)) for inline-namelist parsing in
    ! TASK_PARM MODE=2 (used by tiparm/eqinit chains). Same fix pattern
    ! as tr/tr_api.f90 + fp/fp_api.f90:93; without it, future MODELG=3
    ! tilib fixtures would hit a Fortran runtime error on the unopened
    ! unit.
    BLOCK
       INTEGER :: ios
       OPEN(7, STATUS='SCRATCH', FORM='FORMATTED', IOSTAT=ios)
       IF (ios /= 0) THEN
          ierr = TI_ERR_CALC_FAILED
          RETURN
       END IF
    END BLOCK

    ! Initialize parameter defaults through the standard stack used by
    ! timain.f90: pl_init, eq_init, ti_init (Fortran) all set their own
    ! namelist defaults.
    CALL pl_init
    CALL eq_init
    CALL tiinit_fortran

    ! allocate_ticomm requires nsa_max to be set; mirror the typical
    ! ti_prep behavior of nsa_max = NSMAX (one species index per
    ! particle species). ti_prep itself overrides this when multi-level
    ! ionization (ID_NS=10/11/12) is in use, but for default electron +
    ! hydrogen this is correct and lets us allocate the TICOMM arrays
    ! before any tr_run call so ti_get_state has something to return.
    nsa_max = NSMAX
    CALL allocate_ticomm(alloc_ierr)
    IF (alloc_ierr /= 0) THEN
       ierr = TI_ERR_CALC_FAILED
       RETURN
    END IF

    g_initialized = .TRUE.
    g_prepared    = .FALSE.
    ierr = TI_OK
  END FUNCTION ti_api_init

  !-------------------------------------------------------------------
  ! ti_set_param : dispatch to the parameter registry.
  !-------------------------------------------------------------------
  FUNCTION ti_api_set_param(name, value) RESULT(ierr) BIND(C, NAME="ti_set_param")
    CHARACTER(KIND=C_CHAR), DIMENSION(*), INTENT(IN) :: name
    REAL(C_DOUBLE), VALUE,                INTENT(IN) :: value
    INTEGER(C_INT) :: ierr
    CHARACTER(LEN=64) :: fname
    INTEGER :: i

    IF (.NOT. g_initialized) THEN
       ierr = TI_ERR_NOT_INIT
       RETURN
    END IF

    ! Convert C string (NUL-terminated) to Fortran string.
    fname = ' '
    DO i = 1, LEN(fname)
       IF (name(i) == C_NULL_CHAR) EXIT
       fname(i:i) = name(i)
    END DO

    IF (ti_param_set(TRIM(fname), value) /= 0) THEN
       ierr = TI_ERR_INVALID
    ELSE
       ! A user who changes a profile-shape-altering variable needs to
       ! re-run ti_prep; invalidate g_prepared so the next ti_run picks
       ! up the new parameters.
       g_prepared = .FALSE.
       ierr = TI_OK
    END IF
  END FUNCTION ti_api_set_param

  !-------------------------------------------------------------------
  ! ti_run : advance the simulation by ntmax_in steps.
  !
  ! NOTE: the dummy arg is `ntmax_in` (not `ntmax`) to avoid case-
  ! insensitive collision with the TICOMM global `NTMAX` imported above.
  ! BIND(C, NAME="ti_run") keeps the external symbol as `ti_run`.
  !-------------------------------------------------------------------
  FUNCTION ti_api_run(ntmax_in) RESULT(ierr) BIND(C, NAME="ti_run")
    INTEGER(C_INT), VALUE, INTENT(IN) :: ntmax_in
    INTEGER(C_INT) :: ierr
    INTEGER :: ntmax_save, calc_ierr, prep_ierr

    IF (.NOT. g_initialized) THEN
       ierr = TI_ERR_NOT_INIT
       RETURN
    END IF
    IF (ntmax_in < 0) THEN
       ierr = TI_ERR_INVALID
       RETURN
    END IF

    ! ti_prep builds the initial profile, metric and bpsd state. It must
    ! run before the first ti_exec call and any time the caller updated
    ! a profile-shape-altering namelist variable (ti_api_set_param
    ! clears g_prepared).
    IF (.NOT. g_prepared) THEN
       CALL ti_prep(prep_ierr)
       IF (prep_ierr /= 0) THEN
          ierr = TI_ERR_CALC_FAILED
          RETURN
       END IF
       g_prepared = .TRUE.
    END IF

    ! Override NTMAX for this call so ti_exec runs exactly ntmax_in
    ! iterations. ti_exec increments NT internally; restoring NTMAX
    ! afterwards leaves the namelist-configured value intact for
    ! subsequent calls.
    ntmax_save = NTMAX
    NTMAX      = ntmax_in
    CALL ti_exec(calc_ierr)
    NTMAX      = ntmax_save
    IF (calc_ierr /= 0) THEN
       ierr = TI_ERR_CALC_FAILED
       RETURN
    END IF

    ierr = TI_OK
  END FUNCTION ti_api_run

  !-------------------------------------------------------------------
  ! ti_get_state : populate the C-visible state struct.
  !-------------------------------------------------------------------
  FUNCTION ti_api_get_state(state) RESULT(ierr) BIND(C, NAME="ti_get_state")
    TYPE(ti_state_c), INTENT(OUT) :: state
    INTEGER(C_INT) :: ierr
    INTEGER :: nr, nsa

    ! Always zero the struct so callers never see uninitialized memory.
    state%nt                = 0
    state%nrmax             = 0
    state%nsa_max           = 0
    state%nsmax             = 0
    state%T                 = 0.0_C_DOUBLE
    state%residual_loop_max = 0.0_C_DOUBLE
    state%icount_loop_max   = 0
    state%icount_mat_max    = 0
    state%RNA               = 0.0_C_DOUBLE
    state%RTA               = 0.0_C_DOUBLE
    state%RUA               = 0.0_C_DOUBLE
    state%RBP               = 0.0_C_DOUBLE
    state%RQP               = 0.0_C_DOUBLE
    state%RJP               = 0.0_C_DOUBLE
    state%ZEFF              = 0.0_C_DOUBLE
    state%BETA              = 0.0_C_DOUBLE
    state%BETAP             = 0.0_C_DOUBLE

    IF (.NOT. g_initialized) THEN
       ierr = TI_ERR_NOT_INIT
       RETURN
    END IF

    IF (NRMAX > TI_MAX_NRMAX .OR. nsa_max > TI_MAX_NSA_MAX) THEN
       ! Refusing rather than silently truncating: the static layout
       ! cannot hold the requested grid; rebuild libtiapi with larger
       ! TI_MAX_* constants.
       ierr = TI_ERR_CALC_FAILED
       RETURN
    END IF

    ! Scalars.
    state%nt                = NT
    state%nrmax             = NRMAX
    state%nsa_max           = nsa_max
    state%nsmax             = NSMAX
    state%T                 = T
    state%residual_loop_max = residual_loop_max
    state%icount_loop_max   = icount_loop_max
    state%icount_mat_max    = icount_mat_max

    ! Profiles. RNA/RTA/RUA in TICOMM are (nsa_max, NRMAX); the C struct
    ! shares the same column-major layout (state%RNA is declared
    ! (TI_MAX_NSA_MAX, TI_MAX_NRMAX) in Fortran which corresponds to
    ! double[TI_MAX_NRMAX][TI_MAX_NSA_MAX] in C row-major). Only the
    ! valid (1:nsa_max, 1:NRMAX) sub-block is meaningful; the remainder
    ! is zero from the wipe above.
    IF (ALLOCATED(RNA) .AND. ALLOCATED(RTA) .AND. ALLOCATED(RUA)) THEN
       DO nr = 1, NRMAX
          DO nsa = 1, nsa_max
             state%RNA(nsa, nr) = RNA(nsa, nr)
             state%RTA(nsa, nr) = RTA(nsa, nr)
             state%RUA(nsa, nr) = RUA(nsa, nr)
          END DO
       END DO
    END IF
    IF (ALLOCATED(RBP) .AND. ALLOCATED(RQP) .AND. ALLOCATED(RJP)) THEN
       DO nr = 1, NRMAX
          state%RBP(nr) = RBP(nr)
          state%RQP(nr) = RQP(nr)
          state%RJP(nr) = RJP(nr)
       END DO
    END IF
    IF (ALLOCATED(ZEFF) .AND. ALLOCATED(BETA) .AND. ALLOCATED(BETAP)) THEN
       DO nr = 1, NRMAX
          state%ZEFF(nr)  = ZEFF(nr)
          state%BETA(nr)  = BETA(nr)
          state%BETAP(nr) = BETAP(nr)
       END DO
    END IF

    ierr = TI_OK
  END FUNCTION ti_api_get_state

  !-------------------------------------------------------------------
  ! ti_finalize : release TICOMM arrays and clear the lifecycle flags.
  !-------------------------------------------------------------------
  FUNCTION ti_api_finalize() RESULT(ierr) BIND(C, NAME="ti_finalize")
    INTEGER(C_INT) :: ierr

    IF (.NOT. g_initialized) THEN
       ! Idempotent: nothing to free, but not an error either.
       ierr = TI_OK
       RETURN
    END IF

    CALL deallocate_ticomm
    ! Mirror wrx_api / fp_api shutdown: balance the mtx_initialize done
    ! in ti_api_init.
    CALL mtx_finalize
    ! Pair with the OPEN(7) in ti_api_init so re-init after finalize
    ! does not try to OPEN an already-open unit.
    BLOCK
       INTEGER :: cierr
       CLOSE(7, IOSTAT=cierr)
    END BLOCK
    g_initialized = .FALSE.
    g_prepared    = .FALSE.
    ierr = TI_OK
  END FUNCTION ti_api_finalize

END MODULE ti_api
