! fp_param_registry.f90
!
! Phase L-3: setter table for namelist (fpparm.f90 / &fp/) parameters.
!
! Implements a hand-written SELECT CASE dispatch that maps a parameter
! name (optionally with a 1-origin subscript in square brackets, e.g.
! "PN[1]") to an assignment into the matching fpcomm_parm / plcomm_parm
! variable.
!
! The initial set follows
! docs/superpowers/plans/2026-04-18-fp-library-L3-param-registry.md §"Module Survey":
!   - geometry/device scalars (RR, RA, RB, RKAP, RDLT, BB, RIP)
!   - mesh                    (NRMAX, NPMAX, NTHMAX, NTMAX, NAVMAX)
!   - species count           (NSMAX, NSAMAX, NSBMAX)
!   - species mapping arrays  (NS_NSA[i], NS_NSB[i])
!   - species real arrays     (PA[i], PZ[i], PN[i], PNS[i], PTPR[i],
!                              PTPP[i], PTS[i], PMAX[i])
!   - time evolution          (DELT, EPSFP, LMAXFP)
!   - radial mesh             (R1, DELR1, RMIN, RMAX, E0, ZEFF)
!   - wave heating            (PABS_EC, PABS_LH, PABS_FW, PABS_WR,
!                              PABS_WM, RF_WM)
!   - model switches scalar   (MODELG, MODELE, MODELR, MODELS, MODELD,
!                              MODEL_NBI, MODEL_WAVE, MODEL_DISRUPT,
!                              MODEL_BS, MODEL_LOSS, MODEL_SYNCH,
!                              MODEL_FOW)
!   - model switches arrays   (MODELC[i], MODELW[i])
!
! Approximately 40 unique names covering ~55 settable variables once
! array subscripts are counted. Additional namelist vars may be added
! in a later PR by extending the SELECT CASE list; the parser handles
! any "NAME" or "NAME[idx]" input unchanged.
!
! Mirrors tr/tr_param_registry.f90 (Phase L-3, PR #33).

MODULE fp_param_registry
  USE fpcomm_parm
  USE plcomm, ONLY: KNAMEQ
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: fp_param_set
  PUBLIC :: fp_param_set_str
  PUBLIC :: parse_array_subscript_pub   ! exported for unit-test only

CONTAINS

  FUNCTION fp_param_set(name, value) RESULT(ierr)
    CHARACTER(LEN=*), INTENT(IN) :: name
    REAL(rkind),      INTENT(IN) :: value
    INTEGER :: ierr
    INTEGER :: idx
    CHARACTER(LEN=64) :: b

    ierr = 0
    CALL parse_array_subscript(name, b, idx)

    SELECT CASE (TRIM(b))
    ! --- geometry / device scalars (from plcomm_parm via fpcomm_parm) ---
    CASE ("RR");    RR    = value
    CASE ("RA");    RA    = value
    CASE ("RB");    RB    = value
    CASE ("RKAP");  RKAP  = value
    CASE ("RDLT");  RDLT  = value
    CASE ("BB");    BB    = value
    CASE ("RIP");   RIP   = value
    ! --- mesh ----------------------------------------------------
    CASE ("NRMAX");  NRMAX  = NINT(value)
    CASE ("NPMAX");  NPMAX  = NINT(value)
    CASE ("NTHMAX"); NTHMAX = NINT(value)
    CASE ("NTMAX");  NTMAX  = NINT(value)
    CASE ("NAVMAX"); NAVMAX = NINT(value)
    ! --- species count -------------------------------------------
    ! Early-reject out-of-range values so property-based / fuzz callers
    ! get a clean ierr=1 INVALID here instead of a later SEGV deep in
    ! fp_allocate. 100 = plcomm::NSM hard upper bound; 8 matches
    ! fp/fp_state.f90::FP_MAX_NSAMAX for the C ABI struct.
    CASE ("NSMAX")
       IF (NINT(value) < 1 .OR. NINT(value) > 100) THEN; ierr = 1; RETURN; END IF
       NSMAX  = NINT(value)
    CASE ("NSAMAX")
       IF (NINT(value) < 1 .OR. NINT(value) > 8) THEN; ierr = 1; RETURN; END IF
       NSAMAX = NINT(value)
    CASE ("NSBMAX")
       IF (NINT(value) < 1 .OR. NINT(value) > 8) THEN; ierr = 1; RETURN; END IF
       NSBMAX = NINT(value)
    ! --- species mapping arrays (1-origin, NSM-bound) ------------
    CASE ("NS_NSA")
       IF (idx < 1 .OR. idx > SIZE(NS_NSA)) THEN; ierr = 2; RETURN; END IF
       NS_NSA(idx) = NINT(value)
    CASE ("NS_NSB")
       IF (idx < 1 .OR. idx > SIZE(NS_NSB)) THEN; ierr = 2; RETURN; END IF
       NS_NSB(idx) = NINT(value)
    ! --- species real arrays (1-origin) --------------------------
    CASE ("PA")
       IF (idx < 1 .OR. idx > SIZE(PA))   THEN; ierr = 2; RETURN; END IF
       PA(idx)   = value
    CASE ("PZ")
       IF (idx < 1 .OR. idx > SIZE(PZ))   THEN; ierr = 2; RETURN; END IF
       PZ(idx)   = value
    CASE ("PN")
       IF (idx < 1 .OR. idx > SIZE(PN))   THEN; ierr = 2; RETURN; END IF
       PN(idx)   = value
    CASE ("PNS")
       IF (idx < 1 .OR. idx > SIZE(PNS))  THEN; ierr = 2; RETURN; END IF
       PNS(idx)  = value
    CASE ("PTPR")
       IF (idx < 1 .OR. idx > SIZE(PTPR)) THEN; ierr = 2; RETURN; END IF
       PTPR(idx) = value
    CASE ("PTPP")
       IF (idx < 1 .OR. idx > SIZE(PTPP)) THEN; ierr = 2; RETURN; END IF
       PTPP(idx) = value
    CASE ("PTS")
       IF (idx < 1 .OR. idx > SIZE(PTS))  THEN; ierr = 2; RETURN; END IF
       PTS(idx)  = value
    CASE ("PMAX")
       IF (idx < 1 .OR. idx > SIZE(PMAX)) THEN; ierr = 2; RETURN; END IF
       PMAX(idx) = value
    ! --- time evolution ------------------------------------------
    CASE ("DELT");   DELT   = value
    CASE ("EPSFP");  EPSFP  = value
    CASE ("LMAXFP"); LMAXFP = NINT(value)
    ! --- radial mesh / scalar physics ----------------------------
    CASE ("R1");    R1    = value
    CASE ("DELR1"); DELR1 = value
    CASE ("RMIN");  RMIN  = value
    CASE ("RMAX");  RMAX  = value
    CASE ("E0");    E0    = value
    CASE ("ZEFF");  ZEFF  = value
    ! --- wave heating --------------------------------------------
    CASE ("PABS_EC"); PABS_EC = value
    CASE ("PABS_LH"); PABS_LH = value
    CASE ("PABS_FW"); PABS_FW = value
    CASE ("PABS_WR"); PABS_WR = value
    CASE ("PABS_WM"); PABS_WM = value
    CASE ("RF_WM");   RF_WM   = value
    ! --- model switches (scalar int) -----------------------------
    CASE ("MODELG"); MODELG = NINT(value)
    CASE ("MODELE"); MODELE = NINT(value)
    CASE ("MODELR"); MODELR = NINT(value)
    CASE ("MODELS"); MODELS = NINT(value)
    CASE ("MODELD"); MODELD = NINT(value)
    CASE ("MODEL_NBI");      MODEL_NBI      = NINT(value)
    CASE ("MODEL_WAVE");     MODEL_WAVE     = NINT(value)
    CASE ("MODEL_DISRUPT");  MODEL_DISRUPT  = NINT(value)
    CASE ("MODEL_BS");       MODEL_BS       = NINT(value)
    CASE ("MODEL_LOSS");     MODEL_LOSS     = NINT(value)
    CASE ("MODEL_SYNCH");    MODEL_SYNCH    = NINT(value)
    CASE ("MODEL_FOW");      MODEL_FOW      = NINT(value)
    ! --- model switches (per-species int arrays) -----------------
    CASE ("MODELC")
       IF (idx < 1 .OR. idx > SIZE(MODELC)) THEN; ierr = 2; RETURN; END IF
       MODELC(idx) = NINT(value)
    CASE ("MODELW")
       IF (idx < 1 .OR. idx > SIZE(MODELW)) THEN; ierr = 2; RETURN; END IF
       MODELW(idx) = NINT(value)
    CASE DEFAULT
       ierr = 1   ! unknown name
    END SELECT
  END FUNCTION fp_param_set

  !-------------------------------------------------------------------
  ! fp_param_set_str : string-valued parameter setter.
  !
  ! Mirrors tr/tr_param_registry.f90::tr_param_set_str (PR #103).
  ! Required because the FP namelist /FP/ inherits KNAMEQ from
  ! plcomm (the equilibrium-data file name used by the MODELG=3
  ! eq_load path on fp_iter01). Without this entry point the
  ! Layer 1 fixture cannot point at a real EQDSK; the default
  ! KNAMEQ='eqdata' (from pl_init) is missing in cwd, so eq_load
  ! fails silently and downstream BESEKNX trips with NCALC=-2.
  !-------------------------------------------------------------------
  FUNCTION fp_param_set_str(name, value) RESULT(ierr)
    CHARACTER(LEN=*), INTENT(IN) :: name
    CHARACTER(LEN=*), INTENT(IN) :: value
    INTEGER :: ierr

    ierr = 0
    SELECT CASE (TRIM(ADJUSTL(name)))
    CASE ("KNAMEQ"); KNAMEQ = TRIM(value)
    CASE DEFAULT
       ierr = 1   ! unknown string-valued name
    END SELECT
  END FUNCTION fp_param_set_str

  !-------------------------------------------------------------------
  ! Split "NAME" or "NAME[N]" into (base, idx).
  !
  !   "RR"      -> base="RR",  idx=0       (scalar form)
  !   "PN[1]"   -> base="PN",  idx=1       (1-origin subscript)
  !   "MODELC[2]" -> base="MODELC", idx=2
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
    rb = INDEX(full_name, ']', BACK=.TRUE.)
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

END MODULE fp_param_registry
