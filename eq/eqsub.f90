!     $Id$
!
! Phase F-4 (HIGH tier): free-form F90 conversion of eqsub.f.
! Core helper subroutines: EQAXIS, EQMAGS, EQDERV, setup_psig,
! find_axis, find_xpoint1/2, calc_separtrix, PSIG, PSIGD, PSIGZ0.
! Preserves exact numerical semantics of the original fixed-form
! source.
!
! NOTE on EXTERNAL: Several routines pass PSIGD / EQDERV / PSIGZ0 to
!   external solvers (NEWTN, FBRENT, EQRK4). Those solvers either
!   provide explicit INTERFACE blocks for their callbacks (FBRENT) or
!   accept arbitrary EXTERNAL routines (NEWTN, EQRK4); the EXTERNAL
!   declarations are kept as-is for behavioural fidelity.
!
! NOTE: IMPLICIT NONE is NOT added at file level because the INCLUDEd
!       shim '../eq/eqcomc.inc' supplies an IMPLICIT statement
!       (IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)) and USEs the F-1
!       MODULEs (eqcom0/1/2_mod) for COMMON symbols. The standalone
!       calc_separtrix and PSIGZ0 routines retain their original
!       IMPLICIT NONE annotations.
!
!     ***** CALCULATE MAGNETIC AXIS AND EDGE *****
!
      SUBROUTINE EQAXIS(IERR)

      USE libbrent
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(OUT) :: IERR

      REAL(rkind),DIMENSION(:,:),ALLOCATABLE::  PSIRG,PSIZG,PSIRZG
      EXTERNAL PSIGD,PSIGZ0

      ALLOCATE(PSIRG(NRGM,NZGM),PSIZG(NRGM,NZGM),PSIRZG(NRGM,NZGM))
      ! Defensive zero-init (see PR #123 pattern): libeqapi.so finalize+reinit
      ! cycle can reuse heap chunks with stale values.
      PSIRG  = 0.D0
      PSIZG  = 0.D0
      PSIRZG = 0.D0
      IERR=0
!
!     ----- calculate setup for psig(R,Z) -----
!
      CALL setup_psig
!
!     ----- calculate position of magnetic axis -----
!
      CALL find_axis
!
!      WRITE(6,*) RAXIS,ZAXIS,PSIG(RAXIS,ZAXIS)
!
      IF(MDLEQF.LT.10) THEN
         RMAX=RR+RB
         RMIN=RR-RB
         ZMAX= RKAP*RB
         ZMIN=-RKAP*RB
      ELSE
         RMAX=RGMAX
         RMIN=RGMIN
         ZMAX=ZGMAX
         ZMIN=ZGMIN
      ENDIF
!
!      write(6,'(1P6E12.4)') RAXIS,RMIN,RMAX,ZAXIS,ZMIN,ZMAX
!
      IF(RAXIS.LE.RMAX.AND. &
         RAXIS.GE.RMIN.AND. &
         ZAXIS.LE.ZMAX.AND. &
         ZAXIS.GE.ZMIN) THEN
         PSI0=PSIG(RAXIS,ZAXIS)
         PSIPA=-PSI0
      ELSE
         WRITE(6,'(A)') 'XX EQAXIS: AXIS OUT OF PLASMA:'
         IERR=103
         RETURN
      ENDIF
!
!     ----- calculate outer plasma surface -----
!
      IF(PSIGZ0(RR)*PSIGZ0(RMAX).GE.0.D0) THEN
         REDGE=RMAX
      ELSE
         REDGE=FBRENT(PSIGZ0,RR,RMAX,1.D-8)
      ENDIF
!      write(6,*) 'redge=',redge

      DEALLOCATE(PSIRG,PSIZG,PSIRZG)
      RETURN
      END
!
!     ***** INTEGRATE ALONG THE MAGNETIC FIELD LINE *****
!
      SUBROUTINE EQMAGS(RINIT,ZINIT,NMAX,XA,YA,N,IERR)
!
!     ** Input **
!       RINIT : Initial starting point for tracing
!       ZINIT : Initial starting point for tracing
!       NMAX  : Size of arraies of XA, YA
!     ** Output **
!       XA    : Length from (RINIT,ZINIT) to the current position along the field line
!       YA    : Coordinate of the current position
!       N     : Number of partitions along the magnetic surface
!       IERR  : Error indicator
!
      USE eqlib
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind), INTENT(IN)  :: RINIT, ZINIT
      INTEGER,     INTENT(IN)  :: NMAX
      INTEGER,     INTENT(OUT) :: N, IERR
      REAL(rkind), INTENT(OUT) :: XA(NMAX), YA(2,NMAX)

      EXTERNAL EQDERV
      DIMENSION Y(2),DYDX(2),YOUT(2)

      NEQ=2

      FACT=SQRT(SQRT(2.D0))
      H=FACT*2.D0*PI*RKAP*(RINIT-RAXIS)/NMAX
      ISTEP=0
