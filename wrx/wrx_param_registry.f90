! wrx_param_registry.f90
!
! Phase L-3: setter table for namelist (wrparm.f90 /WR/) parameters.
!
! Implements a hand-written SELECT CASE dispatch that maps a parameter
! name (optionally with a 1-origin subscript in square brackets, e.g.
! "PN[1]") to an assignment into the matching wrcomm / plcomm /
! dpcomm variable.
!
! The initial set follows
! docs/superpowers/plans/2026-04-18-wrx-library-L3-param-registry.md:
!   - geometry/device scalars (RR, RA, RB, RKAP, RDLT, BB, Q0, QA, RIP)
!   - plasma scalars/arrays   (NSMAX, PROFJ, PA[i], PZ[i], PN[i],
!                              PNS[i], PTPR[i], PTPP[i], PTS[i],
!                              PROFN1[i], PROFN2[i], PROFT1[i],
!                              PROFT2[i])
!   - dp/pl integration       (MODELG, MODELQ, NSAMAX_WR,
!                              MODELP[i], MODELV[i], NCMIN[i],
!                              NCMAX[i])
!   - WRX control scalars     (NRAYMAX, NSTPMAX, NRSMAX, NRLMAX,
!                              LMAXNW, MDLWRI, MDLWRG, MDLWRP,
!                              MDLWRQ, MDLWRW)
!   - ray init arrays (NRAYM) (RFIN[i], RPIN[i], ZPIN[i], PHIIN[i],
!                              ANGTIN[i], ANGPIN[i], RNPHIN[i],
!                              RNZIN[i], MODEWIN[i], UUIN[i],
!                              RBRADAIN[i], RBRADBIN[i],
!                              RCURVAIN[i], RCURVBIN[i], RNKIN[i])
!   - ray control scalars     (SMAX, DELS, UUMIN, EPSRAY, DELRAY,
!                              DELDER, DELKR, EPSNW, EPSD0,
!                              pne_threshold, bdr_threshold)
!   - mode switches           (mode_beam, mode_wline, mode_fig,
!                              model_fdrv, model_fdrv_ds)
!
! ~70 unique names covering ~120 settable variables once array
! subscripts are counted. Additional namelist vars may be added later
! by extending the SELECT CASE list; the parser accepts any "NAME" or
! "NAME[idx]" input unchanged.
!
! See docs/superpowers/specs/2026-04-17-tr-library-design.md §5 and
! docs/superpowers/plans/2026-04-18-wrx-library-L3-param-registry.md.

MODULE wrx_param_registry
  USE wrcomm   ! wrcomm_parm + plcomm + dpcomm chain provides everything
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: wrx_param_set
  PUBLIC :: parse_array_subscript_pub   ! exported for unit-test only

