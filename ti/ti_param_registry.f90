! ti_param_registry.f90
!
! Phase L-3: setter table for ti namelist (tiparm.f90 /TI/) parameters.
!
! Implements a hand-written SELECT CASE dispatch that maps a parameter
! name (optionally with a 1-origin subscript in square brackets, e.g.
! "PN[1]" or "MODEL_BND[1,3]") to an assignment into the matching
! TICOMM/PLCOMM variable.
!
! NOTE on PA / PM naming: `plcomm` defines the atomic-mass array as
! `PA(NSM)`. `ti/ticomm.f90:5` does `USE plcomm, pm=>pa` so internal
! ti code refers to it as `pm`, but that rename is local and does NOT
! re-export. We therefore USE plcomm WITHOUT the rename here and expose
! `PA` (the true name) as the C ABI key. See the PR description and
! plan §"PA / pm 命名の決定" for rationale.
!
! `KID_NS` is character-valued and not settable through the float-only
! ti_set_param ABI; not registered.
!
! See docs/superpowers/specs/2026-04-17-tr-library-design.md §5 and
! docs/superpowers/plans/2026-04-18-ti-library-L3-param-registry.md.

MODULE ti_param_registry
  USE plcomm, ONLY: RR, RA, RKAP, RDLT, BB, RIP, &
                    NSMAX, PA, PZ, PN, PNS, PTPR, PTPP, PTS, PU, PUS, &
                    NPA, ID_NS, &
                    PROFN1, PROFN2, PROFT1, PROFT2, PROFU1, PROFU2, &
                    MODELG, MODELQ, model_prof, MODEL_NPROF
  USE ticomm_parm, ONLY: rkind, &
                         NZMIN_NS, NZMAX_NS, NZINI_NS, &
                         PT, MODEL_BND, BND_VALUE, &
                         DT, NRMAX, NTMAX, NTSTEP, NGTSTEP, NGRSTEP, &
                         MAXLOOP, EPSLOOP, EPSMAT, MATTYPE, &
                         MODEL_EQB, MODEL_EQN, MODEL_EQT, MODEL_EQU, &
                         MODEL_KAI, MODEL_DRR, MODEL_VR, MODEL_NC, &
                         MODEL_NF, MODEL_NB, MODEL_EC, MODEL_LH, MODEL_IC, &
                         MODEL_CD, MODEL_SYNC, MODEL_PEL, MODEL_PSC, &
                         PROFJ1, PROFJ2, &
                         DN0, DT0, DU0, VDN0, VDT0, VDU0, DR0, DRS, &
                         DN0_NS, DT0_NS, DU0_NS, VDN0_NS, VDT0_NS, VDU0_NS
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: ti_param_set

  INTEGER, PARAMETER :: ERR_OK            = 0
  INTEGER, PARAMETER :: ERR_UNKNOWN_NAME  = 1
  INTEGER, PARAMETER :: ERR_BAD_INDEX     = 2

