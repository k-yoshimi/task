! wrcomm.f90

MODULE wrcomm_parm
  USE commpi
  USE plcomm
  USE dpcomm
  IMPLICIT NONE
  PUBLIC

  INTEGER,PARAMETER:: NRAYM=100

! --- input parameters ---

  INTEGER:: NRAYMAX,NSTPMAX,NRSMAX,NRLMAX,LMAXNW
  INTEGER:: mode_beam
  INTEGER:: MDLWRI,MDLWRG,MDLWRP,MDLWRQ,MDLWRW
  REAL(rkind):: SMAX,DELS,UUMIN,EPSRAY,DELRAY,DELDER,DELKR,EPSNW
  REAL(rkind):: RF,RPI,ZPI,PHII,RNZI,RNPHII,RKR0,UUI,RKRI,RKPHII,RKZI
  REAL(rkind):: RCURVA,RCURVB,RBRADA,RBRADB,NRADMX
  INTEGER:: mode_wline
  INTEGER:: MODEW,nres_max,nres_type
  REAL(rkind):: pne_threshold,bdr_threshold
  REAL(rkind):: Rmax_wr,Rmin_wr,Zmin_wr,Zmax_wr

  REAL(rkind),DIMENSION(NRAYM):: &
       RFIN,RPIN,ZPIN,PHIIN,RKRIN,RNZIN,RNPHIIN,ANGZIN,ANGPHIN,UUIN, &
       RCURVAIN,RCURVBIN,RBRADAIN,RBRADBIN
  INTEGER,DIMENSION(NRAYM):: &
       MODEWIN

CONTAINS

  SUBROUTINE open_wrcomm_parm
    RETURN
  END SUBROUTINE open_wrcomm_parm

END MODULE wrcomm_parm

