! Phase F-4 (HIGH tier): free-form F90 conversion of eq-eqdsk.f.
! EQDSK file reader (subroutine EQDSKR). Preserves exact numerical
! semantics of the original fixed-form source.
!
! NOTE: IMPLICIT NONE is NOT added here because the INCLUDEd shim
!       '../eq/eqcomc.inc' already supplies an IMPLICIT statement
!       (IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)) and USEs the
!       F-1 MODULEs (eqcom0/1/2_mod) for the COMMON symbols.
!
!     ***** READ EQDSK FORMAT FILE *****
!
      SUBROUTINE EQDSKR(IERR)

      USE libfio
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(OUT) :: IERR

      character case(6)*10
      dimension rlim(NSUM),zlim(NSUM),pressw(NPSM),pwprim(NPSM), &
                dmion(NSUM),rhovn(NSUM),ajtor(NPSM)

      neqdsk=21
      CALL FROPEN(neqdsk,KNAMEQ,1,MODEFR,'EQ',IERR)
      IF(IERR.NE.0) RETURN
!
      REWIND(neqdsk)
      read (neqdsk,2000) (case(i),i=1,6),idum,NRGMAX,NZGMAX
      NPSMAX=NRGMAX
      read (neqdsk,2020) rdim,zdim,Rctr,rleft,zmid
      DR=rdim/(NRGMAX-1)
      DZ=zdim/(NZGMAX-1)
      DO NRG=1,NRGMAX
         RG(NRG)=rleft+DR*(NRG-1)
      ENDDO
      DO NZG=1,NZGMAX
         ZG(NZG)=zmid-0.5D0*zdim+DZ*(NZG-1)
      ENDDO
      read (neqdsk,2020) RAXIS,ZAXIS,PSI0,PSIA,Bctr
!
      PSI0=2.D0*PI*PSI0
      PSIA=2.D0*PI*PSIA
!
      DPS=(PSIA-PSI0)/(NPSMAX-1)
      PSI0=PSI0-PSIA
      PSIPA=-PSI0
      DO NPS=1,NPSMAX
         PSIPS(NPS)=DPS*(NPS-1)
      ENDDO
      read (neqdsk,2020) RIP,simag,xdum,rmaxis,xdum
      RIP=RIP/1.D6
      read (neqdsk,2020) zmaxis,xdum,sibry,xdum,xdum
      read (neqdsk,2020) (TTPS(i),i=1,NPSMAX)
      read (neqdsk,2020) (PPPS(i),i=1,NPSMAX)
      WRITE(6,'(5ES12.4)') (PPPS(i),i=1,NPSMAX)
      read (neqdsk,2020) (TTDTTPS(i),i=1,NPSMAX)
      read (neqdsk,2020) (DPPPS(i),i=1,NPSMAX)
      read (neqdsk,2020) ((PSIRZ(i,j),i=1,NRGMAX),j=1,NZGMAX)
      read (neqdsk,2020) (QQPS(i),i=1,NPSMAX)
      read (neqdsk,2022) NSUMAX,limitr
      read (neqdsk,2020) (RSU(i),ZSU(i),i=1,NSUMAX)
      read (neqdsk,2020) (rlim(i),zlim(i),i=1,limitr)
!
      RSUMAX = RSU(1)
      RSUMIN = RSU(1)
      ZSUMAX = ZSU(1)
      ZSUMIN = ZSU(1)
      R_ZSUMAX = RSU(1)
      R_ZSUMIN = RSU(1)
      do i = 2, nsumax
         if(RSU(i) .GT. RSUMAX) RSUMAX = RSU(i)
         if(RSU(i) .LT. RSUMIN) RSUMIN = RSU(i)
         if(ZSU(i) .GT. ZSUMAX) then
            ZSUMAX   = ZSU(i)
            R_ZSUMAX = RSU(i)
         end if
         if(ZSU(i) .LT. ZSUMIN) then
            ZSUMIN   = ZSU(i)
            R_ZSUMIN = RSU(i)
         end if
      enddo
      WRITE(6,'(A,1P5E12.4)') 'RR:',RR,RSUMIN,RSUMAX
