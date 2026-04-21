! wr_param_registry.f90
!
! Phase L-3: setter table for namelist (wrparm.f90) parameters.
!
! Implements a hand-written SELECT CASE dispatch that maps a parameter
! name (optionally with a 1-origin subscript in square brackets, e.g.
! "PN[1]" or "RFIN[3]") to an assignment into the matching
! WRCOMM / PLCOMM / DPCOMM variable.
!
! The initial set follows the merged plan
! (docs/superpowers/plans/2026-04-18-wr-library-L3-param-registry.md):
!   A. geometry / device scalars (RR, RA, RB, RKAP, RDLT, BB, Q0, QA, RIP)
!   B. plasma scalars/arrays     (NSMAX, PA[i], PZ[i], PN[i], PNS[i],
!                                 PTPR[i], PTPP[i], PTS[i], PU[i], PUS[i],
!                                 PZCL[i])
!   C. profile control           (PROFN1, PROFN2, PROFT1, PROFT2, PROFU1,
!                                 PROFU2, RHOMIN, QMIN, RHOEDG,
!                                 PPN0, PTN0, RF_PL)
!   D. model switches            (MODELG, MODELQ, MODEL_PROF, MODEL_NPROF,
!                                 MODEFW, MODEFR, IDEBUG, MODELP[i],
!                                 MODELV[i], NCMIN[i], NCMAX[i])
!   E. WR scalars                (NRAYMAX, NSTPMAX, NRSMAX, NRLMAX,
!                                 LMAXNW, mode_beam, MDLWRI, MDLWRG,
!                                 MDLWRP, MDLWRQ, MDLWRW, MODEW,
!                                 nres_max, nres_type, mode_wline,
!                                 SMAX, DELS, UUMIN, EPSRAY, DELRAY,
!                                 DELDER, DELKR, EPSNW, RF, RPI, ZPI,
!                                 PHII, RNZI, RNPHII, RKR0, UUI, RCURVA,
!                                 RCURVB, RBRADA, RBRADB, pne_threshold,
!                                 bdr_threshold, Rmax_wr, Rmin_wr,
!                                 Zmax_wr, Zmin_wr)
!   F. WR per-ray arrays         (RFIN[i], RPIN[i], ZPIN[i], PHIIN[i],
!                                 RKRIN[i], RNZIN[i], RNPHIIN[i],
!                                 ANGZIN[i], ANGPHIN[i], UUIN[i],
!                                 RCURVAIN[i], RCURVBIN[i], RBRADAIN[i],
!                                 RBRADBIN[i], MODEWIN[i])
!
! Approximately 80 unique names covering scalar and 1-D array entries.
! Additional namelist vars may be added in a later PR by extending the
! SELECT CASE list; the parser handles any "NAME" or "NAME[idx]" input
! unchanged.
!
! Mirrors tr/tr_param_registry.f90 (Phase L-3, PR #33).

MODULE wr_param_registry
  USE wrcomm_parm
  USE plcomm
  USE dpcomm
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: wr_param_set
  PUBLIC :: parse_array_subscript_pub   ! exported for unit-test only

CONTAINS

  FUNCTION wr_param_set(name, value) RESULT(ierr)
    CHARACTER(LEN=*), INTENT(IN) :: name
    REAL(rkind),      INTENT(IN) :: value
    INTEGER :: ierr
    INTEGER :: idx
    CHARACTER(LEN=32) :: b

    ierr = 0
    CALL parse_array_subscript(name, b, idx)

    SELECT CASE (TRIM(b))
    ! --- A. geometry / device scalars (plcomm) ---------------------
    CASE ("RR");    RR    = value
    CASE ("RA");    RA    = value
    CASE ("RB");    RB    = value
    CASE ("RKAP");  RKAP  = value
    CASE ("RDLT");  RDLT  = value
    CASE ("BB");    BB    = value
    CASE ("Q0");    Q0    = value
    CASE ("QA");    QA    = value
    CASE ("RIP");   RIP   = value

    ! --- B. plasma scalars / arrays (plcomm) -----------------------
    ! Early-reject out-of-range values so property-based / fuzz callers
    ! get a clean ierr=1 INVALID here instead of a later SEGV deep in
    ! wr_allocate. 100 = plcomm::NSM hard upper bound.
    CASE ("NSMAX")
       IF (INT(value) < 1 .OR. INT(value) > 100) THEN; ierr = 1; RETURN; END IF
       NSMAX = INT(value)
    CASE ("PA");    IF (idx < 1 .OR. idx > SIZE(PA))   THEN; ierr = 1; ELSE; PA(idx)   = value; END IF
    CASE ("PZ");    IF (idx < 1 .OR. idx > SIZE(PZ))   THEN; ierr = 1; ELSE; PZ(idx)   = value; END IF
    CASE ("PN");    IF (idx < 1 .OR. idx > SIZE(PN))   THEN; ierr = 1; ELSE; PN(idx)   = value; END IF
    CASE ("PNS");   IF (idx < 1 .OR. idx > SIZE(PNS))  THEN; ierr = 1; ELSE; PNS(idx)  = value; END IF
    CASE ("PTPR");  IF (idx < 1 .OR. idx > SIZE(PTPR)) THEN; ierr = 1; ELSE; PTPR(idx) = value; END IF
    CASE ("PTPP");  IF (idx < 1 .OR. idx > SIZE(PTPP)) THEN; ierr = 1; ELSE; PTPP(idx) = value; END IF
    CASE ("PTS");   IF (idx < 1 .OR. idx > SIZE(PTS))  THEN; ierr = 1; ELSE; PTS(idx)  = value; END IF
    CASE ("PU");    IF (idx < 1 .OR. idx > SIZE(PU))   THEN; ierr = 1; ELSE; PU(idx)   = value; END IF
    CASE ("PUS");   IF (idx < 1 .OR. idx > SIZE(PUS))  THEN; ierr = 1; ELSE; PUS(idx)  = value; END IF
    CASE ("PZCL");  IF (idx < 1 .OR. idx > SIZE(PZCL)) THEN; ierr = 1; ELSE; PZCL(idx) = value; END IF

    ! --- C. profile control (plcomm) -------------------------------
    ! NOTE: PROFN1..PROFU2 and RHOITB/PNITB/PTITB/PUITB are NSM-element
    ! arrays in plcomm, so support both "PROFN1" (idx=0 -> element 1 alias)
    ! and "PROFN1[i]". We only register the array form here; the scalar
    ! form is handled below by treating idx==0 as a request for element 1
    ! (matches the namelist semantics where unsubscripted writes hit (1)).
    CASE ("PROFN1"); CALL set_real_array_or_first(PROFN1, idx, value, ierr)
    CASE ("PROFN2"); CALL set_real_array_or_first(PROFN2, idx, value, ierr)
    CASE ("PROFT1"); CALL set_real_array_or_first(PROFT1, idx, value, ierr)
    CASE ("PROFT2"); CALL set_real_array_or_first(PROFT2, idx, value, ierr)
    CASE ("PROFU1"); CALL set_real_array_or_first(PROFU1, idx, value, ierr)
    CASE ("PROFU2"); CALL set_real_array_or_first(PROFU2, idx, value, ierr)
    CASE ("RHOMIN"); RHOMIN = value
    CASE ("QMIN");   QMIN   = value
    CASE ("RHOITB"); CALL set_real_array_or_first(RHOITB, idx, value, ierr)
    CASE ("PNITB");  CALL set_real_array_or_first(PNITB,  idx, value, ierr)
    CASE ("PTITB");  CALL set_real_array_or_first(PTITB,  idx, value, ierr)
    CASE ("PUITB");  CALL set_real_array_or_first(PUITB,  idx, value, ierr)
    CASE ("RHOEDG"); RHOEDG = value
    CASE ("PPN0");   PPN0   = value
    CASE ("PTN0");   PTN0   = value
    CASE ("RF_PL");  RF_PL  = value

    ! --- D. model switches (plcomm / dpcomm) -----------------------
    CASE ("MODELG");      MODELG      = INT(value)
    CASE ("MODELQ");      MODELQ      = INT(value)
    CASE ("MODEL_PROF");  model_prof  = INT(value)
    CASE ("MODEL_NPROF"); model_nprof = INT(value)
    CASE ("MODEFW");      MODEFW      = INT(value)
    CASE ("MODEFR");      MODEFR      = INT(value)
    CASE ("IDEBUG");      IDEBUG      = INT(value)
    CASE ("MODELP");      IF (idx < 1 .OR. idx > SIZE(MODELP)) THEN; ierr = 1; ELSE; MODELP(idx) = INT(value); END IF
    CASE ("MODELV");      IF (idx < 1 .OR. idx > SIZE(MODELV)) THEN; ierr = 1; ELSE; MODELV(idx) = INT(value); END IF
    CASE ("NCMIN");       IF (idx < 1 .OR. idx > SIZE(NCMIN))  THEN; ierr = 1; ELSE; NCMIN(idx)  = INT(value); END IF
    CASE ("NCMAX");       IF (idx < 1 .OR. idx > SIZE(NCMAX))  THEN; ierr = 1; ELSE; NCMAX(idx)  = INT(value); END IF

    ! --- E. WR scalars (wrcomm_parm) -------------------------------
    CASE ("NRAYMAX");    NRAYMAX    = INT(value)
    CASE ("NSTPMAX");    NSTPMAX    = INT(value)
    CASE ("NRSMAX");     NRSMAX     = INT(value)
    CASE ("NRLMAX");     NRLMAX     = INT(value)
    CASE ("LMAXNW");     LMAXNW     = INT(value)
    CASE ("mode_beam");  mode_beam  = INT(value)
    CASE ("MDLWRI");     MDLWRI     = INT(value)
    CASE ("MDLWRG");     MDLWRG     = INT(value)
    CASE ("MDLWRP");     MDLWRP     = INT(value)
    CASE ("MDLWRQ");     MDLWRQ     = INT(value)
    CASE ("MDLWRW");     MDLWRW     = INT(value)
    CASE ("MODEW");      MODEW      = INT(value)
    CASE ("nres_max");   nres_max   = INT(value)
    CASE ("nres_type");  nres_type  = INT(value)
    CASE ("mode_wline"); mode_wline = INT(value)
    CASE ("SMAX");       SMAX       = value
    CASE ("DELS");       DELS       = value
    CASE ("UUMIN");      UUMIN      = value
    CASE ("EPSRAY");     EPSRAY     = value
    CASE ("DELRAY");     DELRAY     = value
    CASE ("DELDER");     DELDER     = value
    CASE ("DELKR");      DELKR      = value
    CASE ("EPSNW");      EPSNW      = value
    CASE ("RF");         RF         = value
    CASE ("RPI");        RPI        = value
    CASE ("ZPI");        ZPI        = value
    CASE ("PHII");       PHII       = value
    CASE ("RNZI");       RNZI       = value
    CASE ("RNPHII");     RNPHII     = value
    CASE ("RKR0");       RKR0       = value
    CASE ("UUI");        UUI        = value
    CASE ("RCURVA");     RCURVA     = value
    CASE ("RCURVB");     RCURVB     = value
    CASE ("RBRADA");     RBRADA     = value
    CASE ("RBRADB");     RBRADB     = value
    CASE ("pne_threshold"); pne_threshold = value
    CASE ("bdr_threshold"); bdr_threshold = value
    CASE ("Rmax_wr");    Rmax_wr    = value
    CASE ("Rmin_wr");    Rmin_wr    = value
    CASE ("Zmax_wr");    Zmax_wr    = value
    CASE ("Zmin_wr");    Zmin_wr    = value

    ! --- F. WR per-ray arrays (wrcomm_parm, sized NRAYM) -----------
    CASE ("RFIN");     IF (idx < 1 .OR. idx > SIZE(RFIN))     THEN; ierr = 1; ELSE; RFIN(idx)     = value; END IF
    CASE ("RPIN");     IF (idx < 1 .OR. idx > SIZE(RPIN))     THEN; ierr = 1; ELSE; RPIN(idx)     = value; END IF
    CASE ("ZPIN");     IF (idx < 1 .OR. idx > SIZE(ZPIN))     THEN; ierr = 1; ELSE; ZPIN(idx)     = value; END IF
    CASE ("PHIIN");    IF (idx < 1 .OR. idx > SIZE(PHIIN))    THEN; ierr = 1; ELSE; PHIIN(idx)    = value; END IF
    CASE ("RKRIN");    IF (idx < 1 .OR. idx > SIZE(RKRIN))    THEN; ierr = 1; ELSE; RKRIN(idx)    = value; END IF
    CASE ("RNZIN");    IF (idx < 1 .OR. idx > SIZE(RNZIN))    THEN; ierr = 1; ELSE; RNZIN(idx)    = value; END IF
    CASE ("RNPHIIN");  IF (idx < 1 .OR. idx > SIZE(RNPHIIN))  THEN; ierr = 1; ELSE; RNPHIIN(idx)  = value; END IF
    CASE ("ANGZIN");   IF (idx < 1 .OR. idx > SIZE(ANGZIN))   THEN; ierr = 1; ELSE; ANGZIN(idx)   = value; END IF
    CASE ("ANGPHIN");  IF (idx < 1 .OR. idx > SIZE(ANGPHIN))  THEN; ierr = 1; ELSE; ANGPHIN(idx)  = value; END IF
    CASE ("UUIN");     IF (idx < 1 .OR. idx > SIZE(UUIN))     THEN; ierr = 1; ELSE; UUIN(idx)     = value; END IF
    CASE ("RCURVAIN"); IF (idx < 1 .OR. idx > SIZE(RCURVAIN)) THEN; ierr = 1; ELSE; RCURVAIN(idx) = value; END IF
    CASE ("RCURVBIN"); IF (idx < 1 .OR. idx > SIZE(RCURVBIN)) THEN; ierr = 1; ELSE; RCURVBIN(idx) = value; END IF
    CASE ("RBRADAIN"); IF (idx < 1 .OR. idx > SIZE(RBRADAIN)) THEN; ierr = 1; ELSE; RBRADAIN(idx) = value; END IF
    CASE ("RBRADBIN"); IF (idx < 1 .OR. idx > SIZE(RBRADBIN)) THEN; ierr = 1; ELSE; RBRADBIN(idx) = value; END IF
    CASE ("MODEWIN");  IF (idx < 1 .OR. idx > SIZE(MODEWIN))  THEN; ierr = 1; ELSE; MODEWIN(idx)  = INT(value); END IF

    CASE DEFAULT
       ierr = 1   ! unknown name
    END SELECT
  END FUNCTION wr_param_set

  !-------------------------------------------------------------------
  ! Set arr(idx)=value when idx>=1; when idx==0 (no subscript), assign
  ! to element 1 to match the Fortran namelist convention where
  ! "PROFN1=2.0" without a subscript hits the (1) slot.
  !-------------------------------------------------------------------
  SUBROUTINE set_real_array_or_first(arr, idx, value, ierr)
    REAL(rkind), DIMENSION(:), INTENT(INOUT) :: arr
    INTEGER,                   INTENT(IN)    :: idx
    REAL(rkind),               INTENT(IN)    :: value
    INTEGER,                   INTENT(INOUT) :: ierr
    INTEGER :: i
    i = idx
    IF (i == 0) i = 1
    IF (i < 1 .OR. i > SIZE(arr)) THEN
       ierr = 1
       RETURN
    END IF
    arr(i) = value
  END SUBROUTINE set_real_array_or_first

  !-------------------------------------------------------------------
  ! Split "NAME" or "NAME[N]" into (base, idx).
  !
  !   "RR"        -> base="RR",   idx=0    (scalar form)
  !   "PN[1]"     -> base="PN",   idx=1    (1-origin subscript)
  !   "RFIN[12]"  -> base="RFIN", idx=12
  !   malformed   -> base=<full>, idx=-1   (caller returns ierr=1)
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

END MODULE wr_param_registry
