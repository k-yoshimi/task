!     $Id$
!
! Phase F-3 (MED tier): free-form F90 conversion of eqinit.f.
! Initialization routines for TASK/EQ (EQINIT, EQPARM, EQNLIN,
! EQPLST, EQCHEK, EQVIEW). Preserves exact numerical semantics of
! the original fixed-form source.
!
! NOTE: IMPLICIT NONE is NOT added here because the INCLUDEd shim
!       'eqcomm.inc' already supplies an IMPLICIT statement
!       (IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)) and USEs the
!       F-1 MODULEs (eqcom0/1_mod) for the COMMON symbols.
!
!     ****** DEFAULT PARAMETERS ******
!
      SUBROUTINE EQINIT

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
!      INCLUDE '../pl/plcnst.inc'
!
!     ======( DEVICE PARAMETERS )======
!
!        RR    : Plasma major radius                             (m)
!        RA    : Plasma minor radius                             (m)
!        RB    : Wall minor radius                               (m)
!        RKAP  : Plasma shape elongation
!        RDLT  : Plasma shape triangularity *
!        BB    : Magnetic field at center                        (T)
!        Q0    : Safety factor at center
!        QA    : Safety factor on plasma surface
!        RIP   : Plasma current                                 (MA)
!        FRBIN : (RB_inside-RA)/(RB_outside-RA)
!
      RR    = 3.D0
      RA    = 1.D0
      RB    = 1.2D0
      RKAP  = 1.D0
      RDLT  = 0.D0

      BB    = 3.D0
      Q0    = 1.D0
      QA    = 3.D0
      RIP   = 3.D0

      FRBIN = 1.D0
      RBRA  = RB/RA
!
!     ======( MODEL PARAMETERS )======
!
!        MODELG: Control plasma geometry model
!                   0: Slab geometry
!                   1: Cylindrical geometry
!                   2: Toroidal geometry
!                   3: TASK/EQ output geometry
!                   4: VMEC output geometry
!                   5: EQDSK output geometry
!                   6: Boozer output geometry
!        MODELN: Control plasma profile
!                   0: Calculated from PN,PNS,PTPR,PTPP,PTS,PU,PUS; 0 in SOL
!                   1: Calculated from PN,PNS,PTPR,PTPP,PTS,PU,PUS; PNS in SOL
!                   7: Read from file by means of WMDPRF routine (DIII-D)
!                   8: Read from file by means of WMXPRF routine (JT-60)
!                   9: Read from file KNAMTR (TASK/TR)
!        MODELQ: Control safety factor profile (for MODELG=0,1,2)
!                   0: Parabolic q profile (Q0,QA,RHOMIN,RHOITB)
!                   1: Given current profile (RIP,PROFJ0,PROFJ1,PROFJ2)
!
      MODELG= 2
      MODELN= 0
      MODELQ= 0
!
!        RHOMIN: rho at minimum q (0 for positive shear)
!        QMIN  : q minimum for reversed shear
!        RHOEDG: rho at EDGE for smoothing (1 for no smooth)
!
      RHOMIN = 0.D0
      QMIN   = 1.5D0
      RHOEDG = 1.D0
!
!     ======( GRAPHIC PARAMETERS )======
!
!        RHOGMN: minimum rho in radial profile
!        RHOGMX: maximum rho in radial profile
!
      RHOGMN = 0.D0
      RHOGMX = 1.D0
!
!     ======( MODEL PARAMETERS )======
!
!        KNAMEQ: Filename of equilibrium data
!        KNAMWR: Filename of ray tracing data
!        KNAMWM: Filename of full wave data
!        KNAMFP: Filename of Fokker-Planck data
!        KNAMFO: Filename of File output
!        KNAMPF: Filename of profile data
!        KNAMEQ2:Filename of addisional equilibrium data
!
      KNAMEQ = 'eqdata'
      KNAMWR = 'wrdata'
      KNAMWM = 'wmdata'
      KNAMFP = 'fpdata'
      KNAMFO = 'fodata'
      KNAMPF = 'pfdata'
      KNAMEQ2= 'eqdata2'

      NRMAXPL= 100
      NSMAXPL= NSMAX

      IDEBUG = 0
