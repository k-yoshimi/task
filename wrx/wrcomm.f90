! wrcomm.f90

MODULE wrcomm_parm
  USE commpi
  USE plcomm
  USE dpcomm_parm
  IMPLICIT NONE
  PUBLIC

  INTEGER,PARAMETER:: NRAYM=100
  INTEGER,PARAMETER:: idebug_max=99

! --- input parameters ---

  INTEGER:: model_fdrv,model_fdrv_ds
  INTEGER:: NRAYMAX,NSTPMAX,NRSMAX,NRLMAX,LMAXNW
  INTEGER:: mode_beam,mode_wline,mode_fig
  INTEGER:: MDLWRI,MDLWRG,MDLWRP,MDLWRQ,MDLWRW
  REAL(rkind):: SMAX,DELS,UUMIN,EPSRAY,DELRAY,DELDER,DELKR,EPSNW,EPSD0
  REAL(rkind):: pne_threshold,bdr_threshold
  INTEGER:: nsumax
  REAL(rkind):: Rmax_eq,Rmin_eq,Zmin_eq,Zmax_eq,Raxis_eq,Zaxis_eq
  REAL(rkind):: Rmax_wr,Rmin_wr,Zmin_wr,Zmax_wr
  REAL(rkind):: ra_wr
  INTEGER:: nsamax_wr,ns_nsa_wr(nsm),nsa_grf
  REAL(rkind),ALLOCATABLE:: rsu_wr(:),zsu_wr(:)
  INTEGER:: nres_max,nres_type

  REAL(rkind),DIMENSION(NRAYM):: &
       RFIN,RPIN,ZPIN,PHIIN,ANGTIN,ANGPIN,RNPHIN,RNZIN,RNKIN,UUIN, &
       RCURVAIN,RCURVBIN,RBRADAIN,RBRADBIN
  INTEGER,DIMENSION(NRAYM):: &
       MODEWIN
  CHARACTER(len=80):: KNAMWRW

  INTEGER,DIMENSION(idebug_max):: idebug_wr

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
       RAYIN,pwr_nsa_nstp
  REAL(rkind),DIMENSION(:,:,:),ALLOCATABLE:: &
       RAYS,pwr_nsa_nstp_nray
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
       rs_nstp_nray(:,:),rl_nstp_nray(:,:)
  REAL(rkind),ALLOCATABLE:: &
       pos_nrs(:),pwr_nrs_nsa(:,:),pwr_nrs_nsa_nray(:,:,:)
  REAL(rkind),ALLOCATABLE:: &
       pos_nrl(:),pwr_nrl_nsa(:,:),pwr_nrl_nsa_nray(:,:,:)
  REAL(rkind),ALLOCATABLE:: &
       pwr_nsa_nray(:,:),pwr_nsa(:),pwr_nray(:)
  REAL(rkind),ALLOCATABLE:: &
       pos_pwrmax_rs_nsa_nray(:,:),pwrmax_rs_nsa_nray(:,:)
  REAL(rkind),ALLOCATABLE:: &
       pos_pwrmax_rs_nsa(:),pwrmax_rs_nsa(:)
  REAL(rkind),ALLOCATABLE:: &
       pos_pwrmax_rl_nsa_nray(:,:),pwrmax_rl_nsa_nray(:,:)
  REAL(rkind),ALLOCATABLE:: &
       pos_pwrmax_rl_nsa(:),pwrmax_rl_nsa(:)
  reaL(rkind):: pwr_tot
  INTEGER:: INITIAL_DRV

  TYPE wr_nray_status_type
     INTEGER:: nray,nstp
     REAL(rkind):: RF,RCURVA,RCURVB,RBRADA,RBRADB
  END type wr_nray_status_type
  TYPE(wr_nray_status_type):: wr_nray_status
     
