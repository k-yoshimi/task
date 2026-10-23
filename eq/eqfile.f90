!     $Id$
!
! Phase F-4 (HIGH tier): free-form F90 conversion of eqfile.f.
! TASK/EQ file I/O dispatcher (EQSAVE / EQLOAD / EQ_READ / EQRTSK /
! EQMETRIC / read_rppl / draw_cross). Preserves exact numerical /
! file-format semantics of the original fixed-form source.
!
! NOTE on EXTERNAL: EQRTSK passes the local EQFBND function to FBRENT.
!   FBRENT (libbrent) provides an explicit INTERFACE for its callback
!   argument, so the existing EXTERNAL EQFBND declaration is sufficient
!   to satisfy the interface check. Migrating to PROCEDURE POINTER would
!   require restructuring how EQFBND shares state through the EQ shim
!   (it relies on the COMMON-derived ZBRF, RDLT, RKAP); we keep EXTERNAL
!   here to avoid the refactor and any numerical drift. (Documented for
!   Phase F-5 cleanup.)
!
! NOTE: IMPLICIT NONE is NOT added at file level because the INCLUDEd
!       shims '../eq/eqcomc.inc' / '../eq/eqcomq.inc' supply an IMPLICIT
!       statement (IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)) and USE
!       the F-1 MODULEs for COMMON symbols.
!
!     ***** SAVE TASK/EQ DATA *****
!
!     EQSAVE is the entry it always was, without an argument: the S
!     command of the EQ menu calls it (and tr/f77/trfile.f, which no
!     Makefile builds, with an argument it never took). EQSAVE_IERR does
!     the work and returns the outcome; the C API (eq_save) calls it.
!
      SUBROUTINE EQSAVE

      CALL EQSAVE_IERR(IERR)
      RETURN
      END
!
      SUBROUTINE EQSAVE_IERR(IERR_OUT)

      USE libfio
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      CHARACTER(LEN=256) :: KFNAME