!
!     *** PROFILE PARAMETERS ***
!
!        PP0   : Plasma pressure (main component)              (MPa)
!        PP1   : Plasma pressure (sub component)               (MPa)
!        PP2   : Plasma pressure (increment within ITB)        (MPa)
!        PROFP0: Pressure profile parameter
!        PROFP1: Pressure profile parameter
!        PROFP2: Pressure profile parameter
!
!        PPSI=PP0*(1.D0-PSIN**PROFR0)**PROFP0
!    &       +PP1*(1.D0-PSIN**PROFR1)**PROFP1
!    &       +PP2*(1.D0-(PSIN/PSIITB)**PROFR2)**PROFP2
!
!        The third term exists for RHO < RHOITB
!
      PP0    = 0.001D0
      PP1    = 0.0D0
      PP2    = 0.0D0
      PROFP0 = 1.5D0
      PROFP1 = 1.5D0
      PROFP2 = 2.0D0
!
!        PJ0   : Current density at R=RR (main component) : Fixed to 1
!        PJ1   : Current density at R=RR (sub component)       (arb)
!        PJ2   : Current density at R=RR (sub component)       (arb)
!        PROFJ0: Current density profile parameter
!        PROFJ1: Current density profile parameter
!        PROFJ2: Current density profile parameter
!
!      HJPSI=-PJ0*(1.D0-PSIN**PROFR0)**PROFJ0
!     &                *PSIN**(PROFR0-1.D0)
!     &      -PJ1*(1.D0-PSIN**PROFR1)**PROFJ1
!     &                *PSIN**(PROFR1-1.D0)
!     &      -PJ2*(1.D0-PSIN**PROFR2)**PROFJ2
!     &                *PSIN**(PROFR2-1.D0)
!
!        The third term exists for RHO < RHOITB
!
      PJ0    = 1.00D0
      PJ1    = 0.0D0
      PJ2    = 0.0D0
      PROFJ0 = 1.5D0
      PROFJ1 = 1.5D0
      PROFJ2 = 1.5D0
!
!        FF0   : Current density at R=RR (main component) : Fixed to 1
!        FF1   : Current density at R=RR (sub component)       (arb)
!        FF2   : Current density at R=RR (sub component)       (arb)
!        PROFF0: Current density profile parameter
!        PROFF1: Current density profile parameter
!        PROFF2: Current density profile parameter
!
!      FPSI=BB*RR
!     &      +FF0*(1.D0-PSIN**PROFR0)**PROFF0
!     &      +FF1*(1.D0-PSIN**PROFR1)**PROFF1
!     &      +FF2*(1.D0-PSIN**PROFR2)**PROFF2
!
!        The third term exists for RHO < RHOITB
!
      FF0    = 1.0D0
      FF1    = 0.0D0
      FF2    = 0.0D0
      PROFF0 = 1.5D0
      PROFF1 = 1.5D0
      PROFF2 = 1.5D0
!
!        PT0   : Plasma temperature (main component)           (keV)
!        PT1   : Plasma temperature (sub component)            (keV)
!        PT2   : Plasma temperature (increment within ITB)     (keV)
!        PTSEQ : Plasma temperature (at surface)               (keV)
!        PROFTP0: Temperature profile parameter
!        PROFTP1: Temperature profile parameter
!        PROFTP2: Temperature profile parameter
!
!        TPSI=PTSEQ+(PT0-PTSEQ)*(1.D0-PSIN**PROFR0)**PROFTP0
!    &       +PT1*(1.D0-PSIN**PROFR1)**PROFTP1
!    &       +PT2*(1.D0-PSIN/PSIITB)**PROFR2)**PROFTP2
!    &       +PTSEQ
!
!        The third term exits for RHO < RHOITB
!
      PT0    = 1.0D0
      PT1    = 0.0D0
      PT2    = 0.0D0
      PTSEQ  = 0.05D0

      PROFTP0 = 1.5D0
      PROFTP1 = 1.5D0
      PROFTP2 = 2.0D0