!
!      WRITE(6,'(I5,1P3E12.4)') 0,H,RAXIS,ZAXIS
!      WRITE(6,'(I5,1P3E12.4)') NMAX,FACT,PI,RKAP
!      pause

  100 X=0.D0
      Y(1)=RINIT
      Y(2)=ZINIT
!
!      WRITE(6,'(I5,1P3E12.4)') 1,X,Y(1),Y(2)

      N=1
      XA(N)=X
      YA(1,N)=Y(1)
      YA(2,N)=Y(2)

      IMODE=0
      DO I=2,NMAX
         CALL EQDERV(X,Y,DYDX)
         CALL EQRK4(X,Y,DYDX,YOUT,H,NEQ,EQDERV)
         IF(IMODE.EQ.0) THEN
            IF((YOUT(2)-ZINIT)*PSI0.GT.0.D0) IMODE=1
         ELSE
            IF((YOUT(2)-ZINIT)*PSI0.LT.0.D0) GOTO 1000
         ENDIF
         X=X+H
         Y(1)=YOUT(1)
         Y(2)=YOUT(2)
!
!         WRITE(6,'(I5,1P5E12.4)') N+1,X,Y(1),Y(2),DYDX(1),DYDX(2)
!
         N=N+1
         XA(N)=X
         YA(1,N)=Y(1)
         YA(2,N)=Y(2)
      ENDDO

      IF(ISTEP.LE.4) THEN
         H=FACT*H
         ISTEP=ISTEP+1
         GOTO 100
      ENDIF
      WRITE(6,*) &
     & 'XX EQMAGS: NOT ENOUGH N (near-axis under-resolved): N,NMAX=', &
     & N,NMAX
      WRITE(6,'(A,I5,A)') '   NSGMAX=',NSGMAX, &
     &     ' : set NSGMAX>=128 in eqparm & rerun.'
      IF(NPRINT.GE.1) WRITE(6,'(A,1P4E12.4)') &
     &     '   R0,RAXIS,Yend=',RINIT,RAXIS,Y(1),Y(2)
      IERR=1
      RETURN

 1000 CONTINUE
      H=0.1D0*H
      DO I=1,11
         CALL EQDERV(X,Y,DYDX)
         CALL EQRK4(X,Y,DYDX,YOUT,H,NEQ,EQDERV)
         IF((YOUT(2)-ZINIT)*PSI0.LT.0.D0) GOTO 2000
         X=X+H
         Y(1)=YOUT(1)
         Y(2)=YOUT(2)
      ENDDO
      WRITE(6,*) 'XX EQMAGS: UNEXPECTED BEHAVIOR'
      IERR=2
      RETURN

 2000 CONTINUE
      DEL=(ZINIT-Y(2))/(YOUT(2)-Y(2))
      X=X+H*DEL
      Y(1)=Y(1)+(YOUT(1)-Y(1))*DEL
      Y(2)=Y(2)+(YOUT(2)-Y(2))*DEL
      N=N+1
      XA(N)=X
      YA(1,N)=Y(1)
      YA(2,N)=Y(2)
      IERR=0

      RETURN
      END
!
!     ***** DERIVATIVES *****
!
      SUBROUTINE EQDERV(X,Y,DYDX)

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind), INTENT(IN)  :: X
      REAL(rkind), INTENT(IN)  :: Y(2)
      REAL(rkind), INTENT(OUT) :: DYDX(2)

      CALL PSIGD(Y(1),Y(2),PSIRL,PSIZL)

      PSID=SQRT(PSIRL**2+PSIZL**2)

      DYDX(1)=-PSIZL/PSID
      DYDX(2)= PSIRL/PSID
!      WRITE(6,'(1P5E12.4)') X,Y(1),Y(2),DYDX(1),DYDX(2)
      RETURN
      END
!
!     ***** SETUP PSIG *****
!
      SUBROUTINE setup_psig

      USE libspl2d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)

      REAL(rkind),DIMENSION(:,:),ALLOCATABLE:: PSIRG,PSIZG,PSIRZG
