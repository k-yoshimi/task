!     $Id$
!
! Phase F-3 (MED tier): free-form F90 conversion of eqintf.f.
! General interface routines used by downstream callers: GETRZ,
! EQGETB, GETPP, GETQP, eq_get_vps, eq_get_sps, GETRMN, GETRMX,
! GETAXS, GETRSU, GET_RZ, GET_RZB, GET_B, GET_BMINMAX, GET_DVDRHO.
! Preserves exact numerical semantics of the original fixed-form source.
!
! NOTE: IMPLICIT NONE is NOT added here because the INCLUDEd shim
!       '../eq/eqcomq.inc' already supplies an IMPLICIT statement
!       (IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)) and USEs the
!       F-1 MODULEs for the COMMON symbols. Routines that were already
!       IMPLICIT NONE (GET_RZB, GET_B) keep that declaration.
!
!     ***** GET PSIN AND MAGNETIC FIELD *****
!
!           PSIN=0 ON MAGNETIC AXIS
!           PSIN=1 ON PLASMA BOUNDARY
!
!           PSI=PSI0 ON MAGNETIC AXIS
!           PSI=0    ON PLASMA BOUNDARY
!
      SUBROUTINE GETRZ(RP,ZP,PHIP,BR,BZ,BT,RHON)
!
!     *** Input ***
!       RP, ZP : (R,Z) at which one would like to know magnetic fields
!       PHIP   : null
!     *** Output ***
!       BR     : major radius component of the magnetic field
!       BZ     : vertical component of the magnetic field
!       BT     : toroidal magnetic field
!       RHON   : normalized radial coordinate corresponding to (R,Z)
!
      USE libspl2d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL*8, INTENT(IN)  :: RP, ZP, PHIP
      REAL*8, INTENT(OUT) :: BR, BZ, BT, RHON

!     --- out of range: set rhon>1.0 ---
      IF(RP.LE.RG(1).OR. &
         RP.GT.RG(NRGMAX).OR. &
         ZP.LE.ZG(1).OR. &
         ZP.GT.ZG(NZGMAX)) THEN
         BR=0.D0
         BZ=0.D0
         BT=B0*R0/RP
         RHON=2.D0*SQRT(((RP-RG(1))/(RG(NRGMAX)-RG(1))-0.5D0)**2 &
                       +((ZP-ZG(1))/(ZG(NZGMAX)-ZG(1))-0.5D0)**2)
         RETURN
      ENDIF

      CALL SPL2DD(RP,ZP,PSI,DPSIR,DPSIZ, &
                  RG,ZG,UPSIRZ,NRGM,NRGMAX,NZGMAX,IERR)

      PSIN=1.D0-PSI/PSI0
      IF(PSIN.LE.0.D0) THEN
         PSIN=0.D0
         BT=FNTTS(0.D0)/(2.D0*PI*RR)
         BR=0.D0
         BZ=0.D0
      ELSE
         BT=FNTTS(SQRT(PSIN))/(2.D0*PI*RP)
         BR=-DPSIZ/(2.D0*PI*RP)
         BZ= DPSIR/(2.D0*PI*RP)
!         write(6,'(A,1P3E12.4)') 'PSI,DPSIZ,DPSIR      =',PSI,DPSIR,DPSIZ
      ENDIF
      RHON=FNRHON(PSIN)

      RETURN
      END SUBROUTINE GETRZ
!
!     ***** GET PARAMETERS *****
!
      SUBROUTINE EQGETB(BB1,RR1,RIP1,RA1,RKAP1,RDEL1,RB1)

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL*8, INTENT(OUT) :: BB1, RR1, RIP1, RA1, RKAP1, RDEL1, RB1

      BB1  =BB
      RR1  =RR
      RIP1 =RIP
      RA1  =RA
      RKAP1=RKAP
      RDEL1=RDLT
      RB1  =RB
      RETURN
      END SUBROUTINE EQGETB
!
!     ***** GET PRESSURE AS A FUNCTION OF PSIN *****
!
      SUBROUTINE GETPP(RHON,PP)

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL*8, INTENT(IN)  :: RHON
      REAL*8, INTENT(OUT) :: PP

      PP=FNPPS(RHON)
      RETURN
      END SUBROUTINE GETPP
!
!     ***** GET SAFETY FACTOR AS A FUNCTION OF PSIN *****
!
      SUBROUTINE GETQP(RHON,QP)

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL*8, INTENT(IN)  :: RHON
      REAL*8, INTENT(OUT) :: QP

      QP=FNQPS(RHON)
      RETURN
      END SUBROUTINE GETQP
!
!     ***** GET plasma volume *****
!
      SUBROUTINE eq_get_vps(RHON,VPSL)

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL*8, INTENT(IN)  :: RHON
      REAL*8, INTENT(OUT) :: VPSL

      VPSL=FNVPS(RHON)
      RETURN
      END SUBROUTINE eq_get_vps
!
!     ***** GET plasma cross section area *****
!
      SUBROUTINE eq_get_sps(RHON,SPSL)

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL*8, INTENT(IN)  :: RHON
      REAL*8, INTENT(OUT) :: SPSL

      SPSL=FNSPS(RHON)
      RETURN
      END SUBROUTINE eq_get_sps
!
!     ***** GET MINIMUM R AS A FUNCTION OF PSIN *****
!
      SUBROUTINE GETRMN(RHON,RRMINL)

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL*8, INTENT(IN)  :: RHON
      REAL*8, INTENT(OUT) :: RRMINL

      RRMINL=FNRRMN(RHON)
      RETURN
      END SUBROUTINE GETRMN