!----
!        PV0   : Toroidal rotation (main component)              (m/s)
!        PV1   : Toroidal rotation (sub component)               (m/s)
!        PV2   : Toroidal rotation (increment within ITB)        (m/s)
!        PROFV0: Velocity profile parameter
!        PROFV1: Velocity profile parameter
!        PROFV2: Velocity profile parameter
!
!        PVSI=PV0*(1.D0-PSIN**PROFR0)**PROFV0
!    &       +PV1*(1.D0-PSIN**PROFR1)**PROFV1
!    &       +PV2*(1.D0-(PSIN/PSIITB)**PROFR2)**PROFV2
!
!        The third term exits for RHO < RHOITB
!
      PV0    = 0.0D0
      PV1    = 0.0D0
      PV2    = 0.0D0
      PROFV0 = 1.5D0
      PROFV1 = 1.5D0
      PROFV2 = 2.0D0
!
!        PN0EQ : Plasma number density(constant)
!
      PN0EQ  = 1.D20
!
!        PROFR0: Profile parameter
!        PROFR1: Profile parameter
!        PROFR2: Profile parameter
!        RHOITB: Normalized radius SQRT(PSI/PSIA) at ITB
!
      PROFR0 = 1.D0
      PROFR1 = 2.D0
      PROFR2 = 2.D0
!
!        OTC   : Constant OMEGA**2/TPSI
!        HM    : Constant                                       (Am)
!
      OTC = 0.15D0
      HM  = 1.D6
!
!     *** MESH PARAMETERS ***
!
!        NSGMAX: Number of radial mesh points for Grad-Shafranov eq.
!        NTGMAX: Number of poloidal mesh points for Grad-Shafranov eq.
!        NUGMAX: Number of radial mesh points for flux-average quantities
!        NRGMAX: Number of horizontal mesh points in R-Z plane
!        NZGMAX: Number of vertical mesh points in R-Z plane
!        NPSMAX: Number of flux surfaces
!        NRMAX : Number of radial mesh points for flux coordinates
!        NTHMAX: Number of poloidal mesh points for flux coordinates
!        NSUMAX: Number of boundary points
!        NRVMAX: Number of radial mesh of surface average
!        NTVMAX: Number of poloidal mesh for surface average
!
      NSGMAX = 32
      NTGMAX = 32
      NUGMAX = 32

      NRGMAX = 33
      NZGMAX = 33
      NPSMAX = 21

      NRMAX  = 50
      NTHMAX = 64
      NSUMAX = 65

      NRVMAX = 50
      NTVMAX = 200
!
!     *** CONTROL PARAMETERS ***
!
!        EPSEQ  : Convergence criterion for equilibrium
!        NLPMAX : Maximum iteration number of EQ
!        EPSNW  : Convergence criterion for newton method
!        DELNW  : Increment for derivative in newton method
!        NLPNW  : Maximum iteration number in newton method
!
      EPSEQ  = 1.D-6
      NLPMAX = 20
      EPSNW  = 1.D-2
      DELNW  = 1.D-2
      NLPNW  = 20
!
!        MDLEQF : Profile parameter
!            0: given analytic profile  P,J_tor,T,Vph + Ip
!            1: given analytic profile  P,F           + Ip
!            2: given analytic profile  P,J_para      + Ip
!            3: given analytic profile  P,J_para
!            4: given analytic profile  P,q
!            5: given spline profile    P,J_tor,T,Vph + Ip
!            6: given spline profile    P,F           + Ip
!            7: given spline profile    P,J_para      + Ip
!            8: given spline profile    P,J_para
!            9: given spline profile    P,q
!
      MDLEQF = 0
!
!        MDLEQA : Rho in P(rho), F(rho), q(rho),...
!            0: SQRT(PSIP/PSIPA)
!            1: SQRT(PSIT/PSITA)
!
      MDLEQA = 0
!
!        MDLEQC : Poloidal coordinate parameter
!            0: Poloidal length coordinate
!            1: Boozer coordinate
!
      MDLEQC = 0
