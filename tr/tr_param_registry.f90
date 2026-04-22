! tr_param_registry.f90
!
! Phase L-3: setter table for namelist (trparm.f90) parameters.
! Phase L-6 follow-up: extended to cover UNREGISTERED_KEYS of the
! tr_iter01 / tr_tst2 fixtures so Layer 1 equivalence tests can drive
! ``libtrapi.so`` to reproduce the Phase 0 Fortran baselines at 1e-10.
!
! Implements a hand-written SELECT CASE dispatch that maps a parameter
! name (optionally with a 1-origin subscript in square brackets, e.g.
! "PN[1]") to an assignment into the matching TRCOMM variable.
!
! The initial set follows design doc §5.3:
!   - geometry/device scalars (RR, RA, RKAP, RDLT, BB, PHIA, RIPS, RIPE)
!   - plasma scalars/arrays  (NSMAX, PA[i], PZ[i], PN[i], PNS[i], PT[i], PTS[i])
!   - time evolution         (DT, NTMAX, NTSTEP, EPSLTR, LMAXTR)
!   - transport switches     (MDLKAI, MDLETA, MDLAD, MDLAVK, CDW[i], CHP,
!                             CK0, CK1)
!   - module switches        (MDLNB, MDLEC, MDLLH, MDLIC, MDLPEL,
!                             MDLJBS, MDLST, MDLNF, MDLUF)
!
! L-6 additions (tr_iter01 / tr_tst2 UNREGISTERED_KEYS):
!   - geometry selector      (MODELG)
!   - profile shape          (PROFN1, PROFN2)
!   - impurity / composition (MDLIMP, PNC)
!   - graphics step counters (NGTSTP, NGRSTP)
!   - heating / current drive
!       NBI                  (PNBR0, PNBRW, PNBENG, PNBRTG)
!       ICRF                 (PICCD, PICR0, PICRW, PICNPR)
!       ECRF                 (PECCD, PECR0, PECRW, PECNPR)
!       LH                   (PLHCD, PLHR0, PLHRW, PLHNPR, PLHTOT)
!
! Strings (KNAMEQ) are handled through a separate entry point:
!   - tr_param_set_str("KNAMEQ", "eqdata.ITER01")
!
! Additional namelist vars may be added in a later PR by extending the
! SELECT CASE list; the parser handles any "NAME" or "NAME[idx]" input
! unchanged.
!
! See docs/superpowers/specs/2026-04-17-tr-library-design.md §5 and
! docs/superpowers/plans/2026-04-18-tr-library-L3-param-registry.md.

MODULE tr_param_registry
  USE trcomm, ONLY: rkind, &
       RR, RA, RKAP, RDLT, BB, PHIA, &
       NSMAX, PA, PZ, PN, PNS, PT, PTS, &
       RIPS, RIPE, &
       DT, NTMAX, NTSTEP, EPSLTR, LMAXTR, &
       MDLKAI, MDLETA, MDLAD, MDLAVK, CDW, CHP, CK0, CK1, &
       MDLNB, MDLEC, MDLLH, MDLIC, MDLPEL, MDLJBS, MDLST, MDLNF, MDLUF, &
       MODELG, MDLIMP, NGTSTP, NGRSTP, &
       PROFN1, PROFN2, PNC, &
       PNBR0, PNBRW, PNBENG, PNBRTG, &
       PICCD, PICR0, PICRW, PICNPR, &
       PECCD, PECR0, PECRW, PECNPR, &
       PLHCD, PLHR0, PLHRW, PLHNPR, PLHTOT, &
       KNAMEQ
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: tr_param_set
  PUBLIC :: tr_param_set_str
  PUBLIC :: parse_array_subscript_pub   ! exported for unit-test only

