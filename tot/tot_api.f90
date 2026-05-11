! tot_api.f90
!
! Phase L-6: C ABI entry points for libtotapi.so (functional layer).
!
! TOT is the orchestrator module — its lifecycle fans out to the four
! libraryized per-module APIs (tr_api, ti_api, fp_api, wr_api). The
! pl/eq foundation modules are initialized through tr_api_init's own
! pl_init / eq_init calls (and again via the others for idempotent
! safety). wm/dp do NOT have shared-library back-ends yet and are
! intentionally skipped at L-6; the full integrated wm pipeline that
! totmain.f90 drives stays accessible through the standalone `tot`
! binary.
!
! Mapping vs totmain.f90:
!   binary order : pl_init -> eq_init -> tr_init -> dp_init ->
!                  wr_init -> wm_init -> fp_init -> ti_init
!   library order: tr_api_init -> ti_api_init -> fp_api_init ->
!                  wr_api_init   (each *_api_init internally calls
!                                 pl_init + eq_init as needed; the
!                                 second call to pl_init / eq_init is
!                                 a no-op because both are flag-guarded
!                                 in their own modules)
!
! At L-6 the run path only advances the TR transport solver
! (tr_api_run). Wiring fp_api_run / wr_api_run into the run loop
! requires deciding the cross-module data flow (e.g. wr -> tr power
! deposition coupling), which is outside L-6 scope; the orchestrator
! still initializes them so a future L-7 can swap in real coupling
! without changing the public ABI.
!
! get_state aggregates from tr_api_get_state into the TR-authoritative
! slots of tot_state_c. The presence flags reflect the *_api_init
! lifecycle so callers can tell which sub-modules are active. ti / fp /
! wr per-module state aggregation is a follow-up; today their slots in
! tot_state_c are intentionally absent (the .h struct stays L-2 layout)
! and the presence flag is the only signal that they were brought up.
!
! Lifecycle is idempotent in both directions, mirroring tr/tr_api.f90:
! double-init returns OK without re-entering, double-finalize returns
! OK without crashing, and finalize -> init -> run reuses the heap
! cleanly (tr's PR #103 OPEN(7) fix is inherited via tr_api_init).
!
! Error codes (must match tot_api.h enum):
!   0 = OK
!   1 = invalid parameter name / value
!   2 = not initialized (returned by run / get_state before init)
!   3 = per-module init / calculation failed
!   4 = (reserved, used in L-2..L-5 for "not implemented")
!
! The Fortran-side names are tot_api_* to avoid colliding with any
! existing `SUBROUTINE tot_init` style names in tot*.f90; the C-side
! public symbols tot_init, tot_run, tot_set_param, tot_get_state and
! tot_finalize are bound through BIND(C, NAME=...) so external callers
! see the spec'd symbols.

MODULE tot_api
  USE, INTRINSIC :: ISO_C_BINDING
  USE tot_state, ONLY: tot_state_c, TOT_MAX_NRMAX, TOT_MAX_NSMAX
  USE tot_param_registry, ONLY: tot_param_set, tot_param_set_str
  ! Per-module APIs (libraryized in L-3). We rename each *_api_*
  ! function to a tot-local alias so the four namespaces do not collide
  ! when the wrap module pulls them all in.
  USE tr_api, ONLY: tr_api_init,     tr_api_run,     tr_api_get_state, &
                    tr_api_finalize
  USE tr_state, ONLY: tr_state_c
  USE ti_api, ONLY: ti_api_init,     ti_api_run,     ti_api_finalize
  USE fp_api, ONLY: fp_api_init,     fp_api_run,     fp_api_finalize
  ! tot links wrx/libwr.a (not wr/libwr.a), so the only wrcomm copy in
  ! the link graph is wrx's. Using wr_api (from wr/) here would pull in
  ! wr's wrcomm and clash at link time. Route through wrx_api instead —
  ! this mirrors tot_param_registry.f90's wr -> wrx alias dispatch.
  USE wrx_api, ONLY: wr_api_init     => wrx_api_init, &
                     wr_api_run      => wrx_api_run, &
                     wr_api_finalize => wrx_api_finalize
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: tot_api_init, tot_api_run, tot_api_get_state, &
            tot_api_set_param, tot_api_set_param_str, tot_api_finalize

  ! Error codes (must match tot_api.h enum).
  INTEGER(C_INT), PARAMETER :: TOT_ERR_OK              = 0
  INTEGER(C_INT), PARAMETER :: TOT_ERR_INVALID         = 1
  INTEGER(C_INT), PARAMETER :: TOT_ERR_NOT_INIT        = 2
  INTEGER(C_INT), PARAMETER :: TOT_ERR_INIT_FAILED     = 3
  INTEGER(C_INT), PARAMETER :: TOT_ERR_RUN_FAILED      = 3
  INTEGER(C_INT), PARAMETER :: TOT_ERR_NOT_IMPLEMENTED = 4

  ! Lifecycle flag (single-instance orchestrator; matches tr_api.f90).
  LOGICAL, SAVE :: g_initialized = .FALSE.

  ! Per-sub-module presence flags. Mirror what tot_state_c exposes so
  ! get_state can publish the live picture without an extra scan.
  LOGICAL, SAVE :: g_tr_present = .FALSE.
  LOGICAL, SAVE :: g_ti_present = .FALSE.
  LOGICAL, SAVE :: g_fp_present = .FALSE.
  LOGICAL, SAVE :: g_wr_present = .FALSE.

CONTAINS

  !-------------------------------------------------------------------
  ! tot_init : bring up every libraryized sub-module.
  !
  ! Order mirrors totmain.f90 minus the wm/dp slots (those have no
  ! shared-library API yet). Each *_api_init is itself idempotent and
  ! calls pl_init / eq_init / module-local init internally, so the
  ! foundational layer is brought up regardless of which sub-module is
  ! invoked first.
  !
  ! On any sub-module init failure the orchestrator finalizes whatever
  ! has succeeded so far so the heap does not leak across re-init.
  !-------------------------------------------------------------------
  FUNCTION tot_api_init() RESULT(ierr) BIND(C, NAME="tot_init")
    INTEGER(C_INT) :: ierr
    INTEGER(C_INT) :: rc

    IF (g_initialized) THEN
       ! Idempotent: already initialized, just return OK.
       ierr = TOT_ERR_OK
       RETURN
    END IF

    ! tr_api_init also opens unit 7 (OPEN(7, STATUS='SCRATCH', ...)) which
    ! several lib/libkio.f90 inline-namelist paths require. Once tr brings
    ! it up the other modules' set_param / prep paths can reuse it without
    ! re-OPEN'ing (libkio's inline NAMELIST writer hard-codes UNIT=7).
    rc = tr_api_init()
    IF (rc /= 0) THEN
       ierr = TOT_ERR_INIT_FAILED
       RETURN
    END IF
    g_tr_present = .TRUE.

    rc = ti_api_init()
    IF (rc /= 0) THEN
       ! Roll back tr to keep the heap clean for the caller's next
       ! tot_init attempt.
       rc = tr_api_finalize()
       g_tr_present = .FALSE.
       ierr = TOT_ERR_INIT_FAILED
       RETURN
    END IF
    g_ti_present = .TRUE.

    rc = fp_api_init()
    IF (rc /= 0) THEN
       rc = ti_api_finalize();   g_ti_present = .FALSE.
       rc = tr_api_finalize();   g_tr_present = .FALSE.
       ierr = TOT_ERR_INIT_FAILED
       RETURN
    END IF
    g_fp_present = .TRUE.

    rc = wr_api_init()
    IF (rc /= 0) THEN
       rc = fp_api_finalize();   g_fp_present = .FALSE.
       rc = ti_api_finalize();   g_ti_present = .FALSE.
       rc = tr_api_finalize();   g_tr_present = .FALSE.
       ierr = TOT_ERR_INIT_FAILED
       RETURN
    END IF
    g_wr_present = .TRUE.

    g_initialized = .TRUE.
    ierr = TOT_ERR_OK
  END FUNCTION tot_api_init

  !-------------------------------------------------------------------
  ! tot_run : advance the integrated simulation by ntmax_in steps.
  !
  ! L-6 scope: only tr_api_run is invoked (the dominant solver and the
  ! one whose state is exposed in tot_state_c). fp_api_run and
  ! wr_api_run are intentionally NOT called here -- doing so would need
  ! a defined cross-module coupling (wr -> tr power deposition,
  ! fp -> tr current source, etc.) which is outside L-6. The four
  ! sub-modules are still init'd so a future L-7 patch can wire the
  ! coupling without changing the public ABI.
  !-------------------------------------------------------------------
  FUNCTION tot_api_run(ntmax_in) RESULT(ierr) BIND(C, NAME="tot_run")
    INTEGER(C_INT), VALUE, INTENT(IN) :: ntmax_in
    INTEGER(C_INT) :: ierr
    INTEGER(C_INT) :: rc

    IF (.NOT. g_initialized) THEN
       ierr = TOT_ERR_NOT_INIT
       RETURN
    END IF
    IF (ntmax_in < 0) THEN
       ierr = TOT_ERR_INVALID
       RETURN
    END IF

    rc = tr_api_run(ntmax_in)
    IF (rc /= 0) THEN
       ierr = TOT_ERR_RUN_FAILED
       RETURN
    END IF

    ierr = TOT_ERR_OK
  END FUNCTION tot_api_run

  !-------------------------------------------------------------------
  ! tot_get_state : populate the C-visible state struct.
  !
  ! L-6 surfaces the TR-authoritative scalars and profiles only (this
  ! is what the existing tot_state_c layout carries). ti / fp / wr
  ! presence flags are reported but their per-module state is not
  ! aggregated yet; doing so requires extending tot_state_c with
  ! nested per-module slots and is a follow-up.
  !-------------------------------------------------------------------
  FUNCTION tot_api_get_state(state) RESULT(ierr) BIND(C, NAME="tot_get_state")
    TYPE(tot_state_c), INTENT(OUT) :: state
    INTEGER(C_INT) :: ierr
    INTEGER(C_INT) :: rc
    TYPE(tr_state_c) :: trstate
    INTEGER :: nr, ns

    ! Always zero the struct so callers never see uninitialized memory.
    state%tr_present = 0
    state%ti_present = 0
    state%fp_present = 0
    state%wr_present = 0
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
    state%AJRFT  = 0.0_C_DOUBLE   ! L-7b-i
    state%RN     = 0.0_C_DOUBLE
    state%RT     = 0.0_C_DOUBLE
    state%AJ     = 0.0_C_DOUBLE
    state%QP     = 0.0_C_DOUBLE

    IF (.NOT. g_initialized) THEN
       ierr = TOT_ERR_NOT_INIT
       RETURN
    END IF

    ! Presence flags: at L-6 only TR contributes data into tot_state_c
    ! (the integrated profile/scalar slots are aggregated from
    ! tr_api_get_state). ti / fp / wr are init'd by tot_init for a
    ! future L-7 coupling pipeline but their state is NOT yet folded
    ! into the orchestrator struct, so we report present=0 to keep the
    ! L-6 wire format consistent with what the standalone tot binary's
    ! totregress dump emits when only the tr loop has been exercised.
    !
    ! L-7 follow-up: when ti/fp/wr state aggregation lands, flip the
    ! corresponding presence flag based on whether the sub-module has
    ! actually been advanced (g_*_run_called instead of g_*_present).
    IF (g_tr_present) state%tr_present = 1

    ! Aggregate TR state. The transposes (state%RN(ns,nr) <- trstate%RN(ns,nr))
    ! happen inside tr_api_get_state already; we only have to copy
    ! the bounded sub-block into the orchestrator slots.
    IF (g_tr_present) THEN
       rc = tr_api_get_state(trstate)
       IF (rc /= 0) THEN
          ierr = TOT_ERR_RUN_FAILED
          RETURN
       END IF
       IF (trstate%nrmax > TOT_MAX_NRMAX .OR. trstate%nsmax > TOT_MAX_NSMAX) THEN
          ! Refusing rather than silently truncating: the static layout
          ! cannot hold the requested grid; the caller needs to rebuild
          ! libtotapi with a larger TOT_MAX_* constant.
          ierr = TOT_ERR_RUN_FAILED
          RETURN
       END IF
       state%nt     = trstate%nt
       state%nrmax  = trstate%nrmax
       state%nsmax  = trstate%nsmax
       state%T      = trstate%T
       state%WPT    = trstate%WPT
       state%AJT    = trstate%AJT
       state%Q0     = trstate%Q0
       state%BETA0  = trstate%BETA0
       state%BETAP0 = trstate%BETAP0
       state%BETAA  = trstate%BETAA
       state%BETAN  = trstate%BETAN
       state%TAUE1  = trstate%TAUE1
       state%TAUE2  = trstate%TAUE2
       state%ZEFF0  = trstate%ZEFF0
       state%ALI    = trstate%ALI
       state%RQ1    = trstate%RQ1
       state%AJRFT  = trstate%AJRFT   ! L-7b-i: includes EXTERNAL_DRIVEN_I contribution
       DO nr = 1, trstate%nrmax
          DO ns = 1, trstate%nsmax
             state%RN(ns, nr) = trstate%RN(ns, nr)
             state%RT(ns, nr) = trstate%RT(ns, nr)
          END DO
          state%AJ(nr) = trstate%AJ(nr)
          state%QP(nr) = trstate%QP(nr)
       END DO
    END IF

    ierr = TOT_ERR_OK
  END FUNCTION tot_api_get_state

  !-------------------------------------------------------------------
  ! tot_set_param : dispatch a namespaced parameter to the matching
  ! per-module registry.
  !
  ! name   - NUL-terminated C string of the form "<ns>:<bare>" where
  !          <ns> is one of {eq, tr, fp, ti, wr, wrx}. Calls without a
  !          prefix are rejected (TOT_ERR_INVALID) because the tot
  !          parameter space is the UNION of the six backing modules
  !          and there is no single "owner" to default to.
  ! value  - scalar double.
  !
  ! Returns:
  !   0 = success
  !   1 = invalid (bad prefix, unknown bare name, downstream rejected)
  !-------------------------------------------------------------------
  FUNCTION tot_api_set_param(name, value) RESULT(ierr) BIND(C, NAME="tot_set_param")
    CHARACTER(KIND=C_CHAR), DIMENSION(*), INTENT(IN) :: name
    REAL(C_DOUBLE), VALUE,                INTENT(IN) :: value
    INTEGER(C_INT) :: ierr
    CHARACTER(LEN=128) :: fname
    INTEGER :: rc

    CALL c_string_to_fortran(name, fname)
    CALL tot_param_set(TRIM(fname), value, rc)
    IF (rc == 0) THEN
       ierr = TOT_ERR_OK
    ELSE
       ierr = TOT_ERR_INVALID
    END IF
  END FUNCTION tot_api_set_param

  !-------------------------------------------------------------------
  ! tot_set_param_str : string-valued companion to tot_set_param.
  !
  ! At L-3 only the `tr:` and `eq:` namespaces have backing string
  ! setters. Other namespaces return TOT_ERR_INVALID until their
  ! registries grow a matching `_str` entry point.
  !-------------------------------------------------------------------
  FUNCTION tot_api_set_param_str(name, value) RESULT(ierr) &
       BIND(C, NAME="tot_set_param_str")
    CHARACTER(KIND=C_CHAR), DIMENSION(*), INTENT(IN) :: name
    CHARACTER(KIND=C_CHAR), DIMENSION(*), INTENT(IN) :: value
    INTEGER(C_INT) :: ierr
    CHARACTER(LEN=128) :: fname
    CHARACTER(LEN=256) :: fvalue
    INTEGER :: rc

    CALL c_string_to_fortran(name,  fname)
    CALL c_string_to_fortran(value, fvalue)
    CALL tot_param_set_str(TRIM(fname), TRIM(fvalue), rc)
    IF (rc == 0) THEN
       ierr = TOT_ERR_OK
    ELSE
       ierr = TOT_ERR_INVALID
    END IF
  END FUNCTION tot_api_set_param_str

  !-------------------------------------------------------------------
  ! tot_finalize : tear down every sub-module in REVERSE init order.
  !
  ! Idempotent (mirrors tr_api_finalize). The reverse order matches
  ! totmain.f90's exit path and ensures that any sub-module which
  ! depends on another's CLOSE(7)/heap state during teardown sees the
  ! dependency still alive.
  !-------------------------------------------------------------------
  FUNCTION tot_api_finalize() RESULT(ierr) BIND(C, NAME="tot_finalize")
    INTEGER(C_INT) :: ierr
    INTEGER(C_INT) :: rc

    IF (.NOT. g_initialized) THEN
       ! Idempotent: nothing to free, but not an error either.
       ierr = TOT_ERR_OK
       RETURN
    END IF

    ! Tear down in reverse init order; collect the worst rc but always
    ! attempt every step so a failure midway does not leak the rest.
    ! Per-module *_api_finalize is itself idempotent so calling it on
    ! a presence flag that was never set is safe (returns OK).
    ierr = TOT_ERR_OK

    IF (g_wr_present) THEN
       rc = wr_api_finalize()
       IF (rc /= 0 .AND. ierr == TOT_ERR_OK) ierr = TOT_ERR_INIT_FAILED
       g_wr_present = .FALSE.
    END IF
    IF (g_fp_present) THEN
       rc = fp_api_finalize()
       IF (rc /= 0 .AND. ierr == TOT_ERR_OK) ierr = TOT_ERR_INIT_FAILED
       g_fp_present = .FALSE.
    END IF
    IF (g_ti_present) THEN
       rc = ti_api_finalize()
       IF (rc /= 0 .AND. ierr == TOT_ERR_OK) ierr = TOT_ERR_INIT_FAILED
       g_ti_present = .FALSE.
    END IF
    IF (g_tr_present) THEN
       rc = tr_api_finalize()
       IF (rc /= 0 .AND. ierr == TOT_ERR_OK) ierr = TOT_ERR_INIT_FAILED
       g_tr_present = .FALSE.
    END IF

    g_initialized = .FALSE.
  END FUNCTION tot_api_finalize

  !-------------------------------------------------------------------
  ! Copy a NUL-terminated C char array into a fixed-length Fortran
  ! buffer, space-padded. Safe against names/values longer than the
  ! destination: we stop at the first NUL or at LEN(dst), whichever
  ! comes first.
  !-------------------------------------------------------------------
  SUBROUTINE c_string_to_fortran(c_str, f_str)
    CHARACTER(KIND=C_CHAR), DIMENSION(*), INTENT(IN)  :: c_str
    CHARACTER(LEN=*),                     INTENT(OUT) :: f_str
    INTEGER :: i
    f_str = ' '
    DO i = 1, LEN(f_str)
       IF (c_str(i) == C_NULL_CHAR) EXIT
       f_str(i:i) = c_str(i)
    END DO
  END SUBROUTINE c_string_to_fortran

END MODULE tot_api
