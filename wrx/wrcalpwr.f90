! wrcalpwr.f90

MODULE wrcalpwr

  PRIVATE
  PUBLIC wr_calc_pwr
  
CONTAINS

  ! --- calculation of radial profile of power absorption ---

  SUBROUTINE wr_calc_pwr

    USE wrcomm
    USE pllocal
    USE plprof,ONLY: pl_mag_old,pl_rzsu
    USE libgrf
    IMPLICIT NONE
    INTEGER:: nrs,nray,nstp,nrs1,nrs2,locmax
    INTEGER:: nrl1,nrl2,ndrl,nsu,nrl,nsa
    INTEGER:: nstpmax_all
    REAL(rkind):: drs,xl,yl,zl,rs1,rs2,sdrs,delpwr,pwrmax,dpwr,ddpwr
    REAL(rkind):: rlmin,rlmax,drl,rl1,rl2,sdrl
    REAL(rkind):: VV,TT,RF,XP,YP,ZP,RKXP,RKYP,RKZP,UU,OMG,ROMG
    REAL(rkind):: RXP,RYP,RZP,RRKXP,RRKYP,RRKZP
    REAL(rkind):: DOMG,DXP,DYP,DZP,DKXP,DKYP,DKZP,DS
    REAL(rkind):: dx
    REAL(rkind):: xtemp(0:nstpmax),ytemp(0:nstpmax,nsamax_wr,nraymax)
    ! Headless-graphics gate. When WRX_NO_GRAPHICS is set in the
    ! environment (e.g. by libwrxapi.so callers running without an X
    ! display), skip the PAGES/GRD1D/PAGEE block below. Without this
    ! gate, libwrxapi.so SEGVs deep inside libgrf (CALL grd1d ->
    ! grf1d_exec -> stub mismatches in wrx_graphics_stubs.f90, which
    ! were sized for a no-op shim but real grd1d resolves to the
    ! libgrf module symbol via USE libgrf and walks an uninitialized
    ! grf_attr_type past the stub boundary). The binary wrx links
    ! against the full libgsp/libg3d stack so the same calls succeed.
    CHARACTER(LEN=64) :: env_no_gr
    INTEGER :: gr_status, gr_length
    LOGICAL :: skip_graphics

    CALL get_environment_variable('WRX_NO_GRAPHICS', env_no_gr, &
         LENGTH=gr_length, STATUS=gr_status)
    skip_graphics = (gr_status == 0 .AND. gr_length > 0)

!   ----- evaluate plasma major radius range -----

    CALL pl_rzsu(rsu_wr,zsu_wr,nsumax)
    rlmin=MINVAL(rsu_wr)
    rlmax=MAXVAL(rsu_wr)

!     ----- Setup for RADIAL DEPOSITION PROFILE (Minor radius) -----

    drs=1.D0/nrsmax
    DO nrs=1,nrsmax
       pos_nrs(nrs)=(DBLE(nrs)-0.5D0)*drs
    ENDDO
    DO nray=1,nraymax
       DO nsa=1,nsamax_wr
          DO nrs=1,nrsmax
             pwr_nrs_nsa_nray(nrs,nsa,nray)=0.D0
          END DO
       ENDDO
    ENDDO
    DO nsa=1,nsamax_wr
       DO nrs=1,nrsmax
          pwr_nrs_nsa(nrs,nsa)=0.D0
       END DO
    ENDDO

    !     ----- Setup for RADIAL DEPOSITION PROFILE (Major radius) -----

    drl=(rlmax-rlmin)/nrlmax
    DO nrl=1,nrlmax
       pos_nrl(nrl)=rlmin+(dble(nrl)-0.5D0)*drl
    ENDDO
    DO nray=1,nraymax
       DO nsa=1,nsamax_wr
          DO nrl=1,nrlmax
             pwr_nrl_nsa_nray(nrl,nsa,nray)=0.D0
          END DO
       ENDDO
    ENDDO
    DO nrl=1,nrlmax
       DO nsa=1,nsamax_wr
          pwr_nrl_nsa(nrl,nsa)=0.D0
       END DO
    ENDDO