!
!        MDLEQX : Free boundary calculation
!            0: Given PSIB and RIPFC
!            1: PSIB adjusted after loop for given RR,RA,RKAP,RDLT
!            2: PSIB adjusted eqch loop for given RR,RA,RKAP,RDLT
!
      MDLEQX = 0
!
!        MDLEQV : Order of extrapolation of psi in the vacuum region
!                 if positive, wall is linearly extended from plasma surface
!                 if negative, wall is extraporated by polynomials
!
      MDLEQV = 3
!
!        NPRINT: Level print out
!            0: no print
!            1: print first and last loop
!            2: print all loop
!
      NPRINT= 0
!
!        RGMIN: Minimum R of computation region [m]
!        RGMAX: Maxmum  R of computation region [m]
!        ZGMIN: Minimum Z of computation region [m]
!        ZGMAX: Maxmum  Z of computation region [m]
!        ZLIMP: Position of upper X points
!        ZLIMM: Position of lower X points
!
      RGMIN = 1.5D0
      RGMAX = 4.5D0
      ZGMIN =-2.0D0
      ZGMAX = 2.0D0
      ZLIMM =-2.5D0
      ZLIMP = 2.5D0
!
!        PSIB(0:5): Multipole moments of poloidal flux PSIRZ on boundary
!
      PSIB(0) =  2.0D0
      PSIB(1) =  0.5D0
      PSIB(2) =  0.D0
      PSIB(3) =  0.D0
      PSIB(4) =  0.D0
      PSIB(5) =  0.D0
!
!        NPFCMAX : Number of poloidal field coils (PFXs)
!        RIPFC(NPFC) : PFC coil current    [MA]
!        RPFC(NPFC)  : PFC coil position R [m]
!        ZPFC(NPFC)  : PFC coil position Z [m]
!        WPFC(NPFC)  : PFC coil width      [m]
!
      NPFCMAX = 0
      DO NPFC=1,NPFCM
         RIPFC(NPFC) = 0.D0
         RPFC(NPFC)  = 3.D0
         ZPFC(NPFC)  =-1.75D0
         WPFC(NPFC)  = 0.75D0
      ENDDO

      MODEFW=0 ! dangerous setting
      MODEFR=0 ! dangerous setting

      RETURN
      END SUBROUTINE EQINIT
!
!     ****** FINALIZE EQ MODULE STATE ******
!
!     Issue #110: reset SAVE-state guards in eqbpsd so a subsequent
!     EQINIT-cycle re-zeroes the bpsd descriptors. Called from
!     `wrx_api_finalize` (and sister `*_api_finalize` shims) to break
!     the state-leak that caused suite-level SEGV in
!     test_reinit_divergence.
!
!     This is intentionally minimal — eq has no heap allocations to
!     free, just SAVE flags that need rearming for the next init cycle.
!
      SUBROUTINE EQFINI
      USE eqbpsd, ONLY: eq_bpsd_reset
      IMPLICIT NONE
      CALL eq_bpsd_reset
      RETURN
      END SUBROUTINE EQFINI
!
!     ****** INPUT PARAMETERS ******
!
      SUBROUTINE EQPARM(MODE,KIN,IERR)
!
!     MODE=0 : standard namelist input
!     MODE=1 : namelist file input
!     MODE=2 : namelist line input
!
!     IERR=0 : normal end
!     IERR=1 : namelist standard input error
!     IERR=2 : namelist file does not exist
!     IERR=3 : namelist file open error
!     IERR=4 : namelist file read error
!     IERR=5 : namelist file abormal end of file
!     IERR=6 : namelist line input error
!     IERR=7 : unknown MODE
!     IERR=10X : input parameter out of range
!
      USE libkio
      INTEGER,          INTENT(IN)    :: MODE
      CHARACTER(LEN=*), INTENT(IN)    :: KIN
      INTEGER,          INTENT(OUT)   :: IERR
      EXTERNAL EQNLIN,EQPLST

    1 CALL TASK_PARM(MODE,'EQ',KIN,EQNLIN,EQPLST,IERR)
      IF(IERR.NE.0) RETURN

      CALL EQCHEK(IERR)
      IF(MODE.EQ.0.AND.IERR.NE.0) GOTO 1
      IF(IERR.NE.0) IERR=IERR+100

      RETURN
      END SUBROUTINE EQPARM
