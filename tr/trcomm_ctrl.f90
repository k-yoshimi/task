MODULE trcomm_ctrl
!     ****** CONTROL VARIABLES ******
!TRCTL / TRMDS / TRNAM / TRCOM2 / TRUFL / TRLPCK
  USE TRCOM0, ONLY: rkind, NSTM, NEQM
  IMPLICIT NONE
  PUBLIC

! TRCTL
  REAL   :: &
       GTCPU1
  REAL(rkind)   :: &
       T, TST, TPRE, WPPRE, RIP, DR, FKAP, RHOA, RIPA, VSEC, RDPS,DIPDT
  REAL(rkind), DIMENSION(:),ALLOCATABLE :: & ! (NSTM)
       PNSS
  INTEGER:: &
       NT, NRAMAX, NROMAX, NREDGE, NTMAX_SAVE, IREAD
  INTEGER:: &
       icount_of_pellet ! 0 : before start
                        ! positive: number of pellet from t_start

! TRADD (control part: iteration counter)
  INTEGER                      :: NTEQIT

!     ****** MODEL SELECTION VARIABLES ******
! TRMDS
  REAL(rkind)     :: SUMPBM
  INTEGER  :: &
       NEQMAX, MDLEQB, MDLEQN, MDLEQT, MDLEQU, MDLEQZ, MDLEQ0, MDLEQE, &
       MDLEOI, NSCMAX, NSTMAX, MDLWLD, MDDIAG, MDDW, MDLFLX, MDLER, MDCD05, &
       MDEDGE
  INTEGER, DIMENSION(:)  ,ALLOCATABLE :: & ! (NEQM)
       NSS, NSV, NNS, NST
  INTEGER, DIMENSION(:,:),ALLOCATABLE :: & ! (0:NSTM,0:3)
       NEA

!     ****** LOG FILE NAME ******
! TRNAM
  CHARACTER(LEN=80) :: KNAMEQ,KNAMEQ2,KNAMTR,KFNLOG,KFNTXT,KFNCVS
! TRCOM2
  CHARACTER(LEN=80) :: KXNDEV,KXNDCG,KXNID
  CHARACTER(LEN=80) :: KDIRW1,KDIRW2

!     ****** UFILE CONTROL ******
! TRUFL
  REAL(rkind)    :: TIME_INT
  INTEGER :: MDLXP,MDLUF,MODEP,MDNI,MDCURT,MDNM1,MDLJQ,MDPHIA,NTS
  CHARACTER(LEN=80) :: KUFDIR,KUFDEV,KUFDCG
!     ****** LAPACK ******
! TRLPCK
  INTEGER :: MDLPCK

CONTAINS

  SUBROUTINE allocate_trcomm_ctrl(ierr)
    USE TRCOM0, ONLY: NSTM, NEQMAXM
    INTEGER, INTENT(OUT) :: ierr
    ierr = 0

    ALLOCATE(PNSS(NSTM),STAT=ierr)
      IF(ierr /= 0) RETURN
    ! Zero-init PNSS: when NSMAX < NSM (e.g. tst2 has NSMAX=2 but the
    ! turbulence/adhoc coefficient code hard-codes the species loop bound
    ! NSM=4 in tr/trcom0.f90:11), tr_prof_impurity (trprof.f90:314) only
    ! sets PNSS(1), PNSS(2:NSMAX), PNSS(7), PNSS(8) -- leaving the slots
    ! PNSS(NSMAX+1 .. NSM) untouched. trcoef_turbulence.f90:170-171
    ! then reads PNSS(3) / PNSS(4), getting machine-dependent garbage
    ! that cascades to NaN in ALPHA -> AKDWEL -> AK -> RT. The Phase-0
    ! tr2 binary masks this because its fresh-process heap is zero;
    ! libtrapi.so loaded after Python+numpy mallocs sees non-zero
    ! patterns and produces NaN in test_tst2.
    PNSS(:) = 0.D0
    ALLOCATE(NSS(NEQMAXM),NSV(NEQMAXM),NNS(NEQMAXM),NST(NEQMAXM),STAT=ierr)
      IF(ierr /= 0) RETURN
    ALLOCATE(NEA(0:NSTM,0:3),STAT=ierr)
      IF(ierr /= 0) RETURN

    ! Defensive zero-init (see PR #119/#121/#123 pattern): libtrapi.so
    ! finalize+reinit cycle can reuse heap chunks with stale values.
    ! TR_EQS_SELECT (trprep.f90:196-199) writes NSS/NSV(1:NEQMAXM)=-1
    ! and NNS/NST(1:NEQMAXM)=0, and NEA(0:NSTM,0:3)=0 on every call, so
    ! zero-init here is strictly redundant for the binary path — but
    ! TR_EQS_SELECT runs after ALLOCATE_TRCOMM, and the integer fields
    ! are inspected by intermediate code paths (MDDIAG conditionals in
    ! tr_prep that walk the indices). Defensive zero-init guarantees
    ! the ALLOCATED->read window holds a consistent state.
    NSS(:) = 0
    NSV(:) = 0
    NNS(:) = 0
    NST(:) = 0
    NEA(:,:) = 0
  END SUBROUTINE allocate_trcomm_ctrl

  SUBROUTINE deallocate_trcomm_ctrl
    DEALLOCATE(PNSS)
    DEALLOCATE(NSS,NSV,NNS,NST,NEA)
  END SUBROUTINE deallocate_trcomm_ctrl

  SUBROUTINE deallocate_err_trcomm_ctrl
    IF(ALLOCATED(PNSS)) DEALLOCATE(PNSS)
    IF(ALLOCATED(NSS )) DEALLOCATE(NSS )
    IF(ALLOCATED(NSV )) DEALLOCATE(NSV )
    IF(ALLOCATED(NNS )) DEALLOCATE(NNS )
    IF(ALLOCATED(NST )) DEALLOCATE(NST )
    IF(ALLOCATED(NEA )) DEALLOCATE(NEA )
  END SUBROUTINE deallocate_err_trcomm_ctrl

END MODULE trcomm_ctrl
