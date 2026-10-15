!     ****** TRCOMM (wrapper module after Phase 2 split) ******
!
!  TRCOMM was previously a single ~800-line module containing all
!  shared TR variables.  It has been split into 6 logical submodules:
!
!    trcomm_const   : physical constants (PI, AEE, RKEV, ...)
!    trcomm_param   : namelist input parameters (RR, RA, BB, DT, ...)
!    trcomm_ctrl    : control / equation-selection / IO control variables
!    trcomm_mtx     : matrix variables (XV, YV, AX, X, ...)
!    trcomm_profile : profile / source / coefficient / equilibrium / nclass /
!                     ufile / graphic / additional plasma variables
!    trcomm_globals : derived global quantities (WPT, AJT, BETA0, TAUE1, ...)
!
!  This wrapper re-exports every PUBLIC symbol from those submodules so that
!  existing callers using `USE TRCOMM` or `USE TRCOMM, ONLY: SOME_SYMBOL`
!  continue to work unchanged.
!
!  ALLOCATE_TRCOMM / DEALLOCATE_TRCOMM call each submodule's allocate /
!  deallocate routine in dependency order, preserving the original
!  ordering and behaviour.
!
MODULE TRCOMM
  USE TRCOM0
  USE trcomm_const
  USE trcomm_param
  USE trcomm_ctrl
  USE trcomm_mtx
  USE trcomm_profile
  USE trcomm_globals
  IMPLICIT NONE
  PUBLIC

CONTAINS

  SUBROUTINE ALLOCATE_TRCOMM(ierr)

    USE TRCOM0, ONLY : NSMAX, NRMAX, NSZMAX, NSNMAX, &
                       NRMAX_OLD, NSMAX_OLD, NSZMAX_OLD, NSNMAX_OLD, &
                       NSTM, NEQMAXM, NVM, MWM, MLM, NRMP, NGLF, LDAB
    use trcom1, ONLY : ALLOCATE_TRCOM1
    integer, intent(out):: ierr

    ierr = 0
    if(nsmax<1) then
      write(6,*) "XXX ALLOCATE_TRCOMM : ILLEGAL PARAMETER    NSMAX=",nsmax
      ierr = 1
      return
    endif
    if(nrmax<1) then
      write(6,*) "XXX ALLOCATE_TRCOMM : ILLEGAL PARAMETER    NRMAX=",nrmax
      ierr = 1
      return
    endif

    if(nrmax_old==nrmax .and. &
       nsmax_old==nsmax .and. &
       nszmax_old==nszmax .and. &
       nsnmax_old==nsnmax .and. &
       ALLOCATED(PNSS)) return
    if(ALLOCATED(PNSS)) call DEALLOCATE_TRCOMM

    NSTMAX  = NSMAX+NSZMAX+NSNMAX
    NEQMAXM = 3*NSTMAX+1
    NVM     = NEQMAXM
    MWM     = 4*NEQMAXM-1
    MLM     = NEQMAXM*NRMAX
    NRMP    = NRMAX+1
    NGLF    = NRMAX
    LDAB    = 6*NEQMAXM

    CALL allocate_trcomm_ctrl(ierr)
      IF(ierr /= 0) GOTO 900
    CALL allocate_trcomm_mtx(ierr)
      IF(ierr /= 0) GOTO 900
    CALL allocate_trcomm_profile(ierr)
      IF(ierr /= 0) GOTO 900
    CALL allocate_trcomm_globals(ierr)
      IF(ierr /= 0) GOTO 900

    CALL ALLOCATE_TRCOM1(ierr)
      IF(ierr /= 0) GOTO 900

    nrmax_old  = nrmax
    nsmax_old  = nsmax
    nszmax_old = nszmax
    nsnmax_old = nsnmax
    return

 900 continue
    write(6,*) "XX  TRCOMM ALLOCATION ERROR IERR=",ierr
    call DEALLOCATE_ERR_TRCOMM
    return

  END SUBROUTINE ALLOCATE_TRCOMM


  SUBROUTINE DEALLOCATE_TRCOMM
    use trcom1, ONLY : DEALLOCATE_TRCOM1

    ! Idempotency guard: if ALLOCATE_TRCOMM never ran (e.g. interactive
    ! quit 'Q' before a run 'R'; trmain and tr_api_finalize call this
    ! unconditionally at shutdown),
    ! the sub-module deallocators issue bare unguarded DEALLOCATE(...) on
    ! unallocated arrays and abort. PNSS is the first array allocated
    ! (allocate_trcomm_ctrl) -> reliable "did we allocate?" sentinel.
    IF(.NOT.ALLOCATED(PNSS)) RETURN

    ! Deallocate in reverse dependency order
    CALL deallocate_trcomm_globals
    CALL deallocate_trcomm_profile
    CALL deallocate_trcomm_mtx
    CALL deallocate_trcomm_ctrl
    CALL DEALLOCATE_TRCOM1

    return

  END SUBROUTINE DEALLOCATE_TRCOMM


  SUBROUTINE DEALLOCATE_ERR_TRCOMM
    use trcom1, ONLY : DEALLOCATE_ERR_TRCOM1

    CALL deallocate_err_trcomm_globals
    CALL deallocate_err_trcomm_profile
    CALL deallocate_err_trcomm_mtx
    CALL deallocate_err_trcomm_ctrl
    CALL DEALLOCATE_ERR_TRCOM1

    return

  END SUBROUTINE DEALLOCATE_ERR_TRCOMM

  SUBROUTINE open_trcomm
    RETURN
  END SUBROUTINE open_trcomm

END MODULE TRCOMM
