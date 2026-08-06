! fp_api.f90
!
! Phase L-3: C ABI entry points for libfpapi (functional layer).
!
! All five functions are now wired to the real FPCOMM state:
!
!   fp_init       -> mtx_initialize + pl_init + eq_init + ob_init +
!                    fp_init (Fortran). FPCOMM defaults (NRMAX, NSAMAX,
!                    DELT, etc.) come from fpinit::fp_init. Allocation
!                    of FPCOMM arrays happens later, in fp_prep.
!   fp_set_param  -> dispatches to fp_param_registry::fp_param_set which
!                    handles ~40 namelist scalars/arrays.
!   fp_run        -> fp_prep (first call only; this also runs fp_allocate
!                    + fp_allocate_ntg{1,2}) + fp_loop with NTMAX set to
!                    the requested step count. NTMAX is restored after
!                    the loop so the namelist-configured value remains
!                    intact for subsequent calls.
!   fp_get_state  -> populates the fp_state_c struct from the same set of
!                    FPCOMM scalars/arrays that fpregress.f90 dumps:
!                    NRMAX, NSAMAX, NPMAX, NTHMAX, NTG2, TIMEFP, and
!                    profile arrays RNT/RWT/RTT/RJT/RPCT/RPWT(NR,NSA),
!                    plus the volume-integrated global scalars that
!                    FPWRTGLB otherwise only WRITEs to unit 6.
!   fp_finalize   -> fp_deallocate (+ ntg1/ntg2) and clears g_* flags.
!
! The Fortran-side names are fp_api_* to avoid colliding with the existing
! SUBROUTINE fp_init in fpinit.f90 (and friends); the C-side public names
! fp_init, fp_run, fp_set_param, fp_get_state, fp_finalize are bound
! through BIND(C, NAME=...) so external callers see the spec'd symbols.
!
! See docs/superpowers/plans/2026-04-18-fp-library-L3-param-registry.md.

MODULE fp_api
  USE, INTRINSIC :: ISO_C_BINDING
  USE fp_state, ONLY: fp_state_c, FP_MAX_NRMAX, FP_MAX_NSAMAX
  USE fpcomm,   ONLY: rkind, &
       NRMAX, NSAMAX, NPMAX, NTHMAX, NTG2, TIMEFP, &
       NTMAX, NTG1, TVOLR, &
       RNT, RWT, RTT, RJT, RPCT, RPWT, &
       PIT, PWT, PPCT, PPWT, PWRT, PWMT
  USE fp_param_registry, ONLY: fp_param_set, fp_param_set_str
  USE plinit,            ONLY: pl_init
  USE equnit,            ONLY: eq_init
  USE obinit,            ONLY: ob_init
  USE fpinit,            ONLY: fpinit_fortran => fp_init
  USE fpprep,            ONLY: fp_prep
  USE fploop,            ONLY: fp_loop
  USE libmtx,            ONLY: mtx_initialize, mtx_finalize
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: fp_api_init, fp_api_run, fp_api_get_state, &
            fp_api_set_param, fp_api_set_param_str, fp_api_finalize

  ! Error codes (must match fp_api.h enum):
  !   0 = OK
  !   1 = invalid parameter name / value
  !   2 = not initialized
  !   3 = calculation / initialization failed
  !   4 = (reserved, used in L-2 for "not implemented")
  INTEGER(C_INT), PARAMETER :: FP_OK              = 0
  INTEGER(C_INT), PARAMETER :: FP_ERR_INVALID     = 1
  INTEGER(C_INT), PARAMETER :: FP_ERR_NOT_INIT    = 2
  INTEGER(C_INT), PARAMETER :: FP_ERR_CALC_FAILED = 3

  ! Lifecycle flags (module-scope state, single instance only at L-3).
  LOGICAL, SAVE :: g_initialized = .FALSE.
  LOGICAL, SAVE :: g_prepared    = .FALSE.

