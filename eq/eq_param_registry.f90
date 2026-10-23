! eq_param_registry.f90
!
! Phase L-3: setter table for the /EQ/ namelist parameters (eqinit.f:EQNLIN).
!
! This module replaces the Phase L-2 NOT_IMPL shell with a hand-written
! SELECT CASE dispatch that maps a parameter name (optionally with a
! subscript in square brackets, e.g. "PSIB[0]", "RIPFC[3]") to an
! assignment into the matching F90 MODULE variable.
!
! Since Phase F-1 the EQ COMMON state has been mirrored into the F90
! modules eqcom{0,1,2,3}_mod, and the common device/plasma scalars
! (RR, RA, RB, RKAP, RDLT, BB, Q0, QA, RIP, MODELG, KNAMEQ, ...) live
! in plcomm_parm. We therefore dispatch via direct USE/assignment,
! which is the same pattern used by tr_param_registry (PR #33) and
! ti_param_registry (PR #34).
!
! Coverage (per docs/superpowers/plans/2026-04-18-eq-library-L3-param-registry.md):
!   A. device geometry scalars (plcomm_parm)
!        RR, RA, RB, RKAP, RDLT, BB, Q0, QA, RIP, RHOMIN, QMIN, RHOEDG
!   B. pressure / current / F / T / velocity profile scalars (eqcom1_mod)
!        PP0, PP1, PP2, PROFP0, PROFP1, PROFP2,
!        PJ0, PJ1, PJ2, PROFJ0, PROFJ1, PROFJ2,
!        FF0, FF1, FF2, PROFF0, PROFF1, PROFF2,
!        PT0, PT1, PT2, PROFTP0, PROFTP1, PROFTP2, PTSEQ, PN0EQ,
!        PV0, PV1, PV2, PROFV0, PROFV1, PROFV2,
!        PROFR0, PROFR1, PROFR2
!   C. convergence / iteration scalars (eqcom1_mod)
!        EPSEQ, NLPMAX, EPSNW, DELNW, NLPNW
!   D. region scalars (eqcom1_mod)
!        RGMIN, RGMAX, ZGMIN, ZGMAX, ZLIMP, ZLIMM, FRBIN
!   E. integer mesh / model switches (eqcom1_mod + plcomm_parm)
!        MODELG, MODELQ, MDLEQF, MDLEQC, MDLEQA, MDLEQX, MDLEQV,
!        NPRINT, IDEBUG, MODEFR, MODEFW,
!        NRMAX, NTHMAX, NSUMAX, NSGMAX, NTGMAX, NUGMAX,
!        NRGMAX, NZGMAX, NPSMAX, NRVMAX, NTVMAX, NPFCMAX
!   F. 1D arrays
!        PSIB[0..5]   (0-origin, unique to EQ)
!        RIPFC[1..10], RPFC[1..10], ZPFC[1..10], WPFC[1..10]
!
! String parameters (KNAMEQ, KNAMWR, KNAMWM, KNAMFP, KNAMFO, KNAMPF,
! KNAMEQ2) are handled through a separate entry point eq_param_set_str,
! which in turn is exposed as the BIND(C) eq_set_param_str from
! eq_api.f90 (Phase L-3).

MODULE eq_param_registry
  USE plcomm, ONLY: rkind,                                    &
       RR, RA, RB, RKAP, RDLT, BB, Q0, QA, RIP,               &
       RHOMIN, QMIN, RHOEDG,                                  &
       MODELG, MODELQ, IDEBUG, MODEFR, MODEFW,                &
       KNAMEQ, KNAMWR, KNAMWM, KNAMFP, KNAMFO, KNAMPF, KNAMEQ2
  USE eqcom1_mod, ONLY:                                       &
       PP0, PP1, PP2, PROFP0, PROFP1, PROFP2,                 &
       PJ0, PJ1, PJ2, PROFJ0, PROFJ1, PROFJ2,                 &
       FF0, FF1, FF2, PROFF0, PROFF1, PROFF2,                 &
       PT0, PT1, PT2, PROFTP0, PROFTP1, PROFTP2,              &
       PTSEQ, PN0EQ,                                          &
       PV0, PV1, PV2, PROFV0, PROFV1, PROFV2,                 &
       PROFR0, PROFR1, PROFR2,                                &
       EPSEQ, NLPMAX, EPSNW, DELNW, NLPNW,                    &
       RGMIN, RGMAX, ZGMIN, ZGMAX, ZLIMP, ZLIMM, FRBIN,       &
       MDLEQF, MDLEQC, MDLEQA, MDLEQX, MDLEQV, NPRINT,        &
       NRMAX, NTHMAX, NSUMAX, NSGMAX, NTGMAX, NUGMAX,         &
       NRGMAX, NZGMAX, NPSMAX, NRVMAX, NTVMAX, NPFCMAX,       &
       PSIB, RIPFC, RPFC, ZPFC, WPFC,                         &
       RBRA
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: eq_param_set
  PUBLIC :: eq_param_generation
  PUBLIC :: eq_param_set_str
  PUBLIC :: parse_array_subscript_pub   ! exported for unit-test only

  INTEGER, SAVE :: g_generation = 0

CONTAINS

  !-------------------------------------------------------------------
  ! Mutation counter (as tr / fp / ti have since #253).
  !
  ! Every successful numeric set through this registry, whoever calls
  ! it (eq_api_set_param, tot's "eq:" dispatcher), advances
  ! g_generation; eq_api records the count when an eq_run computes or
  ! loads the equilibrium, and eq_save refuses when it moved since.
  ! Two kinds of set are not counted, because they do not change what
  ! eq_save writes: MODEFR and MODEFW, which say how a file is opened,
  ! and the string parameters (eq_param_set_str: KNAMEQ and the other
  ! KNAM*), which the solve does not read; a load reads its file and
  ! records the count itself, and KNAMEQ is where eq_save writes. A set
  ! that fails leaves the counter alone.
  !-------------------------------------------------------------------
  FUNCTION eq_param_generation() RESULT(gen)
    INTEGER :: gen
    gen = g_generation
  END FUNCTION eq_param_generation

  SUBROUTINE eq_param_set(name, value, ierr)
    CHARACTER(LEN=*), INTENT(IN)  :: name
    REAL(rkind),      INTENT(IN)  :: value
    INTEGER,          INTENT(OUT) :: ierr
    INTEGER :: idx
    CHARACTER(LEN=32) :: b

    CALL eq_param_set_impl(name, value, ierr)
    IF (ierr /= 0) RETURN
    CALL parse_array_subscript(name, b, idx)    ! the name as the setter read it
    IF (TRIM(b) /= 'MODEFR' .AND. TRIM(b) /= 'MODEFW') &
       g_generation = g_generation + 1
  END SUBROUTINE eq_param_set

  !-------------------------------------------------------------------
  ! eq_param_set : numeric (scalar or subscripted array) setter.
  !
  ! Matches the signature used by eq_api_set_param (eq_api.f90). The
  ! ierr OUT arg is 0 on success, 1 on unknown name or out-of-range
  ! index.
  !
  ! NOTE: the EQ signature is `SUBROUTINE ... (name, value, ierr)` to
  ! stay compatible with the L-2 caller; tr/ti use FUNCTION-returning-
  ! ierr. Both shapes are valid; we keep the L-2 shape here so
  ! eq_api.f90 does not need a simultaneous edit.
  !-------------------------------------------------------------------
  SUBROUTINE eq_param_set_impl(name, value, ierr)
    CHARACTER(LEN=*), INTENT(IN)  :: name
    REAL(rkind),      INTENT(IN)  :: value
    INTEGER,          INTENT(OUT) :: ierr
    INTEGER :: idx
    CHARACTER(LEN=32) :: b

    ierr = 0
    CALL parse_array_subscript(name, b, idx)

    SELECT CASE (TRIM(b))
    ! ===== A. device geometry scalars (plcomm_parm) ==================
    CASE ("RR")
       RR = value
    CASE ("RA")
       RA = value
       ! Keep RBRA invariant (eqnlin sets RBRA=RB/RA after each read).
       IF (RA /= 0.0_rkind) RBRA = RB / RA
    CASE ("RB")
       RB = value
       IF (RA /= 0.0_rkind) RBRA = RB / RA
    CASE ("RKAP");   RKAP   = value
    CASE ("RDLT");   RDLT   = value
    CASE ("BB");     BB     = value
    CASE ("Q0");     Q0     = value
    CASE ("QA");     QA     = value
    CASE ("RIP");    RIP    = value
    CASE ("RHOMIN"); RHOMIN = value
    CASE ("QMIN");   QMIN   = value
    CASE ("RHOEDG"); RHOEDG = value

    ! ===== B. profile scalars (eqcom1_mod) ===========================
    CASE ("PP0");    PP0    = value
    CASE ("PP1");    PP1    = value
    CASE ("PP2");    PP2    = value
    CASE ("PROFP0"); PROFP0 = value
    CASE ("PROFP1"); PROFP1 = value
    CASE ("PROFP2"); PROFP2 = value
    CASE ("PJ0");    PJ0    = value
    CASE ("PJ1");    PJ1    = value
    CASE ("PJ2");    PJ2    = value
    CASE ("PROFJ0"); PROFJ0 = value
    CASE ("PROFJ1"); PROFJ1 = value
    CASE ("PROFJ2"); PROFJ2 = value
    CASE ("FF0");    FF0    = value
    CASE ("FF1");    FF1    = value
    CASE ("FF2");    FF2    = value
    CASE ("PROFF0"); PROFF0 = value
    CASE ("PROFF1"); PROFF1 = value
    CASE ("PROFF2"); PROFF2 = value
    CASE ("PT0");    PT0    = value
    CASE ("PT1");    PT1    = value
    CASE ("PT2");    PT2    = value
    CASE ("PROFTP0"); PROFTP0 = value
    CASE ("PROFTP1"); PROFTP1 = value
    CASE ("PROFTP2"); PROFTP2 = value
    CASE ("PTSEQ");  PTSEQ  = value
    CASE ("PN0EQ");  PN0EQ  = value
    CASE ("PV0");    PV0    = value
    CASE ("PV1");    PV1    = value
    CASE ("PV2");    PV2    = value
    CASE ("PROFV0"); PROFV0 = value
    CASE ("PROFV1"); PROFV1 = value
    CASE ("PROFV2"); PROFV2 = value
    CASE ("PROFR0"); PROFR0 = value
    CASE ("PROFR1"); PROFR1 = value
    CASE ("PROFR2"); PROFR2 = value

    ! ===== C. convergence / iteration scalars ========================
    CASE ("EPSEQ"); EPSEQ = value
    CASE ("EPSNW"); EPSNW = value
    CASE ("DELNW"); DELNW = value

    ! ===== D. region / boundary scalars ==============================
    CASE ("RGMIN"); RGMIN = value
    CASE ("RGMAX"); RGMAX = value
    CASE ("ZGMIN"); ZGMIN = value
    CASE ("ZGMAX"); ZGMAX = value
    CASE ("ZLIMP"); ZLIMP = value
    CASE ("ZLIMM"); ZLIMM = value
    CASE ("FRBIN"); FRBIN = value

    ! ===== E. integer scalars ========================================
    CASE ("MODELG"); MODELG = INT(value)
    CASE ("MODELQ"); MODELQ = INT(value)
    CASE ("IDEBUG"); IDEBUG = INT(value)
    CASE ("MODEFR"); MODEFR = INT(value)
    CASE ("MODEFW"); MODEFW = INT(value)
    CASE ("MDLEQF"); MDLEQF = INT(value)
    CASE ("MDLEQC"); MDLEQC = INT(value)
    CASE ("MDLEQA"); MDLEQA = INT(value)
    CASE ("MDLEQX"); MDLEQX = INT(value)
    CASE ("MDLEQV"); MDLEQV = INT(value)
    CASE ("NPRINT"); NPRINT = INT(value)
    CASE ("NLPMAX"); NLPMAX = INT(value)
    CASE ("NLPNW");  NLPNW  = INT(value)
    CASE ("NRMAX");  NRMAX  = INT(value)
    CASE ("NTHMAX"); NTHMAX = INT(value)
    CASE ("NSUMAX"); NSUMAX = INT(value)
    CASE ("NSGMAX"); NSGMAX = INT(value)
    CASE ("NTGMAX"); NTGMAX = INT(value)
    CASE ("NUGMAX"); NUGMAX = INT(value)
    CASE ("NRGMAX"); NRGMAX = INT(value)
    CASE ("NZGMAX"); NZGMAX = INT(value)
    CASE ("NPSMAX"); NPSMAX = INT(value)
    CASE ("NRVMAX"); NRVMAX = INT(value)
    CASE ("NTVMAX"); NTVMAX = INT(value)
    CASE ("NPFCMAX"); NPFCMAX = INT(value)

    ! ===== F. 1D arrays ==============================================
    ! PSIB has 0-origin bounds (0..5) -- unique to EQ among the
    ! registry.
    CASE ("PSIB")
       IF (idx < 0 .OR. idx > 5) THEN
          ierr = 1
       ELSE
          PSIB(idx) = value
       END IF
    CASE ("RIPFC")
       IF (idx < 1 .OR. idx > SIZE(RIPFC)) THEN
          ierr = 1
       ELSE
          RIPFC(idx) = value
       END IF
    CASE ("RPFC")
       IF (idx < 1 .OR. idx > SIZE(RPFC)) THEN
          ierr = 1
       ELSE
          RPFC(idx) = value
       END IF
    CASE ("ZPFC")
       IF (idx < 1 .OR. idx > SIZE(ZPFC)) THEN
          ierr = 1
       ELSE
          ZPFC(idx) = value
       END IF
    CASE ("WPFC")
       IF (idx < 1 .OR. idx > SIZE(WPFC)) THEN
          ierr = 1
       ELSE
          WPFC(idx) = value
       END IF

    CASE DEFAULT
       ierr = 1   ! unknown parameter name
    END SELECT
  END SUBROUTINE eq_param_set_impl

  !-------------------------------------------------------------------
  ! eq_param_set_str : string-valued parameter setter.
  !
  ! Covers the file-name parameters (KNAMEQ and friends) that live
  ! in plcomm_parm as CHARACTER(LEN=80).
  !
  ! Mirrors the pattern in tr_param_registry::tr_param_set_str.
  !-------------------------------------------------------------------
  FUNCTION eq_param_set_str(name, value) RESULT(ierr)
    CHARACTER(LEN=*), INTENT(IN) :: name
    CHARACTER(LEN=*), INTENT(IN) :: value
    INTEGER :: ierr

    ierr = 0
    SELECT CASE (TRIM(ADJUSTL(name)))
    CASE ("KNAMEQ");  KNAMEQ  = TRIM(value)
    CASE ("KNAMEQ2"); KNAMEQ2 = TRIM(value)
    CASE ("KNAMWR");  KNAMWR  = TRIM(value)
    CASE ("KNAMWM");  KNAMWM  = TRIM(value)
    CASE ("KNAMFP");  KNAMFP  = TRIM(value)
    CASE ("KNAMFO");  KNAMFO  = TRIM(value)
    CASE ("KNAMPF");  KNAMPF  = TRIM(value)
    CASE DEFAULT
       ierr = 1   ! unknown string-valued name
    END SELECT
  END FUNCTION eq_param_set_str

  !-------------------------------------------------------------------
  ! Split "NAME" or "NAME[N]" into (base, idx).
  !
  !   "RR"       -> base="RR",    idx=-1  (no subscript; scalar form)
  !   "PSIB[0]"  -> base="PSIB",  idx=0   (0-origin; unique to EQ)
  !   "PSIB[5]"  -> base="PSIB",  idx=5
  !   "RIPFC[3]" -> base="RIPFC", idx=3   (1-origin for everything
  !                                        except PSIB)
  !   malformed  -> base=<full>,  idx=-1  (caller returns ierr=1)
  !
  ! NOTE: idx defaults to -1 (not 0) when no subscript is present so
  ! that 0-origin arrays like PSIB correctly reject bare "PSIB" — if
  ! the default were 0, `eq_set_param("PSIB", v)` would silently write
  ! PSIB(0) instead of failing.
  !-------------------------------------------------------------------
  SUBROUTINE parse_array_subscript(full_name, base, idx)
    CHARACTER(LEN=*), INTENT(IN)  :: full_name
    CHARACTER(LEN=*), INTENT(OUT) :: base
    INTEGER,          INTENT(OUT) :: idx
    INTEGER :: lb, rb, ios
    base = ' '
    idx  = -1
    lb = INDEX(full_name, '[')
    rb = INDEX(full_name, ']')
    IF (lb == 0 .AND. rb == 0) THEN
       base = TRIM(ADJUSTL(full_name))
       RETURN
    END IF
    IF (lb == 0 .OR. rb == 0 .OR. rb <= lb + 1) THEN
       base = TRIM(ADJUSTL(full_name))   ! malformed; caller returns ierr=1
       RETURN
    END IF
    base = full_name(1:lb-1)
    READ(full_name(lb+1:rb-1), *, IOSTAT=ios) idx
    IF (ios /= 0) idx = -1
  END SUBROUTINE parse_array_subscript

  !-------------------------------------------------------------------
  ! Public alias exposed for unit-testing parse_array_subscript alone.
  !-------------------------------------------------------------------
  SUBROUTINE parse_array_subscript_pub(full_name, base, idx)
    CHARACTER(LEN=*), INTENT(IN)  :: full_name
    CHARACTER(LEN=*), INTENT(OUT) :: base
    INTEGER,          INTENT(OUT) :: idx
    CALL parse_array_subscript(full_name, base, idx)
  END SUBROUTINE parse_array_subscript_pub

END MODULE eq_param_registry