!   --- calculate power deposition density ----

    DO nray=1,nraymax
       DO nstp=0,nstpmax_nray(nray)-1

          ! --- minor radius profile ---
          
          xl=rays(1,nstp,nray)
          yl=rays(2,nstp,nray)
          zl=rays(3,nstp,nray)
          CALL pl_mag_old(xl,yl,zl,rs1)  ! nstp:   rs1
          xl=rays(1,nstp+1,nray)
          yl=rays(2,nstp+1,nray)
          zl=rays(3,nstp+1,nray)
          CALL pl_mag_old(xl,yl,zl,rs2)  ! nstp+1: rs2

          IF(rs1.LE.1.D0.OR.rs2.LE.1.D0) THEN
             nrs1=INT(rs1/drs)+1   ! (nrs1-1)*drs < rs1 < nrs1*drs
             nrs2=INT(rs2/drs)+1   ! (nrs2-1)*drs < rs2 < nrs2*drs
             IF(nrs1.GT.nrsmax) THEN
                nrs1=nrsmax
                IF(nrs2.GT.nrsmax) EXIT ! both points out of rs < 1.0
             ENDIF
             IF(nrs2.GT.nrsmax) nrs2=nrsmax
             
             IF(nrs1.EQ.nrs2) THEN ! nrs1=nrs2
                                   !    (nrs1-1)*drs < rs1,rs2 < nrs1*drs
                DO nsa=1,nsamax_wr
                   delpwr=pwr_nsa_nstp_nray(nsa,nstp+1,nray)
                   pwr_nrs_nsa_nray(nrs1,nsa,nray) &
                        =pwr_nrs_nsa_nray(nrs1,nsa,nray) &
                        +delpwr
                END DO
             ELSE IF(nrs2.LT.nrs1) THEN  ! rs2 < rs1 ; nrs2 < nrs1
                                         ! rs2 < nrs2*drs < (nrs1-1)*drs < rs1
                DO nsa=1,nsamax_wr
                   delpwr=pwr_nsa_nstp_nray(nsa,nstp+1,nray)/(rs1-rs2)
                   pwr_nrs_nsa_nray(nrs1,nsa,nray) &
                        =pwr_nrs_nsa_nray(nrs1,nsa,nray) &
                        +(rs1-DBLE(nrs1-1)*drs)*delpwr
                   DO nrs=nrs1-1,nrs2+1,-1
                      pwr_nrs_nsa_nray(nrs,nsa,nray) &
                           =pwr_nrs_nsa_nray(nrs,nsa,nray)+drs*delpwr
                   ENDDO
                   pwr_nrs_nsa_nray(nrs2,nsa,nray) &
                        =pwr_nrs_nsa_nray(nrs2,nsa,nray) &
                        +(DBLE(nrs2)*drs-rs2)*delpwr
                END DO
             ELSE IF(nrs1.lt.nrs2) THEN  ! rs1 < rs2 ; nrs1 < nrs2
                                         ! rs1 < nrs1*drs < (nrs2-1)*drs < rs2
                DO nsa=1,nsamax_wr
                   delpwr=pwr_nsa_nstp_nray(nsa,nstp+1,nray)/(rs2-rs1)
                   pwr_nrs_nsa_nray(nrs1,nsa,nray) &
                        =pwr_nrs_nsa_nray(nrs1,nsa,nray) &
                        +(DBLE(nrs1)*drs-rs1)*delpwr
                   DO nrs=nrs1+1,nrs2-1
                      pwr_nrs_nsa_nray(nrs,nsa,nray) &
                           =pwr_nrs_nsa_nray(nrs,nsa,nray)+drs*delpwr
                   ENDDO
                   pwr_nrs_nsa_nray(nrs2,nsa,nray) &
                        =pwr_nrs_nsa_nray(nrs2,nsa,nray) &
                        +(rs2-DBLE(nrs2-1)*drs)*delpwr
                END DO
             END IF
          ENDIF

          ! --- major radius profile ---

          xl=rays(1,nstp,nray)
          yl=rays(2,nstp,nray)
          rl1=SQRT(xl**2+yl**2)
          nrl1=INT((rl1-rlmin)/drl)+1
          xl=rays(1,nstp+1,nray)
          yl=rays(2,nstp+1,nray)
          rl2=SQRT(xl**2+yl**2)
          nrl2=INT((rl2-rlmin)/drl)+1

          IF((nrl1.GE.1.and.nrl1.LE.nrlmax).OR. &
             (nrl2.GE.1.and.nrl2.LE.nrlmax)) THEN
             IF(nrl1.LT.1) nrl1=1
             IF(nrl1.GT.nrlmax) nrl1=nrlmax
             IF(nrl2.LT.1) nrl2=1
             IF(nrl2.GT.nrlmax) nrl2=nrlmax
             ndrl=ABS(nrl2-nrl1)
             IF(ndrl.EQ.0) THEN
                DO nsa=1,nsamax_wr
                   pwr_nrl_nsa_nray(nrl1,nsa,nray) &
                        =pwr_nrl_nsa_nray(nrl1,nsa,nray) &
                        +pwr_nsa_nstp_nray(nsa,nstp+1,nray)
                END DO
             ELSE IF(nrl1.LT.nrl2) THEN
                sdrl=(rl2-rl1)/drl
                DO nsa=1,nsamax_wr
                   delpwr=pwr_nsa_nstp_nray(nsa,nstp+1,nray)/sdrl
                   pwr_nrl_nsa_nray(nrl1,nsa,nray) &
                        =pwr_nrl_nsa_nray(nrl1,nsa,nray) &
                        +(DBLE(nrl1)-(rl1-rlmin)/drl)*delpwr
                   DO nrl=nrl1+1,nrl2-1
                      pwr_nrl_nsa_nray(nrl,nsa,nray) &
                           =pwr_nrl_nsa_nray(nrl,nsa,nray)+delpwr
                   END DO
                   pwr_nrl_nsa_nray(nrl2,nsa,nray) &
                        =pwr_nrl_nsa_nray(nrl2,nsa,nray) &
                        +((rl2-rlmin)/drl-dble(nrl2-1))*delpwr
                END DO
             ELSE
                sdrl=(rl1-rl2)/drl
                DO nsa=1,nsamax_wr
                   delpwr=pwr_nsa_nstp_nray(nsa,nstp+1,nray)/sdrl
                   pwr_nrl_nsa_nray(nrl2,nsa,nray) &
                        =pwr_nrl_nsa_nray(nrl2,nsa,nray) &
                        +(DBLE(nrl2)-(rl2-rlmin)/drl)*delpwr
                   DO nrl=nrl2+1,nrl1-1
                      pwr_nrl_nsa_nray(nrl,nsa,nray) &
                           =pwr_nrl_nsa_nray(nrl,nsa,nray)+delpwr
                   END DO
                   pwr_nrl_nsa_nray(nrl1,nsa,nray) &
                        =pwr_nrl_nsa_nray(nrl1,nsa,nray) &
                        +((rl1-rlmin)/drl-DBLE(nrl1-1))*delpwr
                END DO
             END IF
          END IF
       ENDDO
    END DO

    ! --- total power  ---

    pwr_tot=0.D0
    DO nsa=1,nsamax_wr
       pwr_nsa(nsa)=0.D0
       DO nray=1,nraymax
          pwr_nsa_nray(nsa,nray)=0.D0
          DO nrs=1,nrsmax
             pwr_nsa_nray(nsa,nray) &
                  =pwr_nsa_nray(nsa,nray)+pwr_nrs_nsa_nray(nrs,nsa,nray)
          END DO
          pwr_nsa(nsa)=pwr_nsa(nsa)+pwr_nsa_nray(nsa,nray)
       END DO
       pwr_tot=pwr_tot+pwr_nsa(nsa)
    END DO

    DO nsa=1,nsamax_wr
       DO nrs=1,nrsmax
          pwr_nrs_nsa(nrs,nsa)=0.D0
          DO nray=1,nraymax
             pwr_nrs_nsa(nrs,nsa)=pwr_nrs_nsa(nrs,nsa) &
                  +pwr_nrs_nsa_nray(nrs,nsa,nray)
          END DO
       END DO
       DO nrl=1,nrlmax
          pwr_nrl_nsa(nrl,nsa)=0.D0
          DO nray=1,nraymax
             pwr_nrl_nsa(nrl,nsa)=pwr_nrl_nsa(nrl,nsa) &
                  +pwr_nrl_nsa_nray(nrl,nsa,nray)
          END DO
       END DO
    END DO

    IF (.NOT. skip_graphics) CALL pages

    ! Clamp upper bound so xtemp(nstp+1) and ytemp(nstp+1,...) stay
    ! within their (0:nstpmax) declared bounds. The historic
    ! MAXVAL(...)+1 overshoots by 1 when a ray uses all NSTPMAX steps
    ! (e.g. SMAX/DELS=NSTPMAX exactly), and pwr_nsa_nstp_nray on the
    ! RHS is also (0:nstpmax)-bounded so reading at index NSTPMAX+1 is
    ! an OOB read. Without this clamp, the binary wrx happens not to
    ! crash because the ray usually terminates well before NSTPMAX so
    ! nstpmax_all < NSTPMAX, but libwrxapi.so SEGVs whenever the
    ! caller chooses NSTPMAX = SMAX/DELS exactly (e.g. test_wrxlib.py
    ! TestWrxlibRun: NSTPMAX=2000, SMAX=2.0, DELS=1e-3).
    nstpmax_all=MIN(MAXVAL(nstpmax_nray(1:nraymax))+1, nstpmax-1)
    ! Guard the divisor: nstpmax_all collapses to 0 when NSTPMAX<=1
    ! (MIN(MAXVAL(...)+1, nstpmax-1) -> nstpmax-1 = 0), which would make
    ! dx = 1/0. Reviewers (in-house + codex) flagged this merge-interaction
    ! div-by-zero (kyoshimi's nstpmax-1 clamp + bpsi's 1/nstpmax_all divisor).
    dx=1.D0/MAX(nstpmax_all,1)
    DO nstp=0,nstpmax_all
       xtemp(nstp+1)=nstp*dx
    END DO
    DO nray=1,nraymax
       DO nsa=1,nsamax_wr
          ! Clamp to nstpmax_all so ytemp(nstp+1) stays within (0:nstpmax):
          ! a ray that uses all NSTPMAX steps has nstpmax_nray(nray)=nstpmax,
          ! which would overrun ytemp at nstp+1=nstpmax+1 (the merge re-introduced
          ! bpsi's unclamped nstpmax_nray bound over kyoshimi's nstpmax_all clamp).
          DO nstp=0,MIN(nstpmax_nray(nray),nstpmax_all)
             ytemp(nstp+1,nsa,nray)=pwr_nsa_nstp_nray(nsa,nstp,nray)
          END DO
          DO nstp=MIN(nstpmax_nray(nray),nstpmax_all)+1,nstpmax_all
             ytemp(nstp+1,nsa,nray)=0.D0
          END DO
          
       END DO
    END DO
    ! Print loop: ytemp(:,*,2) is only valid for NRAYMAX>=2; emit a
    ! safe placeholder for the 2-ray column when only one ray is run.
    IF (nraymax >= 2) THEN
       DO nstp=0,nstpmax_all,MAX(nstpmax_all/20,1)
          WRITE(6,'(I8,3ES12.4)') &
               nstp,xtemp(nstp+1),ytemp(nstp+1,1,1),ytemp(nstp+1,1,2)
       END DO
    ELSE
       DO nstp=0,nstpmax_all,MAX(nstpmax_all/20,1)
          WRITE(6,'(I8,2ES12.4)') &
               nstp,xtemp(nstp+1),ytemp(nstp+1,1,1)
       END DO
    END IF
    IF (.NOT. skip_graphics) THEN
       CALL grd1d(1,xtemp,ytemp(:,1,1),nstpmax_nray(1),nstpmax_nray(1),1, &
            '@pwr-nstp vs. nstp@',0)
       ! Guard ray-2 plot: nstpmax_nray and ytemp(:,*,*) are only sized
       ! to NRAYMAX. The original unconditional ray-2 reference would
       ! dereference out-of-bounds memory when NRAYMAX=1.
       IF (nraymax >= 2) THEN
          CALL grd1d(2,xtemp,ytemp(:,1,2),nstpmax_nray(2),nstpmax_nray(2),1, &
               '@pwr-nstp vs. nstp@',0)
       END IF
       CALL grd1d(3,pos_nrs,pwr_nrs_nsa_nray, &
            nrsmax,nrsmax,nsamax_wr*nraymax, &
            '@pwr-nrs vs. pos-nrs@',0)
       CALL grd1d(4,pos_nrl,pwr_nrl_nsa_nray, &
            nrlmax,nrlmax,nsamax_wr*nraymax, &
            '@pwr-nrl vs. pos-nrl@',0)
       CALL pagee
    END IF

    ! --- power divided by division area ---

    DO nray=1,nraymax
       DO nrs=1,nrsmax
          DO nsa=1,nsamax_wr
             pwr_nrs_nsa_nray(nrs,nsa,nray) &
                  =pwr_nrs_nsa_nray(nrs,nsa,nray) &
                  /(2.D0*PI*(DBLE(nrs)-0.5D0)*drs*drs)
          ENDDO
       END DO
       DO nrl=1,nrlmax
          DO nsa=1,nsamax_wr
             pwr_nrl_nsa_nray(nrl,nsa,nray) &
                  =pwr_nrl_nsa_nray(nrl,nsa,nray) &
                  /(2.D0*PI*(DBLE(nrl)-0.5D0)*drl*drl)
          END DO
       ENDDO
    ENDDO

