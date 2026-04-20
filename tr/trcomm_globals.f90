MODULE trcomm_globals
!     ****** GLOBAL VARIABLES ******
! TRGLB
  USE TRCOM0, ONLY: rkind, NFM, NSTM, NSM
  IMPLICIT NONE
  PUBLIC

  REAL(rkind)  ::  &
       WBULKT, WTAILT, WPT, AJT, AJOHT, AJNBT, AJRFT, AJBST, AJTTOR, &
       PINT, POHT, PNBT, PNFT, PBINT, PFINT, POUT, PCXT, PIET, &
       PRBT, PRCT, PRLT, PRSUMT, &
       PEXST, PRFST, SINT, SIET, SNBT, SNFT, SOUT, VLOOP, ALI, RQ1, &
       RPE, Q0, ZEFF0, QF, WPDOT, TAUE1, TAUE2, TAUE89, TAUE98, H98Y2, &
       BETAP0, BETAPA, BETA0, BETAA, BETAQ0, BETAN
  REAL(rkind), DIMENSION(:)  ,ALLOCATABLE :: &  ! (NSM)
       SPSCT
  REAL(rkind), DIMENSION(3)   :: &
       AJRFVT
  REAL(rkind), DIMENSION(NFM) :: &
       ANF0, TF0, ANFAV, TFAV, WFT
  REAL(rkind), DIMENSION(:)  ,ALLOCATABLE :: &  ! (NSTM)
       ANS0, TS0, ANSAV, ANLAV, TSAV, WST, PRFT, PBCLT, PFCLT, PLT, SPET, SLT
  REAL(rkind), DIMENSION(:,:),ALLOCATABLE :: &  ! (NSTM,3)
       PRFVT

CONTAINS

  SUBROUTINE allocate_trcomm_globals(ierr)
    USE TRCOM0, ONLY: NSM, NSTM
    INTEGER, INTENT(OUT) :: ierr
    ierr = 0
    ALLOCATE(SPSCT(NSM),STAT=ierr)
      IF(ierr /= 0) RETURN
    ALLOCATE(ANS0(NSTM),TS0(NSTM),ANSAV(NSTM),ANLAV(NSTM),TSAV(NSTM),STAT=ierr)
      IF(ierr /= 0) RETURN
    ALLOCATE(WST(NSTM),PRFT(NSTM),PBCLT(NSTM),PFCLT(NSTM),STAT=ierr)
      IF(ierr /= 0) RETURN
    ALLOCATE(PLT(NSTM),SPET(NSTM),SLT(NSTM),PRFVT(NSTM,3),STAT=ierr)
      IF(ierr /= 0) RETURN

    ! Defensive zero-init (see PR #121/#123 pattern): libtrapi.so
    ! finalize+reinit cycle can reuse heap chunks with stale values.
    ! Global-scalar *sum* arrays (SPSCT / ANS0 / TS0 / ...) are computed
    ! via DO-loop reductions in trrslt_globals.f90; a reduction writing
    ! only NSMAX<NSTM slots leaves the remaining slots at whatever the
    ! prior run left on the heap, which tr_get_state then exposes.
    SPSCT(:)   = 0.D0
    ANS0(:)    = 0.D0
    TS0(:)     = 0.D0
    ANSAV(:)   = 0.D0
    ANLAV(:)   = 0.D0
    TSAV(:)    = 0.D0
    WST(:)     = 0.D0
    PRFT(:)    = 0.D0
    PBCLT(:)   = 0.D0
    PFCLT(:)   = 0.D0
    PLT(:)     = 0.D0
    SPET(:)    = 0.D0
    SLT(:)     = 0.D0
    PRFVT(:,:) = 0.D0
  END SUBROUTINE allocate_trcomm_globals

  SUBROUTINE deallocate_trcomm_globals
    DEALLOCATE(SPSCT)
    DEALLOCATE(ANS0,TS0,ANSAV,ANLAV,TSAV,WST,PRFT,PBCLT,PFCLT)
    DEALLOCATE(PLT,SPET,SLT,PRFVT)
  END SUBROUTINE deallocate_trcomm_globals

  SUBROUTINE deallocate_err_trcomm_globals
    IF(ALLOCATED(SPSCT)) DEALLOCATE(SPSCT)
    IF(ALLOCATED(ANS0 )) DEALLOCATE(ANS0 )
    IF(ALLOCATED(TS0  )) DEALLOCATE(TS0  )
    IF(ALLOCATED(ANSAV)) DEALLOCATE(ANSAV)
    IF(ALLOCATED(ANLAV)) DEALLOCATE(ANLAV)
    IF(ALLOCATED(TSAV )) DEALLOCATE(TSAV )
    IF(ALLOCATED(WST  )) DEALLOCATE(WST  )
    IF(ALLOCATED(PRFT )) DEALLOCATE(PRFT )
    IF(ALLOCATED(PBCLT)) DEALLOCATE(PBCLT)
    IF(ALLOCATED(PFCLT)) DEALLOCATE(PFCLT)
    IF(ALLOCATED(PLT  )) DEALLOCATE(PLT  )
    IF(ALLOCATED(SPET )) DEALLOCATE(SPET )
    IF(ALLOCATED(SLT  )) DEALLOCATE(SLT  )
    IF(ALLOCATED(PRFVT)) DEALLOCATE(PRFVT)
  END SUBROUTINE deallocate_err_trcomm_globals

END MODULE trcomm_globals