!
!     ****** INPUT NAMELIST ******
!
      SUBROUTINE EQNLIN(NID,IST,IERR)

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(IN)  :: NID
      INTEGER, INTENT(OUT) :: IST, IERR

      NAMELIST /EQ/ RR,RA,RB,RKAP,RDLT,BB,Q0,QA,RIP, &
                    RHOMIN,QMIN,MODELG,MODELQ,RHOITB, &
                    IDEBUG,KNAMEQ,KNAMEQ2, &
                    PP0,PP1,PP2,PROFP0,PROFP1,PROFP2, &
                    FF0,FF1,FF2,PROFF0,PROFF1,PROFF2, &
                    PJ0,PJ1,PJ2,PROFJ0,PROFJ1,PROFJ2, &
                    PT0,PT1,PT2,PROFTP0,PROFTP1,PROFTP2,PTSEQ, &
                    PV0,PV1,PV2,PROFV0,PROFV1,PROFV2,PN0EQ, &
                    PROFR0,PROFR1,PROFR2,EPSEQ,NLPMAX, &
                    NSGMAX,NTGMAX,NUGMAX,EPSNW,DELNW,NLPNW, &
                    NRGMAX,NZGMAX,RGMIN,RGMAX,ZGMIN,ZGMAX,ZLIMP,ZLIMM, &
                    NPSMAX,NRVMAX,NTVMAX,NRMAX,NTHMAX,NSUMAX, &
                    MODEFR,MODEFW, &
                    MDLEQF,MDLEQC,MDLEQA,MDLEQX,MDLEQV,NPRINT, &
                    PSIB,NPFCMAX,RIPFC,RPFC,ZPFC,WPFC,FRBIN

      READ(NID,EQ,IOSTAT=IST,ERR=9800,END=9900)
      RBRA=RB/RA
      IERR=0
      RETURN

 9800 IERR=8
      WRITE(6,*) 'XX READ EQPARM ERROR: IST=',IST
      RETURN
 9900 IERR=9
      RETURN
      END SUBROUTINE EQNLIN
!
!     ***** INPUT PARAMETER LIST *****
!
      SUBROUTINE EQPLST

      WRITE(6,601)
      RETURN

  601 FORMAT(' ','# &EQ : RR,RA,RB,RKAP,RDLT,BB,Q0,QA,RIP'/ &
             9X,'RHOMIN,QMIN,MODELG,MODELQ,RHOITB,'/ &
             9X,'IDEBUG,KNAMEQ,KNAMEQ2,'/ &
             9X,'PP0,PP1,PP2,PROFP0,PROFP1,PROFP2'/ &
             9X,'FF0,FF1,FF2,PROFF0,PROFF1,PROFF2'/ &
             9X,'PJ0,PJ1,PJ2,PROFJ0,PROFJ1,PROFJ2'/ &
             9X,'PT0,PT1,PT2,PROFTP0,PROFTP1,PROFTP2,PTSEQ'/ &
             9X,'PV0,PV1,PV2,PROFV0,PROFV1,PROFV2,PN0EQ,HM'/ &
             9X,'PROFR0,PROFR1,PROFR2'/ &
             9X,'NSGMAX,NTGMAX,NUGMAX,NRGMAX,NZGMAX,NPSMAX'/ &
             9X,'NRMAX,NTHMAX,NSUMAX,NRVMAX,NTVMAX'/ &
             9X,'MDLEQF,MDLEQC,MDLEQA,MDLEQX,MDLEQV,NPRINT'/ &
             9X,'EPSEQ,NLPMAX,EPSNW,DELNW,NLPNW'/ &
             9X,'RGMIN,RGMAX,RZMIN,RZMAX,ZLIMP,ZLIMM'/ &
             9X,'MODEFR,MODEFW,'/ &
             9X,'PSIB,NPFCMAX,RIPFC,RPFC,ZPFC,WPFC,FRBIN')
      END SUBROUTINE EQPLST
