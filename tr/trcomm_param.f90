MODULE trcomm_param
!     ****** NAMELIST INPUT PARAMETERS ******
! TRPRM / TRMDL
  USE TRCOM0, ONLY: rkind, NSMM
  USE trcomm_const, ONLY: NPSCM
  IMPLICIT NONE
  PUBLIC

!     ****** PARAMETERS ******
! TRPRM
  REAL(rkind)   :: &
       RR, RA, RKAP, RDLT, BB, RIPS, RIPE, RIPSS, PHIA, PNC, PNFE, PNNU, &
       PNNUS, PROFN1, PROFN2, PROFT1, PROFT2, PROFU1, PROFU2, &
       PROFNU1, PROFNU2, PROFJ1, &
       PROFJ2, AD0, AV0, CNP, CNH, CDP, CDH, CNN, CWEB, DT, EPSLTR, &
       CHP, CK0, CK1, CKALFA, CKBETA, CKGUMA, CNB, CALF, CSPRS, TSST, &
       SYNCABS, SYNCSELF
  REAL(rkind), DIMENSION(6) :: &
       ALP
  REAL(rkind), DIMENSION(8) :: &
       CDW
  REAL(rkind), DIMENSION(NSMM) :: &
       PA,PZ,PN,PNS,PT,PTS,PU,PUS
  INTEGER, DIMENSION(NSMM) :: &
       NPA
  INTEGER:: &
       LMAXTR, MDLKAI, MDLETA, MDLAD, MDLAVK, MDLKNC, MDLTPF, &
       NTMAX, NTSTEP, NGTSTP, NGRSTP, NGPST, MODELG,MDLDSK,MDTC, &
       MDLPR

!     ****** MODEL PARAMETERS ******
! TRMDL
  REAL(rkind)   :: &
       TPRST, PBSCD, &
       PNBTOT, PNBR0, PNBRW, PNBCD, PNBVY, PNBVW, PNBENG, PNBRTG, &
       PECTOT, PECR0, PECRW, PECCD, PECTOE, PECNPR, &
       PLHTOT, PLHR0, PLHRW, PLHCD, PLHTOE, PLHNPR, &
       PICTOT, PICR0, PICRW, PICCD, PICTOE, PICNPR, &
       PELTOT, PELR0, PELRW, PELRAD, PELVEL, PELTIM, &
       pellet_time_start,pellet_time_interval, &
       ELMWID, ELMDUR, &
! L-7b-i: external user-supplied driven current (Gaussian profile, MA).
! Distinct from PLHCD/PECCD/PICCD: bypasses TRCDEF efficiency model — the
! given current is injected directly with a Gaussian radial shape rather
! than computed from RF wave power × efficiency.
       EXTERNAL_DRIVEN_I, EXTERNAL_DRIVEN_R0, EXTERNAL_DRIVEN_RW
  INTEGER:: &
       number_of_pellet_repeat
  REAL(rkind), DIMENSION(NSMM) :: &
       PELPAT, ELMNRD, ELMTRD, ELMENH
  REAL(rkind), DIMENSION(NPSCM) :: &
       PSCTOT,PSCR0,PSCRW
  INTEGER, DIMENSION(NPSCM) :: &
       NSPSC
  INTEGER:: &
       MDLNB, MDLEC, MDLLH, MDLIC, MDLCD, MDLPEL, MDLJBS, MDLST, MDLNF, &
       IZERO, MDLELM, MDLPSC, NPSCMAX, MDLIMP, NRNBMAX

END MODULE trcomm_param