MODULE wrcomm
  USE wrcomm_parm
  USE dpcomm
  USE commpi
  IMPLICIT NONE

  INTEGER,PARAMETER:: NEQ=8
  INTEGER,PARAMETER:: NBEQ=19
  INTEGER,PARAMETER:: NBVAR=53

  INTEGER,DIMENSION(:),ALLOCATABLE:: &
       NSTPMAX_NRAY
  REAL(rkind),DIMENSION(:,:),ALLOCATABLE:: &
       RAYIN
  REAL(rkind),DIMENSION(:,:,:),ALLOCATABLE:: &
       RAYS
  COMPLEX(rkind),DIMENSION(:,:),ALLOCATABLE:: &
       CEXS,CEYS,CEZS
  REAL(rkind),DIMENSION(:,:),ALLOCATABLE:: &
       RKXS,RKYS,RKZS,RXS,RYS,RZS,BNXS,BNYS,BNZS,BABSS
  REAL(rkind),DIMENSION(:,:),ALLOCATABLE:: &
       RAYB,RAYRB1,RAYRB2
  COMPLEX(rkind),DIMENSION(:),ALLOCATABLE:: &
       CEXB,CEYB,CEZB
  REAL(rkind),DIMENSION(:,:),ALLOCATABLE:: &
       RK1B,RP1B
  REAL(rkind),DIMENSION(:,:,:),ALLOCATABLE:: &
       RK2B,RP2B
  REAL(rkind),DIMENSION(:),ALLOCATABLE:: &
       RAMPB
  REAL(rkind),ALLOCATABLE:: &
       pos_nrs(:),pwr_nrs(:),pwr_nrs_nray(:,:)
  REAL(rkind),ALLOCATABLE:: &
       pos_nrl(:),pwr_nrl(:),pwr_nrl_nray(:,:)
  REAL(rkind),ALLOCATABLE:: &
       rs_nstp_nray(:,:),rl_nstp_nray(:,:)
  REAL(rkind),ALLOCATABLE:: &
       pos_pwrmax_rs_nray(:),pwrmax_rs_nray(:)
  REAL(rkind):: pos_pwrmax_rs,pwrmax_rs
  REAL(rkind),ALLOCATABLE:: &
       pos_pwrmax_rl_nray(:),pwrmax_rl_nray(:)
  REAL(rkind):: pos_pwrmax_rl,pwrmax_rl

  ! Module-scope SAVE state for the wr_allocate / wr_deallocate state
  ! machine. These were previously declared local-SAVE inside
  ! wr_allocate, which made them inaccessible from wr_deallocate or
  ! wr_reset_alloc_state, leading to a finalize-then-reinit double-free
  ! crash (Bugbot HIGH on PR #36): after wr_deallocate the INIT flag
  ! stayed at 1, so the next wr_allocate hit the "ELSE" branch and
  ! tried to deallocate already-stale arrays.
  INTEGER,SAVE,PRIVATE:: WR_ALLOC_INIT=0
  INTEGER,SAVE,PRIVATE:: WR_ALLOC_NRAYMAX_SAVE=0
  INTEGER,SAVE,PRIVATE:: WR_ALLOC_NSTPMAX_SAVE=0
CONTAINS

  SUBROUTINE wr_allocate
    IMPLICIT NONE

    IF(WR_ALLOC_INIT.EQ.0) THEN
       WR_ALLOC_INIT=1
    ELSE
       IF((NRAYMAX.EQ.WR_ALLOC_NRAYMAX_SAVE).AND. &
          (NSTPMAX.EQ.WR_ALLOC_NSTPMAX_SAVE)) RETURN
       CALL wr_deallocate
    END IF

    ALLOCATE(RAYIN(NEQ,NRAYMAX))
    ALLOCATE(NSTPMAX_NRAY(NRAYMAX))
    ALLOCATE(RAYS(0:NEQ,0:NSTPMAX,NRAYMAX))

    ALLOCATE(CEXS(0:NSTPMAX,NRAYMAX))
    ALLOCATE(CEYS(0:NSTPMAX,NRAYMAX))
    ALLOCATE(CEZS(0:NSTPMAX,NRAYMAX))
    ALLOCATE(RKXS(0:NSTPMAX,NRAYMAX))
    ALLOCATE(RKYS(0:NSTPMAX,NRAYMAX))
    ALLOCATE(RKZS(0:NSTPMAX,NRAYMAX))
    ALLOCATE(RXS(0:NSTPMAX,NRAYMAX))
    ALLOCATE(RYS(0:NSTPMAX,NRAYMAX))
    ALLOCATE(RZS(0:NSTPMAX,NRAYMAX))
    ALLOCATE(BNXS(0:NSTPMAX,NRAYMAX))
    ALLOCATE(BNYS(0:NSTPMAX,NRAYMAX))
    ALLOCATE(BNZS(0:NSTPMAX,NRAYMAX))
    ALLOCATE(BABSS(0:NSTPMAX,NRAYMAX))

    ALLOCATE(RAYB(0:NBVAR,0:NSTPMAX))
    ALLOCATE(RAYRB1(0:NSTPMAX,NRAYMAX))
    ALLOCATE(RAYRB2(0:NSTPMAX,NRAYMAX))
    ALLOCATE(CEXB(0:NSTPMAX),CEYB(0:NSTPMAX),CEZB(0:NSTPMAX))
    ALLOCATE(RK1B(3,0:NSTPMAX),RP1B(3,0:NSTPMAX))
    ALLOCATE(RK2B(3,3,0:NSTPMAX),RP2B(3,3,0:NSTPMAX))
    ALLOCATE(RAMPB(0:NSTPMAX))

    ! Defensive zero-init (see PR #123 pattern): libwrapi.so finalize+reinit
    ! cycle can reuse heap chunks with stale values.
    RAYIN = 0.D0
    NSTPMAX_NRAY = 0
    RAYS  = 0.D0
    CEXS = (0.D0, 0.D0); CEYS = (0.D0, 0.D0); CEZS = (0.D0, 0.D0)
    RKXS = 0.D0; RKYS = 0.D0; RKZS = 0.D0
    RXS  = 0.D0; RYS  = 0.D0; RZS  = 0.D0
    BNXS = 0.D0; BNYS = 0.D0; BNZS = 0.D0
    BABSS = 0.D0
    RAYB = 0.D0; RAYRB1 = 0.D0; RAYRB2 = 0.D0
    CEXB = (0.D0, 0.D0); CEYB = (0.D0, 0.D0); CEZB = (0.D0, 0.D0)
    RK1B = 0.D0; RP1B = 0.D0
    RK2B = 0.D0; RP2B = 0.D0
    RAMPB = 0.D0

    ! Remember the shapes we just allocated so a subsequent wr_allocate
    ! call with identical NRAYMAX/NSTPMAX can short-circuit (RETURN).
    WR_ALLOC_NRAYMAX_SAVE = NRAYMAX
    WR_ALLOC_NSTPMAX_SAVE = NSTPMAX
  END SUBROUTINE wr_allocate

  SUBROUTINE wr_deallocate
    IMPLICIT NONE

    ! Guard with ALLOCATED() so wr_deallocate is safe to call even if
    ! wr_allocate was never run, or if it is called twice in a row.
    IF (ALLOCATED(NSTPMAX_NRAY)) DEALLOCATE(NSTPMAX_NRAY)
    IF (ALLOCATED(RAYIN))        DEALLOCATE(RAYIN)
    IF (ALLOCATED(RAYS))         DEALLOCATE(RAYS)
    IF (ALLOCATED(CEXS))         DEALLOCATE(CEXS)
    IF (ALLOCATED(CEYS))         DEALLOCATE(CEYS)
    IF (ALLOCATED(CEZS))         DEALLOCATE(CEZS)
    IF (ALLOCATED(RKXS))         DEALLOCATE(RKXS)
    IF (ALLOCATED(RKYS))         DEALLOCATE(RKYS)
    IF (ALLOCATED(RKZS))         DEALLOCATE(RKZS)
    IF (ALLOCATED(RXS))          DEALLOCATE(RXS)
    IF (ALLOCATED(RYS))          DEALLOCATE(RYS)
    IF (ALLOCATED(RZS))          DEALLOCATE(RZS)
    IF (ALLOCATED(BNXS))         DEALLOCATE(BNXS)
    IF (ALLOCATED(BNYS))         DEALLOCATE(BNYS)
    IF (ALLOCATED(BNZS))         DEALLOCATE(BNZS)
    IF (ALLOCATED(BABSS))        DEALLOCATE(BABSS)
    IF (ALLOCATED(RAYB))         DEALLOCATE(RAYB)
    IF (ALLOCATED(RAYRB1))       DEALLOCATE(RAYRB1)
    IF (ALLOCATED(RAYRB2))       DEALLOCATE(RAYRB2)
    IF (ALLOCATED(CEXB))         DEALLOCATE(CEXB)
    IF (ALLOCATED(CEYB))         DEALLOCATE(CEYB)
    IF (ALLOCATED(CEZB))         DEALLOCATE(CEZB)
    IF (ALLOCATED(RK1B))         DEALLOCATE(RK1B)
    IF (ALLOCATED(RP1B))         DEALLOCATE(RP1B)
    IF (ALLOCATED(RK2B))         DEALLOCATE(RK2B)
    IF (ALLOCATED(RP2B))         DEALLOCATE(RP2B)
    IF (ALLOCATED(RAMPB))        DEALLOCATE(RAMPB)
  END SUBROUTINE wr_deallocate

  !-------------------------------------------------------------------
  ! wr_reset_alloc_state : clear the wr_allocate state machine.
  !
  ! Called from wr_api_finalize after wr_deallocate so that a subsequent
  ! wr_init + wr_run cycle starts from a clean slate. Without this, the
  ! INIT=1 flag persisted across finalize, and the next wr_allocate
  ! would jump to the "ELSE" branch and try to deallocate already-freed
  ! arrays (Bugbot HIGH on PR #36, double-free on reinit).
  !-------------------------------------------------------------------
  SUBROUTINE wr_reset_alloc_state
    IMPLICIT NONE
    WR_ALLOC_INIT         = 0
    WR_ALLOC_NRAYMAX_SAVE = 0
    WR_ALLOC_NSTPMAX_SAVE = 0
  END SUBROUTINE wr_reset_alloc_state
END MODULE wrcomm
