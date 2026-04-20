! wrx_state.f90
!
! C-interoperable state struct for the WRX library API.
!
! Mirrors wrx_api.h::wrx_state_t exactly. Fixed-size arrays with
! compile-time upper bounds; runtime sizes live in the
! nraymax/nstpmax/nrsmax/nrlmax/nsamax fields.
!
! Upper bounds (must match the matching #define in wrx_api.h):
!   WRX_MAX_NRAYMAX = 100  (matches NRAYM in wrcomm_parm)
!   WRX_MAX_NSAMAX  =   8  (matches NSM upper bound used by wr/dp)
!   WRX_MAX_NRSMAX  = 256  (>= the wrinit default 100; 2x head-room)
!   WRX_MAX_NRLMAX  = 256  (>= the wrinit default 200)
!
! 2026-04-20: schema extended to surface the radial-bin power arrays
! (pos_nrs, pos_nrl, pwr_nrs_nsa, pwr_nrl_nsa) and the per-ray pwrmax
! arrays that the Phase-0 baseline (wrx_regress.dat) dumps. Without
! these fields the Layer-1 equivalence tests cannot match the
! baseline JSON shape {arrays, arrays2, scalars}.
!
! Memory layout note:
!   In C, pwr_nsa_nray[NRAYMAX][NSAMAX] is row-major;
!   in Fortran the matching declaration is pwr_nsa_nray(NSAMAX, NRAYMAX)
!   (column-major). The two layouts agree byte-for-byte.

MODULE wrx_state
  USE, INTRINSIC :: ISO_C_BINDING
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: wrx_state_c, &
            WRX_MAX_NRAYMAX, WRX_MAX_NSAMAX, &
            WRX_MAX_NRSMAX,  WRX_MAX_NRLMAX

  INTEGER(C_INT), PARAMETER :: WRX_MAX_NRAYMAX = 100
  INTEGER(C_INT), PARAMETER :: WRX_MAX_NSAMAX  =   8
  INTEGER(C_INT), PARAMETER :: WRX_MAX_NRSMAX  = 256
  INTEGER(C_INT), PARAMETER :: WRX_MAX_NRLMAX  = 256

  TYPE, BIND(C) :: wrx_state_c
     ! --- runtime dims ---
     INTEGER(C_INT) :: nraymax
     INTEGER(C_INT) :: nstpmax
     INTEGER(C_INT) :: nsamax
     INTEGER(C_INT) :: nsmax
     INTEGER(C_INT) :: nrsmax
     INTEGER(C_INT) :: nrlmax
     INTEGER(C_INT) :: modelg
     INTEGER(C_INT) :: mdlwrq
     ! --- scalars (baseline "scalars" group) ---
     REAL(C_DOUBLE) :: pwr_tot
     ! --- 1D arrays (baseline "arrays" group) ---
     INTEGER(C_INT) :: nstpmax_nray(WRX_MAX_NRAYMAX)
     REAL(C_DOUBLE) :: pwr_nray(WRX_MAX_NRAYMAX)
     REAL(C_DOUBLE) :: pwr_nsa(WRX_MAX_NSAMAX)
     REAL(C_DOUBLE) :: pos_nrs(WRX_MAX_NRSMAX)
     REAL(C_DOUBLE) :: pos_nrl(WRX_MAX_NRLMAX)
     ! --- 2D arrays (baseline "arrays2" group) ---
     REAL(C_DOUBLE) :: pwr_nsa_nray(WRX_MAX_NSAMAX, WRX_MAX_NRAYMAX)
     REAL(C_DOUBLE) :: pwr_nrs_nsa(WRX_MAX_NSAMAX, WRX_MAX_NRSMAX)
     REAL(C_DOUBLE) :: pwr_nrl_nsa(WRX_MAX_NSAMAX, WRX_MAX_NRLMAX)
     REAL(C_DOUBLE) :: pos_pwrmax_rs_nsa_nray(WRX_MAX_NSAMAX, WRX_MAX_NRAYMAX)
     REAL(C_DOUBLE) :: pos_pwrmax_rl_nsa_nray(WRX_MAX_NSAMAX, WRX_MAX_NRAYMAX)
     REAL(C_DOUBLE) :: pwrmax_rs_nsa_nray(WRX_MAX_NSAMAX, WRX_MAX_NRAYMAX)
     REAL(C_DOUBLE) :: pwrmax_rl_nsa_nray(WRX_MAX_NSAMAX, WRX_MAX_NRAYMAX)
     ! --- legacy 1D-by-species (kept for BC with existing callers) ---
     REAL(C_DOUBLE) :: pos_pwrmax_rs_nsa(WRX_MAX_NSAMAX)
     REAL(C_DOUBLE) :: pwrmax_rs_nsa(WRX_MAX_NSAMAX)
     REAL(C_DOUBLE) :: pos_pwrmax_rl_nsa(WRX_MAX_NSAMAX)
     REAL(C_DOUBLE) :: pwrmax_rl_nsa(WRX_MAX_NSAMAX)
  END TYPE wrx_state_c

END MODULE wrx_state