CONTAINS

  FUNCTION wrx_param_set(name, value) RESULT(ierr)
    CHARACTER(LEN=*), INTENT(IN) :: name
    REAL(rkind),      INTENT(IN) :: value
    INTEGER :: ierr
    INTEGER :: idx
    CHARACTER(LEN=64) :: b

    ierr = 0
    CALL parse_array_subscript(name, b, idx)

    ! parse_array_subscript returns idx=1 by default for scalar names
    ! (no brackets) so 1-origin Fortran array CASEs see the dominant
    ! index without the caller having to pass "PN[1]" explicitly.
    ! Malformed brackets ("PN[]", "PN[0]", "PN[abc]") yield idx=0 so
    ! the per-CASE upper bound check below catches them first; we then
    ! also defend against idx<1 here (Bugbot fix: per-CASE upper-bound
    ! checks stay; defaults to 1 for 1-origin so callers using "RR"
    ! work).
    IF (idx < 1) THEN
       ierr = 1
       RETURN
    END IF

    SELECT CASE (TRIM(b))
    ! --- geometry / device scalars --------------------------------
    CASE ("RR");    RR    = value
    CASE ("RA");    RA    = value
    CASE ("RB");    RB    = value
    CASE ("RKAP");  RKAP  = value
    CASE ("RDLT");  RDLT  = value
    CASE ("BB");    BB    = value
    CASE ("Q0");    Q0    = value
    CASE ("QA");    QA    = value
    CASE ("RIP");   RIP   = value

    ! --- plasma scalars -------------------------------------------
    CASE ("NSMAX"); NSMAX = INT(value)
    CASE ("PROFJ"); PROFJ = value

    ! --- plasma arrays (1..NSM, 1-origin) --------------------------
    !     SIZE(arr) keeps the bound check correct if NSM is renamed.
    CASE ("PA")
       IF (idx > SIZE(PA))    THEN; ierr = 1; RETURN; END IF
       PA(idx)    = value
    CASE ("PZ")
       IF (idx > SIZE(PZ))    THEN; ierr = 1; RETURN; END IF
       PZ(idx)    = value
    CASE ("PN")
       IF (idx > SIZE(PN))    THEN; ierr = 1; RETURN; END IF
       PN(idx)    = value
    CASE ("PNS")
       IF (idx > SIZE(PNS))   THEN; ierr = 1; RETURN; END IF
       PNS(idx)   = value
    CASE ("PTPR")
       IF (idx > SIZE(PTPR))  THEN; ierr = 1; RETURN; END IF
       PTPR(idx)  = value
    CASE ("PTPP")
       IF (idx > SIZE(PTPP))  THEN; ierr = 1; RETURN; END IF
       PTPP(idx)  = value
    CASE ("PTS")
       IF (idx > SIZE(PTS))   THEN; ierr = 1; RETURN; END IF
       PTS(idx)   = value
    CASE ("PROFN1")
       IF (idx > SIZE(PROFN1)) THEN; ierr = 1; RETURN; END IF
       PROFN1(idx) = value
    CASE ("PROFN2")
       IF (idx > SIZE(PROFN2)) THEN; ierr = 1; RETURN; END IF
       PROFN2(idx) = value
    CASE ("PROFT1")
       IF (idx > SIZE(PROFT1)) THEN; ierr = 1; RETURN; END IF
       PROFT1(idx) = value
    CASE ("PROFT2")
       IF (idx > SIZE(PROFT2)) THEN; ierr = 1; RETURN; END IF
       PROFT2(idx) = value

    ! --- pl/dp integration ----------------------------------------
    CASE ("MODELG");    MODELG    = INT(value)
    CASE ("MODELQ");    MODELQ    = INT(value)
    CASE ("NSAMAX_WR"); NSAMAX_WR = INT(value)
    CASE ("MODELP")
       IF (idx > SIZE(MODELP)) THEN; ierr = 1; RETURN; END IF
       MODELP(idx) = INT(value)
    CASE ("MODELV")
       IF (idx > SIZE(MODELV)) THEN; ierr = 1; RETURN; END IF
       MODELV(idx) = INT(value)
    CASE ("NCMIN")
       IF (idx > SIZE(NCMIN))  THEN; ierr = 1; RETURN; END IF
       NCMIN(idx)  = INT(value)
    CASE ("NCMAX")
       IF (idx > SIZE(NCMAX))  THEN; ierr = 1; RETURN; END IF
       NCMAX(idx)  = INT(value)

    ! --- WRX control scalars ---------------------------------------
    CASE ("NRAYMAX"); NRAYMAX = INT(value)
    CASE ("NSTPMAX"); NSTPMAX = INT(value)
    CASE ("NRSMAX");  NRSMAX  = INT(value)
    CASE ("NRLMAX");  NRLMAX  = INT(value)
    CASE ("LMAXNW");  LMAXNW  = INT(value)
    CASE ("MDLWRI");  MDLWRI  = INT(value)
    CASE ("MDLWRG");  MDLWRG  = INT(value)
    CASE ("MDLWRP");  MDLWRP  = INT(value)
    CASE ("MDLWRQ");  MDLWRQ  = INT(value)
    CASE ("MDLWRW");  MDLWRW  = INT(value)

    ! --- ray init arrays (NRAYM = 100 max in wrcomm_parm) ---------
    CASE ("RFIN")
       IF (idx > SIZE(RFIN))     THEN; ierr = 1; RETURN; END IF
       RFIN(idx)     = value
    CASE ("RPIN")
       IF (idx > SIZE(RPIN))     THEN; ierr = 1; RETURN; END IF
       RPIN(idx)     = value
    CASE ("ZPIN")
       IF (idx > SIZE(ZPIN))     THEN; ierr = 1; RETURN; END IF
       ZPIN(idx)     = value
    CASE ("PHIIN")
       IF (idx > SIZE(PHIIN))    THEN; ierr = 1; RETURN; END IF
       PHIIN(idx)    = value
    CASE ("ANGTIN")
       IF (idx > SIZE(ANGTIN))   THEN; ierr = 1; RETURN; END IF
       ANGTIN(idx)   = value
    CASE ("ANGPIN")
       IF (idx > SIZE(ANGPIN))   THEN; ierr = 1; RETURN; END IF
       ANGPIN(idx)   = value
    CASE ("RNPHIN")
       IF (idx > SIZE(RNPHIN))   THEN; ierr = 1; RETURN; END IF
       RNPHIN(idx)   = value
    CASE ("RNZIN")
       IF (idx > SIZE(RNZIN))    THEN; ierr = 1; RETURN; END IF
       RNZIN(idx)    = value
    CASE ("MODEWIN")
       IF (idx > SIZE(MODEWIN))  THEN; ierr = 1; RETURN; END IF
       MODEWIN(idx)  = INT(value)
    CASE ("UUIN")
       IF (idx > SIZE(UUIN))     THEN; ierr = 1; RETURN; END IF
       UUIN(idx)     = value
    CASE ("RBRADAIN")
       IF (idx > SIZE(RBRADAIN)) THEN; ierr = 1; RETURN; END IF
       RBRADAIN(idx) = value
    CASE ("RBRADBIN")
       IF (idx > SIZE(RBRADBIN)) THEN; ierr = 1; RETURN; END IF
       RBRADBIN(idx) = value
    CASE ("RCURVAIN")
       IF (idx > SIZE(RCURVAIN)) THEN; ierr = 1; RETURN; END IF
       RCURVAIN(idx) = value
    CASE ("RCURVBIN")
       IF (idx > SIZE(RCURVBIN)) THEN; ierr = 1; RETURN; END IF
       RCURVBIN(idx) = value
    CASE ("RNKIN")
       IF (idx > SIZE(RNKIN))    THEN; ierr = 1; RETURN; END IF
       RNKIN(idx)    = value

    ! --- ray control scalars --------------------------------------
    CASE ("SMAX");          SMAX          = value
    CASE ("DELS");          DELS          = value
    CASE ("UUMIN");         UUMIN         = value
    CASE ("EPSRAY");        EPSRAY        = value
    CASE ("DELRAY");        DELRAY        = value
    CASE ("DELDER");        DELDER        = value
    CASE ("DELKR");         DELKR         = value
    CASE ("EPSNW");         EPSNW         = value
    CASE ("EPSD0");         EPSD0         = value
    CASE ("pne_threshold"); pne_threshold = value
    CASE ("bdr_threshold"); bdr_threshold = value

    ! --- mode switches --------------------------------------------
    CASE ("mode_beam");     mode_beam     = INT(value)
    CASE ("mode_wline");    mode_wline    = INT(value)
    CASE ("mode_fig");      mode_fig      = INT(value)
    CASE ("model_fdrv");    model_fdrv    = INT(value)
    CASE ("model_fdrv_ds"); model_fdrv_ds = INT(value)

    CASE DEFAULT
       ierr = 1   ! unknown name
    END SELECT
  END FUNCTION wrx_param_set

  !-------------------------------------------------------------------
  ! Split "NAME" or "NAME[N]" into (base, idx).
  !
  !   "RR"      -> base="RR",  idx=1   (scalar form, idx defaults to 1
  !                                    for 1-origin Fortran convention)
  !   "PN[1]"   -> base="PN",  idx=1
  !   "RFIN[5]" -> base="RFIN",idx=5
  !   "PN[0]"   -> base="PN",  idx=0   (caller rejects idx<1)
  !   "PN[]"    -> base="PN",  idx=0
  !   "PN[abc]" -> base="PN",  idx=0
  !
  ! Bugbot fix: idx defaults to 1 (not 0) so callers passing scalar
  ! names like "RR" don't trip the idx<1 reject path; the per-CASE
  ! SIZE() guards above handle the upper bound for arrays.
  !-------------------------------------------------------------------
  SUBROUTINE parse_array_subscript(full_name, base, idx)
    CHARACTER(LEN=*), INTENT(IN)  :: full_name
    CHARACTER(LEN=*), INTENT(OUT) :: base
    INTEGER,          INTENT(OUT) :: idx
    INTEGER :: lb, rb, ios

    base = full_name
    idx  = 1                       ! 1-origin default for scalar / array
    lb = INDEX(full_name, '[')
    IF (lb == 0) RETURN            ! no subscript -> scalar form, idx=1
    rb = INDEX(full_name, ']')
    IF (rb <= lb + 1) THEN
       ! "PN[" or "PN[]" -> malformed
       base = full_name(1:MAX(lb-1, 1))
       idx  = 0
       RETURN
    END IF
    base = full_name(1:lb-1)
    READ(full_name(lb+1:rb-1), *, IOSTAT=ios) idx
    IF (ios /= 0) idx = 0          ! "PN[abc]" -> sentinel for caller
  END SUBROUTINE parse_array_subscript

  ! Public alias for unit testing only.
  SUBROUTINE parse_array_subscript_pub(full_name, base, idx)
    CHARACTER(LEN=*), INTENT(IN)  :: full_name
    CHARACTER(LEN=*), INTENT(OUT) :: base
    INTEGER,          INTENT(OUT) :: idx
    CALL parse_array_subscript(full_name, base, idx)
  END SUBROUTINE parse_array_subscript_pub

END MODULE wrx_param_registry
