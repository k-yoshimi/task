! tr_api.f90
!
! Phase L-3: C ABI entry points for libtrapi (functional layer).
!
! All five functions are now wired to the real TRCOMM state:
!
!   tr_init       -> pl_init + eq_init + tr_init (Fortran) + ALLOCATE_TRCOMM
!                    populates TRCOMM default values including NRMAX=50,
!                    NSMAX=2, DT, NTSTEP, etc.
!   tr_set_param  -> dispatches to tr_param_registry::tr_param_set which
!                    handles ~34 namelist scalars/arrays.
!   tr_run        -> tr_prep (first call only) + tr_loop with NTMAX set to
!                    the requested step count; NTMAX is restored after
!                    the loop.
!   tr_get_state  -> populates the tr_state_c struct from the same set of
!                    TRCOMM scalars/arrays that trregress.f90 dumps.
!   tr_finalize   -> DEALLOCATE_TRCOMM + clears g_* flags.
!
! The Fortran-side names are tr_api_* to avoid colliding with the existing
! SUBROUTINE tr_init in trinit.f90 (and friends); the C-side public names
! tr_init, tr_run, tr_set_param, tr_get_state, tr_finalize are bound
! through BIND(C, NAME=...) so external callers see the spec'd symbols.
!
! See docs/superpowers/specs/2026-04-17-tr-library-design.md §4.

MODULE tr_api
  USE, INTRINSIC :: ISO_C_BINDING
  USE tr_state, ONLY: tr_state_c, TR_MAX_NRMAX, TR_MAX_NSMAX, &
                      tr_diag_entry_c, &
                      TR_DIAG_PARAM_LEN, TR_DIAG_MSG_LEN, &
                      TR_DIAG_OUT_OF_RANGE, TR_DIAG_FILE_MISSING
  USE TRCOM0,   ONLY: NSM
  USE trcomm,   ONLY: rkind, &
       NRMAX, NSMAX, NT, T, NTMAX, MODELG, KNAMEQ, &
       WPT, AJT, Q0, BETA0, BETAP0, BETAA, BETAN, &
       TAUE1, TAUE2, ZEFF0, ALI, RQ1, RN, RT, AJ, QP, &
       AJRFT, &
       EXTERNAL_DRIVEN_I, EXTERNAL_DRIVEN_RW, &
       ALLOCATE_TRCOMM, DEALLOCATE_TRCOMM
  USE tr_param_registry, ONLY: tr_param_set, tr_param_set_str
  USE plinit,            ONLY: pl_init
  USE equnit,            ONLY: eq_init
  USE trinit,            ONLY: trinit_fortran => tr_init
  USE trprep,            ONLY: tr_prep
  USE trloop,            ONLY: tr_loop
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: tr_api_init, tr_api_run, tr_api_get_state, &
            tr_api_set_param, tr_api_set_param_str, tr_api_finalize, &
            tr_api_validate

  ! Error codes (must match tr_api.h enum):
  !   0 = OK
  !   1 = invalid parameter name / value
  !   2 = not initialized
  !   3 = calculation / initialization failed
  !   4 = (reserved, used in L-2 for "not implemented")
  INTEGER(C_INT), PARAMETER :: TR_OK              = 0
  INTEGER(C_INT), PARAMETER :: TR_ERR_INVALID     = 1
  INTEGER(C_INT), PARAMETER :: TR_ERR_NOT_INIT    = 2
  INTEGER(C_INT), PARAMETER :: TR_ERR_CALC_FAILED = 3

  ! Lifecycle flags (module-scope state, single instance only at L-3).
  LOGICAL, SAVE :: g_initialized = .FALSE.
  LOGICAL, SAVE :: g_prepared    = .FALSE.