!
!     ***** CHECK INPUT PARAMETERS *****
!
      SUBROUTINE EQCHEK(IERR)
!
!     Phase F-1: read eqcom2 / eqcom3 state via the new F90 MODULEs so
!     we share memory with all other shim consumers. A raw INCLUDE of
!     eqcom2.inc / eqcom3.inc here would declare COMMON blocks that
!     are disjoint from the MODULE SAVE storage, silently desyncing
!     EQCHEK from eqcalc / eqcalq / etc.
      USE eqcom2_mod
      USE eqcom3_mod
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)
      INTEGER, INTENT(OUT) :: IERR

      IERR=0

      IF(NSGMAX.GT.NSGM) THEN
         WRITE(6,'(A,I8,I8)') 'XX EQCHEK: NSGMAX.GT.NSGM: ',NSGMAX,NSGM
         IERR=1
      ENDIF
      IF(NTGMAX.GT.NTGM) THEN
         WRITE(6,'(A,I8,I8)') 'XX EQCHEK: NTGMAX.GT.NTGM: ',NTGMAX,NTGM
         IERR=2
      ENDIF
      IF(NUGMAX.GT.NUGM) THEN
         WRITE(6,'(A,I8,I8)') 'XX EQCHEK: NUGMAX.GT.NUGM: ',NUGMAX,NUGM
         IERR=2
      ENDIF
      IF(NRGMAX.GT.NRGM) THEN
         WRITE(6,'(A,I8,I8)') 'XX EQCHEK: NRGMAX.GT.NRGM: ',NRGMAX,NRGM
         IERR=3
      ENDIF
      IF(NZGMAX.GT.NZGM) THEN
         WRITE(6,'(A,I8,I8)') 'XX EQCHEK: NZGMAX.GT.NZGM: ',NRGMAX,NRGM
         IERR=4
      ENDIF
      IF(NPSMAX.GT.NPSM) THEN
         WRITE(6,'(A,I8,I8)') 'XX EQCHEK: NPSMAX.GT.NPSM: ',NPSMAX,NPSM
         IERR=5
      ENDIF
      IF(NRMAX.GT.NRM) THEN
         WRITE(6,'(A,I8,I8)') 'XX EQCHEK: NRMAX.GT.NRM: ',NRMAX,NRM
         IERR=6
      ENDIF
      IF(NTHMAX.GT.NTHM) THEN
         WRITE(6,'(A,I8,I8)') 'XX EQCHEK: NTHMAX.GT.NTHM: ',NTHMAX,NTHM
         IERR=7
      ENDIF
      IF(NSUMAX.GT.NSUM) THEN
         WRITE(6,'(A,I8,I8)') 'XX EQCHEK: NSUMAX.GT.NSUM: ',NSUMAX,NSUM
         IERR=8
      ENDIF
      IF(NRVMAX.GT.NRVM) THEN
         WRITE(6,'(A,I8,I8)') 'XX EQCHEK: NRVMAX.GT.NRVM: ',NRVMAX,NRVM
         IERR=9
      ENDIF
      IF(NTVMAX.GT.NTVM) THEN
         WRITE(6,'(A,I8,I8)') 'XX EQCHEK: NTVMAX.GT.NTVM: ',NTVMAX,NTVM
         IERR=10
      ENDIF

      IF(RB.LT.RA) THEN
         WRITE(6,'(A,1P2E12.4)') &
              '!! RB.LT.RA: set RB=RA: RA,RB=',RA,RB
         RB=RA
      ENDIF

      RETURN
      END SUBROUTINE EQCHEK
