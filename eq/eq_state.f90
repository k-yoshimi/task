! eq_state.f90
!
! Phase L-2: C-interoperable state struct for the EQ library API.
!
! Mirrors eq_api.h::eq_state_t exactly. Fixed-size arrays so the C
! layout is stable regardless of the runtime NRMAX / NTHMAX / NSUMAX
! values.
!
! L-2 scope: type definition only. Population of the struct happens
! through eq_api::eq_get_state, which in turn reads the legacy F77
! COMMON blocks (eqcom0.inc / eqcom1.inc) through the F77 bridge in
! eq_api_common.f. The real registry of settable parameters arrives
! in Phase L-3.
!
! Memory layout note:
!   In C, profile arrays are 1D or row-major; in Fortran they appear
!   1D with matching sizes. Only 1..NRMAX (etc.) carry valid runtime
!   data, the rest is padding up to EQ_MAX_*.

MODULE eq_state
  USE, INTRINSIC :: ISO_C_BINDING
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: eq_state_c, &
            EQ_MAX_NRGM, EQ_MAX_NZGM, EQ_MAX_NPSM, &
            EQ_MAX_NRM,  EQ_MAX_NTHM, EQ_MAX_NSUM, &
            eq_diag_entry_c, &
            EQ_DIAG_PARAM_LEN, EQ_DIAG_MSG_LEN, &
            EQ_DIAG_OUT_OF_RANGE, EQ_DIAG_INCONSISTENT_PAIR, &
            EQ_DIAG_OUT_OF_RANGE_AFTER_DEP, EQ_DIAG_FILE_MISSING, &
            EQ_DIAG_MISSING_REQUIRED

  ! Upper bounds for the C-visible arrays. Match the eqcom0.inc compile-time
  ! maxima (NRGM=513, NZGM=513, NPSM=513, NRVM=1001, NTVM=1025, NSUM=1343,
  ! NRM=1001, NTHM=2049) so eq_get_state never truncates the full-size grids
  ! used by eq / pl / ak.
  INTEGER(C_INT), PARAMETER :: EQ_MAX_NRGM = 513
  INTEGER(C_INT), PARAMETER :: EQ_MAX_NZGM = 513
  INTEGER(C_INT), PARAMETER :: EQ_MAX_NPSM = 513
  INTEGER(C_INT), PARAMETER :: EQ_MAX_NRM  = 1001
  INTEGER(C_INT), PARAMETER :: EQ_MAX_NTHM = 2049
  INTEGER(C_INT), PARAMETER :: EQ_MAX_NSUM = 1343

  TYPE, BIND(C) :: eq_state_c
     ! Grid dimensions (mirrors NRGMAX/NZGMAX/NPSMAX/NRMAX/NTHMAX/NSUMAX
     ! in eqcom1.inc EQPRN2/EQPRN3).
     INTEGER(C_INT)  :: nrgmax
     INTEGER(C_INT)  :: nzgmax
     INTEGER(C_INT)  :: npsmax
     INTEGER(C_INT)  :: nrmax
     INTEGER(C_INT)  :: nthmax
     INTEGER(C_INT)  :: nsumax
     ! Secondary grid counters used by EQRTSK / Phase 0 baselines
     ! (NRVMAX = volume-grid count; NSGMAX/NTGMAX = orthogonal
     ! curvilinear PSI(s,t) grid). All in eqcom1_mod.
     INTEGER(C_INT)  :: nrvmax
     INTEGER(C_INT)  :: nsgmax
     INTEGER(C_INT)  :: ntgmax
     ! Global scalars (EQGLB1..EQGLB2).
     REAL(C_DOUBLE)  :: raxis
     REAL(C_DOUBLE)  :: zaxis
     REAL(C_DOUBLE)  :: psi0
     REAL(C_DOUBLE)  :: psipa
     REAL(C_DOUBLE)  :: psita
     REAL(C_DOUBLE)  :: qaxis
     REAL(C_DOUBLE)  :: qsurf
     REAL(C_DOUBLE)  :: betat
     REAL(C_DOUBLE)  :: betap
     REAL(C_DOUBLE)  :: pvol
     REAL(C_DOUBLE)  :: raave
     REAL(C_DOUBLE)  :: ripx
     ! 1D profiles indexed 1..npsmax (EQOUT2/EQOUT3).
     REAL(C_DOUBLE)  :: psips(EQ_MAX_NPSM)
     REAL(C_DOUBLE)  :: ppps(EQ_MAX_NPSM)
     REAL(C_DOUBLE)  :: ttps(EQ_MAX_NPSM)
     REAL(C_DOUBLE)  :: qqps(EQ_MAX_NPSM)
     ! Equilibrium grid samples (EQOUT1).
     REAL(C_DOUBLE)  :: rg(EQ_MAX_NRGM)
     REAL(C_DOUBLE)  :: zg(EQ_MAX_NZGM)
     ! Per-NR flux-surface profile arrays (1..NRMAX). Mirrors the 7
     ! columns written to the Phase 0 baseline regression.log via
     ! eqregress.f:88-89 (PSIP / PSIT / PPS / TTS / QPS / VPS / RST).
     ! Indexed 0..EQ_MAX_NRM-1; only the first NRMAX entries carry
     ! valid runtime data, rest is zero-padded.
     REAL(C_DOUBLE)  :: profile_psip(EQ_MAX_NRM)
     REAL(C_DOUBLE)  :: profile_psit(EQ_MAX_NRM)
     REAL(C_DOUBLE)  :: profile_pps(EQ_MAX_NRM)
     REAL(C_DOUBLE)  :: profile_tts(EQ_MAX_NRM)
     REAL(C_DOUBLE)  :: profile_qps(EQ_MAX_NRM)
     REAL(C_DOUBLE)  :: profile_vps(EQ_MAX_NRM)
     REAL(C_DOUBLE)  :: profile_rst(EQ_MAX_NRM)
  END TYPE eq_state_c

  ! Issue #143: pre-run parameter validation. Diagnostic record returned
  ! by eq_validate. Must match eq_api.h::eq_diag_entry_t byte-for-byte.
  INTEGER(C_INT), PARAMETER :: EQ_DIAG_PARAM_LEN = 64
  INTEGER(C_INT), PARAMETER :: EQ_DIAG_MSG_LEN   = 128

  ! Diagnostic category codes. Must match eq_api.h::eq_diag_code.
  INTEGER(C_INT), PARAMETER :: EQ_DIAG_OUT_OF_RANGE           = 1
  INTEGER(C_INT), PARAMETER :: EQ_DIAG_INCONSISTENT_PAIR      = 2
  INTEGER(C_INT), PARAMETER :: EQ_DIAG_OUT_OF_RANGE_AFTER_DEP = 3
  INTEGER(C_INT), PARAMETER :: EQ_DIAG_FILE_MISSING           = 4
  INTEGER(C_INT), PARAMETER :: EQ_DIAG_MISSING_REQUIRED       = 5

  TYPE, BIND(C) :: eq_diag_entry_c
     CHARACTER(KIND=C_CHAR) :: param(EQ_DIAG_PARAM_LEN)
     INTEGER(C_INT)         :: code
     CHARACTER(KIND=C_CHAR) :: msg(EQ_DIAG_MSG_LEN)
  END TYPE eq_diag_entry_c

END MODULE eq_state
