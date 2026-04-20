!     $Id$
!
! Phase F-4 (HIGH tier): free-form F90 conversion of eqcalq.f.
! Q-profile / flux-surface diagnostics driver: EQCALQ, EQSETP,
! EQCALQP, EQCALQV, EQSETS, EQSETS_RHO, EQCALF, PPFUNC/TTFUNC/
! DPPFUNC/DTTFUNC, zminmax. Depends on the spline tables that
! eqsplf.f90 evaluates. Preserves exact numerical semantics of the
! original fixed-form source.
!
! NOTE on EXTERNAL: EQSETP and EQCALQP/EQCALQV pass PSIGD / EQDERV to
!   NEWTN / EQRK4 via EXTERNAL declarations (the called solvers accept
!   arbitrary external routines). Kept as-is.
!
! NOTE: IMPLICIT NONE is NOT added at file level because the INCLUDEd
!       shim '../eq/eqcomq.inc' supplies an IMPLICIT statement
!       (IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)) and USEs the F-1
!       MODULEs (eqcom0/1/3_mod) for COMMON symbols. The trailing
!       zminmax helper retains its original IMPLICIT NONE annotation.
!
!     ***** Calculated Flux Functions from PSIRZ *****
!
      SUBROUTINE EQCALQ(IERR)

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(OUT) :: IERR

      IERR=0
!
!     ----- CHECK NRMAX,NTHMAX,NSUMAX are not greater than *M -----
!
      IF(NRMAX.GT.NRM) THEN
         WRITE(6,'(A,2I5)') &
              'NRMAX.GT.NRM: NRMAX,NRM=',NRMAX,NRM
         IERR=IERR+1
      ENDIF
      IF(NTHMAX.GT.NTHM) THEN
         WRITE(6,'(A,2I5)') &
              'NTHMAX.GT.NTHM: NTHMAX,NTHM=',NTHMAX,NTHM
         IERR=IERR+2
      ENDIF
      IF(NSUMAX.GT.NSUM) THEN
         WRITE(6,'(A,2I5)') &
              'NSUMAX.GT.NSUM: NSUMAX,NSUM=',NSUMAX,NSUM
         IERR=IERR+4
      ENDIF
      IF(IERR.NE.0) RETURN

      IF(RB.LT.RA) THEN
         WRITE(6,'(A,1P2E12.4)') &
              '!! RB.LT.RA: set RB=RA: RA,RB=',RA,RB
         RB=RA
      ENDIF

      CALL EQSETP(IERR)
      IF(IERR.NE.0) RETURN

      CALL EQCALQP(IERR)
      IF(IERR.NE.0) RETURN

      IF(.NOT.(NSUMAX.EQ.0.OR. &
               RA-RB.EQ.0.D0.OR. &
               RR+RB-REDGE.EQ.0.D0)) THEN
         CALL EQCALQV(IERR)
         IF(IERR.NE.0) RETURN
      ENDIF

      CALL EQSETS_RHO(IERR)
      CALL EQSETS(IERR)
!
!     ----- Phase L-0 regression dump (env-guarded, no-op unless
!           EQ_REGRESS_DUMP=1). Hook here so every successful R/RUN
!           or C/CONT path produces eq_regress.dat in cwd. -----
      CALL EQ_REGRESS_DUMP_IF_ENABLED

      RETURN
      END
