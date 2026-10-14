! fp_state.f90
!
! Phase L-2: C-interoperable state struct for the FP library API.
!
! Mirrors fp_api.h::fp_state_t exactly. Fixed-size arrays per the
! merged plan docs/superpowers/plans/2026-04-18-fp-library-L2-c-abi-foundation.md.
!
! L-2 scope: type definition only. Population from FPCOMM happens in
! fp_api::fp_get_state during Phase L-3.
!
! Memory layout note:
!   In C, RNT[NSAMAX][NRMAX] is row-major;
!   in Fortran the matching declaration is RNT(NRMAX, NSAMAX) (column-major).
!   The two layouts agree byte-for-byte, but only RNT(0:nrmax-1, 0:nsamax-1)
!   carry valid runtime data (the rest is padding up to FP_MAX_*).
!
! ABI note: new members are APPENDED at the end of fp_state_c so the
! offsets of every pre-existing member stay put. Any change here must be
! mirrored in fp/fp_api.h and python/fplib/_ffi.py::FpStateC, and
! libfpapi.so must be rebuilt (`make -C fp libfpapi.so`) -- a stale .so
! read through a newer ctypes layout returns garbage.

MODULE fp_state
  USE, INTRINSIC :: ISO_C_BINDING
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: fp_state_c, FP_MAX_NRMAX, FP_MAX_NSAMAX

  INTEGER(C_INT), PARAMETER :: FP_MAX_NRMAX  = 100
  INTEGER(C_INT), PARAMETER :: FP_MAX_NSAMAX = 8

  TYPE, BIND(C) :: fp_state_c
     INTEGER(C_INT) :: nrmax
     INTEGER(C_INT) :: nsamax
     INTEGER(C_INT) :: npmax
     INTEGER(C_INT) :: nthmax
     INTEGER(C_INT) :: ntg2
     REAL(C_DOUBLE) :: timefp

     ! profile arrays: shape (FP_MAX_NRMAX, FP_MAX_NSAMAX)
     ! actual data only valid for indices [1..nrmax, 1..nsamax]
     REAL(C_DOUBLE) :: RNT (FP_MAX_NRMAX, FP_MAX_NSAMAX)
     REAL(C_DOUBLE) :: RWT (FP_MAX_NRMAX, FP_MAX_NSAMAX)
     REAL(C_DOUBLE) :: RTT (FP_MAX_NRMAX, FP_MAX_NSAMAX)
     REAL(C_DOUBLE) :: RJT (FP_MAX_NRMAX, FP_MAX_NSAMAX)
     REAL(C_DOUBLE) :: RPCT(FP_MAX_NRMAX, FP_MAX_NSAMAX)
     REAL(C_DOUBLE) :: RPWT(FP_MAX_NRMAX, FP_MAX_NSAMAX)

     ! --- global (volume-integrated) plasma scalars, appended -------
     ! Species-summed counterparts of quantities FP otherwise only
     ! prints to unit 6: FPWRTGLB's rtotal* block
     ! (fp/fpsave.f90:305-311), the W column of the per-species line
     ! (fp/fpsave.f90:252) and the TVOLR banner (fp/fpprep.f90:237).
     ! Unlike the profile arrays above, these depend on the volume
     ! element VOLR / TVOLR, so they are the FP state's only observable
     ! response to a change of equilibrium (MODELG=3 + KNAMEQ).
     REAL(C_DOUBLE) :: TOTAL_IP          ! total plasma current  [MA]
     REAL(C_DOUBLE) :: STORED_ENERGY     ! stored energy         [MJ]
     REAL(C_DOUBLE) :: COLLISION_POWER   ! total collision power [MW]
     REAL(C_DOUBLE) :: ABSORPTION_POWER  ! total absorbed power  [MW]
     REAL(C_DOUBLE) :: ABSORPTION_WR     ! WR (ray-tracing) part [MW]
     REAL(C_DOUBLE) :: ABSORPTION_WM     ! WM (full-wave) part   [MW]
     REAL(C_DOUBLE) :: PLASMA_VOLUME     ! TVOLR                 [m^3]
  END TYPE fp_state_c

END MODULE fp_state
