! eq_api.f90
!
! Phase L-2/L-3: C ABI entry points for libeqapi.
!
! Six BIND(C) functions are exposed:
!
!   eq_init           -> marks the library as initialized (idempotent)
!                        and returns EQ_OK. Does NOT touch the legacy
!                        eq COMMON blocks so existing eq / pl / ak
!                        binaries keep bit-identical behavior.
!   eq_run            -> L-3: mode=1 loads equilibrium via
!                        equnit::eq_load using the current MODELG +
!                        KNAMEQ. Other modes still return
!                        EQ_ERR_NOT_IMPL.
!   eq_set_param      -> delegates to eq_param_registry::eq_param_set
!                        (Phase L-3 real dispatch).
!   eq_set_param_str  -> delegates to eq_param_registry::eq_param_set_str
!                        for file-name parameters (KNAMEQ, KNAMWR, ...).
!   eq_get_state      -> reads grid dimensions and plasma scalars out of
!                        the legacy COMMON blocks via the F77 bridge
!                        routines in eq_api_common.f, then zeros the
!                        C struct and fills the scalars + 1D profiles
!                        up to the compile-time maxima in eq_state.
!   eq_finalize       -> clears the initialized flag. No COMMON cleanup
!                        yet (the legacy binaries rely on implicit
!                        static storage).
!
! Name-collision resolution: equnit.f already defines MODULE equnit
! with PUBLIC eq_init. The C-visible symbol also has to be named
! eq_init (per the design spec), so the BIND(C, NAME="eq_init")
! wrapper lives in this module as FUNCTION eq_api_init. When the
! wrapper needs to call equnit::eq_init / eq_load it renames the
! import with
!   USE equnit, ONLY: equnit_eq_init => eq_init, equnit_eq_load => eq_load
! avoiding the name clash inside this module.
!
! See docs/superpowers/specs/2026-04-17-tr-library-design.md §4 for
! the overall C ABI shape; tr_api.f90 / ti_api.f90 are the L-3
! references.

MODULE eq_api
  USE, INTRINSIC :: ISO_C_BINDING
  USE eq_state, ONLY: eq_state_c, &
                      EQ_MAX_NRGM, EQ_MAX_NZGM, EQ_MAX_NPSM, &
                      EQ_MAX_NRM,  EQ_MAX_NTHM, EQ_MAX_NSUM, &
                      eq_diag_entry_c, &
                      EQ_DIAG_PARAM_LEN, EQ_DIAG_MSG_LEN, &
                      EQ_DIAG_OUT_OF_RANGE, EQ_DIAG_FILE_MISSING
  USE eq_param_registry, ONLY: eq_param_set, eq_param_set_str
  ! Rename equnit::eq_init / eq_load away from the C-visible eq_init /
  ! eq_run symbols.
  USE equnit, ONLY: equnit_eq_init => eq_init, &
                    equnit_eq_load => eq_load
  ! Pull MODELG + KNAMEQ directly from plcomm so eq_api_run can forward
  ! them to equnit_eq_load without going through a COMMON-block bridge.
  USE plcomm, ONLY: MODELG, KNAMEQ
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: eq_api_init, eq_api_run, eq_api_get_state, &
            eq_api_set_param, eq_api_set_param_str, eq_api_finalize, &
            eq_api_validate, eq_api_save

  ! Error codes. Must match eq_api.h.
  INTEGER(C_INT), PARAMETER :: EQ_OK              = 0
  INTEGER(C_INT), PARAMETER :: EQ_ERR_INVALID     = 1
  INTEGER(C_INT), PARAMETER :: EQ_ERR_NOT_INIT    = 2
  INTEGER(C_INT), PARAMETER :: EQ_ERR_CALC_FAILED = 3
  INTEGER(C_INT), PARAMETER :: EQ_ERR_NOT_IMPL    = 4

  ! Lifecycle flag. Module-scope, single-instance (same pattern as tr / ti).
  LOGICAL, SAVE :: g_initialized = .FALSE.