!     ----- find location of absorbed power peak -----

    DO nray=1,nraymax
       DO nsa=1,nsamax_wr
          pwrmax=0.D0
          locmax=0
          DO nrs=1,nrsmax
             IF(pwr_nrs_nsa_nray(nrs,nsa,nray).GT.pwrmax) THEN
                pwrmax=pwr_nrs_nsa_nray(nrs,nsa,nray)
                locmax=nrs
             ENDIF
          END DO
          IF(locmax.LE.1) THEN
             pos_pwrmax_rs_nsa_nray(nsa,nray)=pos_nrs(1)
          ELSE IF(locmax.GE.nrsmax) THEN
             pos_pwrmax_rs_nsa_nray(nsa,nray)=pos_nrs(nrsmax)
          ELSE
             dpwr =(pwr_nrs_nsa_nray(locmax+1,nsa,nray) &
                   -pwr_nrs_nsa_nray(locmax-1,nsa,nray))/(2.D0*drs)
             ddpwr=(pwr_nrs_nsa_nray(locmax+1,nsa,nray) &
                 -2*pwr_nrs_nsa_nray(locmax  ,nsa,nray) &
                   +pwr_nrs_nsa_nray(locmax-1,nsa,nray))/drs**2
             pos_pwrmax_rs_nsa_nray(nsa,nray) &
                  =(locmax-0.5D0)/(nrsmax-1.D0)-dpwr/ddpwr
             pwrmax_rs_nsa_nray(nsa,nray)=pwrmax-dpwr**2/(2.D0*ddpwr)
          ENDIF
   
          pwrmax=0.D0
          locmax=0
          DO nrl=1,nrlmax
             IF(pwr_nrl_nsa(nrl,nsa).GT.pwrmax) THEN
                pwrmax=pwr_nrl_nsa(nrl,nsa)
                locmax=nrl
             ENDIF
          END DO
          IF(locmax.LE.1) THEN
             pos_pwrmax_rl_nsa_nray(nsa,nray)=pos_nrl(1)
          ELSE IF(locmax.GE.nrlmax) THEN
             pos_pwrmax_rl_nsa_nray(nsa,nray)=pos_nrl(nrlmax)
          ELSE
             dpwr =(pwr_nrl_nsa(locmax+1,nsa) &
                   -pwr_nrl_nsa(locmax-1,nsa))/(2.D0*drl)
             ddpwr=(pwr_nrl_nsa(locmax+1,nsa) &
                 -2*pwr_nrl_nsa(locmax,  nsa  ) &
                   +pwr_nrl_nsa(locmax-1,nsa))/drl**2
             pos_pwrmax_rl_nsa_nray(nsa,nray) &
                  =(locmax-0.5D0)/(nrlmax-1.D0)-dpwr/ddpwr
             pwrmax_rl_nsa_nray(nsa,nray)=pwrmax-dpwr**2/(2.D0*ddpwr)
          ENDIF
       END DO
    ENDDO
!    CALL PAGES
!    CALL grd1d(1,pos_nrs,pwr_nrs_nray,nrsmax,nrsmax,nraymax, &
!         '@pwr-nrs vs. pos-nrs@')
!    CALL grd1d(2,pos_nrl,pwr_nrl_nray,nrlmax,nrlmax,nraymax, &
!         '@pwr-nrl vs. pos-nrl@')
!    CALL PAGEE

    RETURN
  END SUBROUTINE wr_calc_pwr
END MODULE wrcalpwr
