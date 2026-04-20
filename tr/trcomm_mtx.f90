MODULE trcomm_mtx
!     ****** MATRIX VARIBALES ******
! TRMTX
  USE TRCOM0, ONLY: rkind
  IMPLICIT NONE
  PUBLIC

  REAL(rkind), DIMENSION(:,:),ALLOCATABLE :: & ! (NVM,NRM)
       XV
  REAL(rkind), DIMENSION(:,:),ALLOCATABLE :: & ! (NFM,NRM)
       YV, AY, Y
  REAL(rkind), DIMENSION(:,:),ALLOCATABLE :: & ! (NSM,NRM)
       ZV, AZ, Z
  REAL(rkind), DIMENSION(:,:),ALLOCATABLE :: & ! (LDAB,MLM)
       AX
  REAL(rkind), DIMENSION(:)  ,ALLOCATABLE :: & ! (MLM)
       X

CONTAINS

  SUBROUTINE allocate_trcomm_mtx(ierr)
    USE TRCOM0, ONLY: NRMAX, NEQMAXM, NFM, NSM
    INTEGER, INTENT(OUT) :: ierr
    ierr = 0
    ALLOCATE(XV(NEQMAXM,NRMAX),STAT=ierr)
      IF(ierr /= 0) RETURN
    ALLOCATE(YV(NFM,NRMAX),AY(NFM,NRMAX),Y(NFM,NRMAX),STAT=ierr)
      IF(ierr /= 0) RETURN
    ALLOCATE(ZV(NSM,NRMAX),AZ(NSM,NRMAX),Z(NSM,NRMAX),STAT=ierr)
      IF(ierr /= 0) RETURN
    ALLOCATE(AX(6*NEQMAXM,NEQMAXM*NRMAX),X(NEQMAXM*NRMAX),STAT=ierr)
      IF(ierr /= 0) RETURN

    ! Defensive zero-init (see PR #121/#123 pattern): libtrapi.so
    ! finalize+reinit cycle can reuse heap chunks with stale values.
    ! AX / X are built fresh each step by trexec (banded LU system), but
    ! XV / YV / AY / Y / ZV / AZ / Z are stepwise variables that are
    ! referenced before being fully overwritten on timestep edges (e.g.
    ! YV is read in fusion-source history); a stale heap chunk from a
    ! prior tr_run leaks into the next run's step-0 state.
    XV(:,:) = 0.D0
    YV(:,:) = 0.D0; AY(:,:) = 0.D0; Y(:,:)  = 0.D0
    ZV(:,:) = 0.D0; AZ(:,:) = 0.D0; Z(:,:)  = 0.D0
    AX(:,:) = 0.D0
    X(:)    = 0.D0
  END SUBROUTINE allocate_trcomm_mtx

  SUBROUTINE deallocate_trcomm_mtx
    DEALLOCATE(XV,YV, AY, Y,ZV, AZ, Z,AX,X)
  END SUBROUTINE deallocate_trcomm_mtx

  SUBROUTINE deallocate_err_trcomm_mtx
    IF(ALLOCATED(XV)) DEALLOCATE(XV)
    IF(ALLOCATED(YV)) DEALLOCATE(YV)
    IF(ALLOCATED(AY)) DEALLOCATE(AY)
    IF(ALLOCATED(Y )) DEALLOCATE(Y )
    IF(ALLOCATED(ZV)) DEALLOCATE(ZV)
    IF(ALLOCATED(AZ)) DEALLOCATE(AZ)
    IF(ALLOCATED(Z )) DEALLOCATE(Z )
    IF(ALLOCATED(AX)) DEALLOCATE(AX)
    IF(ALLOCATED(X )) DEALLOCATE(X )
  END SUBROUTINE deallocate_err_trcomm_mtx

END MODULE trcomm_mtx