CONTAINS

  FUNCTION ti_param_set(name, value) RESULT(ierr)
    CHARACTER(LEN=*), INTENT(IN) :: name
    REAL(rkind),      INTENT(IN) :: value
    INTEGER :: ierr
    CHARACTER(LEN=64) :: base
    INTEGER :: i1, i2

    CALL parse_subscript(name, base, i1, i2)
    ierr = ERR_OK

    SELECT CASE (TRIM(base))
    ! ---- geometry / device (plcomm scalars) ----
    CASE ("RR");           RR    = value
    CASE ("RA");           RA    = value
    CASE ("RKAP");         RKAP  = value
    CASE ("RDLT");         RDLT  = value
    CASE ("BB");           BB    = value
    CASE ("RIP");          RIP   = value

    ! ---- profile shape (plcomm 1D arrays indexed by NS) ----
    CASE ("PROFN1"); IF (i1 < 1 .OR. i1 > SIZE(PROFN1)) THEN; ierr=ERR_BAD_INDEX; ELSE; PROFN1(i1) = value; END IF
    CASE ("PROFN2"); IF (i1 < 1 .OR. i1 > SIZE(PROFN2)) THEN; ierr=ERR_BAD_INDEX; ELSE; PROFN2(i1) = value; END IF
    CASE ("PROFT1"); IF (i1 < 1 .OR. i1 > SIZE(PROFT1)) THEN; ierr=ERR_BAD_INDEX; ELSE; PROFT1(i1) = value; END IF
    CASE ("PROFT2"); IF (i1 < 1 .OR. i1 > SIZE(PROFT2)) THEN; ierr=ERR_BAD_INDEX; ELSE; PROFT2(i1) = value; END IF
    CASE ("PROFU1"); IF (i1 < 1 .OR. i1 > SIZE(PROFU1)) THEN; ierr=ERR_BAD_INDEX; ELSE; PROFU1(i1) = value; END IF
    CASE ("PROFU2"); IF (i1 < 1 .OR. i1 > SIZE(PROFU2)) THEN; ierr=ERR_BAD_INDEX; ELSE; PROFU2(i1) = value; END IF

    ! ---- model switches (plcomm) ----
    CASE ("MODELG");       MODELG       = INT(value)
    CASE ("MODELQ");       MODELQ       = INT(value)
    CASE ("MODEL_PROF");   model_prof   = INT(value)
    CASE ("MODEL_NPROF");  MODEL_NPROF  = INT(value)

    ! ---- plasma scalar int ----
    ! Early-reject out-of-range values so property-based / fuzz callers
    ! get a clean INVALID here instead of a later SEGV in ti_allocate.
    ! 100 = plcomm::NSM hard upper bound. Use ERR_UNKNOWN_NAME (=1)
    ! rather than ERR_BAD_INDEX (=2): BAD_INDEX is reserved for array-
    ! subscript errors and would mislead a direct Fortran caller about
    ! the failure mode. Both codes collapse to TI_ERR_INVALID at the
    ! C ABI (ti_api.f90), matching the ierr=1 convention used by the
    ! sibling tr/fp/wr registries.
    CASE ("NSMAX")
       IF (INT(value) < 1 .OR. INT(value) > 100) THEN
          ierr = ERR_UNKNOWN_NAME; RETURN
       END IF
       NSMAX = INT(value)

    ! ---- 1D arrays indexed by NS (plcomm) ----
    ! PA = atomic mass (plcomm true name). ti namelist calls this "PM" via
    ! the `pm=>pa` rename in ticomm_parm; here we expose only PA.
    CASE ("PA");   IF (i1 < 1 .OR. i1 > SIZE(PA))   THEN; ierr=ERR_BAD_INDEX; ELSE; PA(i1)   = value; END IF
    CASE ("PZ");   IF (i1 < 1 .OR. i1 > SIZE(PZ))   THEN; ierr=ERR_BAD_INDEX; ELSE; PZ(i1)   = value; END IF
    CASE ("PN");   IF (i1 < 1 .OR. i1 > SIZE(PN))   THEN; ierr=ERR_BAD_INDEX; ELSE; PN(i1)   = value; END IF
    CASE ("PNS");  IF (i1 < 1 .OR. i1 > SIZE(PNS))  THEN; ierr=ERR_BAD_INDEX; ELSE; PNS(i1)  = value; END IF
    CASE ("PT");   IF (i1 < 1 .OR. i1 > SIZE(PT))   THEN; ierr=ERR_BAD_INDEX; ELSE; PT(i1)   = value; END IF
    CASE ("PTPR"); IF (i1 < 1 .OR. i1 > SIZE(PTPR)) THEN; ierr=ERR_BAD_INDEX; ELSE; PTPR(i1) = value; END IF
    CASE ("PTPP"); IF (i1 < 1 .OR. i1 > SIZE(PTPP)) THEN; ierr=ERR_BAD_INDEX; ELSE; PTPP(i1) = value; END IF
    CASE ("PTS");  IF (i1 < 1 .OR. i1 > SIZE(PTS))  THEN; ierr=ERR_BAD_INDEX; ELSE; PTS(i1)  = value; END IF
    CASE ("PU");   IF (i1 < 1 .OR. i1 > SIZE(PU))   THEN; ierr=ERR_BAD_INDEX; ELSE; PU(i1)   = value; END IF
    CASE ("PUS");  IF (i1 < 1 .OR. i1 > SIZE(PUS))  THEN; ierr=ERR_BAD_INDEX; ELSE; PUS(i1)  = value; END IF

    ! ---- 1D int arrays indexed by NS ----
    CASE ("NPA");      IF (i1 < 1 .OR. i1 > SIZE(NPA))      THEN; ierr=ERR_BAD_INDEX; ELSE; NPA(i1)      = INT(value); END IF
    CASE ("ID_NS");    IF (i1 < 1 .OR. i1 > SIZE(ID_NS))    THEN; ierr=ERR_BAD_INDEX; ELSE; ID_NS(i1)    = INT(value); END IF
    CASE ("NZMIN_NS"); IF (i1 < 1 .OR. i1 > SIZE(NZMIN_NS)) THEN; ierr=ERR_BAD_INDEX; ELSE; NZMIN_NS(i1) = INT(value); END IF
    CASE ("NZMAX_NS"); IF (i1 < 1 .OR. i1 > SIZE(NZMAX_NS)) THEN; ierr=ERR_BAD_INDEX; ELSE; NZMAX_NS(i1) = INT(value); END IF
    CASE ("NZINI_NS"); IF (i1 < 1 .OR. i1 > SIZE(NZINI_NS)) THEN; ierr=ERR_BAD_INDEX; ELSE; NZINI_NS(i1) = INT(value); END IF

    ! ---- 2D arrays indexed by (i, NS) ----
    CASE ("MODEL_BND")
       IF (i1 < 1 .OR. i1 > SIZE(MODEL_BND, 1) .OR. &
           i2 < 1 .OR. i2 > SIZE(MODEL_BND, 2)) THEN
          ierr = ERR_BAD_INDEX
       ELSE
          MODEL_BND(i1, i2) = INT(value)
       END IF
    CASE ("BND_VALUE")
       IF (i1 < 1 .OR. i1 > SIZE(BND_VALUE, 1) .OR. &
           i2 < 1 .OR. i2 > SIZE(BND_VALUE, 2)) THEN
          ierr = ERR_BAD_INDEX
       ELSE
          BND_VALUE(i1, i2) = value
       END IF

    ! ---- time evolution (ticomm_parm) ----
    CASE ("DT");           DT       = value
    CASE ("NRMAX");        NRMAX    = INT(value)
    CASE ("NTMAX");        NTMAX    = INT(value)
    CASE ("NTSTEP");       NTSTEP   = INT(value)
    CASE ("NGTSTEP");      NGTSTEP  = INT(value)
    CASE ("NGRSTEP");      NGRSTEP  = INT(value)
    CASE ("MAXLOOP");      MAXLOOP  = INT(value)
    CASE ("EPSLOOP");      EPSLOOP  = value
    CASE ("EPSMAT");       EPSMAT   = value
    CASE ("MATTYPE");      MATTYPE  = INT(value)
    CASE ("PROFJ1");       PROFJ1   = value
    CASE ("PROFJ2");       PROFJ2   = value

    ! ---- transport-coefficient scalars (ticomm_parm) ----
    ! These appear in the ti_ar / ti_min / ti_w namelists; without them
    ! the libtiapi.so run uses tiinit defaults and drifts ~2% from the
    ! Phase-0 baseline at every species/radius.
    CASE ("DN0");          DN0      = value
    CASE ("DT0");          DT0      = value
    CASE ("DU0");          DU0      = value
    CASE ("VDN0");         VDN0     = value
    CASE ("VDT0");         VDT0     = value
    CASE ("VDU0");         VDU0     = value
    CASE ("DR0");          DR0      = value
    CASE ("DRS");          DRS      = value

    ! ---- per-species transport-coefficient arrays ----
    CASE ("DN0_NS");  IF (i1 < 1 .OR. i1 > SIZE(DN0_NS))  THEN; ierr=ERR_BAD_INDEX; ELSE; DN0_NS(i1)  = value; END IF
    CASE ("DT0_NS");  IF (i1 < 1 .OR. i1 > SIZE(DT0_NS))  THEN; ierr=ERR_BAD_INDEX; ELSE; DT0_NS(i1)  = value; END IF
    CASE ("DU0_NS");  IF (i1 < 1 .OR. i1 > SIZE(DU0_NS))  THEN; ierr=ERR_BAD_INDEX; ELSE; DU0_NS(i1)  = value; END IF
    CASE ("VDN0_NS"); IF (i1 < 1 .OR. i1 > SIZE(VDN0_NS)) THEN; ierr=ERR_BAD_INDEX; ELSE; VDN0_NS(i1) = value; END IF
    CASE ("VDT0_NS"); IF (i1 < 1 .OR. i1 > SIZE(VDT0_NS)) THEN; ierr=ERR_BAD_INDEX; ELSE; VDT0_NS(i1) = value; END IF
    CASE ("VDU0_NS"); IF (i1 < 1 .OR. i1 > SIZE(VDU0_NS)) THEN; ierr=ERR_BAD_INDEX; ELSE; VDU0_NS(i1) = value; END IF

    ! ---- transport / source switches ----
    CASE ("MODEL_EQB");    MODEL_EQB    = INT(value)
    CASE ("MODEL_EQN");    MODEL_EQN    = INT(value)
    CASE ("MODEL_EQT");    MODEL_EQT    = INT(value)
    CASE ("MODEL_EQU");    MODEL_EQU    = INT(value)
    CASE ("MODEL_KAI");    MODEL_KAI    = INT(value)
    CASE ("MODEL_DRR");    MODEL_DRR    = INT(value)
    CASE ("MODEL_VR");     MODEL_VR     = INT(value)
    CASE ("MODEL_NC");     MODEL_NC     = INT(value)
    CASE ("MODEL_NF");     MODEL_NF     = INT(value)
    CASE ("MODEL_NB");     MODEL_NB     = INT(value)
    CASE ("MODEL_EC");     MODEL_EC     = INT(value)
    CASE ("MODEL_LH");     MODEL_LH     = INT(value)
    CASE ("MODEL_IC");     MODEL_IC     = INT(value)
    CASE ("MODEL_CD");     MODEL_CD     = INT(value)
    CASE ("MODEL_SYNC");   MODEL_SYNC   = INT(value)
    CASE ("MODEL_PEL");    MODEL_PEL    = INT(value)
    CASE ("MODEL_PSC");    MODEL_PSC    = INT(value)

    CASE DEFAULT
       ierr = ERR_UNKNOWN_NAME
    END SELECT
  END FUNCTION ti_param_set

  ! Parse "BASE", "BASE[i]", or "BASE[i,j]" into base + indices.
  ! i / j default to 0 when absent; -1 on parse error.
  SUBROUTINE parse_subscript(full_name, base, i1, i2)
    CHARACTER(LEN=*), INTENT(IN)  :: full_name
    CHARACTER(LEN=*), INTENT(OUT) :: base
    INTEGER,           INTENT(OUT) :: i1, i2
    INTEGER :: lb, rb, comma, ios

    base = full_name
    i1 = 0
    i2 = 0
    lb = INDEX(full_name, "[")
    rb = INDEX(full_name, "]", BACK=.TRUE.)
    IF (lb > 0 .AND. rb > lb) THEN
       base = full_name(1:lb-1)
       comma = INDEX(full_name(lb+1:rb-1), ",")
       IF (comma > 0) THEN
          READ(full_name(lb+1:lb+comma-1), *, IOSTAT=ios) i1
          IF (ios /= 0) i1 = -1
          READ(full_name(lb+comma+1:rb-1), *, IOSTAT=ios) i2
          IF (ios /= 0) i2 = -1
       ELSE
          READ(full_name(lb+1:rb-1), *, IOSTAT=ios) i1
          IF (ios /= 0) i1 = -1
       END IF
    END IF
  END SUBROUTINE parse_subscript

END MODULE ti_param_registry