! for negative Ip and negative BB
      IF(RIP.LT.0.D0) RIP=-RIP
      IF(Bctr.LT.0.D0) Bctr=-Bctr
      IF(TTPS(1).LT.0.D0) THEN
         DO NPS=1,NPSMAX
            TTPS(NPS)=-TTPS(NPS)
         ENDDO
      ENDIF

! *** The following variable defined in Tokamaks 3rd, Sec. 14.14 ***
      RR   = 0.5d0 * (RSUMAX + RSUMIN)
      RA   = 0.5d0 * (RSUMAX - RSUMIN)
      !==  RB: wall minor radius  ======================
      !    Multiplication factor 1.1 is tentatively set.
      RB   = 1.1d0 * RA
!      RB   = 1.2d0 * RA
      !=================================================
      RKAP = (ZSUMAX - ZSUMIN) / (RSUMAX - RSUMIN)

!  ---- corrected on 2010/01/18 for negative triangularity ----
!      RDLT = 0.5d0 * (ABS(RR-R_ZSUMIN) + ABS(RR-R_ZSUMAX)) / RA

      RDLT = 0.5d0 * ((RR-R_ZSUMIN) + (RR-R_ZSUMAX)) / RA
      BB   = Bctr*Rctr/RR
      RIPX = RIP
!
!      GOTO 1000
!      kvtor=0
!      rvtor=0
!      nmass=0
!      read (neqdsk,2024,end=1000) kvtor,rvtor,nmass
!      WRITE(6,*) kvtor,rvtor,nmass
!      if (kvtor.gt.0) then
!         read (neqdsk,2020) (pressw(i),i=1,NPSMAX)
!         read (neqdsk,2020) (pwprim(i),i=1,NPSMAX)
!      endif
!      if (nmass.gt.0) then
!         read (neqdsk,2020) (dmion(i),i=1,NPSMAX)
!      endif
!      read (neqdsk,2020,end=1000) (rhovn(i),i=1,NPSMAX)
! 1000 CONTINUE
!
      REWIND(neqdsk)
      CLOSE(neqdsk)
!      write (6,'(I5,1PE12.4)') (i,QQPS(i),i=1,NPSMAX)
!
!      WRITE(6,'(1P3E12.4)') RR,BB,RIP
!      WRITE(6,'(1P4E12.4)') RAXIS,ZAXIS,PSI0,PSIA
!      WRITE(6,'(1P4E12.4)') RG(1),RG(2),RG(NRGMAX-1),RG(NRGMAX)
!      WRITE(6,'(1P4E12.4)') ZG(1),ZG(2),ZG(NZGMAX-1),ZG(NZGMAX)
!      WRITE(6,'(1P4E12.4)') PSIPS(1),PSIPS(2),
!     &                      PSIPS(NPSMAX-1),PSIPS(NPSMAX)
!
      DO NZG=1,NZGMAX
         DO NRG=1,NRGMAX
            PSIRZ(NRG,NZG)=2.D0*PI*PSIRZ(NRG,NZG)-PSIA
         ENDDO
      ENDDO
      DO i=1,NPSMAX
         TTPS(i)   =2.D0*PI*TTPS(i)
         TTDTTPS(i)=4.D0*PI**2*TTDTTPS(i)
         DTTPS(i)  =TTDTTPS(i)/TTPS(i)
!honda         write(6,*) PSIPS(i),QQPS(i)
      ENDDO
!
      DO NZG=1,NZGMAX
      DO NRG=1,NRGMAX
         HJTRZ(NRG,NZG)=0.D0
      ENDDO
      ENDDO
!
!     ** Simplified check for Toroidal current and parallel current **
!
!$$$      DO i=1,NPSMAX
!$$$         write(6,*) PSIPS(i),
!$$$     &              -RR*DPPPS(i)-TTDTTPS(i)/(4.D0*PI**2*RR*RMU0),
!$$$     &              (-TTPS(i)*DPPPS(i)/BB-DTTPS(i)*BB/RMU0)/(2.D0*PI)
!$$$      ENDDO
!
      return
!
 2000 format (6a8,3i4)
 2020 format (5e16.9)
 2022 format (2i5)
! 2024 format (i5,e16.9,i5)
       end