CONTAINS

  !-------------------------------------------------------------------
  ! eq_init : L-2 scaffold. Flip the lifecycle flag and return EQ_OK.
  !-------------------------------------------------------------------
  FUNCTION eq_api_init() RESULT(ierr) BIND(C, NAME="eq_init")
    INTEGER(C_INT) :: ierr
    ! Populate the eq COMMON defaults (NRMAX=50, NTHMAX=64, NSUMAX=65,
    ! MODELG=2, KNAMEQ='eqdata', ...). The C-ABI is the SOLE entry
    ! point in the libeqapi.so context (no eq menu driver runs), so
    ! these defaults MUST be set here -- otherwise NRMAX/NTHMAX stay 0
    ! and equnit::eq_load's save/restore of those counters around
    ! eqload() leaves the post-load grid sized 0, which then corrupts
    ! the heap inside SPL2D in eqcalq (eqcalq.f90:1041). Callers can
    ! still override MODELG / KNAMEQ / etc. afterwards via
    ! eq_set_param / eq_set_param_str.
    CALL equnit_eq_init
    g_initialized = .TRUE.
    ierr = EQ_OK
  END FUNCTION eq_api_init

  !-------------------------------------------------------------------
  ! eq_run : dispatch on `mode` to the analytic or file-load path.
  !
  !   mode == 0 : run the analytic Grad-Shafranov solver (EQCALC).
  !               Mirrors the legacy `eqx2` CLI's `R` command and is
  !               the natural run path when MODELG=2 (the default,
  !               analytic toroidal geometry). EQCALC reads
  !               PP*/PJ*/FF*/PT*/PV* coefficients from the EQCOMM
  !               module and solves the fixed-boundary Grad-Shafranov
  !               problem; callers set those via eq_set_param
  !               beforehand.
  !   mode == 1 : load equilibrium from the file pointed to by KNAMEQ,
  !               then run eq_bpsd_init / eqcalq / eq_bpsd_put via
  !               equnit::eq_load. Mirrors the legacy `L` command.
  !               Requires MODELG ∈ {3, 5, 8} and a valid KNAMEQ.
  !   other     : EQ_ERR_NOT_IMPL (reserved for future modes).
  !-------------------------------------------------------------------
  FUNCTION eq_api_run(mode) RESULT(ierr) BIND(C, NAME="eq_run")
    INTEGER(C_INT), VALUE, INTENT(IN) :: mode
    INTEGER(C_INT) :: ierr
    INTEGER :: calc_ierr, load_ierr
    CHARACTER(LEN=80) :: knameq_local
    ! Contract: NOT_INIT takes precedence over INVALID (mirrors tr_api_run).
    ! So callers that hit an uninitialised library always see the same
    ! NOT_INIT error regardless of what other arguments they passed.
    IF (.NOT. g_initialized) THEN
       ierr = EQ_ERR_NOT_INIT
       RETURN
    END IF
    IF (mode < 0) THEN
       ierr = EQ_ERR_INVALID
       RETURN
    END IF

    SELECT CASE (mode)
    CASE (0)
       ! Analytic Grad-Shafranov solve via EQCALC, then post-process
       ! via EQCALQ to populate the ψ-surface profile + scalar
       ! diagnostics (qaxis/qsurf/betat/betap/pvol). EQCALC alone
       ! solves the fixed-boundary GS equation but doesn't compute the
       ! flux-surface averaged quantities; EQCALQ (also called by the
       ! `L` path after EQ_READ) computes the metric and reduces the
       ! 2D ψ-grid to 1D ψ-surface arrays. Mirrors the legacy CLI's
       ! `R` then `F` workflow.
       CALL EQCALC(calc_ierr)
       IF (calc_ierr /= 0) THEN
          ierr = EQ_ERR_CALC_FAILED
          RETURN
       END IF
       CALL EQCALQ(calc_ierr)
       IF (calc_ierr /= 0) THEN
          ierr = EQ_ERR_CALC_FAILED
          RETURN
       END IF
       ierr = EQ_OK
    CASE (1)
       ! EQDSK-based load via equnit::eq_load(MODELG, KNAMEQ, ierr).
       ! MODELG and KNAMEQ come from plcomm_parm; callers are expected
       ! to set them via eq_set_param / eq_set_param_str beforehand.
       knameq_local = KNAMEQ
       CALL equnit_eq_load(MODELG, knameq_local, load_ierr)
       IF (load_ierr /= 0) THEN
          ierr = EQ_ERR_CALC_FAILED
          RETURN
       END IF
       ierr = EQ_OK
    CASE DEFAULT
       ierr = EQ_ERR_NOT_IMPL
    END SELECT
  END FUNCTION eq_api_run

  !-------------------------------------------------------------------
  ! eq_set_param : delegate to the L-3 parameter registry.
  !-------------------------------------------------------------------
  FUNCTION eq_api_set_param(name, value) RESULT(ierr) &
           BIND(C, NAME="eq_set_param")
    CHARACTER(KIND=C_CHAR), DIMENSION(*), INTENT(IN) :: name
    REAL(C_DOUBLE), VALUE,                INTENT(IN) :: value
    INTEGER(C_INT) :: ierr
    CHARACTER(LEN=64) :: fname
    INTEGER :: i, reg_ierr

    IF (.NOT. g_initialized) THEN
       ierr = EQ_ERR_NOT_INIT
       RETURN
    END IF

    ! Convert C string (NUL-terminated) to Fortran string.
    fname = ' '
    DO i = 1, LEN(fname)
       IF (name(i) == C_NULL_CHAR) EXIT
       fname(i:i) = name(i)
    END DO

    CALL eq_param_set(TRIM(fname), value, reg_ierr)
    IF (reg_ierr == 0) THEN
       ierr = EQ_OK
    ELSE
       ierr = EQ_ERR_INVALID
    END IF
  END FUNCTION eq_api_set_param

  !-------------------------------------------------------------------
  ! eq_set_param_str : string-valued parameter setter (KNAMEQ, ...).
  !
  ! Mirrors the pattern in tr_api::tr_api_set_param_str.
  !-------------------------------------------------------------------
  FUNCTION eq_api_set_param_str(name, value) RESULT(ierr) &
           BIND(C, NAME="eq_set_param_str")
    CHARACTER(KIND=C_CHAR), DIMENSION(*), INTENT(IN) :: name
    CHARACTER(KIND=C_CHAR), DIMENSION(*), INTENT(IN) :: value
    INTEGER(C_INT) :: ierr
    CHARACTER(LEN=64) :: fname
    CHARACTER(LEN=80) :: fvalue
    INTEGER :: i, reg_ierr

    IF (.NOT. g_initialized) THEN
       ierr = EQ_ERR_NOT_INIT
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

    reg_ierr = eq_param_set_str(TRIM(fname), TRIM(fvalue))
    IF (reg_ierr == 0) THEN
       ierr = EQ_OK
    ELSE
       ierr = EQ_ERR_INVALID
    END IF
  END FUNCTION eq_api_set_param_str

  !-------------------------------------------------------------------
  ! eq_get_state : fill the C-visible struct from the legacy COMMON
  ! state via the F77 bridge in eq_api_common.f.
  !-------------------------------------------------------------------
  FUNCTION eq_api_get_state(state) RESULT(ierr) BIND(C, NAME="eq_get_state")
    TYPE(eq_state_c), INTENT(OUT) :: state
    INTEGER(C_INT) :: ierr
    INTEGER :: nrgmax_c, nzgmax_c, npsmax_c
    INTEGER :: nrmax_c,  nthmax_c, nsumax_c
    INTEGER :: nrvmax_c, nsgmax_c, ntgmax_c
    REAL(C_DOUBLE) :: raxis_v, zaxis_v, psi0_v, psipa_v, psita_v
    REAL(C_DOUBLE) :: qaxis_v, qsurf_v, betat_v, betap_v
    REAL(C_DOUBLE) :: pvol_v,  raave_v, ripx_v
    INTEGER :: ncopy_ps, nr_copy, nz_copy, nprof_copy

    ! Always zero the struct so callers never see uninitialized memory.
    state%nrgmax = 0
    state%nzgmax = 0
    state%npsmax = 0
    state%nrmax  = 0
    state%nthmax = 0
    state%nsumax = 0
    state%nrvmax = 0
    state%nsgmax = 0
    state%ntgmax = 0
    state%raxis  = 0.0_C_DOUBLE
    state%zaxis  = 0.0_C_DOUBLE
    state%psi0   = 0.0_C_DOUBLE
    state%psipa  = 0.0_C_DOUBLE
    state%psita  = 0.0_C_DOUBLE
    state%qaxis  = 0.0_C_DOUBLE
    state%qsurf  = 0.0_C_DOUBLE
    state%betat  = 0.0_C_DOUBLE
    state%betap  = 0.0_C_DOUBLE
    state%pvol   = 0.0_C_DOUBLE
    state%raave  = 0.0_C_DOUBLE
    state%ripx   = 0.0_C_DOUBLE
    state%psips  = 0.0_C_DOUBLE
    state%ppps   = 0.0_C_DOUBLE
    state%ttps   = 0.0_C_DOUBLE
    state%qqps   = 0.0_C_DOUBLE
    state%rg     = 0.0_C_DOUBLE
    state%zg     = 0.0_C_DOUBLE
    state%profile_psip = 0.0_C_DOUBLE
    state%profile_psit = 0.0_C_DOUBLE
    state%profile_pps  = 0.0_C_DOUBLE
    state%profile_tts  = 0.0_C_DOUBLE
    state%profile_qps  = 0.0_C_DOUBLE
    state%profile_vps  = 0.0_C_DOUBLE
    state%profile_rst  = 0.0_C_DOUBLE

    IF (.NOT. g_initialized) THEN
       ierr = EQ_ERR_NOT_INIT
       RETURN
    END IF

    ! Pull the current runtime counters (NRGMAX/NZGMAX/...) via the F77 bridge.
    ! Compile-time PARAMETER dims (NRGM/NZGM/...) are hard-encoded as
    ! EQ_MAX_* in eq_state.f90 and do not need a runtime fetch.
    CALL EQ_COMMON_GET_GRID_COUNTS(nrgmax_c, nzgmax_c, npsmax_c, &
                                   nrmax_c, nthmax_c, nsumax_c)

    state%nrgmax = nrgmax_c
    state%nzgmax = nzgmax_c
    state%npsmax = npsmax_c
    state%nrmax  = nrmax_c
    state%nthmax = nthmax_c
    state%nsumax = nsumax_c

    ! Secondary counters (NRVMAX/NSGMAX/NTGMAX) needed to mirror the
    ! Phase 0 baseline metrics for MODELG=3 EQRTSK loads.
    CALL EQ_COMMON_GET_AUX_GRID_COUNTS(nrvmax_c, nsgmax_c, ntgmax_c)
    state%nrvmax = nrvmax_c
    state%nsgmax = nsgmax_c
    state%ntgmax = ntgmax_c

    ! Per-NR flux-surface profile (NR=1..NRMAX) — mirrors the 7
    ! columns the Phase 0 baseline writes via eqregress.f. Indexed
    ! 1..NRMAX is the active runtime slice; trailing entries up to
    ! EQ_MAX_NRM stay zero from the initialisation above.
    !
    ! Bounds cap: the C-side state%profile_* arrays are sized
    ! EQ_MAX_NRM (1001) and the Fortran-side NRMAX (== nrmax_c) is
    ! nominally bounded by the same compile-time NRM=1001. Cap
    ! defensively with MIN(nrmax_c, EQ_MAX_NRM) anyway so a future
    ! resize of NRM (or stale eqcom1_mod state) cannot overflow the
    ! C buffer. Mirrors the same MIN(...) pattern used for the 1D
    ! profiles (npsmax_c) and the RZ grid (nrgmax_c/nzgmax_c) below.
    nprof_copy = MIN(nrmax_c, EQ_MAX_NRM)
    IF (nprof_copy > 0) THEN
       CALL EQ_COMMON_GET_PROFILE(nprof_copy, &
            state%profile_psip, state%profile_psit, &
            state%profile_pps,  state%profile_tts,  &
            state%profile_qps,  state%profile_vps,  &
            state%profile_rst)
    END IF

    ! Pull scalar plasma parameters.
    CALL EQ_COMMON_GET_SCALARS(raxis_v, zaxis_v, psi0_v, psipa_v, &
                               psita_v, qaxis_v, qsurf_v,         &
                               betat_v, betap_v, pvol_v,          &
                               raave_v, ripx_v)
    state%raxis = raxis_v
    state%zaxis = zaxis_v
    state%psi0  = psi0_v
    state%psipa = psipa_v
    state%psita = psita_v
    state%qaxis = qaxis_v
    state%qsurf = qsurf_v
    state%betat = betat_v
    state%betap = betap_v
    state%pvol  = pvol_v
    state%raave = raave_v
    state%ripx  = ripx_v

    ! 1D profile copy. NPSMAX can be zero before the first calc runs
    ! (L-2); cap at the compile-time maximum to avoid overruns.
    ncopy_ps = MIN(npsmax_c, EQ_MAX_NPSM)
    IF (ncopy_ps > 0) THEN
       CALL EQ_COMMON_GET_PROFILES_1D(ncopy_ps, state%psips, &
                                      state%ppps, state%ttps, &
                                      state%qqps)
    END IF

    ! RZ grid copy.
    nr_copy = MIN(nrgmax_c, EQ_MAX_NRGM)
    nz_copy = MIN(nzgmax_c, EQ_MAX_NZGM)
    IF (nr_copy > 0 .OR. nz_copy > 0) THEN
       CALL EQ_COMMON_GET_RZ_GRID(nr_copy, nz_copy, state%rg, state%zg)
    END IF

    ierr = EQ_OK
  END FUNCTION eq_api_get_state

  !-------------------------------------------------------------------
  ! eq_finalize : L-2 scaffold. Clear the flag, no COMMON cleanup.
  !-------------------------------------------------------------------
  FUNCTION eq_api_finalize() RESULT(ierr) BIND(C, NAME="eq_finalize")
    INTEGER(C_INT) :: ierr
    g_initialized = .FALSE.
    ierr = EQ_OK
  END FUNCTION eq_api_finalize

  !-------------------------------------------------------------------
  ! Issue #143 pilot: pre-run cross-parameter validation.
  !
  ! Returns up to diag_cap diagnostics in diag(0..ndiag-1). Read-only:
  ! does NOT modify any eq state. Caller workflow:
  !   eq_init -> eq_set_param(...) -> eq_validate -> fix -> eq_run
  !
  ! Categories covered:
  !   OUT_OF_RANGE  : 10 EQCHEK overflow guards (NSGMAX/NTGMAX/NUGMAX/
  !                   NRGMAX/NZGMAX/NPSMAX/NRMAX/NTHMAX/NSUMAX/NRVMAX
  !                   vs the eqcom0_mod compile-time maxima).
  !   FILE_MISSING  : MODELG in {3,5,8} requires non-blank KNAMEQ.
  !
  ! Future categories (left for follow-up PRs as the validation surface
  ! grows): INCONSISTENT_PAIR, OUT_OF_RANGE_AFTER_DEP, MISSING_REQUIRED.
  !-------------------------------------------------------------------
  FUNCTION eq_api_validate(diag, diag_cap, ndiag) &
           RESULT(ierr) BIND(C, NAME="eq_validate")
    USE eqcom0_mod, ONLY: NRGM, NZGM, NPSM, NSGM, NTGM, NUGM, &
                          NRM, NTHM, NSUM, NRVM
    USE eqcom1_mod, ONLY: NSGMAX, NTGMAX, NUGMAX, NRGMAX, NZGMAX, &
                          NPSMAX, NRMAX, NTHMAX, NSUMAX, NRVMAX
    TYPE(eq_diag_entry_c), INTENT(OUT) :: diag(diag_cap)
    INTEGER(C_INT), VALUE, INTENT(IN)  :: diag_cap
    INTEGER(C_INT),        INTENT(OUT) :: ndiag
    INTEGER(C_INT) :: ierr
    INTEGER :: nlocal

    IF (.NOT. g_initialized) THEN
       ndiag = 0
       ierr  = EQ_ERR_NOT_INIT
       RETURN
    END IF

    nlocal = 0

    ! ---- OUT_OF_RANGE: grid-overflow guards (port from EQCHEK in
    !      eqinit.f90:509-548; same checks the binary path runs at
    !      EQPARM time, missing from libeqapi.so callers). ---------
    CALL push_oor("NSGMAX", NSGMAX, NSGM)
    CALL push_oor("NTGMAX", NTGMAX, NTGM)
    CALL push_oor("NUGMAX", NUGMAX, NUGM)
    CALL push_oor("NRGMAX", NRGMAX, NRGM)
    CALL push_oor("NZGMAX", NZGMAX, NZGM)
    CALL push_oor("NPSMAX", NPSMAX, NPSM)
    CALL push_oor("NRMAX",  NRMAX,  NRM)
    CALL push_oor("NTHMAX", NTHMAX, NTHM)
    CALL push_oor("NSUMAX", NSUMAX, NSUM)
    CALL push_oor("NRVMAX", NRVMAX, NRVM)

    ! ---- FILE_MISSING: MODELG in {3,5,8} requires non-blank KNAMEQ.
    !      eq_run(1) -> equnit_eq_load otherwise opens "" silently
    !      and fills the post-load grid with garbage.
    IF (MODELG == 3 .OR. MODELG == 5 .OR. MODELG == 8) THEN
       IF (LEN_TRIM(KNAMEQ) == 0) THEN
          CALL push_diag("KNAMEQ", EQ_DIAG_FILE_MISSING, &
               "MODELG=3/5/8 requires non-blank KNAMEQ (eqdata file)")
       END IF
    END IF

    ndiag = nlocal
    IF (nlocal == 0) THEN
       ierr = EQ_OK
    ELSE
       ierr = EQ_ERR_INVALID
    END IF

  CONTAINS

    !---------------------------------------------------------------
    ! Helper: emit a single OUT_OF_RANGE diagnostic if requested
    ! grid count exceeds the compile-time maximum. Idempotent w.r.t.
    ! diag_cap exhaustion (extra diagnostics are silently dropped).
    !---------------------------------------------------------------
    SUBROUTINE push_oor(name_str, requested, max_value)
      CHARACTER(LEN=*), INTENT(IN) :: name_str
      INTEGER, INTENT(IN)          :: requested, max_value
      CHARACTER(LEN=EQ_DIAG_MSG_LEN) :: m
      IF (requested <= max_value) RETURN
      WRITE(m, '(A,I0,A,I0)') &
           "value ", requested, " exceeds compile-time maximum ", max_value
      CALL push_diag(name_str, EQ_DIAG_OUT_OF_RANGE, m)
    END SUBROUTINE push_oor

    !---------------------------------------------------------------
    ! Helper: append (param, code, msg) to diag(). Skips if diag_cap
    ! is exhausted but still increments nlocal so caller can detect
    ! truncation by ndiag > diag_cap (NOTE: callers should size
    ! diag_cap >= EQ_DIAG_CAP_HINT == 32 to avoid this).
    !---------------------------------------------------------------
    SUBROUTINE push_diag(name_str, code_in, msg_in)
      CHARACTER(LEN=*), INTENT(IN) :: name_str, msg_in
      INTEGER(C_INT),   INTENT(IN) :: code_in
      INTEGER :: i, n
      nlocal = nlocal + 1
      IF (nlocal > diag_cap) RETURN
      ! Zero-fill, then copy + NUL-terminate.
      DO i = 1, EQ_DIAG_PARAM_LEN
         diag(nlocal)%param(i) = C_NULL_CHAR
      END DO
      n = MIN(LEN_TRIM(name_str), EQ_DIAG_PARAM_LEN - 1)
      DO i = 1, n
         diag(nlocal)%param(i) = name_str(i:i)
      END DO
      DO i = 1, EQ_DIAG_MSG_LEN
         diag(nlocal)%msg(i) = C_NULL_CHAR
      END DO
      n = MIN(LEN_TRIM(msg_in), EQ_DIAG_MSG_LEN - 1)
      DO i = 1, n
         diag(nlocal)%msg(i) = msg_in(i:i)
      END DO
      diag(nlocal)%code = code_in
    END SUBROUTINE push_diag

  END FUNCTION eq_api_validate

  !=====================================================================
  ! eq_save : C-ABI wrapper around eqfile::EQSAVE.
  !
  !   - Writes the current EQ state (PSIRZ, profiles, scalars) to the
  !     TASK-internal binary file at the path stored in module-level
  !     KNAMEQ. Caller MUST set KNAMEQ via eq_set_param_str before
  !     calling this. EQSAVE itself does not propagate errors, so this
  !     wrapper verifies the outcome: EQ_ERR_INVALID for a blank KNAMEQ,
  !     EQ_ERR_CALC_FAILED when no non-empty file exists afterwards
  !     (missing directory, permission denied, ...), EQ_OK otherwise.
  !=====================================================================
  FUNCTION eq_api_save() RESULT(ierr) BIND(C, NAME="eq_save")
    INTEGER(C_INT) :: ierr
    LOGICAL :: file_exists
    INTEGER :: file_size, ierr_save
    IF (.NOT. g_initialized) THEN
       ierr = EQ_ERR_NOT_INIT
       RETURN
    END IF
    ! #227 item 3: EQSAVE is a bare external subroutine with no IERR
    ! out-argument -- on an FWOPEN failure (blank KNAMEQ, missing
    ! directory, permission denied) it simply RETURNs, leaving no file.
    ! Reporting EQ_OK there claims a success that did not happen, so
    ! verify the artefact rather than trusting the call.
    IF (LEN_TRIM(KNAMEQ) == 0) THEN
       ierr = EQ_ERR_INVALID
       RETURN
    END IF
    CALL EQSAVE(ierr_save)
    IF (ierr_save /= 0) THEN
       ierr = EQ_ERR_CALC_FAILED
       RETURN
    END IF
!   Belt and braces: the open succeeded, so also confirm an artefact exists.
    INQUIRE(FILE=TRIM(KNAMEQ), EXIST=file_exists, SIZE=file_size)
    IF ((.NOT. file_exists) .OR. (file_size <= 0)) THEN
       ierr = EQ_ERR_CALC_FAILED
       RETURN
    END IF
    ierr = EQ_OK
  END FUNCTION eq_api_save

END MODULE eq_api