!
!     ****** SHOW PARAMETERS ******
!
      SUBROUTINE EQVIEW

      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)

      WRITE(6,601) 'RR    ',RR, &
                   'RA    ',RA, &
                   'RKAP  ',RKAP, &
                   'RDLT  ',RDLT
      WRITE(6,601) 'BB    ',BB, &
                   'RIP   ',RIP, &
                   'Q0    ',Q0, &
                   'QA    ',QA
      WRITE(6,601) 'RHOMIN',RHOMIN, &
                   'QMIN  ',QMIN, &
                   'RB    ',RB
      WRITE(6,601) 'RGMIN ',RGMIN, &
                   'RGMAX ',RGMAX, &
                   'ZGMIN ',ZGMIN, &
                   'ZGMAX ',ZGMAX
      WRITE(6,601) 'ZLIMP ',ZLIMP, &
                   'ZLIMM ',ZLIMM, &
                   'FRBIN ',FRBIN
      WRITE(6,601) 'PP0   ',PP0, &
                   'PROFP0',PROFP0, &
                   'PJ0   ',PJ0, &
                   'PROFJ0',PROFJ0
      WRITE(6,601) 'PP1   ',PP1, &
                   'PROFP1',PROFP1, &
                   'PJ1   ',PJ1, &
                   'PROFJ1',PROFJ1
      WRITE(6,601) 'FF0   ',FF0, &
                   'PROFF0',PROFF0
      WRITE(6,601) 'FF1   ',FF1, &
                   'PROFF1',PROFF1
      WRITE(6,601) 'FF2   ',FF2, &
                   'PROFF2',PROFF2
      WRITE(6,601) 'PT0   ',PT0, &
                   'PROFT0',PROFTP0, &
                   'PV0   ',PV0, &
                   'PROFV0',PROFV0
      WRITE(6,601) 'PT1   ',PT1, &
                   'PROFT1',PROFTP1, &
                   'PV1   ',PV1, &
                   'PROFV1',PROFV1
      WRITE(6,601) 'PT2   ',PT2, &
                   'PROFT2',PROFTP2, &
                   'PV2   ',PV2, &
                   'PROFV2',PROFV2
      WRITE(6,601) 'PTSEQ ',PTSEQ, &
                   'PN0EQ ',PN0EQ
      WRITE(6,601) 'PROFR0',PROFR0, &
                   'PROFR1',PROFR1, &
                   'PROFR2',PROFR2
      WRITE(6,601) 'EPSEQ ',EPSEQ, &
                   'EPSNW ',EPSNW, &
                   'DELNW ',DELNW
      IF(MDLEQF.GE.10.AND.MDLEQF.LT.20) THEN
         WRITE(6,601) 'PSIB:0',PSIB(0), &
                      'PSIB:1',PSIB(1), &
                      'PSIB:2',PSIB(2), &
                      'PSIB:3',PSIB(3)
         WRITE(6,604) &
              (NPFC,RIPFC(NPFC),RPFC(NPFC),ZPFC(NPFC),WPFC(NPFC), &
               NPFC=1,NPFCMAX)
      ENDIF
      WRITE(6,602) 'NSGMAX',NSGMAX, &
                   'NTGMAX',NTGMAX, &
                   'NUGMAX',NUGMAX, &
                   'MODELG',MODELG
      WRITE(6,602) 'NRGMAX',NRGMAX, &
                   'NZGMAX',NZGMAX, &
                   'NRVMAX',NRVMAX, &
                   'NTVMAX',NTVMAX
      WRITE(6,602) 'NRMAX ',NRMAX, &
                   'NTHMAX',NTHMAX, &
                   'NPSMAX',NPSMAX, &
                   'NSUMAX',NSUMAX
      WRITE(6,602) 'MDLEQF',MDLEQF, &
                   'MDLEQC',MDLEQC, &
                   'MDLEQA',MDLEQA, &
                   'MODELQ',MODELQ
      WRITE(6,602) 'MDLEQX',MDLEQX, &
                   'MDLEQV',MDLEQV, &
                   'MODEFR',MODEFR, &
                   'MDDEFW',MODEFW
      WRITE(6,602) 'NPRINT',NPRINT, &
                   'NLPMAX',NLPMAX, &
                   'NLPNW ',NLPNW

      RETURN
  601 FORMAT(4(A6,'=',1PE11.2:2X))
  602 FORMAT(4(A6,'=',I7:6X))
!  603 FORMAT(4(A6,'=',I7:6X))
  604 FORMAT(' NPFC ','RIPFC ',6X,'RPFC  ',6X,'ZPFC  ',6X,'WPFC'/ &
             (I6,1P4E12.4))
      END SUBROUTINE EQVIEW