!
!     ----- calculate spline coef for psi(R,Z) -----
!
      ALLOCATE(PSIRG(NRGM,NZGM),PSIZG(NRGM,NZGM),PSIRZG(NRGM,NZGM))
      ! Defensive zero-init (see PR #123 pattern): libeqapi.so finalize+reinit
      ! cycle can reuse heap chunks with stale values.
      PSIRG  = 0.D0
      PSIZG  = 0.D0
      PSIRZG = 0.D0

      CALL SPL2D(RG,ZG,PSIRZ,PSIRG,PSIZG,PSIRZG,UPSIRZ, &
                 NRGM,NRGMAX,NZGMAX,0,0,IERR)
      IF(IERR.NE.0) THEN
         WRITE(6,*) 'XX setup_psig: SPL2D ERROR: IERR=',IERR
         STOP
      ENDIF
      DEALLOCATE(PSIRG,PSIZG,PSIRZG)
      RETURN
      END
!
!     ***** calculate position of magnetic axis *****
!
      SUBROUTINE find_axis

      USE eqlib
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      EXTERNAL PSIGD

      DELT=1.D-8
      EPS=1.D-4
      ILMAX=40
      LIST=0
      RINIT=RAXIS
      ZINIT=ZAXIS
      RSAVE=RAXIS
      ZSAVE=ZAXIS
      CALL NEWTN(PSIGD,RINIT,ZINIT,RAXIS,ZAXIS, &
                 DELT,EPS,ILMAX,LIST,IER)
      IF(IER.NE.0) THEN
         WRITE(6,'(A,I5,1P2E12.4)') &
              'XX EQAXIS: NEWTN ERROR: IER=',IER,RSAVE,ZSAVE
         WRITE(6,'(A)') 'XX EQAXIS: AXIS NOT FOUND:'
         IERR=102
         RETURN
      ENDIF
      RETURN
      END
!
!     ***** calculate position of xpoint1 *****
!
      SUBROUTINE find_xpoint1

      USE eqlib
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      EXTERNAL PSIGD

      DELT=1.D-8
      EPS=1.D-4
      ILMAX=40
      LIST=0
      RINIT=RXPNT1
      ZINIT=ZXPNT1
      RSAVE=RINIT
      ZSAVE=ZINIT
      CALL NEWTN(PSIGD,RINIT,ZINIT,RXPNT1,ZXPNT1, &
                 DELT,EPS,ILMAX,LIST,IER)
      IF(IER.NE.0) THEN
         WRITE(6,'(A,I5,1P2E12.4)') &
              'XX find_xpoint1: NEWTN ERROR: IER=',IER,RSAVE,ZSAVE
         WRITE(6,'(A)') 'XX xpint1 NOT FOUND:'
         IERR=102
         RETURN
      ENDIF
      RETURN
      END
!
!     ***** calculate position of xpoint2 *****
!
      SUBROUTINE find_xpoint2

      USE eqlib
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      EXTERNAL PSIGD

      DELT=1.D-8
      EPS=1.D-6
      ILMAX=40
      LIST=0
      RINIT=RXPNT2
      ZINIT=ZXPNT2
      RSAVE=RINIT
      ZSAVE=ZINIT
      CALL NEWTN(PSIGD,RINIT,ZINIT,RXPNT2,ZXPNT2, &
                 DELT,EPS,ILMAX,LIST,IER)
      IF(IER.NE.0) THEN
         WRITE(6,'(A,I5,1P2E12.4)') &
              'XX find_xpoint2: NEWTN ERROR: IER=',IER,RSAVE,ZSAVE
         WRITE(6,'(A)') 'XX xpint1 NOT FOUND:'
         IERR=102
         RETURN
      ENDIF
      RETURN
      END
!
!     ***** INTEGRATE ALONG THE MAGNETIC FIELD LINE *****
!
      SUBROUTINE calc_separtrix(RINIT,ZINIT,RXP,ZXP,H,NMAX, &
                                XA,RA,ZA,NTOT,IERR)
!
!     ** Input **
!       RINIT : Initial starting point for tracing
!       ZINIT : Initial starting point for tracing
!       RXP   : Location of xpoint
!       ZYP   : Location o f xpoint
!       H     : Step size
!       NMAX  : Size of arraies of XA, YA
!     ** Output **
!       XA    : Length along the field line from (RINIT,ZINIT)
!       YA    : Position of separatrix points
!       N     : Number of positions
!       IERR  : Error indicator
!
!      INCLUDE '../eq/eqcomc.inc'
!
      USE bpsd_kinds,ONLY: rkind
      USE eqlib
      IMPLICIT NONE
      REAL(rkind),INTENT(IN):: RINIT,ZINIT,RXP,ZXP,H
      INTEGER,INTENT(IN):: NMAX
      REAL(rkind),INTENT(OUT)::XA(NMAX),RA(NMAX),ZA(NMAX)
      INTEGER,INTENT(OUT):: NTOT,IERR

      INTEGER,PARAMETER:: NEQ=2
      REAL(rkind):: XA1(NMAX),YA1(2,NMAX)
      REAL(rkind):: XA2(NMAX),YA2(2,NMAX)
      REAL(rkind):: X,Y(2),DYDX(2),YOUT(2),DISTANCE
      INTEGER:: N,I,N1,N2
      EXTERNAL EQDERV

      X=0.D0
      Y(1)=RINIT
      Y(2)=ZINIT
      N=1
      XA1(N)=X
      YA1(1,N)=Y(1)
      YA1(2,N)=Y(2)
!
      DO I=2,NMAX
         CALL EQDERV(X,Y,DYDX)
         CALL EQRK4(X,Y,DYDX,YOUT,H,NEQ,EQDERV)
         X=X+H
         Y(1)=YOUT(1)
         Y(2)=YOUT(2)
         N=N+1
         XA1(N)=X
         YA1(1,N)=Y(1)
         YA1(2,N)=Y(2)
         DISTANCE=SQRT((Y(1)-RXP)**2+(Y(2)-ZXP)**2)
         IF(DISTANCE < 1.2D0*H) GOTO 1000
      ENDDO
      GOTO 9100

 1000 CONTINUE
      N1=N+1
      XA1(N1)=X+DISTANCE
      YA1(1,N1)=RXP
      YA1(2,N1)=ZXP

      X=0.D0
      Y(1)=RINIT
      Y(2)=ZINIT
      N=1
      XA2(N)=X
      YA2(1,N)=Y(1)
      YA2(2,N)=Y(2)
!
      DO I=2,NMAX
         CALL EQDERV(X,Y,DYDX)
         CALL EQRK4(X,Y,DYDX,YOUT,-H,NEQ,EQDERV)
         X=X-H
         Y(1)=YOUT(1)
         Y(2)=YOUT(2)
         N=N+1
         XA2(N)=X
         YA2(1,N)=Y(1)
         YA2(2,N)=Y(2)
         DISTANCE=SQRT((Y(1)-RXP)**2+(Y(2)-ZXP)**2)
         IF(DISTANCE < 1.2D0*H) GOTO 2000
      ENDDO
      GO TO 9200

 2000 CONTINUE
      N2=N+1
      XA2(N2)=X-DISTANCE
      YA2(1,N2)=RXP
      YA2(2,N2)=ZXP

      NTOT=N1+N2-1
      DO N=1,N2
         XA(N)=XA2(N2-N+1)
         RA(N)=YA2(1,N2-N+1)
         ZA(N)=YA2(2,N2-N+1)
      ENDDO
      DO N=N2+1,NTOT
         XA(N)=XA1(N-N2+1)
         RA(N)=YA1(1,N-N2+1)
         ZA(N)=YA1(2,N-N2+1)
      END DO
      IERR=0
      RETURN

 9100 WRITE(6,*) 'XX calc_separtrix: XP not found for positive angle'
      IERR=1
      RETURN
 9200 WRITE(6,*) 'XX calc_separtrix: XP not found for negative angle'
      IERR=1
      RETURN
      END
!
!     ***** INTERPOLATE FUNCTION OF PSI(R,Z) *****
!
      FUNCTION PSIG(R,Z)

      USE libspl2d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind), INTENT(IN) :: R, Z

      CALL SPL2DF(R,Z,PSIL,RG,ZG,UPSIRZ,NRGM,NRGMAX,NZGMAX,IERR)
      IF(IERR.NE.0) THEN
         WRITE(6,*) 'XX PSIG: SPL2DF ERROR: IERR=',IERR
         WRITE(6,'(A,1P2E12.4)') '   R,Z=',R,Z
      ENDIF
      PSIG=PSIL
      RETURN
      END
!
!     ***** INTERPOLATE SUBROUTINE DPSIDR,DPSIDZ(R,Z) *****
!
      SUBROUTINE PSIGD(R,Z,DPSIDR,DPSIDZ)

      USE libspl2d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind), INTENT(IN)  :: R, Z
      REAL(rkind), INTENT(OUT) :: DPSIDR, DPSIDZ

      CALL SPL2DD(R,Z,PSIL,DPSIDR,DPSIDZ, &
                  RG,ZG,UPSIRZ,NRGM,NRGMAX,NZGMAX,IERR)
      IF(IERR.NE.0) THEN
         WRITE(6,*) 'XX PSIGD: SPL2DD ERROR: IERR=',IERR
         WRITE(6,'(A,1P2E12.4)') '   R,Z=',R,Z
      ENDIF
      RETURN
      END
!
!     ***** INTERPOLATE FUNCTION OF PSI on ZAXIS *****
!
      FUNCTION PSIGZ0(R)
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind) R,PSIGZ0
      PSIGZ0=PSIG(R,ZAXIS)
      RETURN
      END