!
!     ***** SETUP DATA (spline PSIRZ and find axis) *****
!
      SUBROUTINE EQSETP(IERR)

      USE libspl1d
      USE libspl2d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(OUT) :: IERR

      REAL(rkind),DIMENSION(:,:),ALLOCATABLE:: PSIRG,PSIZG,PSIRZG
      REAL(rkind),DIMENSION(:,:),ALLOCATABLE:: HJTRG,HJTZG,HJTRZG

      DIMENSION DERIV(NPSM)
      EXTERNAL PSIGD

      ALLOCATE(PSIRG(NRGM,NZGM),PSIZG(NRGM,NZGM),PSIRZG(NRGM,NZGM))
      ALLOCATE(HJTRG(NRGM,NZGM),HJTZG(NRGM,NZGM),HJTRZG(NRGM,NZGM))
      ! Defensive zero-init (see PR #123 pattern): libeqapi.so finalize+reinit
      ! cycle can reuse heap chunks with stale values.
      PSIRG  = 0.D0; PSIZG  = 0.D0; PSIRZG = 0.D0
      HJTRG  = 0.D0; HJTZG  = 0.D0; HJTRZG = 0.D0

      CALL SPL2D(RG,ZG,PSIRZ,PSIRG,PSIZG,PSIRZG,UPSIRZ, &
                 NRGM,NRGMAX,NZGMAX,0,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL2D for PSIRZ: IERR=',IERR

      CALL SPL2D(RG,ZG,HJTRZ,HJTRG,HJTZG,HJTRZG,UHJTRZ, &
                 NRGM,NRGMAX,NZGMAX,0,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL2D for HJTRZ: IERR=',IERR

!     *** Initial parameters for first guess of EQAXIS input ***
      IF(MODELG.NE.5) THEN
         RAXIS=RR
         ZAXIS=0.D0
      END IF
      PSI0=PSIG(RAXIS,ZAXIS)
      PSIPA=-PSI0
!     **********************************************************
!
!     *** Calculate RAXIS, ZAXIS, PSI0 and PSIPA ***
!      WRITE(6,'(A,1P4E12.4)')
!     &     'IN:RAXIS,ZAXIS,PSI0,PSIPA=',RAXIS,ZAXIS,PSI0,PSIPA
      CALL EQAXIS(IERR)
!      WRITE(6,'(A,1P4E12.4)')
!     &     'OT:RAXIS,ZAXIS,PSI0,PSIPA=',RAXIS,ZAXIS,PSI0,PSIPA
      IF(IERR.NE.0) RETURN
!     **********************************************
!
!      IF(MODELG.EQ.5) THEN
!     *** Reconstruct PSIPS ***********************************************
!     *  PSIPS originates from PSI0 and PSIA in eqdsk data.
!     *  However, EQAXIS calculates PSI0 and the position of the magnetic
!     *    axis by using PSIRZ interpolated by cubic spline, and these
!     *    are slightly different from those in eqdsk data.
!     *  Then the radial psi-coordinate is corrected to fit itself to the
!     *    interpolated PSI contour.
!         DPS = PSIPA / (NPSMAX - 1)
!         DO NPS=1,NPSMAX
!            PSIPS(NPS) = DPS * (NPS - 1)
!         ENDDO
!     *********************************************************************
!      ENDIF
!
!      DO NPS=1,NPSMAX
!         WRITE(6,'(A,I5,1P3E12.4)') 'NPS:',NPS,PSIPS(NPS),
!     &                             PPPS(NPS),TTPS(NPS)
!      ENDDO

      CALL SPL1D(PSIPS,PPPS,  DERIV,UPPPS, NPSMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for PPPS: IERR=',IERR
      CALL SPL1D(PSIPS,TTPS,  DERIV,UTTPS, NPSMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for TTPS: IERR=',IERR
      IF(MODELG.EQ.5) THEN
         CALL SPL1D(PSIPS,DPPPS,  DERIV,UDPPPS, NPSMAX,0,IERR)
         IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for DPPPS: IERR=',IERR
         CALL SPL1D(PSIPS,DTTPS,  DERIV,UDTTPS, NPSMAX,0,IERR)
         IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for DTTPS: IERR=',IERR
      ENDIF

      DEALLOCATE(PSIRG,PSIZG,PSIRZG)
      DEALLOCATE(HJTRG,HJTZG,HJTRZG)

      RETURN
      END
!
!     ***** CALCULATE FLUX VARIABLES IN PLASMA *****
!
      SUBROUTINE EQCALQP(IERR)

      USE libspl1d
      USE libitp
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(OUT) :: IERR

      EXTERNAL EQDERV
      DIMENSION XA(NTVM),YA(2,NTVM)
      DIMENSION XCHI0(NTVM),XCHI1(NTVM)
      DIMENSION RCHI(NTVM),ZCHI(NTVM),DXCHI(NTVM)
      DIMENSION BRCHI(NTVM),BZCHI(NTVM),BTCHI(NTVM),BBCHI(NTVM)
      DIMENSION URCHI(4,NTVM),UZCHI(4,NTVM)
      DIMENSION UBRCHI(4,NTVM),UBZCHI(4,NTVM)
      DIMENSION UBTCHI(4,NTVM),UBBCHI(4,NTVM)

      IERR=0
!
!     ----- SET DR, DTH -----
!
      IF(NSUMAX.EQ.0.OR.RA-RB.EQ.0.D0.OR.RR+RB-REDGE.EQ.0.D0) THEN
         NRPMAX=NRMAX
      ELSE
         DR=(RB-RA+REDGE-RAXIS)/(NRMAX-1)
         NRPMAX=NINT((REDGE-RAXIS)/DR)+1
      ENDIF
!      write(6,*) 'nrmax,nrpmax,nsumax=',nrmax,nrpmax,nsumax
      DR=(REDGE-RAXIS)/(NRPMAX-1)
      DTH=2.d0*PI/NTHMAX
!
!     ----- SET NUMBER OF DIVISION for integration -----
!
      IF(NTVMAX.GT.NTVM) NTVMAX=NTVM
!
!     ----- CALCULATE PSI,PPS,TTS,PSIT and RPS, ZPS
!           on magnetic surfaces, PSIP(NR) -----
!
      NR=1
      DO NTH=1,NTHMAX+1
         RPS(NTH,NR)=RAXIS
         ZPS(NTH,NR)=ZAXIS
      ENDDO
      PSIP(1)=PSIG(RAXIS,ZAXIS)-PSI0
      PPS(1)=PPFUNC(PSIP(1))
      TTS(1)=TTFUNC(PSIP(1))
!
!         WRITE(6,'(A,I5,1P3E12.4)') 'NR:',NR,
!     &        PSIP(NR),PPS(NR),TTS(NR)

      DO NR=2,NRPMAX
         RINIT=RAXIS+DR*(NR-1)
         ZINIT=ZAXIS
         PSIP(NR)=PSIG(RINIT,ZINIT)-PSI0
         PPS(NR)=PPFUNC(PSIP(NR))
         TTS(NR)=TTFUNC(PSIP(NR))
!
!         WRITE(6,'(A,I5,1P5E12.4)') 'NR:',NR,
!     &        PSIP(NR),PPS(NR),TTS(NR),RINIT,ZINIT

         CALL EQMAGS(RINIT,ZINIT,NTVMAX,XA,YA,NA,IERR)

         SUMS=0.D0
         SUMV=0.D0
         SUMAVRR =0.D0
         SUMAVRR2=0.D0
         SUMAVIR2=0.D0
         SUMAVBB =0.D0
         SUMAVBB2=0.D0
         SUMAVIB2=0.D0
         SUMAVGV =0.D0
         SUMAVGV2=0.D0
         SUMAVGR2=0.D0
         SUMAVIR =0.D0

         RMIN=RAXIS
         RMAX=RAXIS
         ZMIN=ZAXIS
         ZMAX=ZAXIS
         NZMINR=1
         NZMAXR=1
         BMIN=ABS(2.D0*BB)
         BMAX=0.D0

         XCHI0(1)=0.D0
         XCHI1(1)=0.D0
         RCHI(1)=RINIT
         ZCHI(1)=ZINIT

         DO N=2,NA
            H=XA(N)-XA(N-1)
            R=0.5D0*(YA(1,N-1)+YA(1,N))
            Z=0.5D0*(YA(2,N-1)+YA(2,N))
            CALL PSIGD(R,Z,DPSIDR,DPSIDZ)
            BPL=SQRT(DPSIDR**2+DPSIDZ**2)/(2.D0*PI*R)
            BTL=TTS(NR)/(2.D0*PI*R)
            B2L=BTL**2+BPL**2

            SUMV=SUMV+H/BPL
            SUMS=SUMS+H*R

            SUMAVRR =SUMAVRR +H*R/BPL
            SUMAVRR2=SUMAVRR2+H*R*R/BPL
            SUMAVIR2=SUMAVIR2+H/(BPL*R*R)
            SUMAVBB =SUMAVBB +H*SQRT(B2L)/BPL
            SUMAVBB2=SUMAVBB2+H*B2L/BPL
            SUMAVIB2=SUMAVIB2+H/(B2L*BPL)
            SUMAVGV =SUMAVGV +H*R
            SUMAVGV2=SUMAVGV2+H*R*R*BPL
            SUMAVGR2=SUMAVGR2+H*BPL
            SUMAVIR =SUMAVIR +H/(BPL*R)

            XCHI1(N)=SUMAVIR2
            RCHI(N)=YA(1,N)
            ZCHI(N)=YA(2,N)
            BRCHI(N)=-DPSIDZ/(2.D0*PI*R)
            BZCHI(N)= DPSIDR/(2.D0*PI*R)
            BTCHI(N)= BTL
            BBCHI(N)= SQRT(B2L)

            R=YA(1,N)
            Z=YA(2,N)
            CALL PSIGD(R,Z,DPSIDR,DPSIDZ)
            BPL=SQRT(DPSIDR**2+DPSIDZ**2)/(2.D0*PI*R)
            BTL=TTS(NR)/(2.D0*PI*R)
            B2L=BTL**2+BPL**2
            B=SQRT(B2L)

            RMIN=MIN(RMIN,R)
            RMAX=MAX(RMAX,R)
            IF(Z.LT.ZMIN) THEN
               ZMIN=Z
               NZMINR=N
            ENDIF
            IF(Z.GT.ZMAX) THEN
               ZMAX=Z
               NZMAXR=N
            ENDIF
            BMIN=MIN(BMIN,B)
            BMAX=MAX(BMAX,B)
         ENDDO

         QPS(NR)=SUMAVIR2*TTS(NR)/(4.D0*PI**2)
         DVDPSIP(NR)=SUMV
         DVDPSIT(NR)=SUMV/QPS(NR)
         SPS(NR)=SUMS*2.D0*PI
         RLEN(NR)=XA(NA)
         AVERR  (NR)=SUMAVRR /SUMV
         AVERR2 (NR)=SUMAVRR2/SUMV
         AVEIR2 (NR)=SUMAVIR2/SUMV
         AVEBB  (NR)=SUMAVBB /SUMV
         AVEBB2 (NR)=SUMAVBB2/SUMV
         AVEIB2 (NR)=SUMAVIB2/SUMV
         AVEGV  (NR)=SUMAVGV      *2.d0*PI
         AVEGV2 (NR)=SUMAVGV2*SUMV*4.d0*PI**2
         AVEGVR2(NR)=SUMAVGR2*SUMV*4.d0*PI**2
!honda         write(6,'(4E15.7)') PSIP(NR),SUMAVGR2,SUMV,AVEGVR2(NR)
         AVEGP2 (NR)=SUMAVGV2/SUMV*4.d0*PI**2
         AVEIR  (NR)=SUMAVIR /SUMV
         RITOR  (NR)=SUMAVGR2

         call zminmax(YA,NZMINR,ZMIN,ZMINR)
         call zminmax(YA,NZMAXR,ZMAX,ZMAXR)

         RRMIN(NR)=RMIN
         RRMAX(NR)=RMAX
         ZZMIN(NR)=ZMIN
         ZZMAX(NR)=ZMAX
         RZMIN(NR)=ZMINR
         RZMAX(NR)=ZMAXR
         RRPSI(NR)=0.5D0*(RMAX+RMIN)
         RSPSI(NR)=0.5D0*(RMAX-RMIN)
         ELIPPSI(NR)=(ZMAX-ZMIN)/(2.D0*RSPSI(NR))
         TRIGPSI(NR)=(RRPSI(NR)-(ZMAXR+ZMINR)/2.D0)/RSPSI(NR)
         BBMIN(NR)=BMIN
         BBMAX(NR)=BMAX
!
!        ----- CALCULATE POLOIDAL COORDINATES -----
!
         IF(NTHMAX.GT.0) THEN
            DO N=1,NA
               XCHI0(N)=2.D0*PI*XA(N)/XA(NA)
               XCHI1(N)=2.D0*PI*XCHI1(N)/XCHI1(NA)
            ENDDO
            RCHI(NA)=RCHI(1)
            ZCHI(NA)=ZCHI(1)
            BRCHI(1)=0.5D0*(BRCHI(2)+BRCHI(NA-1))
            BZCHI(1)=0.5D0*(BZCHI(2)+BZCHI(NA-1))
            BTCHI(1)=0.5D0*(BTCHI(2)+BTCHI(NA-1))
            BBCHI(1)=0.5D0*(BBCHI(2)+BBCHI(NA-1))
            BRCHI(NA)=BRCHI(1)
            BZCHI(NA)=BZCHI(1)
            BTCHI(NA)=BTCHI(1)
            BBCHI(NA)=BBCHI(1)
!
!            write(6,'(I5,1P2E12.4)') (N,RCHI(N),ZCHI(N),N=1,NA)
!
            IF(MDLEQC.EQ.0) THEN
               CALL SPL1D(XCHI0,RCHI,DXCHI,URCHI,NA,4,IERR)
               IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for RCHI: IERR=',IERR
               CALL SPL1D(XCHI0,ZCHI,DXCHI,UZCHI,NA,4,IERR)
               IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for ZCHI: IERR=',IERR
               CALL SPL1D(XCHI0,BRCHI,DXCHI,UBRCHI,NA,4,IERR)
               IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for BRCHI: IERR=',IERR
               CALL SPL1D(XCHI0,BZCHI,DXCHI,UBZCHI,NA,4,IERR)
               IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for BZCHI: IERR=',IERR
               CALL SPL1D(XCHI0,BTCHI,DXCHI,UBTCHI,NA,4,IERR)
               IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for BTCHI: IERR=',IERR
               CALL SPL1D(XCHI0,BBCHI,DXCHI,UBBCHI,NA,4,IERR)
               IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for BBCHI: IERR=',IERR
            ELSE
               CALL SPL1D(XCHI1,RCHI,DXCHI,URCHI,NA,4,IERR)
               IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for RCHI: IERR=',IERR
               CALL SPL1D(XCHI1,ZCHI,DXCHI,UZCHI,NA,4,IERR)
               IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for ZCHI: IERR=',IERR
               CALL SPL1D(XCHI1,BRCHI,DXCHI,UBRCHI,NA,4,IERR)
               IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for BRCHI: IERR=',IERR
               CALL SPL1D(XCHI1,BZCHI,DXCHI,UBZCHI,NA,4,IERR)
               IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for BZCHI: IERR=',IERR
               CALL SPL1D(XCHI1,BTCHI,DXCHI,UBTCHI,NA,4,IERR)
               IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for BTCHI: IERR=',IERR
               CALL SPL1D(XCHI1,BBCHI,DXCHI,UBBCHI,NA,4,IERR)
               IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for BBCHI: IERR=',IERR
            ENDIF

            RPS(1,NR)=YA(1,1)
            ZPS(1,NR)=YA(2,1)
            DO NTH=2,NTHMAX+1
               TH=DTH*(NTH-1)
               IF(MDLEQC.EQ.0) THEN
                  CALL SPL1DF(TH,RPS(NTH,NR),XCHI0,URCHI,NA,IERR)
                  CALL SPL1DF(TH,ZPS(NTH,NR),XCHI0,UZCHI,NA,IERR)
               ELSE
                  CALL SPL1DF(TH,RPS(NTH,NR),XCHI1,URCHI,NA,IERR)
                  CALL SPL1DF(TH,ZPS(NTH,NR),XCHI1,UZCHI,NA,IERR)
               ENDIF
            ENDDO
         ENDIF
      ENDDO
!
!     ----- current profile evaluation -----
!
      DO NR=2,NRPMAX
         DPPSL=DPPFUNC(PSIP(NR))
         DTTSL=DTTFUNC(PSIP(NR))
         TTSL =TTFUNC(PSIP(NR))
         AVEJTR(NR)=-RR*DPPSL-TTSL*DTTSL/(4.d0*PI**2*RMU0*RR)
         AVEJPR(NR)=(-TTSL*DPPSL-DTTSL*AVEBB2(NR)/RMU0) &
                    /(2.d0*PI*ABS(BB))
!         WRITE(6,'(A,I6,4ES12.4)') 'AVEJ=',NR,
!     &        AVEJTR(NR),AVEJPR(NR),AVEGP2(NR),AVEGVR2(NR)
      ENDDO
!
!     +++++ SETUP AXIS DATA +++++
!
      PS2 = PSIP(2)
      PS3 = PSIP(3)
      PS4 = PSIP(4)
      QPS(1)     = FCTR2(PS2,PS3,PS4,QPS(2),QPS(3),QPS(4))
      DVDPSIP(1) = FCTR2(PS2,PS3,PS4,DVDPSIP(2),DVDPSIP(3),DVDPSIP(4))
      DVDPSIT(1) = FCTR2(PS2,PS3,PS4,DVDPSIT(2),DVDPSIT(3),DVDPSIT(4))
!      DSDPSIT(1) = FCTR2(PS2,PS3,PS4,DSDPSIT(2),DSDPSIT(3),DSDPSIT(4))
      RLEN(1)    = 0.D0
      AVERR (1)  = FCTR2(PS2,PS3,PS4,AVERR  (2),AVERR  (3),AVERR  (4))
      AVERR2(1)  = FCTR2(PS2,PS3,PS4,AVERR2 (2),AVERR2 (3),AVERR2 (4))
      AVEIR2(1)  = FCTR2(PS2,PS3,PS4,AVEIR2 (2),AVEIR2 (3),AVEIR2 (4))
      AVEBB (1)  = FCTR2(PS2,PS3,PS4,AVEBB  (2),AVEBB  (3),AVEBB  (4))
      AVEBB2(1)  = FCTR2(PS2,PS3,PS4,AVEBB2 (2),AVEBB2 (3),AVEBB2 (4))
      AVEIB2(1)  = FCTR2(PS2,PS3,PS4,AVEIB2 (2),AVEIB2 (3),AVEIB2 (4))
      AVEGV (1)  = FCTR2(PS2,PS3,PS4,AVEGV  (2),AVEGV  (3),AVEGV  (4))
      AVEGV2(1)  = FCTR2(PS2,PS3,PS4,AVEGV2 (2),AVEGV2 (3),AVEGV2 (4))
      AVEGVR2(1) = FCTR2(PS2,PS3,PS4,AVEGVR2(2),AVEGVR2(3),AVEGVR2(4))
      AVEGP2(1)  = FCTR2(PS2,PS3,PS4,AVEGP2 (2),AVEGP2 (3),AVEGP2 (4))
      AVEJPR(1)  = FCTR2(PS2,PS3,PS4,AVEJPR (2),AVEJPR (3),AVEJPR (4))
      AVEJTR(1)  = FCTR2(PS2,PS3,PS4,AVEJTR (2),AVEJTR (3),AVEJTR (4))
      AVEIR (1)  = FCTR2(PS2,PS3,PS4,AVEIR  (2),AVEIR  (3),AVEIR  (4))
      RITOR (1)  = 0.D0

      RRMIN(1)   = RAXIS
      RRMAX(1)   = RAXIS
      ZZMIN(1)   = ZAXIS
      ZZMAX(1)   = ZAXIS
      RZMIN(1)   = RAXIS
      RZMAX(1)   = RAXIS
      RRPSI(1)   = RAXIS
      RSPSI(1)   = 0.D0
      ELIPPSI(1) = ELIPPSI(2)
      TRIGPSI(1) = 0.D0
      BBMIN(1)   = ABS(TTS(1)/(2.D0*PI*RAXIS))
      BBMAX(1)   = ABS(TTS(1)/(2.D0*PI*RAXIS))
!
!     ----- CALCULATE TOROIDAL FLUX -----
!
!     Based on the definition of the safety factor, PSIT is calculated
!       by using average of the inverse safety factor. This way of
!       the evaluation is valid even if q is nearly infinite
!       (eg. current hole).
!
      PSIT(1)=0.D0
      VPS(1)=0.D0
      SPS(1)=0.D0
      DO NR=2,NRPMAX
         PSIT(NR)=PSIT(NR-1) &
                 +2.0D0*QPS(NR)*QPS(NR-1)/(QPS(NR)+QPS(NR-1)) &
                       *(PSIP(NR)-PSIP(NR-1))
         VPS(NR)=VPS(NR-1) &
                 +0.5D0*(DVDPSIP(NR-1)+DVDPSIP(NR)) &
                       *(PSIP(NR)-PSIP(NR-1))
!         SPS(NR)=SPS(NR-1)
!     &           +0.5D0*(DSDPSIT(NR-1)+DSDPSIT(NR))
!     &                 *(PSIT(NR)-PSIT(NR-1))
      ENDDO
      PSITA=PSIT(NRPMAX)
      PSIPA=PSIP(NRPMAX)

!$$$      do nr=1,nrmax
!$$$         write(6,'(I5,1P6E12.4)')
!$$$     &        nr,psip(nr)/psipa,psit(nr)/psita,
!$$$     &        vps(nr),sps(nr),dvdpsip(nr),dvdpsit(nr)
!$$$      enddo

      RST(1)=0.D0
      DO NR=2,NRPMAX
         RST(NR)=SQRT(PSIT(NR)/(PI*BB))
      ENDDO
      RSTA=RST(NRPMAX)

      RHOT(1)=0.D0
      DO NR=2,NRPMAX
         RHOT(NR)=SQRT(PSIT(NR)/PSITA)
      ENDDO
!
!     ----- CALCULATE EDGE VALUE -----
!
      RINIT=REDGE
      ZINIT=ZAXIS
      TTSA=TTFUNC(0.D0)
      CALL EQMAGS(RINIT,ZINIT,NTVMAX,XA,YA,NA,IERR)

      SUMS=0.D0
      SUMV=0.D0
      SUMQ=0.D0
      DO N=2,NA
         H=XA(N)-XA(N-1)
         R=0.5D0*(YA(1,N-1)+YA(1,N))
         Z=0.5D0*(YA(2,N-1)+YA(2,N))
         CALL PSIGD(R,Z,DPSIDR,DPSIDZ)
         BPRL=SQRT(DPSIDR**2+DPSIDZ**2)
         BPL=BPRL/(2.D0*PI*R)
         BTL=TTSA/(2.D0*PI*R)
         B=SQRT(BPL**2+BTL**2)

         SUMS=SUMS+H*R
         SUMV=SUMV+H*R/BPRL
         SUMQ=SUMQ+H/(R*BPRL)
      ENDDO

      SPSA=SPS(NRPMAX)
      VPSA=VPS(NRPMAX)
      QPSA=QPS(NRPMAX)
!
!     ----- CALCULATE PLASMA SURFACE -----
!
      CALL EQCALF(REDGE,ZAXIS,NTHMAX,RSU,ZSU,IERR)

      RGMIN=RSU(1)
      RGMAX=RSU(1)
      ZGMIN=ZSU(1)
      ZGMAX=ZSU(1)
      DO NTH=2,NTHMAX
!            write(6,'(A,I5,1P2E12.4)')
!     &           'NTH,RSU,ZSU=',NTH,RSU(NTH),ZSU(NTH)
         RGMIN=MIN(RGMIN,RSU(NTH))
         RGMAX=MAX(RGMAX,RSU(NTH))
         ZGMIN=MIN(ZGMIN,ZSU(NTH))
         ZGMAX=MAX(ZGMAX,ZSU(NTH))
      ENDDO
      DO NTH=1,NTHMAX
         RSW(NTH)=RSU(NTH)
         ZSW(NTH)=ZSU(NTH)
      ENDDO

!      write (6,'(I5,1PE12.4)') (i,QPS(i),i=1,NRMAX)


      RETURN
      END
!
!     ***** CALCULATE FLUX VARIABLES IN VACUUM *****
!
      SUBROUTINE EQCALQV(IERR)

      USE libspl1d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(OUT) :: IERR
      EXTERNAL EQDERV
      DIMENSION XA(NTVM),YA(2,NTVM)
      DIMENSION XCHI0(NTVM),XCHI1(NTVM)
      DIMENSION RCHI(NTVM),ZCHI(NTVM),DXCHI(NTVM)
      DIMENSION URCHI(4,NTVM),UZCHI(4,NTVM)
      DIMENSION THW(NTHMP)
      DIMENSION RPSW(NTHMP),DRPSW(NTHMP)
      DIMENSION ZPSW(NTHMP),DZPSW(NTHMP)
      REAL(rkind),ALLOCATABLE:: URPSW(:,:),UZPSW(:,:)

      ALLOCATE(URPSW(4,NTHMP),UZPSW(4,NTHMP))
      ! Defensive zero-init (see PR #123 pattern): libeqapi.so finalize+reinit
      ! cycle can reuse heap chunks with stale values.
      URPSW = 0.D0
      UZPSW = 0.D0

      npmax=abs(MDLEQV)
      IERR=0
      IF(NRMAX.EQ.NRPMAX) RETURN
!
!     +++++ SETUP VACUUM DATA +++++
!

      DR_OUT=(RR+RB-REDGE)/(NRMAX-NRPMAX)
      DR_IN =FRBIN*(RR+RB-REDGE)/(NRMAX-NRPMAX)
      DTH=2.d0*PI/NTHMAX

      IF(MDLEQF.LT.10) THEN
         DO NR=NRPMAX+1,NRMAX
            RL_OUT=REDGE+DR_OUT*(NR-NRPMAX)
            RL_IN =REDGE+DR_IN *(NR-NRPMAX)
            ZL=ZAXIS
            Sratio=(RL_OUT-RR)**2/(REDGE-RR)**2
            PSIP(NR)=PSIG(RL_OUT,ZL)-PSI0
            PPS(NR)=0.D0
            TTS(NR)=2.D0*PI*BB*RR

            DVDPSIP(NR)=DVDPSIP(NRPMAX)*Sratio
            DVDPSIT(NR)=DVDPSIT(NRPMAX)
            RLEN(NR)=RLEN(NRPMAX)*SQRT(Sratio)
            AVERR(NR)=AVERR(NRPMAX)
            AVERR2(NR)=AVERR2(NRPMAX)
            AVEIR2(NR)=AVEIR2(NRPMAX)
            AVEBB(NR)=AVEBB(NRPMAX)
            AVEBB2(NR)=AVEBB2(NRPMAX)
            AVEIB2(NR)=AVEIB2(NRPMAX)
            AVEGV(NR)=AVEGV(NRPMAX)
            AVEGV2(NR)=AVEGV2(NRPMAX)
            AVEGVR2(NR)=AVEGVR2(NRPMAX)
            AVEGP2(NR)=AVEGP2(NRPMAX)
            SPS(NR)=SPS(NRPMAX)*SQRT(Sratio)
            AVEIR(NR)=AVEIR(NRPMAX)

            VPS(NR)=VPS(NRPMAX)*Sratio
            PSIT(NR)=PSIT(NRPMAX)*Sratio
            QPS(NR)=QPS(NRPMAX)*Sratio
            RITOR(NR)=RITOR(NRPMAX)

            F_OUT=(RL_OUT-RR)/(REDGE-RR)
            F_IN =(RL_IN -RR)/(REDGE-RR)
            DTHL=2.D0*PI/NTHMAX
            DO nth=1,nthmax+1
               FACTOR=0.5D0*(F_OUT+F_IN) &
                     +0.5D0*(F_OUT-F_IN)*COS(DTHL*(NTH-1))
               rps(NTH,NR)=RAXIS+(RPS(NTH,NRPMAX)-RAXIS)*FACTOR
               zps(NTH,NR)=       ZPS(NTH,NRPMAX)       *FACTOR
            END DO

            RMIN=RAXIS
            RMAX=RAXIS
            ZMIN=ZAXIS
            ZMAX=ZAXIS

            DO NTH=1,NTHMAX+1
               ya(1,nth)=RPS(NTH,NR)
               ya(2,nth)=ZPS(NTH,NR)
               RMIN=MIN(RMIN,RPS(NTH,NR))
               RMAX=MAX(RMAX,RPS(NTH,NR))
               IF(ZPS(NTH,NR).LT.ZMIN) THEN
                  ZMIN=ZPS(NTH,NR)
                  NZMINR=NTH
               ENDIF
               IF(ZPS(NTH,NR).GT.ZMAX) THEN
                  ZMAX=ZPS(NTH,NR)
                  NZMAXR=NTH
               ENDIF
            ENDDO

            call zminmax(YA,NZMINR,ZMIN,ZMINR)
            call zminmax(YA,NZMAXR,ZMAX,ZMAXR)

            RRMIN(NR)=RMIN
            RRMAX(NR)=RMAX
            ZZMIN(NR)=ZMIN
            ZZMAX(NR)=ZMAX
            RZMIN(NR)=ZMINR
            RZMAX(NR)=ZMAXR
            RRPSI(NR)=(RMAX+RMIN)/2.D0
            RSPSI(NR)=(RMAX-RMIN)/2.D0
            ELIPPSI(NR)=(ZMAX-ZMIN)/(2.D0*RSPSI(NR))
            TRIGPSI(NR)=(RRPSI(NR)-(ZMAXR+ZMINR)/2.D0)/RSPSI(NR)

            FACTOR_OUT=(RL_OUT-RAXIS)/(REDGE-RAXIS)
            BBMIN(NR)=BBMIN(NRPMAX)/FACTOR
            FACTOR_IN =(RL_IN -RAXIS)/(REDGE-RAXIS)
            BBMAX(NR)=BBMAX(NRPMAX)*FACTOR
         ENDDO
!
      ELSE
!
!     ****** Free boundary without X point ******
!
!     ----- CALCULATE PSI,PPS,TTS,PSIT and RPS, ZPS on mag surfaces -----
!
         DO NR=NRPMAX+1,NRMAX
            RINIT=REDGE+DR_OUT*(NR-NRPMAX)
            ZINIT=ZAXIS
            PSIP(NR)=PSIG(RINIT,ZINIT)-PSI0
            PPS(NR)=0.D0
            TTS(NR)=2.D0*PI*BB*RR
!
!         WRITE(6,'(A,I5,1P3E12.4)') 'NR:',NR,
!     &        PSIP(NR),PPS(NR),TTS(NR)

            CALL EQMAGS(RINIT,ZINIT,NTVMAX,XA,YA,NA,IERR)
            IF(IERR.NE.0) GOTO 1000

            SUMS=0.D0
            SUMV=0.D0
            SUMAVRR =0.D0
            SUMAVRR2=0.D0
            SUMAVIR2=0.D0
            SUMAVBB =0.D0
            SUMAVBB2=0.D0
            SUMAVIB2=0.D0
            SUMAVGV =0.D0
            SUMAVGV2=0.D0
            SUMAVGR2=0.D0
            SUMAVIR =0.D0

            RMIN=RAXIS
            RMAX=RAXIS
            ZMIN=ZAXIS
            ZMAX=ZAXIS
            BMIN=ABS(2.D0*BB)
            BMAX=0.D0

            XCHI0(1)=0.D0
            XCHI1(1)=0.D0
            RCHI(1)=RINIT
            ZCHI(1)=ZINIT

            DO N=2,NA
               H=XA(N)-XA(N-1)
               R=0.5D0*(YA(1,N-1)+YA(1,N))
               Z=0.5D0*(YA(2,N-1)+YA(2,N))
               CALL PSIGD(R,Z,DPSIDR,DPSIDZ)
               BPL=SQRT(DPSIDR**2+DPSIDZ**2)/(2.D0*PI*R)
               BTL=TTS(NR)/(2.D0*PI*R)
               B2L=BTL**2+BPL**2

               SUMV=SUMV+H/BPL
               SUMS=SUMS+H*R

               SUMAVRR =SUMAVRR +H*R/BPL
               SUMAVRR2=SUMAVRR2+H*R*R/BPL
               SUMAVIR2=SUMAVIR2+H/(BPL*R*R)
               SUMAVBB =SUMAVBB +H*SQRT(B2L)/BPL
               SUMAVBB2=SUMAVBB2+H*B2L/BPL
               SUMAVIB2=SUMAVIB2+H/(B2L*BPL)
               SUMAVGV =SUMAVGV +H*R
               SUMAVGV2=SUMAVGV2+H*R*R*BPL
               SUMAVGR2=SUMAVGR2+H*BPL
               SUMAVIR =SUMAVIR +H/(BPL*R)

               XCHI1(N)=SUMAVIR2
               RCHI(N)=YA(1,N)
               ZCHI(N)=YA(2,N)

               R=YA(1,N)
               Z=YA(2,N)
               CALL PSIGD(R,Z,DPSIDR,DPSIDZ)
               BPL=SQRT(DPSIDR**2+DPSIDZ**2)/(2.D0*PI*R)
               BTL=TTS(NR)/(2.D0*PI*R)
               B2L=BTL**2+BPL**2
               B=SQRT(B2L)

               RMIN=MIN(RMIN,R)
               RMAX=MAX(RMAX,R)
               IF(Z.LT.ZMIN) THEN
                  ZMIN=Z
                  NZMINR=N
               ENDIF
               IF(Z.GT.ZMAX) THEN
                  ZMAX=Z
                  NZMAXR=N
               ENDIF
               BMIN=MIN(BMIN,B)
               BMAX=MAX(BMAX,B)
            ENDDO

            QPS(NR)=SUMAVIR2*TTS(NR)/(4.D0*PI**2)
            RITOR(NR)=RITOR(NRPMAX)
            DVDPSIP(NR)=SUMV
            DVDPSIT(NR)=SUMV/QPS(NR)
            SPS(NR)=SUMS*2.D0*PI
            RLEN(NR)=XA(NA)
            AVERR  (NR)=SUMAVRR /SUMV
            AVERR2 (NR)=SUMAVRR2/SUMV
            AVEIR2 (NR)=SUMAVIR2/SUMV
            AVEBB  (NR)=SUMAVBB /SUMV
            AVEBB2 (NR)=SUMAVBB2/SUMV
            AVEIB2 (NR)=SUMAVIB2/SUMV
            AVEGV  (NR)=SUMAVGV      *2.D0*PI
            AVEGV2 (NR)=SUMAVGV2*SUMV*4.D0*PI**2
            AVEGVR2(NR)=SUMAVGR2*SUMV*4.D0*PI**2
            AVEGP2 (NR)=SUMAVGV2/SUMV*4.D0*PI**2
            AVEIR  (NR)=SUMAVIR /SUMV

            call zminmax(YA,NZMINR,ZMIN,ZMINR)
            call zminmax(YA,NZMAXR,ZMAX,ZMAXR)

            RRMIN(NR)=RMIN
            RRMAX(NR)=RMAX
            ZZMIN(NR)=ZMIN
            ZZMAX(NR)=ZMAX
            RZMIN(NR)=ZMINR
            RZMAX(NR)=ZMAXR
            RRPSI(NR)=(RMAX+RMIN)/2.D0
            RSPSI(NR)=(RMAX-RMIN)/2.D0
            ELIPPSI(NR)=(ZMAX-ZMIN)/(2.D0*RSPSI(NR))
            TRIGPSI(NR)=(RRPSI(NR)-(ZMAXR+ZMINR)/2.D0)/RSPSI(NR)
            BBMIN(NR)=BMIN
            BBMAX(NR)=BMAX
!
!        ----- CALCULATE POLOIDAL COORDINATES -----
!
            IF(NTHMAX.GT.0) THEN
               DO N=1,NA
                  XCHI0(N)=2.D0*PI*XA(N)/XA(NA)
                  XCHI1(N)=2.D0*PI*XCHI1(N)/XCHI1(NA)
               ENDDO
               RCHI(NA)=RCHI(1)
               ZCHI(NA)=ZCHI(1)
!
               IF(MDLEQC.EQ.0) THEN
                  CALL SPL1D(XCHI0,RCHI,DXCHI,URCHI,NA,4,IERR)
                  IF(IERR.NE.0) &
                       WRITE(6,*) 'XX SPL1D for RCHI: IERR=',IERR
                  CALL SPL1D(XCHI0,ZCHI,DXCHI,UZCHI,NA,4,IERR)
                  IF(IERR.NE.0) &
                       WRITE(6,*) 'XX SPL1D for ZCHI: IERR=',IERR
               ELSE
                  CALL SPL1D(XCHI1,RCHI,DXCHI,URCHI,NA,4,IERR)
                  IF(IERR.NE.0) &
                       WRITE(6,*) 'XX SPL1D for RCHI: IERR=',IERR
                  CALL SPL1D(XCHI1,ZCHI,DXCHI,UZCHI,NA,4,IERR)
                  IF(IERR.NE.0) &
                       WRITE(6,*) 'XX SPL1D for ZCHI: IERR=',IERR
               ENDIF

               RPS(1,NR)=YA(1,1)
               ZPS(1,NR)=YA(2,1)
               DO NTH=2,NTHMAX+1
                  TH=DTH*(NTH-1)
                  IF(MDLEQC.EQ.0) THEN
                     CALL SPL1DF(TH,RPS(NTH,NR),XCHI0,URCHI,NA,IERR)
                     CALL SPL1DF(TH,ZPS(NTH,NR),XCHI0,UZCHI,NA,IERR)
                  ELSE
                     CALL SPL1DF(TH,RPS(NTH,NR),XCHI1,URCHI,NA,IERR)
                     CALL SPL1DF(TH,ZPS(NTH,NR),XCHI1,UZCHI,NA,IERR)
                  ENDIF
               ENDDO
            ENDIF
         ENDDO
 1000    CONTINUE
!
      ENDIF

!      WRITE(6,'(A,2I5)') 'NRPMAX,NRMAX=',NRPMAX,NRMAX
!      DO NR=1,NRMAX
!         WRITE(6,'(I5,1P3E12.4)') NR,QPS(NR),VPS(NR),RLEN(NR)
!      ENDDO
!
!     ----- CALCULATE TOROIDAL FLUX -----
!
      DO NR=NRPMAX+1,NRMAX
         PSIT(NR)=PSIT(NR-1) &
                 +2.0D0*QPS(NR)*QPS(NR-1)/(QPS(NR)+QPS(NR-1)) &
                          *(PSIP(NR)-PSIP(NR-1))
      ENDDO

      PSITB=PSIT(NRMAX)
      PSIPB=PSIP(NRMAX)

      DO NR=NRPMAX+1,NRMAX
         RST(NR)=SQRT(PSIT(NR)/(PI*BB))
      ENDDO
      RSTB=RST(NRMAX)

      DO NR=NRPMAX+1,NRMAX
         RHOT(NR)=SQRT(PSIT(NR)/PSITA)
      ENDDO

      DO NR=NRPMAX+1,NRMAX
         AVEJPR(NR)=0.D0
         AVEJTR(NR)=0.D0
      ENDDO
!
!      ----- CALCULATE PLASMA SURFACE -----
!
      CALL EQCALF(REDGE,ZAXIS,NSUMAX,RSU,ZSU,IERR)
!
!      +++++ CALCULATE WALL DATA +++++
!
!     FACTOR=(RB+RR-RAXIS)/(REDGE-RAXIS)

      DO NTH=1,NTHMAX
         THW(NTH)=(NTH-1)*2.d0*PI/NTHMAX
         RPSW(NTH)=RPS(NTH,NRMAX)
         ZPSW(NTH)=ZPS(NTH,NRMAX)
!         WRITE(6,'(A,I5,1P3E12.4)')
!     &        'NTH: ',NTH,THW(NTH),RPSW(NTH),ZPSW(NTH)
      ENDDO
      NTH=NTHMAX+1
      THW(NTH)=2.d0*PI
      RPSW(NTH)=RPS(1,NRMAX)
      ZPSW(NTH)=ZPS(1,NRMAX)
!         WRITE(6,'(A,I5,1P5E12.4)')
!     &        'NTH: ',NTH,THW(NTH),RPSW(NTH),ZPSW(NTH)
      CALL SPL1D(THW,RPSW,DRPSW,URPSW,NTHMAX+1,4,IERR)
      CALL SPL1D(THW,ZPSW,DZPSW,UZPSW,NTHMAX+1,4,IERR)
      DO NSU=1,NSUMAX+1
         THWL=(NSU-1)*2.d0*PI/NSUMAX
         CALL SPL1DF(THWL,RSW(NSU),THW,URPSW,NTHMAX+1,IERR)
         CALL SPL1DF(THWL,ZSW(NSU),THW,UZPSW,NTHMAX+1,IERR)
!         WRITE(6,'(A,I5,1P5E12.4)')
!     &        'NSU: ',NSU,THWL,RSU(NSU),ZSU(NSU),RSW(NSU),ZSW(NSU)
      ENDDO

      IF(MDLEQF.LT.10) THEN
         RGMIN=RSW(1)
         RGMAX=RSW(1)
         ZGMIN=ZSW(1)
         ZGMAX=ZSW(1)
         DO NSU=2,NSUMAX
            RGMIN=MIN(RGMIN,RSW(NSU))
            RGMAX=MAX(RGMAX,RSW(NSU))
            ZGMIN=MIN(ZGMIN,ZSW(NSU))
            ZGMAX=MAX(ZGMAX,ZSW(NSU))
         ENDDO
      ENDIF
!      WRITE(6,'(A,I5)') 'MDLEQF=',MDLEQF
!      WRITE(6,'(A,1P4E12.4)') 'RG,ZG=',RGMIN,RGMAX,ZGMIN,ZGMAX

      RETURN
      END
!
!     ***** CALCULATE SPLINES AND INTEGRAL QUANTITIES *****
!
      SUBROUTINE EQSETS(IERR)

      USE libspl1d
      USE libspl2d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(OUT) :: IERR

      DIMENSION DERIV(NRM)
      REAL(rkind),ALLOCATABLE:: D01(:,:),D10(:,:),D11(:,:)
      REAL(rkind) CHIPL

      ALLOCATE(D01(NTHMP,NRM),D10(NTHMP,NRM),D11(NTHMP,NRM))
      ! Defensive zero-init (see PR #123 pattern): libeqapi.so finalize+reinit
      ! cycle can reuse heap chunks with stale values.
      D01 = 0.D0
      D10 = 0.D0
      D11 = 0.D0
!
!      DO NR=1,NRMAX
!         WRITE(6,'(A,I5,1P5E12.4)')
!     &        'NR:',NR,PSIP(NR),PSIT(NR),QPS(NR),TTS(NR),AVEJPR(NR)
!      ENDDO

      IERR=0
      DTH=2.D0*PI/NTHMAX
!
!     *** For functions defined in eqsplf.f ***
!
!      WRITE(6,'(A)') 'PSIP='
!      WRITE(6,'(1P5E12.4)') (PSIP(NR),NR=1,NRMAX)
!      write(6,'(A)') 'psit='
!      write(6,'(1P5E12.4)') (PSIT(NR),NR=1,NRMAX)
      CALL SPL1D(PSIP,PSIT,DERIV,UPSIT,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for PSIT: IERR=',IERR
      CALL SPL1D(PSIT,PSIP,DERIV,UPSIP,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for PSIP: IERR=',IERR
!
!     *** Make spline coefficients to convert F(PSIP) to F(RHOT) ***
!                   where F is an arbitrary function.
!
      CALL SPL1D(PSIP,PPS,DERIV,UPPS,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for PPS: IERR=',IERR
      CALL SPL1D(PSIP,TTS,DERIV,UTTS,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for TTS: IERR=',IERR
      CALL SPL1D(PSIP,QPS,DERIV,UQPS,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for QPS: IERR=',IERR

      CALL SPL1D(PSIP,VPS,DERIV,UVPS,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for VPS: IERR=',IERR
      CALL SPL1D(PSIP,SPS,DERIV,USPS,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for SPS: IERR=',IERR
      CALL SPL1D(PSIP,RLEN,DERIV,URLEN,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for RLEN: IERR=',IERR

      CALL SPL1D(PSIP,RRMIN,DERIV,URRMIN,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for RRMIN: IERR=',IERR
      CALL SPL1D(PSIP,RRMAX,DERIV,URRMAX,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for RRMAX: IERR=',IERR
      CALL SPL1D(PSIP,ZZMIN,DERIV,UZZMIN,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for ZZMIN: IERR=',IERR
      CALL SPL1D(PSIP,ZZMAX,DERIV,UZZMAX,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for ZZMAX: IERR=',IERR
      CALL SPL1D(PSIP,BBMIN,DERIV,UBBMIN,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for BBMIN: IERR=',IERR
      CALL SPL1D(PSIP,BBMAX,DERIV,UBBMAX,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for BBMAX: IERR=',IERR

      CALL SPL1D(PSIP,AVERR ,DERIV,UAVERR ,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for AVERRR: IERR=',IERR
      CALL SPL1D(PSIP,AVERR2,DERIV,UAVERR2,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for AVERRR2: IERR=',IERR
      CALL SPL1D(PSIP,AVEIR2,DERIV,UAVEIR2,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for AVEIR2: IERR=',IERR
      CALL SPL1D(PSIP,AVEBB ,DERIV,UAVEBB ,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for AVEBB: IERR=',IERR
      CALL SPL1D(PSIP,AVEBB2,DERIV,UAVEBB2,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for AVEBB2: IERR=',IERR
      CALL SPL1D(PSIP,AVEIB2,DERIV,UAVEIB2,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for AVEIB2: IERR=',IERR
      CALL SPL1D(PSIP,AVEGV ,DERIV,UAVEGV ,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for AVEGV: IERR=',IERR
      CALL SPL1D(PSIP,AVEGV2,DERIV,UAVEGV2,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for AVEGV2: IERR=',IERR
      CALL SPL1D(PSIP,AVEGVR2,DERIV,UAVEGVR2,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for AVEGVR2: IERR=',IERR
      CALL SPL1D(PSIP,AVEGP2,DERIV,UAVEGP2,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for AVEGP2: IERR=',IERR
      CALL SPL1D(PSIP,AVEJPR,DERIV,UAVEJPR,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for AVEJPR: IERR=',IERR
      CALL SPL1D(PSIP,AVEJTR,DERIV,UAVEJTR,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for AVEJTR: IERR=',IERR
      CALL SPL1D(PSIP,AVEIR ,DERIV,UAVEIR ,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for AVEIR: IERR=',IERR

      CALL SPL1D(PSIP,RRPSI  ,DERIV,URRPSI  ,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for RRPSI: IERR=',IERR
      CALL SPL1D(PSIP,RSPSI  ,DERIV,URSPSI  ,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for RSPSI: IERR=',IERR
      CALL SPL1D(PSIP,ELIPPSI,DERIV,UELIPPSI,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for ELIPPSI: IERR=',IERR
      CALL SPL1D(PSIP,TRIGPSI,DERIV,UTRIGPSI,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for TRIGPSI: IERR=',IERR
      CALL SPL1D(PSIP,DVDPSIP,DERIV,UDVDPSIP,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for DVDPSIP: IERR=',IERR
      CALL SPL1D(PSIP,DVDPSIT,DERIV,UDVDPSIT,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for DVDPSIT: IERR=',IERR
!
!        +++++ CALCULATE DERIVATIVES +++++
!
      DTH=2.D0*PI/NTHMAX
      DO NTH=1,NTHMAX+1
         CHIP(NTH)=DTH*(NTH-1)
      ENDDO

      CALL SPL2D(CHIP,RHOT,RPS,D10,D01,D11,URPS, &
                 NTHMP,NTHMAX+1,NRMAX,4,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL2D for RPS: IERR=',IERR

      CALL SPL2D(CHIP,RHOT,ZPS,D10,D01,D11,UZPS, &
                 NTHMP,NTHMAX+1,NRMAX,4,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL2D for ZPS: IERR=',IERR

      DO NR=1,NRMAX
         RHOTL=RHOT(NR)
!         write(6,'(A,I5,1P3E12.4)') 'NR,RHOT:',NR,RHOTL,RHOTL**2,
!     &        PSITA*RHOTL**2
         QPSL=FNQPS(RHOTL)
         DO NTH=1,NTHMAX+1
            CHIPL=CHIP(NTH)
            CALL SPL2DD(CHIPL,RHOTL,RPSL,DRCHIL,DRRHOL, &
                        CHIP,RHOT,URPS,NTHMP,NTHMAX+1,NRMAX,IERR)
            CALL SPL2DD(CHIPL,RHOTL,ZPSL,DZCHIL,DZRHOL, &
                        CHIP,RHOT,UZPS,NTHMP,NTHMAX+1,NRMAX,IERR)
            DRPSI(NTH,NR)=DRRHOL*QPSL/(2.D0*PSITA)
            DZPSI(NTH,NR)=DZRHOL*QPSL/(2.D0*PSITA)
            DRCHI(NTH,NR)=DRCHIL
            DZCHI(NTH,NR)=DZCHIL
!
!            IF(NR.LE.5) WRITE(6,'(I5,1P4E12.4)')
!     &           NR,DRRHOL,DRPSI(NTH,NR),QPSL,PSITA

            CALL PSIGD(RPSL,ZPSL,DPSIDR,DPSIDZ)
            BPR(NTH,NR)= DPSIDZ/(2.D0*PI*RPSL)
            BPZ(NTH,NR)=-DPSIDR/(2.D0*PI*RPSL)
            BPT(NTH,NR)=SQRT(BPR(NTH,NR)**2+BPZ(NTH,NR)**2)
            BTP(NTH,NR)= TTS(NR)/(2.D0*PI*RPSL)
!
!            IF(NTH.EQ.1) WRITE(6,'(2I3,1P6E12.4)')
!     &           NTH,NR,RPSL,ZPSL,
!     &           BPR(NTH,NR),BPZ(NTH,NR),BPT(NTH,NR),BTP(NTH,NR)

         ENDDO
      ENDDO
!
!        +++++ CALCULATE MAGNETIC FIELD +++++
!
!      DO NR=1,NRMAX,5
!         DO NTH=1,NTHMAX
!            WRITE(6,'(2I5,1P3E12.4)')
!     &           NR,NTH,RPS(NTH,NR),DRPSI(NTH,NR),DRCHI(NTH,NR)
!         ENDDO
!      ENDDO
!
!        +++++ CALCULATE INTEGRATED QUANTITIES +++++
!
!$$$      NDPMAX=100
!$$$      DELPS=-PSI0/NDPMAX
!$$$      PPSL=FNPPS(0.D0)
!$$$      VPSL=FNVPS(0.D0)
!$$$      SPSL=FNSPS(0.D0)
!$$$      SUMV =0.5D0*VPSL*DELPS
!$$$      SUMS =0.5D0*SPSL*DELPS
!$$$      SUMPV=0.5D0*PPSL*VPSL*DELPS
!$$$      SUMPS=0.5D0*PPSL*SPSL*DELPS
!$$$      DO NDP=1,NDPMAX-1
!$$$         PSIL=PSI0+DELPS*NDP
!$$$         PSIN=1.D0-PSIL/PSI0
!$$$         RHON=FNRHON(PSIN)
!$$$         PPSL=FNPPS(RHON)
!$$$         VPSL=FNVPS(RHON)
!$$$         SPSL=FNSPS(RHON)
!$$$         SUMV =SUMV +VPSL*DELPS
!$$$         SUMS =SUMS +SPSL*DELPS
!$$$         SUMPV=SUMPV+PPSL*VPSL*DELPS
!$$$         SUMPS=SUMPS+PPSL*SPSL*DELPS
!$$$      ENDDO
!$$$      PPSL=FNPPS(1.D0)
!$$$      VPSL=FNVPS(1.D0)
!$$$      SPSL=FNSPS(1.D0)
!$$$      SUMV =SUMV +0.5D0*VPSL*DELPS
!$$$      SUMS =SUMS +0.5D0*SPSL*DELPS
!$$$      SUMPV=SUMPV+0.5D0*PPSL*VPSL*DELPS
!$$$      SUMPS=SUMPS+0.5D0*PPSL*SPSL*DELPS
!$$$      PVOL=SUMV
!$$$      PAREA=SUMS
!$$$      RAAVE=SQRT(PAREA/PI)
!$$$      PVAVE=SUMPV/SUMV
!$$$      PSAVE=SUMPS/SUMS
!$$$      BPA=RMU0*RIP*1.D6/FNRLEN(1.D0)
!$$$      BETAT=PVAVE/(BB**2/(2.D0*RMU0))
!$$$      BETAP=PSAVE/(BPA**2/(2.D0*RMU0))
!$$$      QAXIS=FNQPS(0.D0)
!$$$      QSURF=FNQPS(1.D0)

      NDRMAX=100
      DELRHO=1.D0/NDRMAX
      RHON1=0.D0
      RHONH=0.5D0*DELRHO
      RHON2=DELRHO
      PPSL1=FNPPS(RHON1)
      PPSL2=FNPPS(RHON2)
      CALL SPL1DF(FNPSIP(RHONH),DVDRHOL,PSIP,UDVDRHO,NRMAX,IERR)
      SUMV=DVDRHOL*DELRHO ! Volume
      SUMPV=0.5D0*(PPSL1+PPSL2)*DVDRHOL*DELRHO ! Pressure times volume
      CALL SPL1DF(FNPSIP(RHONH),AVEIRL,PSIP,UAVEIR,NRMAX,IERR)
      SUMS=DVDRHOL*AVEIRL*DELRHO ! Cross-section
      DO NDR=1,NDRMAX-1
         RHON1=RHON1+DELRHO
         RHONH=RHONH+DELRHO
         RHON2=RHON2+DELRHO
         PPSL1=FNPPS(RHON1)
         PPSL2=FNPPS(RHON2)
         CALL SPL1DF(FNPSIP(RHONH),DVDRHOL,PSIP,UDVDRHO,NRMAX,IERR)
         SUMV=SUMV+DVDRHOL*DELRHO
         SUMPV=SUMPV+0.5D0*(PPSL1+PPSL2)*DVDRHOL*DELRHO
         CALL SPL1DF(FNPSIP(RHONH),AVEIRL,PSIP,UAVEIR,NRMAX,IERR)
         SUMS=SUMS+DVDRHOL*AVEIRL*DELRHO
      ENDDO

      PVOL =SUMV           ! Volume (or FNVPS(1.D0))
      PAREA=SUMS/(2.D0*PI) ! Cross section
      RAAVE=SQRT(PAREA/PI) ! Minor radius determined by cross section
      PVAVE=SUMPV/PVOL     ! Volume averaged pressure
      BPA=RMU0*RIP*1.D6/FNRLEN(1.D0)   ! Poloidal magnetic field at the separatrix
      BETAT=PVAVE/(BB**2/(2.D0*RMU0))  ! Toroidal beta
      BETAP=PVAVE/(BPA**2/(2.D0*RMU0)) ! Poloidal beta
      QAXIS=FNQPS(0.D0)    ! Safety factor at the magnetic axis
      QSURF=FNQPS(1.D0)    ! Safety factor at the separatrix

      IF(NPRINT.GE.2) THEN
!$$$         WRITE(6,'(A,1P4E12.4)')
!$$$     &        'PVOL,PAREA,PVAVE,PSAVE  =',PVOL,PAREA,PVAVE,PSAVE
         WRITE(6,'(A,1P3E12.4)') &
              'PVOL,PAREA,PVAVE  =',PVOL,PAREA,PVAVE
         WRITE(6,'(A,1P4E12.4)') &
              'BETAT,BETAP,QAXIS,QSURF =',BETAT,BETAP,QAXIS,QSURF
      ENDIF

      RETURN
      END
!
!     ***** Convert flux-surface-averaged quantities with grad V
!             to those with grad rho *****
!
      SUBROUTINE EQSETS_RHO(IERR)

      USE libspl1d
      USE libitp
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(OUT) :: IERR

      dimension DERIV(NRM)

      DO NR = 1, NRMAX
         DVDRHO(NR) = 2.D0 * PSITA * RHOT(NR) * DVDPSIT(NR) ! V'
      ENDDO

      DO NR = 2, NRMAX
         AVEGRR2(NR) = AVEGVR2(NR) / DVDRHO(NR)**2 ! <|grad rho|^2/R^2>
         AVEGR  (NR) = AVEGV(NR)   / DVDRHO(NR)    ! <|grad rho|>
         AVEGR2 (NR) = AVEGV2(NR)  / DVDRHO(NR)**2 ! <|grad rho|^2>
      ENDDO
      AVEGRR2(1) = FCTR(RHOT(2),RHOT(3),AVEGRR2(2),AVEGRR2(3))
      AVEGR  (1) = FCTR(RHOT(2),RHOT(3),AVEGR  (2),AVEGR  (3))
      AVEGR2 (1) = FCTR(RHOT(2),RHOT(3),AVEGR2 (2),AVEGR2 (3))

      CALL SPL1D(PSIP,DVDRHO ,DERIV,UDVDRHO ,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for DVDRHO: IERR=',IERR
      CALL SPL1D(PSIP,AVEGRR2,DERIV,UAVEGRR2,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for AVEGRR2: IERR=',IERR
      CALL SPL1D(PSIP,AVEGR  ,DERIV,UAVEGR  ,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for AVEGR: IERR=',IERR
      CALL SPL1D(PSIP,AVEGR2 ,DERIV,UAVEGR2 ,NRMAX,0,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for AVEGR2: IERR=',IERR

      RETURN
      END
!
!     ***** CALCULATE FLUX SURFACE *****
!
      SUBROUTINE EQCALF(RINIT,ZINIT,NTHUMAX,RU,ZU,IERR)

      USE libspl1d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind), INTENT(IN)  :: RINIT, ZINIT
      INTEGER,     INTENT(IN)  :: NTHUMAX
      REAL(rkind), INTENT(OUT) :: RU(NTHUMAX+1), ZU(NTHUMAX+1)
      INTEGER,     INTENT(OUT) :: IERR

      DIMENSION XA(NTVM),YA(2,NTVM)
      DIMENSION RCHI(NTVM),ZCHI(NTVM),DXCHI(NTVM)
      DIMENSION URCHI(4,NTVM),UZCHI(4,NTVM)

      IERR=0
      DTH=2.D0*PI/NTHUMAX
!
!     ----- SET NUMBER OF DIVISION for integration -----
!

      NMAX=200
      IF(NMAX.GT.NTVM) NMAX=NTVM
!
!     ----- CALCULATE PSIP, PSIT, PPS, TTS, RPS and ZPS -----
!     -----              on magnetic surfaces           -----
!
      CALL EQMAGS(RINIT,ZINIT,NMAX,XA,YA,NA,IERR)

      FACTOR=2.D0*PI/XA(NA)
      RCHI(1)=RINIT
      ZCHI(1)=ZINIT
      XA(1)=FACTOR*XA(1)
      DO N=2,NA-1
         RCHI(N)=YA(1,N)
         ZCHI(N)=YA(2,N)
         XA(N)=FACTOR*XA(N)
      ENDDO
      RCHI(NA)=RCHI(1)
      ZCHI(NA)=ZCHI(1)
      XA(NA)=FACTOR*XA(NA)

      CALL SPL1D(XA,RCHI,DXCHI,URCHI,NA,4,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for RCHI: IERR=',IERR
      CALL SPL1D(XA,ZCHI,DXCHI,UZCHI,NA,4,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for ZCHI: IERR=',IERR

      RU(1)=RINIT
      ZU(1)=ZINIT
      DO NTH=2,NTHUMAX
         TH=DTH*(NTH-1)
         CALL SPL1DF(TH,RU(NTH),XA,URCHI,NA,IERR)
         CALL SPL1DF(TH,ZU(NTH),XA,UZCHI,NA,IERR)
      ENDDO
      RU(NTHUMAX+1)=RINIT
      ZU(NTHUMAX+1)=ZINIT

      RETURN
      END
!
!     ***** INTERPOLATE FUNCTION OF PP(PSIP) *****
!
      FUNCTION PPFUNC(PSIPL)

      USE libspl1d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind), INTENT(IN) :: PSIPL

      IF(PSIPL.GT.PSIPS(NPSMAX)) THEN
         PPFUNC=0.D0
         RETURN
      END IF
      CALL SPL1DF(PSIPL,PPL,PSIPS,UPPPS,NPSMAX,IERR)
      IF(IERR.NE.0) THEN
         WRITE(6,*) 'XX PPFUNC: SPL1DF ERROR : IERR=',IERR
         WRITE(6,*) PSIPL,PSIPS(1),PSIPS(NPSMAX)
      ENDIF
      PPFUNC=PPL
      RETURN
      END
!
!     ***** INTERPOLATE FUNCTION OF TT(PSIP) *****
!
      FUNCTION TTFUNC(PSIPL)

      USE libspl1d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind), INTENT(IN) :: PSIPL

      IF(PSIPL.GT.PSIPS(NPSMAX)) THEN
         CALL SPL1DF(PSIPS(NPSMAX),TTL,PSIPS,UTTPS,NPSMAX,IERR)
         TTFUNC=TTL
         RETURN
      END IF
      CALL SPL1DF(PSIPL,TTL,PSIPS,UTTPS,NPSMAX,IERR)
      IF(IERR.NE.0) WRITE(6,*) 'XX TTFUNC: SPL1DF ERROR : IERR=',IERR
      TTFUNC=TTL
      RETURN
      END
!
!     ***** INTERPOLATE FUNCTION OF PP(PSIP) *****
!
      FUNCTION DPPFUNC(PSIPL)

      USE libspl1d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind), INTENT(IN) :: PSIPL

      IF(PSIPL.GT.PSIPS(NPSMAX)) THEN
         IF(MODELG.EQ.5) THEN
            CALL SPL1DF(PSIPS(NPSMAX),DPPL,PSIPS,UDPPPS,NPSMAX,IERR)
         ELSE
            CALL SPL1DD(PSIPS(NPSMAX),PPL,DPPL,PSIPS,UPPPS,NPSMAX,IERR)
         END IF
         DPPFUNC=DPPL
         RETURN
      END IF
      IF(MODELG.EQ.5) THEN
         CALL SPL1DF(PSIPL,DPPL,PSIPS,UDPPPS,NPSMAX,IERR)
         IF(IERR.NE.0)WRITE(6,*) 'XX DPPFUNC: SPL1DF ERROR : IERR=',IERR
         DPPFUNC=DPPL
       ELSE
         CALL SPL1DD(PSIPL,PPL,DPPL,PSIPS,UPPPS,NPSMAX,IERR)
         IF(IERR.NE.0) THEN
            WRITE(6,*) 'XX DPPFUNC: SPL1DD ERROR : IERR=',IERR
            WRITE(6,*) PSIPL,PSIPS(1),PSIPS(NPSMAX)
         ENDIF
         DPPFUNC=DPPL
      ENDIF
      RETURN
      END
!
!     ***** INTERPOLATE FUNCTION OF TT(PSIP) *****
!
      FUNCTION DTTFUNC(PSIPL)

      USE libspl1d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      REAL(rkind), INTENT(IN) :: PSIPL

      IF(PSIPL.GT.PSIPS(NPSMAX)) THEN
         IF(MODELG.EQ.5) THEN
            CALL SPL1DF(PSIPS(NPSMAX),DTTL,PSIPS,UDTTPS,NPSMAX,IERR)
         ELSE
            CALL SPL1DD(PSIPS(NPSMAX),TTL,DTTL,PSIPS,UTTPS,NPSMAX,IERR)
         END IF
         DTTFUNC=DTTL
         RETURN
      END IF
      IF(MODELG.EQ.5) THEN
         CALL SPL1DF(PSIPL,DTTL,PSIPS,UDTTPS,NPSMAX,IERR)
         IF(IERR.NE.0)WRITE(6,*) 'XX DTTFUNC: SPL1DF ERROR : IERR=',IERR
         DTTFUNC=DTTL
      ELSE
         CALL SPL1DD(PSIPL,TTL,DTTL,PSIPS,UTTPS,NPSMAX,IERR)
         IF(IERR.NE.0)WRITE(6,*) 'XX DTTFUNC: SPL1DD ERROR : IERR=',IERR
         DTTFUNC=DTTL
      ENDIF
      RETURN
      END


!     ------ calculate zmin and zmax -----
!                assume: z=a(r-r0)^2+z0
!       Input : ya(1, n) : R(psi)
!               ya(2, n) : Z(psi)
!               n        : poloidal index
!       Output: z0, r0

      subroutine zminmax(ya,n,z0,r0)

      USE bpsd_kinds,ONLY: rkind
      implicit none
      real(rkind),dimension(2,*),intent(in):: ya
      integer,intent(in):: n
      real(rkind),intent(out):: z0,r0
      real(rkind):: r1,r2,r3,z1,z2,z3,dz1,dz2,ra1,ra2,a

      r1=ya(1,n-1)
      z1=ya(2,n-1)
      r2=ya(1,n)
      z2=ya(2,n)
      r3=ya(1,n+1)
      z3=ya(2,n+1)
      dz1=(z1-z2)/(r1-r2)
      dz2=(z2-z3)/(r2-r3)
      ra1=0.5d0*(r1+r2)
      ra2=0.5d0*(r2+r3)

      r0=(ra2*dz1-ra1*dz2)/(dz1-dz2)
      a=dz2/(ra2-r0)
      z0=z2-0.5d0*a*(r2-r0)**2
      return
      end subroutine zminmax