!     IERR_OUT: 0 when the file was opened and written; FWOPEN's IERR (1
!     to 8) when it refused the file; 9 when the file was opened and a
!     WRITE or the CLOSE reported an error, or the file is shorter than
!     what was written to the unit (#227 item 3). After a 9 what is at
!     the path is left as it is. It cannot be taken for the equilibrium
!     that was to be saved (usually it is a short file) and must not be
!     loaded: EQRTSK does not guard its READs. A caller cannot tell success from failure by
!     looking for the file afterwards: a repeat save to a path that
!     already holds a previous, non-empty file looks identical.
      IERR_OUT=0
      CALL FWOPEN(21,KNAMEQ,0,MODEFW,'EQ',IERR)
      IF(IERR.NE.0) THEN
         IERR_OUT=IERR
         RETURN
      ENDIF

      REWIND(21)
!     FWOPEN opens an existing file with STATUS='OLD' and no ACTION: a file
!     without write permission is then opened for reading, FWOPEN returns 0,
!     and it is this first WRITE that fails.
      WRITE(21,IOSTAT=IST) RR,BB,RIP
      IF(IST.NE.0) THEN
         WRITE(6,*) 'XX EQSAVE: FILE CANNOT BE WRITTEN: IOSTAT = ',IST
         CLOSE(21,IOSTAT=IST)
         IERR_OUT=9
         RETURN
      ENDIF
      WRITE(21,ERR=900) NRGMAX,NZGMAX
      WRITE(21,ERR=900) (RG(NRG),NRG=1,NRGMAX)
      WRITE(21,ERR=900) (ZG(NZG),NZG=1,NZGMAX)
      WRITE(21,ERR=900) ((PSIRZ(NRG,NZG),NRG=1,NRGMAX),NZG=1,NZGMAX)
      WRITE(21,ERR=900) NPSMAX
      WRITE(21,ERR=900) (PSIPS(NPS),NPS=1,NPSMAX)
      WRITE(21,ERR=900) (PPPS(NPS),NPS=1,NPSMAX)
      WRITE(21,ERR=900) (TTPS(NPS),NPS=1,NPSMAX)
      WRITE(21,ERR=900) (TEPS(NPS),NPS=1,NPSMAX)
      WRITE(21,ERR=900) (OMPS(NPS),NPS=1,NPSMAX)

      WRITE(21,ERR=900) NSGMAX,NTGMAX,NUGMAX,NRMAX,NTHMAX,NSUMAX,NRVMAX,NTVMAX
      WRITE(21,ERR=900) ((PSI(NSG,NTG),NSG=1,NSGMAX),NTG=1,NTGMAX)
      WRITE(21,ERR=900) ((DELPSI(NSG,NTG),NSG=1,NSGMAX),NTG=1,NTGMAX)
      WRITE(21,ERR=900) ((HJT(NSG,NTG),NSG=1,NSGMAX),NTG=1,NTGMAX)
      WRITE(21,ERR=900) RAXIS,ZAXIS,PSITA,PSIPA,PSI0
      WRITE(21,ERR=900) (PSIPNV(NRV),NRV=1,NRVMAX)
      WRITE(21,ERR=900) (PSIPV(NRV),NRV=1,NRVMAX)
      WRITE(21,ERR=900) (PSITV(NRV),NRV=1,NRVMAX)
      WRITE(21,ERR=900) (QPV(NRV),NRV=1,NRVMAX)
      WRITE(21,ERR=900) (TTV(NRV),NRV=1,NRVMAX)
      WRITE(21,ERR=900) RA,RKAP,RDLT,RB,FRBIN
      WRITE(21,ERR=900) PJ0,PJ1,PJ2,PROFJ0,PROFJ1,PROFJ2
      WRITE(21,ERR=900) PP0,PP1,PP2,PROFP0,PROFP1,PROFP2
      WRITE(21,ERR=900) PT0,PT1,PT2,PROFTP0,PROFTP1,PROFTP2
      WRITE(21,ERR=900) PV0,PV1,PV2,PROFV0,PROFV1,PROFV2
      WRITE(21,ERR=900) PROFR0,PROFR1,PROFR2
!      WRITE(21) PTS,PN0,HM
      WRITE(21,ERR=900) ((HJTRZ(NRG,NZG),NRG=1,NRGMAX),NZG=1,NZGMAX)

!     A write the system refuses is not always reported. Measured with
!     gfortran 15 on macOS and a file size limit of 16 to 20000 bytes,
!     with nothing, an empty file or a file of 8 to 45956 bytes at the
!     path: the first WRITE returned an error under the 16-byte limit
!     over a file that was not empty, and in every other case the WRITEs
!     and the CLOSE returned 0 over a short file. So the length written
!     to the unit is compared with the length of the file after the
!     CLOSE. The name is asked of the unit: with MODEFW 4 to 7
!     FWOPEN opens the name it read, not KNAMEQ. A file that is not a
!     regular file (a device) has length 0 and is reported short as well.
!     When either length cannot be had (-1) the comparison is left out.
      NSIZEW=-1
      INQUIRE(UNIT=21,NAME=KFNAME,SIZE=NSIZEW)
      CLOSE(21,ERR=900)
      IF(NSIZEW.GE.0) THEN
         NSIZEF=-1
         INQUIRE(FILE=KFNAME,SIZE=NSIZEF)
         IF(NSIZEF.GE.0.AND.NSIZEF.LT.NSIZEW) THEN
            WRITE(6,*) 'XX EQSAVE: FILE IS SHORTER THAN WRITTEN: ', &
                       NSIZEF,' OF ',NSIZEW,' BYTES'
            IERR_OUT=9
            RETURN
         ENDIF
      ENDIF

!      WRITE(6,*) 'HJTRZ=',HJTRZ(10,10)

      WRITE(6,*) '# DATA WAS SUCCESSFULLY SAVED TO THE FILE.'

      RETURN

  900 WRITE(6,*) 'XX EQSAVE: FILE WRITE ERROR'
      CLOSE(21,IOSTAT=IST)
      IERR_OUT=9
      RETURN
      END
!
!     ***** LOAD EQUILIBRIUM DATA *****
!
      SUBROUTINE EQLOAD(MODELG1,KNAMEQ1,IERR)

      USE eqbpsd
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER,         INTENT(IN)  :: MODELG1
      CHARACTER(LEN=80),INTENT(IN) :: KNAMEQ1
      INTEGER,         INTENT(OUT) :: IERR

      MODELG=MODELG1
      KNAMEQ=KNAMEQ1
      CALL EQ_READ(IERR)
      RETURN
      END
!
!     ***** LOAD EQUILIBRIUM DATA *****
!
      SUBROUTINE EQ_READ(IERR)

      USE equread,ONLY: eqdsk
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(OUT) :: IERR

      IERR=0
      IF(MODELG.EQ.3.OR.MODELG.EQ.9) THEN
         CALL EQRTSK(IERR)
      ELSEIF(MODELG.EQ.5.OR.MODELG.EQ.25) THEN
         CALL EQDSKR(IERR)
!        Keep EQDSKR's error: EQCALQ would reset IERR and report a
!        failed load (e.g. a missing file) as success.
         IF(IERR.EQ.0) CALL EQCALQ(IERR)
      ELSEIF(MODELG.EQ.8) THEN
         CALL EQJAEAR(IERR)
      ELSEIF(MODELG.EQ.15) THEN
         CALL EQDSK
      ELSE
         WRITE(6,*) 'XX EQLOAD: UNKNOWN MODELG: MODELG=',MODELG
         IERR=1
      ENDIF

      RETURN
      END
!
!     ***** LOAD TASK/EQ DATA *****
!
      SUBROUTINE EQRTSK(IERR)

      USE libfio
      USE libbrent
      USE libspl1d
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(OUT) :: IERR
      DIMENSION DERIV(NRVM)
      EXTERNAL EQFBND

      CALL FROPEN(21,KNAMEQ,0,MODEFR,'EQ',IERR)
      IF(IERR.NE.0) RETURN

      READ(21) RR,BB,RIP
      READ(21) NRGMAX,NZGMAX
      READ(21) (RG(NRG),NRG=1,NRGMAX)
      READ(21) (ZG(NZG),NZG=1,NZGMAX)
      READ(21) ((PSIRZ(NRG,NZG),NRG=1,NRGMAX),NZG=1,NZGMAX)
      READ(21) NPSMAX
      READ(21) (PSIPS(NPS),NPS=1,NPSMAX)
      READ(21) (PPPS(NPS),NPS=1,NPSMAX)
      READ(21) (TTPS(NPS),NPS=1,NPSMAX)
      READ(21) (TEPS(NPS),NPS=1,NPSMAX)
      READ(21) (OMPS(NPS),NPS=1,NPSMAX)

      READ(21) NSGMAX,NTGMAX,NUGMAX,NRMAX,NTHMAX,NSUMAX,NRVMAX,NTVMAX
      READ(21) ((PSI(NTG,NSG),NTG=1,NTGMAX),NSG=1,NSGMAX)
      READ(21) ((DELPSI(NTG,NSG),NTG=1,NTGMAX),NSG=1,NSGMAX)
      READ(21) ((HJT(NTG,NSG),NTG=1,NTGMAX),NSG=1,NSGMAX)
      READ(21) RAXIS,ZAXIS,PSITA,PSIPA,PSI0
      READ(21) (PSIPNV(NRV),NRV=1,NRVMAX)
      READ(21) (PSIPV(NRV),NRV=1,NRVMAX)
      READ(21) (PSITV(NRV),NRV=1,NRVMAX)
      READ(21) (QPV(NRV),NRV=1,NRVMAX)
      READ(21) (TTV(NRV),NRV=1,NRVMAX)
      READ(21) RA,RKAP,RDLT,RB,FRBIN
      READ(21) PJ0,PJ1,PJ2,PROFJ0,PROFJ1,PROFJ2
      READ(21) PP0,PP1,PP2,PROFP0,PROFP1,PROFP2
      READ(21) PT0,PT1,PT2,PROFTP0,PROFTP1,PROFTP2
      READ(21) PV0,PV1,PV2,PROFV0,PROFV1,PROFV2
      READ(21) PROFR0,PROFR1,PROFR2
!      READ(21) PTS,PN0,HM
      READ(21,ERR=1000) ((HJTRZ(NRG,NZG),NRG=1,NRGMAX),NZG=1,NZGMAX)

      CALL EQMESH
      EPSZ=1.D-8
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

      GOTO 1001
 1000 CONTINUE
         DO NZG=1,NZGMAX
         DO NRG=1,NRGMAX
            HJTRZ(NRG,NZG)=0.D0
         ENDDO
         ENDDO
 1001 CONTINUE
!
      CLOSE(21)
      RIPX=RIP

      IF(MODELG.EQ.9) THEN
         CALL EQMESH
         CALL SPL1D(PSIPNV,PSITV,DERIV,UPSITV,NRVMAX,0,IERR)
         IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for PSITV: IERR=',IERR
         CALL SPL1D(PSIPNV,QPV,DERIV,UQPV,NRVMAX,0,IERR)
         IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for QPV: IERR=',IERR
         CALL SPL1D(PSIPNV,TTV,DERIV,UTTV,NRVMAX,0,IERR)
         IF(IERR.NE.0) WRITE(6,*) 'XX SPL1D for TTV: IERR=',IERR
         CALL EQDEFB
!         DO NSG=1,NSGMAX
!            WRITE(6,'(A,I5)') 'PSI NSG=',NSG
!            WRITE(6,'(1P5E12.4)') (PSI(NTG,NSG),NTG=1,NTGMAX)
!         ENDDO
!         DO NSG=1,NSGMAX
!            WRITE(6,'(A,I5)') 'HJT NSG=',NSG
!            WRITE(6,'(1P5E12.4)') (HJT(NTG,NSG),NTG=1,NTGMAX)
!         ENDDO
!         WRITE(6,'(A,I5,1P4E12.4)')
!     &        ('NV:',NV,PSIPNV(NV),PSITV(NV),QPV(NV),TTV(NV),
!     &         NV=1,NRVMAX)
      ENDIF
!
!     WRITE(6,*) 'HJTRZ=',HJTRZ(10,10)

      RETURN
      END
!
!     ***** SAVE METRICS *****
!
      SUBROUTINE EQMETRIC(IERR)

      USE libspl1d
      USE libfio
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(OUT) :: IERR

      character KNAMET*80
      data KNAMET /'eq_metric.dat'/

      nmetric=21
      CALL FWOPEN(nmetric,KNAMET,1,MODEFW,'EQ',IERR)
      IF(IERR.NE.0) RETURN

      REWIND(nmetric)
      WRITE(nmetric,'(A,2X,A,6X,A,8X,A,3X,A)') '#','rho_tor','dV/drho', &
           '<1/R^2>',"<|grad rho|^2/R^2>"
      DO NR = 1, NRPMAX
         CALL SPL1DF(FNPSIP(RHOT(NR)),DAT1,PSIP,UDVDRHO ,NRMAX,IERR)
         WRITE(nmetric,'(1X,F10.7,1P3E15.7)') RHOT(NR),DAT1, &
              fnavir2(rhot(nr)),fnavgrr2(nr)
      ENDDO
      WRITE(nmetric,'(80X)')
      WRITE(nmetric,'(A,2X,A,3X,A,3X,A,5X,A,9X,A)') '#','rho_tor', &
           "<|grad rho|>","<|grad rho|^2>","<B^2>","<1/B^2>"
      WRITE(nmetric,'(1X,0PF10.7,1P4E15.7)') (RHOT(NR), &
           fnavgr(rhot(nr)),fnavgr2(rhot(nr)), &
           fnavbb2(rhot(nr)),fnavib2(rhot(nr)),NR=1,NRPMAX)
      CLOSE(nmetric)

      WRITE(6,*) '# METRIC DATA WAS SUCCESSFULLY SAVED TO "', &
                 KNAMET(1:13),'".'

      RETURN
      END
!
!     ***** READ RIPPLE CONTOUR DATA FROM OFMC ****
!
      subroutine read_rppl(ierr)

      USE libfio
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom3_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(OUT) :: ierr

      character kfile*20, kline*130

      kfile='ripple.profile'
      nrppl=21
      CALL FROPEN(nrppl,kfile,1,MODEFR,'EQ',IERR)
      IF(IERR.NE.0) RETURN
!
      rewind(nrppl)
!
!     *** R-coordinates ***
      idx = 0
      do
         if(idx == 0) then
            read(nrppl,'(A130)',iostat=ist) kline
            if(index(kline,"R-coordinate") /= 0) then ! detect the start position of the data chunk
               idx = 1
            end if
            cycle
         end if
!
         read(nrppl,'(1x,10e13.5)') (Rrp(i),i=1,NRrpM)
         exit
      end do
!
!     *** Z-coordinates ***
      idx = 0
      do
         if(idx == 0) then
            read(nrppl,'(A130)',iostat=ist) kline
            if(index(kline,"Z-coordinate") /= 0) then ! detect the start position of the data chunk
               idx = 1
            end if
            cycle
         end if
!
         read(nrppl,'(1x,10e13.5)') (Zrp(i),i=1,NZrpM)
         exit
      end do
!
!     *** Ripple contour ***
      idx = 0
      j   = 0
      do
         if(idx == 0) then
            read(nrppl,'(A130)',iostat=ist) kline
            if(index(kline,"at") /= 0) then ! detect the start position of the data chunk
               idx = 1
               j = j + 1
            end if
            cycle
         end if
!
         read(nrppl,'(1x,10e13.5)') (RpplRZ(i,j),i=1,NRrpM)
         idx = 0
         if(j == NZrpM) then
            exit
         else
            cycle
         end if
      end do
!
      close(nrppl)
!
      return
      end

      SUBROUTINE draw_cross(x,y,len)
      USE bpsd_kinds,ONLY: rkind
      IMPLICIT NONE
      REAL(rkind),INTENT(IN):: x,y,len
      INTERFACE
         FUNCTION GUCLIP(x)
            USE bpsd_kinds,ONLY: rkind
            REAL(rkind),INTENT(IN):: x
            REAL:: GUCLIP
         END FUNCTION GUCLIP
      END INTERFACE

      CALL MOVE2D(GUCLIP(x-0.5D0*len),GUCLIP(y))
      CALL DRAW2D(GUCLIP(x+0.5D0*len),GUCLIP(y))
      CALL MOVE2D(GUCLIP(x),GUCLIP(y-0.5D0*len))
      CALL DRAW2D(GUCLIP(x),GUCLIP(y+0.5D0*len))
      RETURN
      END
