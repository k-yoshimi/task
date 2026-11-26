!     $Id$
!
! Phase F-4 (HIGH tier): free-form F90 conversion of eqcalc.f.
! Main equilibrium driver: EQCALC, EQMESH, EQPSIN/R, EQDEFB, EQFBND,
! EQLOOP, EQBAND, EQRHSV, EQSOLV, EQTORZ, EQSETF, PSIF, HJTF, EQCALP.
! Preserves exact numerical semantics of the original fixed-form
! source.
!
! NOTE on EXTERNAL: EQDEFB / EQTORZ pass EQFBND to FBRENT, which
!   provides an explicit INTERFACE for its callback; the EXTERNAL
!   declaration is sufficient and is kept as-is (avoids restructuring
!   how EQFBND shares ZBRF/RDLT/RKAP through the COMMON shim).
!
! NOTE: IMPLICIT NONE is NOT added at file level because the INCLUDEd
!       shim '../eq/eqcomc.inc' supplies an IMPLICIT statement
!       (IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)) and USEs the F-1
!       MODULEs (eqcom0/1/2_mod) for COMMON symbols.
!
!   **************************************
!   **       CALCULATE EQUILIBRIUM      **
!   **************************************
!
      SUBROUTINE EQCALC(IERR)

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(OUT) :: IERR

      IERR=0
      CALL EQMESH
      IF(Q0*QA.GT.0.D0) THEN
         CALL EQPSIN
      ELSE
         CALL EQPSIR
      ENDIF
      CALL EQDEFB
      CALL EQLOOP(IERR)
         IF(IERR.NE.0.AND.IERR.NE.100) RETURN
      CALL EQTORZ
      CALL EQCALP
      RETURN
      END
!
!   ************************************************
!   **       Mesh Definition (sigma, theta)       **
!   ************************************************
!
      SUBROUTINE EQMESH

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)

      DSG=1.D0/NSGMAX
      DTG=2.D0*PI/NTGMAX

      DO NSG=1,NSGMAX
         SIGM(NSG)=DSG*(NSG-0.5D0)
      ENDDO
      DO NSG=1,NSGMAX+1
         SIGG(NSG)=DSG*(NSG-1.D0)
      ENDDO
      DO NTG=1,NTGMAX
         THGM(NTG)=DTG*(NTG-0.5D0)
      ENDDO
      DO NTG=1,NTGMAX+1
         THGG(NTG)=DTG*(NTG-1.D0)
      ENDDO
      RETURN
      END
!
!   ************************************************
!   **           Initial Psi for tokamak          **
!   ************************************************
!
      SUBROUTINE EQPSIN

      USE libspl1d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      DIMENSION DERIV(NRVM)

      RAXIS=RR
      ZAXIS=0.0D0