!
!     ***** GET MAXIMUM R AS A FUNCTION OF PSIN *****
!
      SUBROUTINE GETRMX(RHON,RRMAXL)

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL*8, INTENT(IN)  :: RHON
      REAL*8, INTENT(OUT) :: RRMAXL

      RRMAXL=FNRRMX(RHON)
      RETURN
      END SUBROUTINE GETRMX
!
!     ***** GET MAGNETIC AXIS *****
!
      SUBROUTINE GETAXS(RAXIS1,ZAXIS1)

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL*8, INTENT(OUT) :: RAXIS1, ZAXIS1

      RAXIS1=RAXIS
      ZAXIS1=ZAXIS
      RETURN
      END SUBROUTINE GETAXS
!
!     ***** GET PLASMA BOUNDARY POSITION *****
!
      SUBROUTINE GETRSU(RSU1,ZSU1,NSUMAX1)

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind),ALLOCATABLE,INTENT(OUT) :: RSU1(:),ZSU1(:)
      INTEGER,                INTENT(OUT) :: NSUMAX1

      IF(ALLOCATED(RSU1)) DEALLOCATE(RSU1)
      IF(ALLOCATED(ZSU1)) DEALLOCATE(ZSU1)
      NSUMAX1=NSUMAX
      ALLOCATE(RSU1(NSUMAX1))
      ALLOCATE(ZSU1(NSUMAX1))
      ! Defensive zero-init (see PR #123 pattern): libeqapi.so finalize+reinit
      ! cycle can reuse heap chunks with stale values.
      RSU1 = 0.D0
      ZSU1 = 0.D0
      DO NSU=1,NSUMAX1
         RSU1(NSU)=RSU(NSU)
         ZSU1(NSU)=ZSU(NSU)
      ENDDO
      RETURN
      END SUBROUTINE GETRSU
!
!     ***** GET R and Z for rhot and th *****
!
      SUBROUTINE GET_RZ(rhon_,rchip_,R_,Z_)

      USE libspl2d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind), INTENT(IN)  :: rhon_, rchip_
      REAL(rkind), INTENT(OUT) :: R_, Z_
      REAL(rkind):: chip_

      CALL SPL2DF(rchip_,rhon_,R_, &
                        CHIP,RHOT,URPS,NTHMP,NTHMAX+1,NRMAX,IERR)
      CALL SPL2DF(rchip_,rhon_,Z_, &
                        CHIP,RHOT,UZPS,NTHMP,NTHMAX+1,NRMAX,IERR)
      RETURN
      END SUBROUTINE GET_RZ
!
!     ***** GET magnetic field for rhot and th *****
!
      SUBROUTINE GET_RZB(rhon_,chip_,R_,Z_,BR_,BZ_,BT_,BB_)

      USE bpsd,ONLY: rkind
      IMPLICIT NONE
      REAL(rkind),INTENT(IN):: rhon_,chip_
      REAL(rkind),INTENT(OUT):: R_,Z_,BR_,BZ_,BT_,BB_
      REAL(rkind):: rhon_dummy

      CALL GET_RZ(rhon_,chip_,R_,Z_)
      CALL GETRZ(R_,Z_,0.D0,BR_,BZ_,BT_,rhon_dummy)
      BB_=SQRT(BR_**2+BZ_**2+BT_**2)
      RETURN
      END SUBROUTINE GET_RZB
!
!     ***** GET total magnetic field for rhot and th *****
!
      SUBROUTINE GET_B(rhon_,chip_,BB_)

      USE bpsd,ONLY: rkind
      IMPLICIT NONE
      REAL(rkind),INTENT(IN):: rhon_,chip_
      REAL(rkind),INTENT(OUT):: BB_
      REAL(rkind):: R_,Z_,BR_,BZ_,BT_,RHON

      CALL GET_RZ(rhon_,chip_,R_,Z_)
      CALL GETRZ(R_,Z_,0.D0,BR_,BZ_,BT_,RHON)
      BB_=SQRT(BR_**2+BZ_**2+BT_**2)
      RETURN
      END SUBROUTINE GET_B
!
!     ***** GET BBMIN and BBMAX for rhot *****
!
      SUBROUTINE GET_BMINMAX(rhon_,BBMIN_,BBMAX_)

      USE bpsd,ONLY: rkind
      USE libspl1d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind),INTENT(IN):: rhon_
      REAL(rkind),INTENT(OUT):: BBMIN_,BBMAX_

      CALL SPL1DF(rhon_,BBMIN_,RHOT,UBBMIN,NRMAX,IERR)
      CALL SPL1DF(rhon_,BBMAX_,RHOT,UBBMAX,NRMAX,IERR)
      RETURN
      END SUBROUTINE GET_BMINMAX
!
!     ***** GET DVDRHO for rhot *****
!
      SUBROUTINE GET_DVDRHO(rhon_,DVDRHO_)

      USE bpsd,ONLY: rkind
      USE libspl1d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind),INTENT(IN):: rhon_
      REAL(rkind),INTENT(OUT):: DVDRHO_

      CALL SPL1DF(FNPSIP(rhon_),DVDRHO_,PSIP,UDVDRHO,NRMAX,IERR)

      RETURN
      END SUBROUTINE GET_DVDRHO