CONTAINS

  SUBROUTINE wr_allocate
    IMPLICIT NONE
    INTEGER,SAVE:: INIT=0
    INTEGER,SAVE:: NRAYMAX_SAVE=0
    INTEGER,SAVE:: NSTPMAX_SAVE=0
    INTEGER,SAVE:: nrsmax_save=0
    INTEGER,SAVE:: nrlmax_save=0
    INTEGER,SAVE:: nsamax_save=0

    IF(INIT.EQ.0) THEN
       INIT=1
    ELSE
       ! Skip re-allocation only when dims unchanged AND arrays still
       ! allocated. The pure dim check (original) is broken for
       ! finalize+reinit cycles inside libwrxapi.so: after wr_deallocate
       ! has freed every array, NSTPMAX_NRAY et al. are UNALLOCATED but
       ! the *_SAVE scalars still hold the previous values, so the
       ! unguarded check early-returns and the next access of
       ! pwr_nsa_nstp_nray / pwr_nrl_nsa_nray segfaults
       ! (use-after-free). ALLOCATED(NSTPMAX_NRAY) is the canary; binary
       ! wrx runs once per process so never hits this path.
       IF((NRAYMAX.EQ.NRAYMAX_SAVE).AND. &
          (NSTPMAX.EQ.NSTPMAX_SAVE).AND. &
          (nrsmax.EQ.nrsmax_save).AND. &
          (nrlmax.EQ.nrlmax_save).AND. &
          (nsamax_wr.EQ.nsamax_save).AND. &
          ALLOCATED(NSTPMAX_NRAY)) RETURN
       IF(ALLOCATED(NSTPMAX_NRAY)) CALL wr_deallocate
    END IF

    ALLOCATE(RAYIN(NEQ,NRAYMAX))
    ALLOCATE(NSTPMAX_NRAY(NRAYMAX))
    ALLOCATE(pwr_nsa_nstp(NSAMAX_WR,0:NSTPMAX))
    ALLOCATE(RAYS(0:NEQ,0:NSTPMAX,NRAYMAX))
    ALLOCATE(pwr_nsa_nstp_nray(NSAMAX_WR,0:NSTPMAX,NRAYMAX))

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

    ALLOCATE(rs_nstp_nray(nstpmax,nraymax),rl_nstp_nray(nstpmax,nraymax))
    ALLOCATE(pos_nrs(nrsmax),pos_nrl(nrlmax))
    ALLOCATE(pwr_nrs_nsa(nrsmax,nsamax_wr),pwr_nrl_nsa(nrlmax,nsamax_wr))
    ALLOCATE(pwr_nrs_nsa_nray(nrsmax,nsamax_wr,nraymax))
    ALLOCATE(pwr_nrl_nsa_nray(nrlmax,nsamax_wr,nraymax))
    ALLOCATE(pwr_nsa_nray(nsamax_wr,nraymax))
    ALLOCATE(pwr_nray(nraymax),pwr_nsa(nsamax_wr))
    ALLOCATE(pos_pwrmax_rs_nsa_nray(nsamax_wr,nraymax))
    ALLOCATE(pwrmax_rs_nsa_nray(nsamax_wr,nraymax))
    ALLOCATE(pos_pwrmax_rl_nsa_nray(nsamax_wr,nraymax))
    ALLOCATE(pwrmax_rl_nsa_nray(nsamax_wr,nraymax))
    ! Per-species summaries used only by wrx_get_state. Declared in
    ! wrcomm but never allocated by the historic binary path; reading
    ! them via the .so SEGVs (use of unallocated allocatable). Allocate
    ! and zero-init alongside the corresponding _nsa_nray pair.
    ALLOCATE(pos_pwrmax_rs_nsa(nsamax_wr))
    ALLOCATE(pwrmax_rs_nsa(nsamax_wr))
    ALLOCATE(pos_pwrmax_rl_nsa(nsamax_wr))
    ALLOCATE(pwrmax_rl_nsa(nsamax_wr))

    ! Initialize regression-dump-relevant arrays to 0.0 so that any element
    ! not subsequently written by the solver does not leak uninitialized
    ! heap memory into the wrx_regress.dat dump (Phase L-0 determinism).
    ! Without this, e.g. pwr_nray (currently never assigned), and
    ! pwrmax_{rs,rl}_nsa_nray (only assigned in the interior locmax branch
    ! of wr_calc_pwr) carry garbage subnormals that break bit-exact baselines.
    NSTPMAX_NRAY = 0
    pos_nrs = 0.D0
    pos_nrl = 0.D0
    pwr_nray = 0.D0
    pwr_nsa = 0.D0
    pwr_nsa_nray = 0.D0
    pwr_nrs_nsa = 0.D0
    pwr_nrl_nsa = 0.D0
    pwr_nrs_nsa_nray = 0.D0
    pwr_nrl_nsa_nray = 0.D0
    pos_pwrmax_rs_nsa_nray = 0.D0
    pwrmax_rs_nsa_nray = 0.D0
    pos_pwrmax_rl_nsa_nray = 0.D0
    pwrmax_rl_nsa_nray = 0.D0
    pos_pwrmax_rs_nsa = 0.D0
    pwrmax_rs_nsa = 0.D0
    pos_pwrmax_rl_nsa = 0.D0
    pwrmax_rl_nsa = 0.D0

    ! Defensive zero-init of every remaining allocatable array.
    ! Mirrors the tr/trcomm_profile.f90 sweep landed 2026-04-20: a fresh
    ! `wrx` binary launch starts with a kernel-zeroed heap (effectively
    ! zero), but `libwrxapi.so` re-init after `wrx_finalize` goes through
    ! glibc malloc, which may return a chunk that still holds the
    ! previous run's values. Without this sweep, the second wrx_run in
    ! one process either SIGSEGVs in libgrf::grd1d (called from
    ! wrcalpwr.f90) or produces a divergent get_state. See task #110 and
    ! the WRX_REINIT_OK gate retired by this commit.
    RAYIN = 0.D0
    RAYS  = 0.D0
    pwr_nsa_nstp       = 0.D0
    pwr_nsa_nstp_nray  = 0.D0
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
    rs_nstp_nray = 0.D0; rl_nstp_nray = 0.D0

  END SUBROUTINE wr_allocate

  SUBROUTINE wr_deallocate
    IMPLICIT NONE

    DEALLOCATE(NSTPMAX_NRAY)
    DEALLOCATE(RAYIN,pwr_nsa_nstp)
    DEALLOCATE(RAYS,pwr_nsa_nstp_nray)
    DEALLOCATE(CEXS,CEYS,CEZS)
    DEALLOCATE(RKXS,RKYS,RKZS,RXS,RYS,RZS,BNXS,BNYS,BNZS,BABSS)
    DEALLOCATE(RAYB,RAYRB1,RAYRB2)
    DEALLOCATE(CEXB,CEYB,CEZB)
    DEALLOCATE(RK1B,RP1B)
    DEALLOCATE(RK2B,RP2B,RAMPB)

    DEALLOCATE(rs_nstp_nray,rl_nstp_nray)
    DEALLOCATE(pos_nrs,pwr_nrs_nsa,pwr_nrs_nsa_nray)
    DEALLOCATE(pos_nrl,pwr_nrl_nsa,pwr_nrl_nsa_nray)
    DEALLOCATE(pwr_nsa_nray,pwr_nsa,pwr_nray)
    DEALLOCATE(pos_pwrmax_rs_nsa_nray)
    DEALLOCATE(pwrmax_rs_nsa_nray)
    DEALLOCATE(pos_pwrmax_rl_nsa_nray)
    DEALLOCATE(pwrmax_rl_nsa_nray)
    DEALLOCATE(pos_pwrmax_rs_nsa,pwrmax_rs_nsa)
    DEALLOCATE(pos_pwrmax_rl_nsa,pwrmax_rl_nsa)

  END SUBROUTINE wr_deallocate
END MODULE wrcomm
