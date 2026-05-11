! tot_state.f90
!
! Phase L-2: C-interoperable state struct for the TOT orchestrator API.
!
! Mirrors tot_api.h::tot_state_t exactly. TOT is an orchestrator that fans
! out to per-module APIs (tr, ti, fp, wr, ...); the state container here
! carries per-module presence flags plus a small set of integrated state
! slots. L-3+ will replace the placeholder slots with nested per-module
! state types (TYPE(tr_state_c), TYPE(ti_state_c), ...) once the build
! system can guarantee every module's L-2 is complete.
!
! L-2 scope: type definition only; no population from any *COMM module.
! Crucially, this file intentionally does NOT `USE tr_state` (nor any
! other per-module state module). Keeping the L-2 stub independent means
! the SRCS_API target can compile even when per-module L-2 branches have
! not yet merged into the tree that is building tot. Real composition is
! wired in L-3+.
!
! See docs/superpowers/specs/2026-04-17-tr-library-design.md  Section 4.

MODULE tot_state
  USE, INTRINSIC :: ISO_C_BINDING
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: tot_state_c, &
            TOT_MAX_NRMAX, TOT_MAX_NSMAX, &
            TOT_TR_PRESENT, TOT_TI_PRESENT, &
            TOT_FP_PRESENT, TOT_WR_PRESENT

  ! Upper bounds used by the integrated state slots. These are the same
  ! values carried by tr_api.h / ti_api.h / fp_api.h / wr_api.h at L-2 so
  ! the orchestrator container can be layout-compatible once the
  ! per-module L-2 state types are nested in L-3+.
  INTEGER(C_INT), PARAMETER :: TOT_MAX_NRMAX = 500
  INTEGER(C_INT), PARAMETER :: TOT_MAX_NSMAX = 8

  ! Presence flag bit positions (index into tot_state_c%present(:)).
  ! 1-based because Fortran arrays in this module default to 1-based.
  INTEGER(C_INT), PARAMETER :: TOT_TR_PRESENT = 1
  INTEGER(C_INT), PARAMETER :: TOT_TI_PRESENT = 2
  INTEGER(C_INT), PARAMETER :: TOT_FP_PRESENT = 3
  INTEGER(C_INT), PARAMETER :: TOT_WR_PRESENT = 4

  TYPE, BIND(C) :: tot_state_c
     ! --- orchestrator presence flags ---------------------------------
     !   0 = module not initialized (or not compiled into this build)
     !   1 = module initialized and its sub-state slot is populated
     INTEGER(C_INT) :: tr_present
     INTEGER(C_INT) :: ti_present
     INTEGER(C_INT) :: fp_present
     INTEGER(C_INT) :: wr_present

     ! --- integrated scalar slots (aggregated across modules) ---------
     ! Populated by L-3 via the per-module *_get_state calls. At L-2
     ! these are just struct members with fixed layout so a C caller
     ! can take the address of each field.
     INTEGER(C_INT) :: nt          ! TR time-step counter (authoritative)
     INTEGER(C_INT) :: nrmax       ! TR radial grid size
     INTEGER(C_INT) :: nsmax       ! TR species count
     REAL(C_DOUBLE) :: T           ! simulation time [s]
     REAL(C_DOUBLE) :: WPT         ! total stored energy [J]
     REAL(C_DOUBLE) :: AJT         ! total plasma current [A]
     REAL(C_DOUBLE) :: Q0          ! safety factor on axis
     REAL(C_DOUBLE) :: BETA0       ! beta on axis
     REAL(C_DOUBLE) :: BETAP0      ! poloidal beta on axis
     REAL(C_DOUBLE) :: BETAA       ! volume-averaged beta
     REAL(C_DOUBLE) :: BETAN       ! normalized beta
     REAL(C_DOUBLE) :: TAUE1       ! energy confinement time (def 1)
     REAL(C_DOUBLE) :: TAUE2       ! energy confinement time (def 2)
     REAL(C_DOUBLE) :: ZEFF0       ! effective charge on axis
     REAL(C_DOUBLE) :: ALI         ! internal inductance
     REAL(C_DOUBLE) :: RQ1         ! q=1 surface radius

     ! --- integrated profile slots -----------------------------------
     ! Fixed-size arrays mirror tr_state_c layout; only
     ! [0..nrmax-1][0..nsmax-1] are valid at runtime, rest is padding.
     REAL(C_DOUBLE) :: RN(TOT_MAX_NSMAX, TOT_MAX_NRMAX)
     REAL(C_DOUBLE) :: RT(TOT_MAX_NSMAX, TOT_MAX_NRMAX)
     REAL(C_DOUBLE) :: AJ(TOT_MAX_NRMAX)
     REAL(C_DOUBLE) :: QP(TOT_MAX_NRMAX)

     ! L-7b-i: total RF + external driven current [MA]. Mirrors AJRFT
     ! in tr_state_c; appended at end-of-struct for ABI v2 compatibility.
     REAL(C_DOUBLE) :: AJRFT
  END TYPE tot_state_c

END MODULE tot_state