CONTAINS

  !-------------------------------------------------------------------
  ! tr_init : allocate TRCOMM and populate default parameter values.
  !-------------------------------------------------------------------
  FUNCTION tr_api_init() RESULT(ierr) BIND(C, NAME="tr_init")
    INTEGER(C_INT) :: ierr
    INTEGER :: alloc_ierr, ios_close

    IF (g_initialized) THEN
       ! Idempotent: already initialized, just return OK.
       ierr = TR_OK
       RETURN
    END IF

    ! Initialize parameter defaults through the standard stack used by
    ! trmain.f90: pl_init, eq_init, tr_init (Fortran) all set their own
    ! namelist defaults.
    CALL pl_init
    CALL eq_init
    ! Mirror trmain.f90:57 — open the scratch unit that tr_set_metric
    ! and friends use for inline namelist (eq_parm(2,'nrmax= 51',...))
    ! buffering. lib/libkio.f90:248-258 hard-codes WRITE(7)/REWIND(7),
    ! so NEWUNIT= is not viable; this matches the legacy convention
    ! used by trmain/eqmain. Without it, the C ABI path computes
    ! initial profiles with junk geometry and trcalc produces
    ! NEGATIVE TEMPERATURE at step 0 (Layer 1 repro: tr_tst2 MODELG=3).
    BLOCK
       INTEGER :: ios
       OPEN(7, STATUS='SCRATCH', FORM='FORMATTED', IOSTAT=ios)
       IF (ios /= 0) THEN
          ierr = TR_ERR_CALC_FAILED
          RETURN
       END IF
    END BLOCK
    CALL trinit_fortran

    ! Allocate TRCOMM arrays using NRMAX / NSMAX (etc.) defaults set by
    ! trinit_fortran.
    CALL ALLOCATE_TRCOMM(alloc_ierr)
    IF (alloc_ierr /= 0) THEN
       ! Pair the OPEN(7) above so a failed init does not leak the
       ! scratch unit (Bugbot MED on PR #103).
       CLOSE(7, IOSTAT=ios_close)
       ierr = TR_ERR_CALC_FAILED
       RETURN
    END IF

    g_initialized = .TRUE.
    g_prepared    = .FALSE.
    ierr = TR_OK
  END FUNCTION tr_api_init

  !-------------------------------------------------------------------
  ! tr_set_param : dispatch to the parameter registry.
  !-------------------------------------------------------------------
  FUNCTION tr_api_set_param(name, value) RESULT(ierr) BIND(C, NAME="tr_set_param")
    CHARACTER(KIND=C_CHAR), DIMENSION(*), INTENT(IN) :: name
    REAL(C_DOUBLE), VALUE,                INTENT(IN) :: value
    INTEGER(C_INT) :: ierr
    CHARACTER(LEN=64) :: fname
    INTEGER :: i, n

    IF (.NOT. g_initialized) THEN
       ierr = TR_ERR_NOT_INIT
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

    ! Changing NRMAX / NSMAX after allocation would invalidate the
    ! currently-allocated arrays. Rather than silently re-allocating we
    ! require the caller to finalize and re-init in that case.
    IF (tr_param_set(TRIM(fname), value) /= 0) THEN
       ierr = TR_ERR_INVALID
    ELSE
       ! A user who changes a profile-shape-altering variable needs to
       ! re-run tr_prep; invalidate g_prepared so the next tr_run picks
       ! up the new parameters.
       g_prepared = .FALSE.
       ierr = TR_OK
    END IF
  END FUNCTION tr_api_set_param

  !-------------------------------------------------------------------
  ! tr_set_param_str : string-valued parameter setter (KNAMEQ, ...).
  !
  ! Accepts two NUL-terminated C strings; both must fit in the
  ! fixed-length Fortran buffers (64 bytes for the name, 128 bytes for
  ! the value, matching the longest entry in the trcomm_ctrl
  ! CHARACTER(LEN=80) declarations with some slack).
  !-------------------------------------------------------------------
  FUNCTION tr_api_set_param_str(name, value) RESULT(ierr) BIND(C, NAME="tr_set_param_str")
    CHARACTER(KIND=C_CHAR), DIMENSION(*), INTENT(IN) :: name
    CHARACTER(KIND=C_CHAR), DIMENSION(*), INTENT(IN) :: value
    INTEGER(C_INT) :: ierr
    CHARACTER(LEN=64)  :: fname
    CHARACTER(LEN=128) :: fvalue
    INTEGER :: i

    IF (.NOT. g_initialized) THEN
       ierr = TR_ERR_NOT_INIT
       RETURN
    END IF

    ! Convert both C strings (NUL-terminated) to Fortran strings.
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

    IF (tr_param_set_str(TRIM(fname), TRIM(fvalue)) /= 0) THEN
       ierr = TR_ERR_INVALID
    ELSE
       ! Changing KNAMEQ (equilibrium data file) alters the tr_prep
       ! inputs; invalidate g_prepared so the next tr_run rebuilds.
       g_prepared = .FALSE.
       ierr = TR_OK
    END IF
  END FUNCTION tr_api_set_param_str

  !-------------------------------------------------------------------
  ! tr_run : advance the simulation by ntmax_in steps.
  !
  ! NOTE: the dummy arg is `ntmax_in` (not `ntmax`) to avoid case-
  ! insensitive collision with the TRCOMM global `NTMAX` imported above.
  ! BIND(C, NAME="tr_run") keeps the external symbol as `tr_run`.
  !-------------------------------------------------------------------
  FUNCTION tr_api_run(ntmax_in) RESULT(ierr) BIND(C, NAME="tr_run")
    INTEGER(C_INT), VALUE, INTENT(IN) :: ntmax_in
    INTEGER(C_INT) :: ierr
    INTEGER :: ntmax_save, calc_ierr, prep_ierr

    IF (.NOT. g_initialized) THEN
       ierr = TR_ERR_NOT_INIT
       RETURN
    END IF
    IF (ntmax_in < 0) THEN
       ierr = TR_ERR_INVALID
       RETURN
    END IF

    ! tr_prep builds the initial profile, metric and bpsd state. It must
    ! run before the first tr_loop call and any time the caller updated
    ! a profile-shape-altering namelist variable (tr_api_set_param
    ! clears g_prepared).
    IF (.NOT. g_prepared) THEN
       CALL tr_prep(prep_ierr)
       IF (prep_ierr /= 0) THEN
          ierr = TR_ERR_CALC_FAILED
          RETURN
       END IF
       g_prepared = .TRUE.
    END IF

    ! Override NTMAX for this call so tr_loop steps exactly ntmax_in
    ! times. tr_loop increments NT internally; restoring NTMAX afterwards
    ! leaves the namelist-configured value intact for subsequent calls.
    ntmax_save = NTMAX
    NTMAX      = NT + ntmax_in
    CALL tr_loop(calc_ierr)
    NTMAX      = ntmax_save
    IF (calc_ierr /= 0) THEN
       ierr = TR_ERR_CALC_FAILED
       RETURN
    END IF

    ierr = TR_OK
  END FUNCTION tr_api_run

  !-------------------------------------------------------------------
  ! tr_get_state : populate the C-visible state struct.
  !
  ! The scalar / profile set matches trregress.f90 so that Layer-1 tests
  ! (L-6) can diff a C-driven run against a Fortran-driven run.
  !-------------------------------------------------------------------
  FUNCTION tr_api_get_state(state) RESULT(ierr) BIND(C, NAME="tr_get_state")
    TYPE(tr_state_c), INTENT(OUT) :: state
    INTEGER(C_INT) :: ierr
    INTEGER :: nr, ns

    ! Always zero the struct so callers never see uninitialized memory.
    state%nt     = 0
    state%nrmax  = 0
    state%nsmax  = 0
    state%T      = 0.0_C_DOUBLE
    state%WPT    = 0.0_C_DOUBLE
    state%AJT    = 0.0_C_DOUBLE
    state%Q0     = 0.0_C_DOUBLE
    state%BETA0  = 0.0_C_DOUBLE
    state%BETAP0 = 0.0_C_DOUBLE
    state%BETAA  = 0.0_C_DOUBLE
    state%BETAN  = 0.0_C_DOUBLE
    state%TAUE1  = 0.0_C_DOUBLE
    state%TAUE2  = 0.0_C_DOUBLE
    state%ZEFF0  = 0.0_C_DOUBLE
    state%ALI    = 0.0_C_DOUBLE
    state%RQ1    = 0.0_C_DOUBLE
    state%RN     = 0.0_C_DOUBLE
    state%RT     = 0.0_C_DOUBLE
    state%AJ     = 0.0_C_DOUBLE
    state%QP     = 0.0_C_DOUBLE
    state%AJRFT  = 0.0_C_DOUBLE     ! L-7b-i

    IF (.NOT. g_initialized) THEN
       ierr = TR_ERR_NOT_INIT
       RETURN
    END IF

    IF (NRMAX > TR_MAX_NRMAX .OR. NSMAX > TR_MAX_NSMAX) THEN
       ! Refusing rather than silently truncating: the static layout
       ! cannot hold the requested grid, the caller needs to rebuild
       ! libtrapi with a larger TR_MAX_* constant.
       ierr = TR_ERR_CALC_FAILED
       RETURN
    END IF

    ! Scalars (match trregress.f90 dump set).
    state%nt     = NT
    state%nrmax  = NRMAX
    state%nsmax  = NSMAX
    state%T      = T
    state%WPT    = WPT
    state%AJT    = AJT
    state%Q0     = Q0
    state%BETA0  = BETA0
    state%BETAP0 = BETAP0
    state%BETAA  = BETAA
    state%BETAN  = BETAN
    state%TAUE1  = TAUE1
    state%TAUE2  = TAUE2
    state%ZEFF0  = ZEFF0
    state%ALI    = ALI
    state%RQ1    = RQ1
    state%AJRFT  = AJRFT             ! L-7b-i: includes EXTERNAL_DRIVEN_I contribution

    ! Profiles: only populate when TRCOMM arrays are allocated (they are
    ! after ALLOCATE_TRCOMM succeeds during tr_api_init). The transpose
    ! state%RN(ns, nr) = RN(nr, ns) takes care of the Fortran column-major
    ! vs C row-major layout (see §4.2 of the design doc).
    IF (ALLOCATED(RN) .AND. ALLOCATED(RT) .AND. &
        ALLOCATED(AJ) .AND. ALLOCATED(QP)) THEN
       DO nr = 1, NRMAX
          DO ns = 1, NSMAX
             state%RN(ns, nr) = RN(nr, ns)
             state%RT(ns, nr) = RT(nr, ns)
          END DO
          state%AJ(nr) = AJ(nr)
          state%QP(nr) = QP(nr)
       END DO
    END IF

    ierr = TR_OK
  END FUNCTION tr_api_get_state

  !-------------------------------------------------------------------
  ! tr_finalize : release TRCOMM arrays and clear the lifecycle flags.
  !-------------------------------------------------------------------
  FUNCTION tr_api_finalize() RESULT(ierr) BIND(C, NAME="tr_finalize")
    INTEGER(C_INT) :: ierr

    IF (.NOT. g_initialized) THEN
       ! Idempotent: nothing to free, but not an error either.
       ierr = TR_OK
       RETURN
    END IF

    CALL DEALLOCATE_TRCOMM
    ! Pair with the OPEN(7) in tr_api_init so re-init after finalize
    ! does not try to OPEN an already-open unit (SCRATCH would auto-
    ! delete on program exit but a same-process re-init would fail).
    CLOSE(7, IOSTAT=ierr)
    g_initialized = .FALSE.
    g_prepared    = .FALSE.
    ierr = TR_OK
  END FUNCTION tr_api_finalize

  !-------------------------------------------------------------------
  ! Issue #143 pilot: pre-run cross-parameter validation.
  !
  ! Returns up to diag_cap diagnostics in diag(0..ndiag-1). Read-only:
  ! does NOT modify any tr state. Caller workflow:
  !   tr_init -> tr_set_param(...) -> tr_validate -> fix -> tr_run
  !
  ! Categories covered at L-3 pilot:
  !   OUT_OF_RANGE: NSMAX overflow vs TRCOM0 compile-time NSM=4. The
  !                 registry accepts NSMAX in [2, 8] (matching the C
  !                 ABI TR_MAX_NSMAX capacity); values 5..8 then
  !                 overflow the TRCOM0::NSM compile-time maximum used
  !                 by several pl/ak imports, so trip this check
  !                 before tr_run lets the mesh hit the mismatch.
  !   FILE_MISSING: MODELG in {3,5,8} requires non-blank KNAMEQ. This
  !                 mirrors the eq_api::eq_api_validate guard — without
  !                 it, tr_run -> pl_prof_init -> equnit::eq_load opens
  !                 "" silently and fills the post-load grid with garbage.
  !
  ! Future categories (follow-up PRs): INCONSISTENT_PAIR,
  ! OUT_OF_RANGE_AFTER_DEP, MISSING_REQUIRED.
  !
  ! Note: NRMAX / NSZMAX / NSNMAX are NOT currently settable via
  ! tr_set_param (the registry does not expose them), so runtime values
  ! stay at their tr_init defaults and never exceed the compile-time
  ! maxima. Follow-ups that extend the registry should add matching
  ! checks here.
  !-------------------------------------------------------------------
  FUNCTION tr_api_validate(diag, diag_cap, ndiag) &
           RESULT(ierr) BIND(C, NAME="tr_validate")
    TYPE(tr_diag_entry_c), INTENT(OUT) :: diag(diag_cap)
    INTEGER(C_INT), VALUE, INTENT(IN)  :: diag_cap
    INTEGER(C_INT),        INTENT(OUT) :: ndiag
    INTEGER(C_INT) :: ierr
    INTEGER :: nlocal

    IF (.NOT. g_initialized) THEN
       ndiag = 0
       ierr  = TR_ERR_NOT_INIT
       RETURN
    END IF

    nlocal = 0

    ! ---- OUT_OF_RANGE: NSMAX overflow vs TRCOM0::NSM=4. -----------
    CALL push_oor("NSMAX", NSMAX, NSM)

    ! ---- FILE_MISSING: MODELG in {3,5,7,8} requires non-blank KNAMEQ.
    !      Without it, a subsequent tr_run path opens "" silently and
    !      fills the post-load grid with garbage:
    !        - MODELG 3/5/8: tr_run -> pl_prof_init -> equnit::eq_load
    !        - MODELG 7:     tr_set_metric -> pl_vmec (VMEC reader,
    !                        also takes KNAMEQ as the input filename)
    !      --------------------------------------------------------
    IF (MODELG == 3 .OR. MODELG == 5 .OR. MODELG == 7 .OR. MODELG == 8) THEN
       IF (LEN_TRIM(KNAMEQ) == 0) THEN
          CALL push_diag("KNAMEQ", TR_DIAG_FILE_MISSING, &
               "MODELG=3/5/7/8 requires non-blank KNAMEQ (eq/VMEC file)")
       END IF
    END IF

    ! ---- L-7b-i: OUT_OF_RANGE: EXTERNAL_DRIVEN_I requires positive width.
    !      Non-zero I with non-positive RW would silently normalize to zero
    !      in trprf, leaving AJRF unchanged. Surface this so callers know
    !      their setting was no-op rather than physically applied.
    IF (EXTERNAL_DRIVEN_I /= 0.D0 .AND. EXTERNAL_DRIVEN_RW <= 0.D0) THEN
       CALL push_diag("EXTERNAL_DRIVEN_RW", TR_DIAG_OUT_OF_RANGE, &
            "non-positive width with non-zero EXTERNAL_DRIVEN_I; profile cannot be normalized (silent no-op)")
    END IF

    ndiag = nlocal
    IF (nlocal == 0) THEN
       ierr = TR_OK
    ELSE
       ierr = TR_ERR_INVALID
    END IF

  CONTAINS

    !---------------------------------------------------------------
    ! Emit an OUT_OF_RANGE diagnostic if requested > max_value.
    !---------------------------------------------------------------
    SUBROUTINE push_oor(name_str, requested, max_value)
      CHARACTER(LEN=*), INTENT(IN) :: name_str
      INTEGER, INTENT(IN)          :: requested, max_value
      CHARACTER(LEN=TR_DIAG_MSG_LEN) :: m
      IF (requested <= max_value) RETURN
      WRITE(m, '(A,I0,A,I0)') &
           "value ", requested, " exceeds compile-time maximum ", max_value
      CALL push_diag(name_str, TR_DIAG_OUT_OF_RANGE, m)
    END SUBROUTINE push_oor

    !---------------------------------------------------------------
    ! Append (param, code, msg) to diag(). Skips storage if diag_cap
    ! is exhausted but still increments nlocal so the caller can
    ! detect truncation via ndiag_out > diag_cap.
    !---------------------------------------------------------------
    SUBROUTINE push_diag(name_str, code_in, msg_in)
      CHARACTER(LEN=*), INTENT(IN) :: name_str, msg_in
      INTEGER(C_INT),   INTENT(IN) :: code_in
      INTEGER :: i, n
      nlocal = nlocal + 1
      IF (nlocal > diag_cap) RETURN
      ! Zero-fill, then copy + NUL-terminate.
      DO i = 1, TR_DIAG_PARAM_LEN
         diag(nlocal)%param(i) = C_NULL_CHAR
      END DO
      n = MIN(LEN_TRIM(name_str), TR_DIAG_PARAM_LEN - 1)
      DO i = 1, n
         diag(nlocal)%param(i) = name_str(i:i)
      END DO
      DO i = 1, TR_DIAG_MSG_LEN
         diag(nlocal)%msg(i) = C_NULL_CHAR
      END DO
      n = MIN(LEN_TRIM(msg_in), TR_DIAG_MSG_LEN - 1)
      DO i = 1, n
         diag(nlocal)%msg(i) = msg_in(i:i)
      END DO
      diag(nlocal)%code = code_in
    END SUBROUTINE push_diag

  END FUNCTION tr_api_validate

END MODULE tr_api