CONTAINS

  FUNCTION tr_param_set(name, value) RESULT(ierr)
    CHARACTER(LEN=*), INTENT(IN) :: name
    REAL(rkind),      INTENT(IN) :: value
    INTEGER :: ierr
    INTEGER :: idx
    CHARACTER(LEN=32) :: b

    ierr = 0
    CALL parse_array_subscript(name, b, idx)

    SELECT CASE (TRIM(b))
    ! --- geometry / device scalars ---------------------------------
    CASE ("RR");    RR    = value
    CASE ("RA");    RA    = value
    CASE ("RKAP");  RKAP  = value
    CASE ("RDLT");  RDLT  = value
    CASE ("BB");    BB    = value
    CASE ("PHIA");  PHIA  = value
    CASE ("MODELG");  MODELG = INT(value)
    ! --- plasma scalars --------------------------------------------
    ! NSMAX range: [2, TR_MAX_NSMAX=8]. Lower bound is 2 (electrons +
    ! at least one ion species) — NSMAX=1 would make `PZ(2:NSMAX)`
    ! a zero-size slice in tr_prof_impurity (trprof.f90:303), causing
    ! `ANI=SUM(PZ(2:1)*RN(NR,2:1))=0`, then `DILUTE=1-ANZ/0=-Inf`,
    ! triggering an unconditional STOP at trprof.f90:310 that aborts
    ! the host process. Early-reject at the registry so property-based
    ! callers (fuzz sweeps, misconfigured clients) get a clean ierr=1
    ! INVALID instead of a deep-Fortran abort. The upper bound matches
    ! the C ABI struct capacity declared in tr/tr_state.f90::TR_MAX_NSMAX.
    CASE ("NSMAX")
       IF (INT(value) < 2 .OR. INT(value) > 8) THEN; ierr = 1; RETURN; END IF
       NSMAX = INT(value)
    ! --- plasma arrays (1..NSMM, 1-origin; NSMM=100 per tr/trcom0.f90)
    !     SIZE(arr) keeps the bound check correct if the declared
    !     dimension constant is renamed.
    CASE ("PA");    IF (idx < 1 .OR. idx > SIZE(PA))  THEN; ierr = 1; ELSE; PA(idx)  = value; END IF
    CASE ("PZ");    IF (idx < 1 .OR. idx > SIZE(PZ))  THEN; ierr = 1; ELSE; PZ(idx)  = value; END IF
    CASE ("PN");    IF (idx < 1 .OR. idx > SIZE(PN))  THEN; ierr = 1; ELSE; PN(idx)  = value; END IF
    CASE ("PNS");   IF (idx < 1 .OR. idx > SIZE(PNS)) THEN; ierr = 1; ELSE; PNS(idx) = value; END IF
    CASE ("PT");    IF (idx < 1 .OR. idx > SIZE(PT))  THEN; ierr = 1; ELSE; PT(idx)  = value; END IF
    CASE ("PTS");   IF (idx < 1 .OR. idx > SIZE(PTS)) THEN; ierr = 1; ELSE; PTS(idx) = value; END IF
    ! --- profile shape ---------------------------------------------
    CASE ("PROFN1"); PROFN1 = value
    CASE ("PROFN2"); PROFN2 = value
    ! --- impurity / composition ------------------------------------
    CASE ("PNC");   PNC   = value
    CASE ("MDLIMP"); MDLIMP = INT(value)
    ! --- current ---------------------------------------------------
    CASE ("RIPS");  RIPS  = value
    CASE ("RIPE");  RIPE  = value
    ! --- time evolution --------------------------------------------
    CASE ("DT");     DT     = value
    CASE ("NTMAX");  NTMAX  = INT(value)
    CASE ("NTSTEP"); NTSTEP = INT(value)
    CASE ("EPSLTR"); EPSLTR = value
    CASE ("LMAXTR"); LMAXTR = INT(value)
    CASE ("NGTSTP"); NGTSTP = INT(value)
    CASE ("NGRSTP"); NGRSTP = INT(value)
    ! --- transport model switches & coefficients -------------------
    CASE ("MDLKAI"); MDLKAI = INT(value)
    CASE ("MDLETA"); MDLETA = INT(value)
    CASE ("MDLAD");  MDLAD  = INT(value)
    CASE ("MDLAVK"); MDLAVK = INT(value)
    CASE ("CDW");    IF (idx < 1 .OR. idx > SIZE(CDW)) THEN; ierr = 1; ELSE; CDW(idx) = value; END IF
    CASE ("CHP");    CHP   = value
    CASE ("CK0");    CK0   = value
    CASE ("CK1");    CK1   = value
    ! --- module switches -------------------------------------------
    CASE ("MDLNB");  MDLNB  = INT(value)
    CASE ("MDLEC");  MDLEC  = INT(value)
    CASE ("MDLLH");  MDLLH  = INT(value)
    CASE ("MDLIC");  MDLIC  = INT(value)
    CASE ("MDLPEL"); MDLPEL = INT(value)
    CASE ("MDLJBS"); MDLJBS = INT(value)
    CASE ("MDLST");  MDLST  = INT(value)
    CASE ("MDLNF");  MDLNF  = INT(value)
    CASE ("MDLUF");  MDLUF  = INT(value)
    ! --- heating / current-drive scalars ---------------------------
    !     NBI
    CASE ("PNBR0");  PNBR0  = value
    CASE ("PNBRW");  PNBRW  = value
    CASE ("PNBENG"); PNBENG = value
    CASE ("PNBRTG"); PNBRTG = value
    !     ICRF
    CASE ("PICCD");  PICCD  = value
    CASE ("PICR0");  PICR0  = value
    CASE ("PICRW");  PICRW  = value
    CASE ("PICNPR"); PICNPR = value
    !     ECRF
    CASE ("PECCD");  PECCD  = value
    CASE ("PECR0");  PECR0  = value
    CASE ("PECRW");  PECRW  = value
    CASE ("PECNPR"); PECNPR = value
    !     LH
    CASE ("PLHCD");  PLHCD  = value
    CASE ("PLHR0");  PLHR0  = value
    CASE ("PLHRW");  PLHRW  = value
    CASE ("PLHNPR"); PLHNPR = value
    CASE ("PLHTOT"); PLHTOT = value
    CASE DEFAULT
       ierr = 1   ! unknown name
    END SELECT
  END FUNCTION tr_param_set

  !-------------------------------------------------------------------
  ! tr_param_set_str : string-valued parameter setter.
  !
  ! Separate entry from tr_param_set because the Fortran namelist /TR/
  ! has a small number of CHARACTER(LEN=80) variables (KNAMEQ and
  ! friends) that cannot be carried through a REAL(rkind) pipe.
  !
  ! L-6 coverage: KNAMEQ (equilibrium-data file name, used by the
  ! MODELG=3 eq-load path on tr_iter01 / tr_tst2).
  !
  ! Additional string variables (KNAMEQ2, KNAMTR, KFNLOG, KFNTXT,
  ! KFNCVS, KUFDIR, KUFDEV, KUFDCG) can be added by extending the
  ! SELECT CASE below without touching the C ABI (only the name list).
  !-------------------------------------------------------------------
  FUNCTION tr_param_set_str(name, value) RESULT(ierr)
    CHARACTER(LEN=*), INTENT(IN) :: name
    CHARACTER(LEN=*), INTENT(IN) :: value
    INTEGER :: ierr

    ierr = 0
    SELECT CASE (TRIM(ADJUSTL(name)))
    CASE ("KNAMEQ"); KNAMEQ = TRIM(value)
    CASE DEFAULT
       ierr = 1   ! unknown string-valued name
    END SELECT
  END FUNCTION tr_param_set_str

  !-------------------------------------------------------------------
  ! Split "NAME" or "NAME[N]" into (base, idx).
  !
  !   "RR"      -> base="RR",  idx=0       (scalar form)
  !   "PN[1]"   -> base="PN",  idx=1       (1-origin subscript)
  !   "CDW[12]" -> base="CDW", idx=12
  !   malformed -> base=<full>, idx=-1     (caller returns ierr=1)
  !-------------------------------------------------------------------
  SUBROUTINE parse_array_subscript(full_name, base, idx)
    CHARACTER(LEN=*), INTENT(IN)  :: full_name
    CHARACTER(LEN=*), INTENT(OUT) :: base
    INTEGER,          INTENT(OUT) :: idx
    INTEGER :: lb, rb, ios
    base = ' '
    idx  = 0
    lb = INDEX(full_name, '[')
    rb = INDEX(full_name, ']')
    IF (lb == 0 .AND. rb == 0) THEN
       base = TRIM(ADJUSTL(full_name))
       RETURN
    END IF
    IF (lb == 0 .OR. rb == 0 .OR. rb <= lb + 1) THEN
       base = TRIM(ADJUSTL(full_name))   ! malformed; caller returns ierr=1
       idx  = -1
       RETURN
    END IF
    base = full_name(1:lb-1)
    READ(full_name(lb+1:rb-1), *, IOSTAT=ios) idx
    IF (ios /= 0) idx = -1
  END SUBROUTINE parse_array_subscript

  ! Public alias for unit testing only.
  SUBROUTINE parse_array_subscript_pub(full_name, base, idx)
    CHARACTER(LEN=*), INTENT(IN)  :: full_name
    CHARACTER(LEN=*), INTENT(OUT) :: base
    INTEGER,          INTENT(OUT) :: idx
    CALL parse_array_subscript(full_name, base, idx)
  END SUBROUTINE parse_array_subscript_pub

END MODULE tr_param_registry