CONTAINS

  !-------------------------------------------------------------------
  ! fp_init : run the standard FP namelist-default stack.
  !
  ! Mirrors fpmain.f90 with mtx_initialize -> pl_init -> eq_init ->
  ! ob_init -> fp_init (Fortran). FPCOMM array allocation is intentionally
  ! deferred to fp_prep (called from fp_run on the first invocation):
  ! fp_allocate depends on NRSTART/NREND/NPSTART/NPEND set up by
  ! fp_comm_setup, which itself runs inside fp_prep.
  !-------------------------------------------------------------------
  FUNCTION fp_api_init() RESULT(ierr) BIND(C, NAME="fp_init")
    INTEGER(C_INT) :: ierr

    IF (g_initialized) THEN
       ! Idempotent: already initialized, just return OK.
       ierr = FP_OK
       RETURN
    END IF

    CALL mtx_initialize
    ! Mirror fpmain.f90:41 — open the scratch unit that lib/libkio.f90
    ! hard-codes (WRITE(7)/REWIND(7)) for inline-namelist parsing
    ! used by fp_prep / eq_load chains. Same fix pattern as
    ! tr/tr_api.f90 (PR #103); without it, MODELG=3 fixtures
    ! (e.g. fp_iter01) corrupt geometry state silently and produce
    ! NaN profile.RJT.
    BLOCK
       INTEGER :: ios
       OPEN(7, STATUS='SCRATCH', FORM='FORMATTED', IOSTAT=ios)
       IF (ios /= 0) THEN
          ierr = FP_ERR_CALC_FAILED
          RETURN
       END IF
    END BLOCK
    CALL pl_init
    CALL eq_init
    CALL ob_init
    CALL fpinit_fortran

    g_initialized = .TRUE.
    g_prepared    = .FALSE.
    ierr = FP_OK
  END FUNCTION fp_api_init

  !-------------------------------------------------------------------
  ! fp_set_param : dispatch to the parameter registry.
  !-------------------------------------------------------------------
  FUNCTION fp_api_set_param(name, value) RESULT(ierr) BIND(C, NAME="fp_set_param")
    CHARACTER(KIND=C_CHAR), DIMENSION(*), INTENT(IN) :: name
    REAL(C_DOUBLE), VALUE,                INTENT(IN) :: value
    INTEGER(C_INT) :: ierr
    CHARACTER(LEN=64) :: fname
    INTEGER :: i, n

    IF (.NOT. g_initialized) THEN
       ierr = FP_ERR_NOT_INIT
       RETURN
    END IF

    ! Convert C string (NUL-terminated) to Fortran string.
    fname = ' '
    n = 0
    DO i = 1, LEN(fname)
       IF (name(i) == C_NULL_CHAR) EXIT
       fname(i:i) = name(i)
       n = i
    END DO

    IF (fp_param_set(TRIM(fname), REAL(value, KIND=rkind)) /= 0) THEN
       ierr = FP_ERR_INVALID
    ELSE
       ! A user who changes a profile-shape-altering variable needs to
       ! re-run fp_prep; invalidate g_prepared so the next fp_run picks
       ! up the new parameters.
       g_prepared = .FALSE.
       ierr = FP_OK
    END IF
  END FUNCTION fp_api_set_param

  !-------------------------------------------------------------------
  ! fp_set_param_str : string-valued parameter setter (KNAMEQ, ...).
  !
  ! Mirrors tr/tr_api.f90::tr_api_set_param_str (PR #103). Required
  ! for any future MODELG=3 fp fixture so the caller can set the
  ! equilibrium-data file name; without this the default
  ! KNAMEQ='eqdata' is missing in cwd, eq_load fails, and downstream
  ! BESEKNX trips with NCALC=-2.
  !-------------------------------------------------------------------
  FUNCTION fp_api_set_param_str(name, value) RESULT(ierr) BIND(C, NAME="fp_set_param_str")
    CHARACTER(KIND=C_CHAR), DIMENSION(*), INTENT(IN) :: name
    CHARACTER(KIND=C_CHAR), DIMENSION(*), INTENT(IN) :: value
    INTEGER(C_INT) :: ierr
    CHARACTER(LEN=64)  :: fname
    CHARACTER(LEN=128) :: fvalue
    INTEGER :: i

    IF (.NOT. g_initialized) THEN
       ierr = FP_ERR_NOT_INIT
       RETURN
    END IF

    fname = ' '
    DO i = 1, LEN(fname)
       IF (name(i) == C_NULL_CHAR) EXIT
       fname(i:i) = name(i)
    END DO
    fvalue = ' '
    DO i = 1, LEN(fvalue)
       IF (value(i) == C_NULL_CHAR) EXIT
       fvalue(i:i) = value(i)
    END DO

    IF (fp_param_set_str(TRIM(fname), TRIM(fvalue)) /= 0) THEN
       ierr = FP_ERR_INVALID
    ELSE
       g_prepared = .FALSE.
       ierr = FP_OK
    END IF
  END FUNCTION fp_api_set_param_str

  !-------------------------------------------------------------------
  ! fp_run : advance the simulation by ntmax_in steps.
  !
  ! NOTE: the dummy arg is `ntmax_in` (not `ntmax`) to avoid case-
  ! insensitive collision with the FPCOMM global `NTMAX` imported above.
  ! BIND(C, NAME="fp_run") keeps the external symbol as `fp_run`.
  !-------------------------------------------------------------------
  FUNCTION fp_api_run(ntmax_in) RESULT(ierr) BIND(C, NAME="fp_run")
    INTEGER(C_INT), VALUE, INTENT(IN) :: ntmax_in
    INTEGER(C_INT) :: ierr
    INTEGER :: ntmax_save, prep_ierr

    IF (.NOT. g_initialized) THEN
       ierr = FP_ERR_NOT_INIT
       RETURN
    END IF
    IF (ntmax_in < 0) THEN
       ierr = FP_ERR_INVALID
       RETURN
    END IF

    ! fp_prep allocates the FPCOMM arrays, sets up the velocity / radial
    ! mesh, and initializes the distribution function. It must run before
    ! the first fp_loop call and any time the caller updated a profile-
    ! shape-altering namelist variable (fp_api_set_param clears
    ! g_prepared).
    IF (.NOT. g_prepared) THEN
       CALL fp_prep(prep_ierr)
       IF (prep_ierr /= 0) THEN
          ierr = FP_ERR_CALC_FAILED
          RETURN
       END IF
       g_prepared = .TRUE.
    END IF

    ! Override NTMAX for this call so fp_loop steps exactly ntmax_in
    ! times. Restoring NTMAX afterwards leaves the namelist-configured
    ! value intact for subsequent calls.
    ntmax_save = NTMAX
    NTMAX      = ntmax_in
    CALL fp_loop
    NTMAX      = ntmax_save

    ierr = FP_OK
  END FUNCTION fp_api_run

  !-------------------------------------------------------------------
  ! fp_get_state : populate the C-visible state struct.
  !
  ! The scalar / profile set matches fpregress.f90 so that Layer-1 tests
  ! (L-6) can diff a C-driven run against a Fortran-driven run.
  !
  ! Memory layout: fp_state_c declares e.g. RNT(FP_MAX_NRMAX, FP_MAX_NSAMAX)
  ! in Fortran column-major order, which matches the C-side declaration
  ! double RNT[FP_MAX_NSAMAX][FP_MAX_NRMAX] (row-major) byte-for-byte.
  ! Only state%RNT(1:NRMAX, 1:NSAMAX) carries valid runtime data.
  !
  ! The 7 appended global scalars are the species sums FPWRTGLB builds
  ! before printing them (fp/fpsave.f90:260-311). They are the only part
  ! of the state that sees the volume element VOLR / TVOLR: the six
  ! profile arrays are per-unit-volume moments and stay bit-identical
  ! when only the equilibrium changes (MODELD=0, no wave, no CD), so
  ! without these an EQ->FP handoff is invisible to the caller.
  !-------------------------------------------------------------------
  FUNCTION fp_api_get_state(state) RESULT(ierr) BIND(C, NAME="fp_get_state")
    TYPE(fp_state_c), INTENT(OUT) :: state
    INTEGER(C_INT) :: ierr
    INTEGER :: nr, nsa, ntg_last, ntg1_last

    ! Always zero the struct so callers never see uninitialized memory.
    state%nrmax  = 0
    state%nsamax = 0
    state%npmax  = 0
    state%nthmax = 0
    state%ntg2   = 0
    state%timefp = 0.0_C_DOUBLE
    state%RNT  = 0.0_C_DOUBLE
    state%RWT  = 0.0_C_DOUBLE
    state%RTT  = 0.0_C_DOUBLE
    state%RJT  = 0.0_C_DOUBLE
    state%RPCT = 0.0_C_DOUBLE
    state%RPWT = 0.0_C_DOUBLE
    state%TOTAL_IP         = 0.0_C_DOUBLE
    state%STORED_ENERGY    = 0.0_C_DOUBLE
    state%COLLISION_POWER  = 0.0_C_DOUBLE
    state%ABSORPTION_POWER = 0.0_C_DOUBLE
    state%ABSORPTION_WR    = 0.0_C_DOUBLE
    state%ABSORPTION_WM    = 0.0_C_DOUBLE
    state%PLASMA_VOLUME    = 0.0_C_DOUBLE

    IF (.NOT. g_initialized) THEN
       ierr = FP_ERR_NOT_INIT
       RETURN
    END IF

    IF (NRMAX > FP_MAX_NRMAX .OR. NSAMAX > FP_MAX_NSAMAX) THEN
       ! Refusing rather than silently truncating: the static layout
       ! cannot hold the requested grid; the caller needs to rebuild
       ! libfpapi with a larger FP_MAX_* constant.
       ierr = FP_ERR_CALC_FAILED
       RETURN
    END IF

    ! Scalars (match fpregress.f90 dump set).
    state%nrmax  = NRMAX
    state%nsamax = NSAMAX
    state%npmax  = NPMAX
    state%nthmax = NTHMAX
    state%ntg2   = NTG2
    state%timefp = TIMEFP

    ! Profiles: only populate when FPCOMM arrays are allocated (i.e.
    ! after fp_prep ran successfully). Use the same NTG_LAST defensive
    ! index as fpregress.f90.
    IF (ALLOCATED(RNT) .AND. ALLOCATED(RWT) .AND. ALLOCATED(RTT) .AND. &
        ALLOCATED(RJT) .AND. ALLOCATED(RPCT) .AND. ALLOCATED(RPWT)) THEN
       ntg_last = MAX(NTG2, 1)
       DO nsa = 1, NSAMAX
          DO nr = 1, NRMAX
             state%RNT (nr, nsa) = RNT (nr, nsa, ntg_last)
             state%RWT (nr, nsa) = RWT (nr, nsa, ntg_last)
             state%RTT (nr, nsa) = RTT (nr, nsa, ntg_last)
             state%RJT (nr, nsa) = RJT (nr, nsa, ntg_last)
             state%RPCT(nr, nsa) = RPCT(nr, nsa, ntg_last)
             state%RPWT(nr, nsa) = RPWT(nr, nsa, ntg_last)
          END DO
       END DO
    END IF

    ! Global scalars. TVOLR and the P*T(NSA,NTG1) accumulators only
    ! exist once fp_prep has run (TVOLR: fp/fpprep.f90:231-234; the
    ! arrays: fpcomm::fp_allocate_ntg1) and only carry a sample once
    ! FPSGLB has bumped NTG1 (fp/fploop.f90:200). Before that they stay
    ! at the zeros set above rather than exposing uninitialised memory.
    IF (g_prepared) THEN
       state%PLASMA_VOLUME = TVOLR
       IF (NTG1 >= 1 .AND. ALLOCATED(PIT) .AND. ALLOCATED(PWT) .AND. &
           ALLOCATED(PPCT) .AND. ALLOCATED(PPWT) .AND. &
           ALLOCATED(PWRT) .AND. ALLOCATED(PWMT)) THEN
          ntg1_last = MIN(NTG1, SIZE(PIT, 2))
          DO nsa = 1, MIN(NSAMAX, SIZE(PIT, 1))
             ! Species sums, mirroring FPWRTGLB's rtotal* accumulators
             ! (fp/fpsave.f90:277-286).
             state%TOTAL_IP         = state%TOTAL_IP         + PIT (nsa, ntg1_last)
             state%STORED_ENERGY    = state%STORED_ENERGY    + PWT (nsa, ntg1_last)
             state%COLLISION_POWER  = state%COLLISION_POWER  + PPCT(nsa, ntg1_last)
             state%ABSORPTION_POWER = state%ABSORPTION_POWER + PPWT(nsa, ntg1_last)
             state%ABSORPTION_WR    = state%ABSORPTION_WR    + PWRT(nsa, ntg1_last)
             state%ABSORPTION_WM    = state%ABSORPTION_WM    + PWMT(nsa, ntg1_last)
          END DO
       END IF
    END IF

    ierr = FP_OK
  END FUNCTION fp_api_get_state

  !-------------------------------------------------------------------
  ! fp_finalize : clear the lifecycle flags.
  !
  ! IMPORTANT: fp_deallocate is intentionally NOT called here.
  ! fp_allocate in fpcomm.f90 guards a handful of arrays with model
  ! switches (e.g. Rconnor is only allocated when MODEL_DISRUPT /= 0),
  ! but fp_deallocate deallocates the same arrays unconditionally.
  ! Calling it after a "plain" fp_run therefore aborts with
  !   "Attempt to DEALLOCATE unallocated 'rconnor'"
  ! fpmain.f90 itself never calls fp_deallocate (it relies on process
  ! exit to release memory); we follow the same convention here.
  !
  ! Consequence: a second fp_init/fp_run cycle in the same process is
  ! not fully supported at L-3 (fp_allocate's internal NRMAX_save etc.
  ! short-circuit reallocation when sizes match). That limitation is
  ! inherited from the existing fpcomm lifecycle and is outside the
  ! scope of Phase L-3.
  !-------------------------------------------------------------------
  FUNCTION fp_api_finalize() RESULT(ierr) BIND(C, NAME="fp_finalize")
    INTEGER(C_INT) :: ierr

    IF (.NOT. g_initialized) THEN
       ! Idempotent: nothing to free, but not an error either.
       ierr = FP_OK
       RETURN
    END IF

    CALL mtx_finalize
    ! Pair with the OPEN(7) in fp_api_init so re-init after finalize
    ! does not try to OPEN an already-open unit.
    CLOSE(7, IOSTAT=ierr)

    g_initialized = .FALSE.
    g_prepared    = .FALSE.
    ierr = FP_OK
  END FUNCTION fp_api_finalize

END MODULE fp_api