!
!     --- assuming elliptic crosssection, flat current profile ---
!
      IF(MOD(MDLEQF,5).EQ.4) THEN
         PSITA=PI*RKAP*RA**2*BB
         PSIPA=PSITA*2/QA
         PSI0=-PSIPA
      ELSE
         PSI0=-0.5D0*RMU0*RIP*1.D6*RR
         PSIPA=-PSI0
         PSITA=PI*RKAP*RA**2*BB
      ENDIF

      DRHO=1.D0/(NRVMAX-1)
      DO NRV=1,NRVMAX
         RHOL=(NRV-1)*DRHO
         PSIPNV(NRV)=RHOL*RHOL
         PSIPV(NRV)=PSIPA*RHOL*RHOL
         PSITV(NRV)=PSITA*RHOL*RHOL
         QPV(NRV)=PSITA/PSIPA
         TTV(NRV)=2.D0*PI*RR*BB
      ENDDO

      DO NSG=1,NSGMAX
      DO NTG=1,NTGMAX
          PSI(NTG,NSG)=PSI0*(1.D0-SIGM(NSG)*SIGM(NSG))
          DELPSI(NTG,NSG)=0.D0
          HJT(NTG,NSG)=0.D0
      ENDDO
      ENDDO

      CALL SPL1D(PSIPNV,PSITV,DERIV,UPSITV,NRVMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for PSITV: IERR=',IERR
      CALL SPL1D(PSIPNV,QPV,DERIV,UQPV,NRVMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for QPV: IERR=',IERR
      CALL SPL1D(PSIPNV,TTV,DERIV,UTTV,NRVMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for TTV: IERR=',IERR
!
!      WRITE(6,'(A,I5,1P4E12.4)')
!     &     ('NRV:',NRV,PSIPNV(NRV),PSITV(NRV),QPV(NRV),TTV(NRV),
!     &      NRV=1,NRVMAX)
!
      RETURN
      END
!
!   ************************************************
!   **            Initial Psi for RFP             **
!   ************************************************
!
      SUBROUTINE EQPSIR

      USE libspl1d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      DIMENSION DERIV(NRVM)

      RAXIS=RR
      ZAXIS=0.0D0
!
!     --- assuming elliptic crosssection, flat current profile ---
!
      IF(MOD(MDLEQF,5).EQ.4) THEN
         PSITA=PI*RKAP*RA**2*BB
         PSIPA=PSITA*2/QA
         PSI0=-PSIPA
      ELSE
         PSI0=-0.5D0*RMU0*RIP*1.D6*RR
         PSIPA=-PSI0
         PSITA=PI*RKAP*RA**2*BB
      ENDIF

      DRHO=1.D0/(NRVMAX-1)
      DO NRV=1,NRVMAX
         RHOL=(NRV-1)*DRHO
         PSIPNV(NRV)=RHOL*RHOL
         PSIPV(NRV)=PSIPA*RHOL*RHOL
         PSITV(NRV)=PSITA*RHOL*RHOL
         QPV(NRV)=PSITA/PSIPA
         TTV(NRV)=2.D0*PI*RR*BB
      ENDDO

      DO NSG=1,NSGMAX
      DO NTG=1,NTGMAX
          PSI(NTG,NSG)=PSI0*(1-SIGM(NSG)*SIGM(NSG))
          DELPSI(NTG,NSG)=0.D0
          HJT(NTG,NSG)=0.D0
      ENDDO
      ENDDO

      CALL SPL1D(PSIPNV,PSITV,DERIV,UPSITV,NRVMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for PSITV: IERR=',IERR
      CALL SPL1D(PSIPNV,QPV,DERIV,UQPV,NRVMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for QPV: IERR=',IERR
      CALL SPL1D(PSIPNV,TTV,DERIV,UTTV,NRVMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for TTV: IERR=',IERR
!
!      WRITE(6,'(A,I5,1P4E12.4)')
!     &     ('NRV:',NRV,PSIPNV(NRV),PSITV(NRV),QPV(NRV),TTV(NRV),
!     &      NRV=1,NRVMAX)
!
      RETURN
      END
!
!   ************************************************
!   **          Boundary Definition               **
!   ************************************************
!
      SUBROUTINE EQDEFB

      USE libbrent
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      EXTERNAL EQFBND

      DIMENSION DRHOM(NTGM),DRHOG(NTGMP)
!
!     ------ Define criteria for the Brent method ------
!
      EPSZ=1.D-8
!
!     ------ Define boundary radius RHOM/G ------
!
      DO NTG=1,NTGMAX
         ZBRF=TAN(THGM(NTG))
         THDASH=FBRENT(EQFBND,THGM(NTG)-1.0D0,THGM(NTG)+1.0D0,EPSZ)
         RHOM(NTG)=RA*SQRT(COS(THDASH+RDLT*SIN(THDASH))**2 &
                          +RKAP**2*SIN(THDASH)**2)

         ZBRF=TAN(THGG(NTG))
         THDASH=FBRENT(EQFBND,THGG(NTG)-1.0D0,THGG(NTG)+1.0D0,EPSZ)
         RHOG(NTG)=RA*SQRT(COS(THDASH+RDLT*SIN(THDASH))**2 &
                          +RKAP**2*SIN(THDASH)**2)
      ENDDO
      RHOG(NTGMAX+1)=RHOG(1)
!
!     ------ Define Delta theta on the boundary ------
!
      DRHOM(1)=0.5D0*(RHOM(2)-RHOM(NTGMAX))/DTG
      DO NTG=2,NTGMAX-1
         DRHOM(NTG)=0.5D0*(RHOM(NTG+1)-RHOM(NTG-1))/DTG
      ENDDO
      DRHOM(NTGMAX)=0.5D0*(RHOM(1)-RHOM(NTGMAX-1))/DTG

      DRHOG(1)=0.5D0*(RHOG(2)-RHOG(NTGMAX))/DTG
      DO NTG=2,NTGMAX-1
         DRHOG(NTG)=0.5D0*(RHOG(NTG+1)-RHOG(NTG-1))/DTG
      ENDDO
      DRHOG(NTGMAX)=0.5D0*(RHOG(1)-RHOG(NTGMAX-1))/DTG
      DRHOG(NTGMAX+1)=DRHOG(1)
!
!     ------ Calculate major radius on grid points ------
!
      DO NSG=1,NSGMAX
      DO NTG=1,NTGMAX+1
         RMG(NSG,NTG)=RR+SIGM(NSG)*RHOG(NTG)*COS(THGG(NTG))
      ENDDO
      ENDDO

      DO NSG=1,NSGMAX+1
      DO NTG=1,NTGMAX
         RGM(NSG,NTG)=RR+SIGG(NSG)*RHOM(NTG)*COS(THGM(NTG))
      ENDDO
      ENDDO

      DO NSG=1,NSGMAX
      DO NTG=1,NTGMAX
         RMM(NTG,NSG)=RR+SIGM(NSG)*RHOM(NTG)*COS(THGM(NTG))
         ZMM(NTG,NSG)=   SIGM(NSG)*RHOM(NTG)*SIN(THGM(NTG))
      ENDDO
      ENDDO
!
!     ------ Calculate factors for coefficient matrix ------
!
      DO NSG=1,NSGMAX+1
      DO NTG=1,NTGMAX
         AA(NSG,NTG)=SIGG(NSG)/RGM(NSG,NTG) &
                    +(DRHOM(NTG)*DRHOM(NTG)*SIGG(NSG)) &
                    /(RGM(NSG,NTG)*RHOM(NTG)*RHOM(NTG))
         AB(NSG,NTG)=-DRHOM(NTG)/(RGM(NSG,NTG)*RHOM(NTG))
      ENDDO
      ENDDO
      DO NSG=1,NSGMAX
      DO NTG=1,NTGMAX+1
         AC(NSG,NTG)=-DRHOG(NTG)/(RMG(NSG,NTG)*RHOG(NTG))
         AD(NSG,NTG)=1/(RMG(NSG,NTG)*SIGM(NSG))
      ENDDO
      ENDDO
!
!      DO NSG=1,2
!         DO NTG=1,NTGMAX
!            WRITE(6,'(2I5,1P4E12.4)') NSG,NTG,AA(NSG,NTG),AB(NSG,NTG),
!     &                                       AC(NSG,NTG),AD(NSG,NTG)
!         ENDDO
!      ENDDO
!      PAUSE

      RETURN
      END
!
!   ************************************************
!   **         Boundary shape function            **
!   ************************************************
!
      FUNCTION EQFBND(X)

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind):: EQFBND
      REAL(rkind), INTENT(IN) :: X

      EQFBND=ZBRF*COS(X+RDLT*SIN(X))-RKAP*SIN(X)
      RETURN
      END
!
!   ************************************************
!   **               Iteration Loop               **
!   ************************************************
!
      SUBROUTINE EQLOOP(IERR)

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(OUT) :: IERR

      IERR=0
!
!     ----- Adaptive under-relaxation of the GS Picard iteration -----
!     A full Picard step (PSI <- solution) oscillates for stiff (high-q,
!     low-current) equilibria. Damp the update when the residual grows and
!     relax back towards a full step while it decreases.
      OMEGA=1.D0
      SULMP=1.D30
!
      DO NLOOP=1,NLPMAX
         CALL EQBAND
         CALL EQRHSV(IERR)
         IF(IERR.NE.0) RETURN
         CALL EQSOLV

         SUM0=0.D0
         SUM1=0.D0
         DO NSG=1,NSGMAX
            DO NTG=1,NTGMAX
               SUM0=SUM0+PSI(NTG,NSG)**2
               SUM1=SUM1+DELPSI(NTG,NSG)**2
            ENDDO
         ENDDO
         SUML=SQRT(SUM1/SUM0)
!
!        --- adapt the relaxation factor and damp the just-applied step ---
         IF(SUML.GT.SULMP) THEN
            OMEGA=MAX(0.1D0,0.5D0*OMEGA)
         ELSE
            OMEGA=MIN(1.D0,1.2D0*OMEGA)
         ENDIF
         SULMP=SUML
         IF(OMEGA.LT.1.D0) THEN
            DO NSG=1,NSGMAX
               DO NTG=1,NTGMAX
                  PSI(NTG,NSG)=PSI(NTG,NSG)-(1.D0-OMEGA)*DELPSI(NTG,NSG)
               ENDDO
            ENDDO
         ENDIF
!
         IF(SUML.LT.EPSEQ) THEN
            IF(NPRINT.GE.1) THEN
               WRITE(6,'(A,1P4E14.6,I5)') &
                 'SUML,R/ZAXIS,PSI0=',SUML,RAXIS,ZAXIS,PSI0,NLOOP
            ENDIF
            RETURN
         ELSE
            IF((NPRINT.EQ.1.AND.NLOOP.EQ.1).OR. &
                NPRINT.GE.2) THEN
               WRITE(6,'(A,1P4E14.6)') &
                 'SUML,R/ZAXIS,PSI0=',SUML,RAXIS,ZAXIS,PSI0
            ENDIF
         ENDIF
      ENDDO

      IF(NPRINT.GE.1) THEN
         WRITE(6,'(A,1P4E14.6,I5)') &
                 'SUML,R/ZAXIS,PSI0=',SUML,RAXIS,ZAXIS,PSI0,NLOOP
      ENDIF
      WRITE(6,*) 'XX EQLOOP: NLOOP exceeds NLPMAX'
      IERR=100

      RETURN
      END
!
!   ***********************************************
!   **            Matrix calculation             **
!   ***********************************************
!
      SUBROUTINE EQBAND

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
!
!     ------ Define matrix length MMAX and matrix half width NBND ------
!
      MMAX=NSGMAX*NTGMAX
      NBND=2*NTGMAX
!
!     ------ Initialize band matrix coefficients Q ------
!
      DO N=1,MMAX
      DO M=1,2*NBND-1
          Q(M,N)=0.D0
      ENDDO
      ENDDO
!
!     ------ Calculate band matrix coefficients Q ------
!
      DO NSG=1,NSGMAX
      DO NTG=1,NTGMAX
         I=(NSG-1)*NTGMAX+NTG
         IF(NTG.EQ.1)THEN
            Q(NBND         -1,I)= (AB(NSG,NTG)+AC(NSG,NTG)) &
                                 /(4.D0*DSG*DTG)
            Q(NBND  +NTGMAX-1,I)= (AB(NSG,NTG)-AB(NSG+1,NTG)) &
                                 /(4.D0*DSG*DTG) &
                                 +AD(NSG,NTG)/(DTG*DTG)
            Q(NBND+2*NTGMAX-1,I)=-(AB(NSG+1,NTG)+AC(NSG,NTG)) &
                                 /(4.D0*DSG*DTG)
         ELSE
            Q(NBND  -NTGMAX-1,I)= (AB(NSG,NTG)+AC(NSG,NTG)) &
                                 /(4.D0*DSG*DTG)
            Q(NBND         -1,I)=(AB(NSG,NTG)-AB(NSG+1,NTG)) &
                                 /(4.D0*DSG*DTG) &
                                 +AD(NSG,NTG)/(DTG*DTG)
            Q(NBND  +NTGMAX-1,I)=-(AB(NSG+1,NTG)+AC(NSG,NTG)) &
                                 /(4.D0*DSG*DTG)
         ENDIF
         Q(NBND-NTGMAX,I)=  AA(NSG,NTG)/(DSG*DSG) &
                         -(AC(NSG,NTG+1)-AC(NSG,NTG))/(4.D0*DSG*DTG)
         Q(NBND       ,I)=-(AA(NSG+1,NTG)+AA(NSG,NTG))/(DSG*DSG) &
                         -(AD(NSG,NTG+1)+AD(NSG,NTG))/(DTG*DTG)
         Q(NBND+NTGMAX,I)=  AA(NSG+1,NTG)/(DSG*DSG) &
                         +(AC(NSG,NTG+1)-AC(NSG,NTG))/(4.D0*DSG*DTG)
!
!     ------ Set periodic condition ------
!
         IF(NTG.EQ.NTGMAX) THEN
            Q(NBND-2*NTGMAX+1,I)=-(AB(NSG,NTG)+AC(NSG,NTG+1)) &
                                  /(4.D0*DSG*DTG)
            Q(NBND-  NTGMAX+1,I)= (AB(NSG+1,NTG)-AB(NSG,NTG)) &
                                  /(4.D0*DSG*DTG) &
                                +  AD(NSG,NTG+1)/(DTG*DTG)
            Q(NBND         +1,I)= (AB(NSG+1,NTG)+AC(NSG,NTG+1)) &
                                  /(4.D0*DSG*DTG)
         ELSE
            Q(NBND-NTGMAX+1,I)=-(AB(NSG,NTG)+AC(NSG,NTG+1)) &
                                /(4.D0*DSG*DTG)
            Q(NBND       +1,I)= (AB(NSG+1,NTG)-AB(NSG,NTG)) &
                                /(4.D0*DSG*DTG) &
                              +  AD(NSG,NTG+1)/(DTG*DTG)
            Q(NBND+NTGMAX+1,I)= (AB(NSG+1,NTG)+AC(NSG,NTG+1)) &
                                /(4.D0*DSG*DTG)
         ENDIF
      ENDDO
      ENDDO
!
!     ------ Set radial boundary condition ------
!
      DO I=1,NTGMAX
      DO J=1,NTGMAX/2
         Q(NBND+J-I,I)=Q(NBND+J-I,I) &
                      +Q(NBND+J-I-NTGMAX/2,I)
         Q(NBND+J-I-NTGMAX/2,I)=0.D0
         Q(NBND+J-I+NTGMAX/2,I)=Q(NBND+J-I+NTGMAX/2,I) &
                               +Q(NBND+J-I-NTGMAX,I)
         Q(NBND+J-I-NTGMAX,I)=0.D0
      ENDDO
      ENDDO
      DO I=1,NTGMAX
      DO J=1,NTGMAX
         Q(NBND+J-I,I+(NSGMAX-1)*NTGMAX) &
                         =Q(NBND+J-I,I+(NSGMAX-1)*NTGMAX) &
                         -Q(NBND+J-I+NTGMAX,I+(NSGMAX-1)*NTGMAX)
         Q(NBND+J-I+NTGMAX,I+(NSGMAX-1)*NTGMAX)=0.D0
      ENDDO
      ENDDO
      RETURN
      END
!
!   ************************************************
!   **                RHS vector                  **
!   ************************************************
!
      SUBROUTINE EQRHSV(IERR)

      USE libspl1d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(OUT) :: IERR
      DIMENSION DERIV(NRVM)

      IERR=0
!
!     ----- calculate PSIRZ(R,Z) from PSI(sigma, theta) -----
!
      CALL EQTORZ
!
!     ----- calculate flux average from PSIRZ(R,Z) -----
!
      CALL EQCALV(IERR)
      IF(IERR.NE.0) RETURN
!
!     ----- calculate right hand side vector -----
!
      IMDLEQF=MOD(MDLEQF,5)
!
!     ----- Given pressure and toroidal current profiles -----
!
      IF(IMDLEQF.EQ.0) THEN
         RRC=RAXIS
         FJP=0.D0
         FJT=0.D0
         DO NSG=1,NSGMAX
         DO NTG=1,NTGMAX
            PSIPNL=1.D0-PSI(NTG,NSG)/PSI0
            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
            CALL EQJPSI(PSIPNL,HJPSID,HJPSI)
            CALL EQTPSI(PSIPNL,TPSI,DTPSI)
            CALL EQOPSI(PSIPNL,OMGPSI,DOMGPSI)
            PP(NTG,NSG)=PPSI
            HJP(NTG,NSG)=-2.D0*PI*RMM(NTG,NSG)*DPPSI
            HJP1(NTG,NSG)=-2.D0*PI*RMM(NTG,NSG)*DPPSI
            HJT1(NTG,NSG)=-HJPSI
            HJP2A=EXP(RMM(NTG,NSG)**2*OMGPSI**2*AMP/(2.D0*TPSI))
            HJP2B=EXP(RRC**2         *OMGPSI**2*AMP/(2.D0*TPSI))
            HJP2C=HJP2A-(RRC**2/RMM(NTG,NSG)**2)*HJP2B
            HJP2D=HJP2A-(RRC**4/RMM(NTG,NSG)**4)*HJP2B
            HJP2E=-0.5D0*2.D0*PI*PPSI*RMM(NTG,NSG)**3
            HJP2F=AMP*(2.D0*OMGPSI*DOMGPSI/TPSI &
                 -DTPSI*OMGPSI**2/TPSI**2)
            HJP2(NTG,NSG)=HJP2C*HJP1(NTG,NSG)+HJP2D*HJP2E*HJP2F
            HJT2(NTG,NSG)=(RRC/RMM(NTG,NSG))*HJT1(NTG,NSG)
            DVOL=SIGM(NSG)*RHOM(NTG)*RHOM(NTG)*DSG*DTG

            FJP=FJP+HJP2(NTG,NSG)*DVOL
            FJT=FJT+HJT2(NTG,NSG)*DVOL
         ENDDO
         ENDDO
         TJ=(RIP*1.D6-FJP)/FJT

         DO NSG=1,NSGMAX
         DO NTG=1,NTGMAX
            HJT(NTG,NSG)=HJP2(NTG,NSG)+TJ*HJT2(NTG,NSG)
            PSIPNL=1.D0-PSI(NTG,NSG)/PSI0
            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
            CALL EQJPSI(PSIPNL,HJPSID,HJPSI)
            CALL EQTPSI(PSIPNL,TPSI,DTPSI)
            CALL EQOPSI(PSIPNL,OMGPSI,DOMGPSI)
            TT(NTG,NSG)=SQRT((2.D0*PI*BB*RR)**2 &
                       +2.D0*RMU0*RRC &
                       *(2.D0*PI*TJ*HJPSID-RRC*PPSI &
                       *EXP(RRC**2*OMGPSI**2*AMP/(2.D0*TPSI))))
            RHO(NTG,NSG)=(PPSI*AMP/TPSI) &
                        *EXP(RMM(NTG,NSG)**2*OMGPSI**2*AMP/(2.D0*TPSI))
         ENDDO
         ENDDO
         RIPX=RIP
!
!         DO NSG=1,3
!            DO NTG=1,NTGMAX
!               WRITE(6,'(2I5,1P3E12.4)')
!     &              NSG,NTG,RMM(NTG,NSG),ZMM(NTG,NSG),PSI(NTG,NSG)
!               WRITE(6,'(2I5,1P3E12.4)')
!     &              NSG,NTG,HJP1(NTG,NSG),HJT1(NTG,NSG),PP(NTG,NSG)
!               WRITE(6,'(2I5,1P3E12.4)')
!     &              NSG,NTG,HJP2(NTG,NSG),HJT2(NTG,NSG),TT(NTG,NSG)
!            ENDDO
!         ENDDO
!         PAUSE
!
!     ----- Given pressure and poloidal current profiles -----
!
      ELSEIF(IMDLEQF.EQ.1) THEN
         FJP=0.D0
         FJT1=0.D0
         FJT2=0.D0
         DO NSG=1,NSGMAX
         DO NTG=1,NTGMAX
            PSIPNL=1.D0-PSI(NTG,NSG)/PSI0
            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
            CALL EQFPSI(PSIPNL,FPSI,DFPSI)
            PP(NTG,NSG)=PPSI
            HJP(NTG,NSG)=-2.D0*PI*RMM(NTG,NSG)*DPPSI
            HJP1(NTG,NSG)=-2.D0*PI*RMM(NTG,NSG)*DPPSI
            HJT1(NTG,NSG)=-2.D0*PI*BB*RR       *DFPSI &
                                      /(2.D0*PI*RMU0*RMM(NTG,NSG))
            HJT2(NTG,NSG)=-(FPSI-2.D0*PI*BB*RR)*DFPSI &
                                      /(2.D0*PI*RMU0*RMM(NTG,NSG))
            HJP2(NTG,NSG)=HJP1(NTG,NSG)
            DVOL=SIGM(NSG)*RHOM(NTG)*RHOM(NTG)*DSG*DTG
            FJP =FJP +HJP2(NTG,NSG)*DVOL
            FJT1=FJT1+HJT1(NTG,NSG)*DVOL
            FJT2=FJT2+HJT2(NTG,NSG)*DVOL
         ENDDO
         ENDDO
         IF(FJT1.GT.0.D0) THEN
            TJ=(-FJT1+SQRT(FJT1**2+4.D0*FJT2*(RIP*1.D6-FJP))) &
               /(2.D0*FJT2)
         ELSE
            TJ=(-FJT1-SQRT(FJT1**2+4.D0*FJT2*(RIP*1.D6-FJP))) &
               /(2.D0*FJT2)
         ENDIF

         DO NSG=1,NSGMAX
         DO NTG=1,NTGMAX
            HJT(NTG,NSG)=HJP2(NTG,NSG)+TJ*HJT1(NTG,NSG) &
                                      +TJ*TJ*HJT2(NTG,NSG)
            PSIPNL=1.D0-PSI(NTG,NSG)/PSI0
            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
            CALL EQFPSI(PSIPNL,FPSI,DFPSI)
            CALL EQTPSI(PSIPNL,TPSI,DTPSI)
            TT(NTG,NSG)=2.D0*PI*BB*RR+TJ*(FPSI-2.D0*PI*BB*RR)
            RHO(NTG,NSG)=0.D0
         ENDDO
         ENDDO
         RIPX=RIP
!
!     ----- Given pressure and parallel current profiles -----
!
      ELSEIF(IMDLEQF.EQ.2) THEN
         CALL EQIPJP
!         DO NR=1,11
!            PSIPNL=0.002D0*(NR-1)
!            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
!            WRITE(6,'(A,I5,1P3E12.4)') 'NR,PSIPNL,PPSI,DPPSI=',
!     &           NR,PSIPNL,PPSI,DPPSI
!         ENDDO
         FJP=0.D0
         FJT1=0.D0
         FJT2=0.D0
         DO NSG=1,NSGMAX
         DO NTG=1,NTGMAX
            PSIPNL=1.D0-PSI(NTG,NSG)/PSI0
            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
            CALL EQFIPV(PSIPNL,FPSI,DFPSI)
            PP(NTG,NSG)=PPSI
            HJP(NTG,NSG)=-2.D0*PI*RMM(NTG,NSG)*DPPSI
            HJP1(NTG,NSG)=-2.D0*PI*RMM(NTG,NSG)*DPPSI
            HJT1(NTG,NSG)=-2.D0*PI*BB*RR       *DFPSI &
                                    /(2.D0*PI*RMU0*RMM(NTG,NSG))
            HJT2(NTG,NSG)=-(FPSI-2.D0*PI*BB*RR)*DFPSI &
                                    /(2.D0*PI*RMU0*RMM(NTG,NSG))
            HJP2(NTG,NSG)=HJP1(NTG,NSG)
            DVOL=SIGM(NSG)*RHOM(NTG)*RHOM(NTG)*DSG*DTG
            FJP=FJP+HJP2(NTG,NSG)*DVOL
            FJT1=FJT1+HJT1(NTG,NSG)*DVOL
            FJT2=FJT2+HJT2(NTG,NSG)*DVOL
         ENDDO
         ENDDO
         IF(FJT1.GT.0.D0) THEN
            TJ=(-FJT1+SQRT(FJT1**2+4.D0*FJT2*(RIP*1.D6-FJP))) &
               /(2.D0*FJT2)
         ELSE
            TJ=(-FJT1-SQRT(FJT1**2+4.D0*FJT2*(RIP*1.D6-FJP))) &
               /(2.D0*FJT2)
         ENDIF

         DO NSG=1,NSGMAX
         DO NTG=1,NTGMAX
            HJT(NTG,NSG)=HJP2(NTG,NSG)+TJ*HJT1(NTG,NSG) &
                                      +TJ*TJ*HJT2(NTG,NSG)
            PSIPNL=1.D0-PSI(NTG,NSG)/PSI0
            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
            CALL EQFPSI(PSIPNL,FPSI,DFPSI)
            TT(NTG,NSG)=2.D0*PI*BB*RR+TJ*(FPSI-2.D0*PI*BB*RR)
            RHO(NTG,NSG)=0.D0
         ENDDO
         ENDDO
         RIPX=RIP
!
!     ----- Given pressure and parallel current profiles -----
!
      ELSEIF(IMDLEQF.EQ.3) THEN
         CALL EQIPJP
!         DO NR=1,11
!            PSIPNL=0.002D0*(NR-1)
!            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
!            CALL EQFIPV(PSIPNL,FPSI,DFPSI)
!            WRITE(6,'(A,I5,1P5E12.4)') 'PSI,PP,FFF=',
!     &           NR,PSIPNL,PPSI,DPPSI,FPSI,DFPSI
!         ENDDO
         FJP=0.D0
         FJT=0.D0
         DO NSG=1,NSGMAX
         DO NTG=1,NTGMAX
            PSIPNL=1.D0-PSI(NTG,NSG)/PSI0
            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
            CALL EQFIPV(PSIPNL,FPSI,DFPSI)
            PP(NTG,NSG)=PPSI
            HJP(NTG,NSG)=-2.D0*PI*RMM(NTG,NSG)*DPPSI
!            IF(NTG.EQ.1.OR.NTG.EQ.NTGMAX/2+1) THEN
!               WRITE(6,'(A,I5,1P4E12.4)')
!     &              'NSG,PSIPNL,RMM,DPPSI,HJP=',
!     &               NSG,PSIPNL,RMM(NTG,NSG),DPPSI,HJP(NTG,NSG)
!            ENDIF
            HJP1(NTG,NSG)=-2.D0*PI*RMM(NTG,NSG)*DPPSI
            HJT1(NTG,NSG)=-FPSI*DFPSI/(2.D0*PI*RMU0*RMM(NTG,NSG))
            HJP2(NTG,NSG)=HJP1(NTG,NSG)
            DVOL=SIGM(NSG)*RHOM(NTG)*RHOM(NTG)*DSG*DTG
            FJP=FJP+HJP2(NTG,NSG)*DVOL
            FJT=FJT+HJT1(NTG,NSG)*DVOL

            HJT(NTG,NSG)=HJP2(NTG,NSG)+HJT1(NTG,NSG)
            TT(NTG,NSG)=FPSI
            RHO(NTG,NSG)=0.D0
         ENDDO
         ENDDO
         RIPX=(FJP+FJT)*1.D-6
!         WRITE(6,'(A,1P3E12.4)') 'RIPX=',RIPX,FJP*1.D-6,FJT*1.D-6
!
!     ----- Given pressure and safety factor profiles ------
!
      ELSEIF(IMDLEQF.EQ.4) THEN
         CALL EQIPQP
         FJP=0.D0
         FJT=0.D0
         DO NSG=1,NSGMAX
         DO NTG=1,NTGMAX
            PSIPNL=1.D0-PSI(NTG,NSG)/PSI0
            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
            CALL EQFIPV(PSIPNL,FPSI,DFPSI)
            PP(NTG,NSG)=PPSI
            HJP(NTG,NSG)=-2.D0*PI*RMM(NTG,NSG)*DPPSI
            HJP1(NTG,NSG)=-2.D0*PI*RMM(NTG,NSG)*DPPSI
            HJT1(NTG,NSG)=-FPSI*DFPSI/(2.D0*PI*RMU0*RMM(NTG,NSG))
            HJP2(NTG,NSG)=HJP1(NTG,NSG)
            DVOL=SIGM(NSG)*RHOM(NTG)*RHOM(NTG)*DSG*DTG
            FJP=FJP+HJP2(NTG,NSG)*DVOL
            FJT=FJT+HJT1(NTG,NSG)*DVOL

            HJT(NTG,NSG)=HJP2(NTG,NSG)+HJT1(NTG,NSG)
            TT(NTG,NSG)=FPSI
            RHO(NTG,NSG)=0.D0
         ENDDO
         ENDDO
         RIPX=(FJP+FJT)*1.D-6
!         WRITE(6,'(A,1P3E12.4)') 'RIPX=',RIPX,FJP*1.D-6,FJT*1.D-6
      ENDIF
!
!     ----- CALCULATE POLOIDAL CURRENT -----
!
      IMDLEQF=MOD(MDLEQF,5)
      DO NRV=1,NRVMAX
         PSIPNL=PSIPNV(NRV)
         IF (IMDLEQF.EQ.0) THEN
            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
            CALL EQJPSI(PSIPNL,HJPSID,HJPSI)
            CALL EQTPSI(PSIPNL,TPSI,DTPSI)
            CALL EQOPSI(PSIPNL,OMGPSI,DOMGPSI)
            TTVL=SQRT((2.D0*PI*BB*RR)**2 &
                        +2.D0*RMU0*RRC &
                        *(2.D0*PI*TJ*HJPSID-RRC*PPSI &
                        *EXP(RRC**2*OMGPSI**2*AMP/(2.D0*TPSI))))
         ELSEIF (IMDLEQF.EQ.1) THEN
            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
            CALL EQFPSI(PSIPNL,FPSI,DFPSI)
            TTVL=2.D0*PI*BB*RR+TJ*(FPSI-2.D0*PI*BB*RR)
         ELSEIF (IMDLEQF.EQ.2) THEN
            CALL EQFIPV(PSIPNL,FPSI,DFPSI)
            TTVL=2.D0*PI*BB*RR+TJ*(FPSI-2.D0*PI*BB*RR)
         ELSEIF (IMDLEQF.EQ.3) THEN
            CALL EQFIPV(PSIPNL,FPSI,DFPSI)
            TTVL=FPSI
         ELSEIF (IMDLEQF.EQ.4) THEN
            CALL EQFIPV(PSIPNL,FPSI,DFPSI)
            TTVL=FPSI
         ENDIF
         TTV(NRV)=TTVL
      ENDDO

      CALL SPL1D(PSIPNV,PSITV,DERIV,UPSITV,NRVMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for PSITV: IERR=',IERR
      CALL SPL1D(PSIPNV,QPV,DERIV,UQPV,NRVMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for QPV: IERR=',IERR
      CALL SPL1D(PSIPNV,TTV,DERIV,UTTV,NRVMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for TTV: IERR=',IERR
!
!      WRITE(6,'(A,I5,1P4E12.4)')
!     &     ('NRV:',NRV,PSIPNV(NRV),PSITV(NRV),QPV(NRV),TTV(NRV),
!     &      NRV=1,NRVMAX)
!
      RETURN
      END
!
!   ************************************************
!   **              Matrix Solver                 **
!   ************************************************
!
      SUBROUTINE EQSOLV

      USE libbnd
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)

      REAL(rkind),ALLOCATABLE:: FJT(:),PSIOLD(:,:)

      ALLOCATE(FJT(MLM),PSIOLD(NTGM,NSGM))
      ! Defensive zero-init (see PR #123 pattern): libeqapi.so finalize+reinit
      ! cycle can reuse heap chunks with stale values.
      FJT    = 0.D0
      PSIOLD = 0.D0

      DO NSG=1,NSGMAX
      DO NTG=1,NTGMAX
         PSIOLD(NTG,NSG)=PSI(NTG,NSG)
      ENDDO
      ENDDO

      DO NSG=1,NSGMAX
         I=(NSG-1)*NTGMAX
         DO NTG=1,NTGMAX
            FJT(I+NTG)=2.D0*PI*RMU0*HJT(NTG,NSG) &
                       *SIGM(NSG)*RHOM(NTG)*RHOM(NTG)
         ENDDO
      ENDDO
!
!      DO NSG=1,2
!         DO NTG=1,NTGMAX
!            WRITE(6,'(2I5,1PE12.4)') NSG,NTG,HJT(NSG,NTG)
!         ENDDO
!      ENDDO
!      PAUSE
!
!      DO I=1,3
!         WRITE(6,'(1p5E12.4)') FJT(I),(Q(J,I),J=1,4*NTGMAX-1)
!      ENDDO

      CALL BANDRD(Q,FJT,NTGMAX*NSGMAX,4*NTGMAX-1,MWM,IERR)
         IF(IERR.NE.0) THEN
            WRITE(6,*) 'XX EQSOLV: BANDRD ERROR: IERR = ',IERR
         ENDIF
!
!      WRITE(6,'(1p5E12.4)') (FJT(I),I=1,2*NTGMAX)

      DO NSG=1,NSGMAX
         I=(NSG-1)*NTGMAX
         DO NTG=1,NTGMAX
            PSI(NTG,NSG)=FJT(I+NTG)
         ENDDO
      ENDDO
!      WRITE(6,'(1p5E12.4)') (PSI(I,1),I=1,NTGMAX)
!      WRITE(6,'(1p5E12.4)') (PSI(I,2),I=1,NTGMAX)
!      WRITE(6,'(1p5E12.4)') (PSI(I,3),I=1,NTGMAX)
!      WRITE(6,'(1p5E12.4)') (PSI(I,4),I=1,NTGMAX)

      DO NSG=1,NSGMAX
      DO NTG=1,NTGMAX
         DELPSI(NTG,NSG)=PSI(NTG,NSG)-PSIOLD(NTG,NSG)
      ENDDO
      ENDDO
      RETURN
      END
!
!   ************************************************
!   **          sigma,theta to R,Z                **
!   ************************************************
!
      SUBROUTINE EQTORZ

      USE libbrent
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      EXTERNAL EQFBND

      RMIN= RR-RB
      RMAX= RR+RB
      ZMIN=-RKAP*RB
      ZMAX= RKAP*RB

      SIG1=1.D0
      SIG2=0.95D0

      DTRG=(RMAX-RMIN)/(NRGMAX-1)
      DTZG=(ZMAX-ZMIN)/(NZGMAX-1)
      EPSZ=1.D-8

      DO NRG=1,NRGMAX
         RG(NRG)=RMIN+DTRG*(NRG-1)
      ENDDO
      DO NZG=1,NZGMAX
         ZG(NZG)=ZMIN+DTZG*(NZG-1)
      ENDDO

      CALL EQSETF

      DO NRG=1,NRGMAX
      DO NZG=1,NZGMAX
         IF((RG(NRG)-RR.EQ.0.D0).AND. &
            (ZG(NZG).EQ.0.D0)) THEN
            RHOL=0.D0
            SIGL=0.D0
         ELSE
            THL=ATAN2(ZG(NZG),RG(NRG)-RR)
            IF(THL.LT.0.D0) THL=THL+2.D0*PI
            ZBRF=TAN(THL)
            THDASH=FBRENT(EQFBND,THL-1.0D0,THL+1.0D0,EPSZ)
            RHOL=RA*SQRT(COS(THDASH+RDLT*SIN(THDASH))**2 &
                        +RKAP**2*SIN(THDASH)**2)
            SIGL=SQRT((RG(NRG)-RR)**2+ZG(NZG)**2)/RHOL
         ENDIF
         IF(SIGL.LT.1.D0) THEN
            PSIRZ(NRG,NZG)=PSIF(SIGL,THL)
            HJTRZ(NRG,NZG)=HJTF(SIGL,THL)
         ELSE
            PSI1=PSIF(SIG1,THL)
            PSI2=PSIF(SIG2,THL)
            PSIRZ(NRG,NZG)=PSI2+(PSI1-PSI2)*(SIGL-SIG2)/(SIG1-SIG2)
            HJTRZ(NRG,NZG)=0.D0
         ENDIF
      ENDDO
      ENDDO

      RETURN
      END
!
!   ******************************************
!   ***** Calculate Spline Coeff for Psi *****
!   ******************************************
!
      SUBROUTINE EQSETF

      USE libspl2d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)

      REAL(rkind),ALLOCATABLE:: PSISX(:,:),PSITX(:,:)
      REAL(rkind),ALLOCATABLE:: PSISTX(:,:)

      ALLOCATE(PSISX(NTGPM,NSGPM),PSITX(NTGPM,NSGPM))
      ALLOCATE(PSISTX(NTGPM,NSGPM))
      ! Defensive zero-init (see PR #123 pattern): libeqapi.so finalize+reinit
      ! cycle can reuse heap chunks with stale values.
      PSISX  = 0.D0
      PSITX  = 0.D0
      PSISTX = 0.D0
!
!     ----- mesh extended in sigma (radius) and theta (periodic) -----
!
      SIGMX(1)=0.D0
      DO NSG=1,NSGMAX
         SIGMX(NSG+1)=SIGM(NSG)
      ENDDO
      SIGMX(NSGMAX+2)=1.D0

      THGMX(1)=0.D0
      DO NTG=1,NTGMAX
         THGMX(NTG+1)=THGM(NTG)
      ENDDO
      THGMX(NTGMAX+2)=2.D0*PI

      SUMPSI=0.D0
      SUMHJT=0.D0
      DO NTG=1,NTGMAX
         SUMPSI=SUMPSI+(9.D0*PSI(NTG,1)-PSI(NTG,2))/8.D0
         SUMHJT=SUMHJT+(9.D0*HJT(NTG,1)-HJT(NTG,2))/8.D0
      ENDDO
      PSIL=SUMPSI/NTGMAX
      HJTL=SUMHJT/NTGMAX
      DO NTG=1,NTGMAX+2
         PSIST(NTG,1)=PSIL
         HJTST(NTG,1)=HJTL
      ENDDO

      DO NSG=1,NSGMAX
      DO NTG=1,NTGMAX
         PSIST(NTG+1,NSG+1)=PSI(NTG,NSG)
         HJTST(NTG+1,NSG+1)=HJT(NTG,NSG)
      ENDDO
      ENDDO

      DO NSG=1,NSGMAX
         PSIST(       1,NSG+1)=(9.D0*PSI(     1,NSG)-PSI(       2,NSG)) &
                               /16.D0 &
                              +(9.D0*PSI(NTGMAX,NSG)-PSI(NTGMAX-1,NSG)) &
                               /16.D0
         PSIST(NTGMAX+2,NSG+1)=PSIST(1,NSG+1)
         HJTST(       1,NSG+1)=(9.D0*HJT(     1,NSG)-HJT(       2,NSG)) &
                               /16.D0 &
                              +(9.D0*HJT(NTGMAX,NSG)-HJT(NTGMAX-1,NSG)) &
                               /16.D0
         HJTST(NTGMAX+2,NSG+1)=HJTST(1,NSG+1)
      ENDDO

      DO NTG=1,NTGMAX+2
         PSIST(NTG,NSGMAX+2)=0.D0
         HJTST(NTG,NSGMAX+2)=0.D0
      ENDDO

      CALL SPL2D(THGMX,SIGMX,PSIST,PSITX,PSISX,PSISTX,UPSIST, &
                 NTGPM,NTGMAX+2,NSGMAX+2,4,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL2D for PSIX: IERR=',IERR
      CALL SPL2D(THGMX,SIGMX,HJTST,PSITX,PSISX,PSISTX,UHJTST, &
                 NTGPM,NTGMAX+2,NSGMAX+2,4,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL2D for PSIX: IERR=',IERR
      RETURN
      END
!
!   *******************************************
!   ***** Calculate Psi at (sigma, theta) *****
!   *******************************************
!
      FUNCTION PSIF(RSIG,RTHG)

      USE libspl2d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind), INTENT(IN) :: RSIG, RTHG

      CALL SPL2DF(RTHG,RSIG,PSIL,THGMX,SIGMX,UPSIST, &
                  NTGPM,NTGMAX+2,NSGMAX+2,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX PSIF: SPL2DF ERROR : IERR=',IERR
      PSIF=PSIL
      RETURN
      END
!
!   *******************************************
!   ***** Calculate Hjt at (sigma, theta) *****
!   *******************************************
!
      FUNCTION HJTF(RSIG,RTHG)

      USE libspl2d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind), INTENT(IN) :: RSIG, RTHG

      CALL SPL2DF(RTHG,RSIG,HJTL,THGMX,SIGMX,UHJTST, &
                  NTGPM,NTGMAX+2,NSGMAX+2,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX HJTF: SPL2DF ERROR : IERR=',IERR
      HJTF=HJTL
      RETURN
      END
!
!   ************************************************
!   **      CALCULATE pp,tt,temp,omega,rho        **
!   ************************************************
!
      SUBROUTINE EQCALP

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)

      IMDLEQF=MOD(MDLEQF,5)
      DPS=PSIPA/(NPSMAX-1)
      DO NPS=1,NPSMAX
         PSIPS(NPS)=DPS*(NPS-1)
         PSIPNL=PSIPS(NPS)/PSIPA

         IF (IMDLEQF.EQ.0) THEN
            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
            CALL EQJPSI(PSIPNL,HJPSID,HJPSI)
            CALL EQTPSI(PSIPNL,TPSI,DTPSI)
            CALL EQOPSI(PSIPNL,OMGPSI,DOMGPSI)
            PPPS(NPS)=PPSI
            OMPS(NPS)=OMGPSI
            TTPS(NPS)=SQRT((2.D0*PI*BB*RR)**2 &
                        +2.D0*RMU0*RRC &
                        *(2.D0*PI*TJ*HJPSID-RRC*PPSI &
                        *EXP(RRC**2*OMGPSI**2*AMP/(2.D0*TPSI))))
            TEPS(NPS)=TPSI/(AEE*1.D3)
         ELSEIF (IMDLEQF.EQ.1) THEN
            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
            CALL EQFPSI(PSIPNL,FPSI,DFPSI)
            PPPS(NPS)=PPSI
            TTPS(NPS)=2.D0*PI*BB*RR+TJ*(FPSI-2.D0*PI*BB*RR)
            OMPS(NPS)=0.D0
            TEPS(NPS)=0.D0
         ELSEIF (IMDLEQF.EQ.2) THEN
            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
            CALL EQFIPV(PSIPNL,FPSI,DFPSI)
            PPPS(NPS)=PPSI
            TTPS(NPS)=2.D0*PI*BB*RR+TJ*(FPSI-2.D0*PI*BB*RR)
            OMPS(NPS)=0.D0
            TEPS(NPS)=0.D0
         ELSEIF (IMDLEQF.EQ.3) THEN
            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
            CALL EQFIPV(PSIPNL,FPSI,DFPSI)
            PPPS(NPS)=PPSI
            TTPS(NPS)=FPSI
            OMPS(NPS)=0.D0
            TEPS(NPS)=0.D0
         ELSEIF (IMDLEQF.EQ.4) THEN
            CALL EQPPSI(PSIPNL,PPSI,DPPSI)
            CALL EQFIPV(PSIPNL,FPSI,DFPSI)
            PPPS(NPS)=PPSI
            TTPS(NPS)=FPSI
            OMPS(NPS)=0.D0
            TEPS(NPS)=0.D0
         ENDIF
      ENDDO
      RETURN
      END
