! tr_state.f90
!
! Phase L-2: C-interoperable state struct for the TR library API.
!
! Mirrors tr_api.h::tr_state_t exactly. Fixed-size arrays per
! docs/superpowers/specs/2026-04-17-tr-library-design.md  Section 4.2.
!
! L-2 scope: type definition only. Population from TRCOMM happens in
! tr_api::tr_get_state during Phase L-3.
!
! Memory layout note:
!   In C, RN[NRMAX][NSMAX] is row-major;
!   in Fortran the matching declaration is RN(NSMAX, NRMAX) (column-major).
!   The two layouts agree byte-for-byte, but only RN(0:nrmax-1, 0:nsmax-1)
!   carry valid runtime data (the rest is padding up to TR_MAX_*).

MODULE tr_state
  USE, INTRINSIC :: ISO_C_BINDING
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: tr_state_c, TR_MAX_NRMAX, TR_MAX_NSMAX, &
            tr_diag_entry_c, &
            TR_DIAG_PARAM_LEN, TR_DIAG_MSG_LEN, &
            TR_DIAG_OUT_OF_RANGE, TR_DIAG_INCONSISTENT_PAIR, &
            TR_DIAG_OUT_OF_RANGE_AFTER_DEP, TR_DIAG_FILE_MISSING, &
            TR_DIAG_MISSING_REQUIRED

  INTEGER(C_INT), PARAMETER :: TR_MAX_NRMAX = 500
  INTEGER(C_INT), PARAMETER :: TR_MAX_NSMAX = 8

  ! Issue #143 pre-run validation infrastructure. Mirrors eq_state.f90.
  ! Python-side constants in python/trlib/_ffi.py must match.
  INTEGER(C_INT), PARAMETER :: TR_DIAG_PARAM_LEN = 64
  INTEGER(C_INT), PARAMETER :: TR_DIAG_MSG_LEN   = 128

  ! Diagnostic category codes — mirror enum tr_diag_code in tr_api.h.
  INTEGER(C_INT), PARAMETER :: TR_DIAG_OUT_OF_RANGE           = 1
  INTEGER(C_INT), PARAMETER :: TR_DIAG_INCONSISTENT_PAIR      = 2
  INTEGER(C_INT), PARAMETER :: TR_DIAG_OUT_OF_RANGE_AFTER_DEP = 3
  INTEGER(C_INT), PARAMETER :: TR_DIAG_FILE_MISSING           = 4
  INTEGER(C_INT), PARAMETER :: TR_DIAG_MISSING_REQUIRED       = 5

  TYPE, BIND(C) :: tr_state_c
     INTEGER(C_INT)  :: nt
     INTEGER(C_INT)  :: nrmax
     INTEGER(C_INT)  :: nsmax
     REAL(C_DOUBLE)  :: T
     REAL(C_DOUBLE)  :: WPT
     REAL(C_DOUBLE)  :: AJT
     REAL(C_DOUBLE)  :: Q0
     REAL(C_DOUBLE)  :: BETA0
     REAL(C_DOUBLE)  :: BETAP0
     REAL(C_DOUBLE)  :: BETAA
     REAL(C_DOUBLE)  :: BETAN
     REAL(C_DOUBLE)  :: TAUE1
     REAL(C_DOUBLE)  :: TAUE2
     REAL(C_DOUBLE)  :: ZEFF0
     REAL(C_DOUBLE)  :: ALI
     REAL(C_DOUBLE)  :: RQ1
     REAL(C_DOUBLE)  :: RN(TR_MAX_NSMAX, TR_MAX_NRMAX)
     REAL(C_DOUBLE)  :: RT(TR_MAX_NSMAX, TR_MAX_NRMAX)
     REAL(C_DOUBLE)  :: AJ(TR_MAX_NRMAX)
     REAL(C_DOUBLE)  :: QP(TR_MAX_NRMAX)
     ! L-7b-i: total RF + external driven current [MA] (sum into AJRFT global,
     ! includes the new EXTERNAL_DRIVEN_I contribution from trprf).
     REAL(C_DOUBLE)  :: AJRFT
  END TYPE tr_state_c

  ! One validation diagnostic entry. Mirrors tr_api.h::tr_diag_entry_t.
  TYPE, BIND(C) :: tr_diag_entry_c
     CHARACTER(KIND=C_CHAR) :: param(TR_DIAG_PARAM_LEN)
     INTEGER(C_INT)         :: code
     CHARACTER(KIND=C_CHAR) :: msg(TR_DIAG_MSG_LEN)
  END TYPE tr_diag_entry_c

END MODULE tr_state
