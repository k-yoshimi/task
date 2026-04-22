!     ***********************************************************
!
!       Phase 3 split of trrslt.f90 --- physics-derived globals
!
!       Contains (kept as bare external subroutines, as in the pre-Phase-3
!       trrslt.f90, to avoid a circular module dependency with trexec which
!       provides tr_coef_decide used by TRGLOB):
!         TRGLOB  (calculate global quantities)
!         TRATOT  (save data to GVT/GVRT time-series)
!         TRATOG  (save data to GTR/GVR graphics arrays)
!
!     ***********************************************************

!     ***********************************************************

!           CALCULATE GLOBAL QUANTITIES

!     ***********************************************************

      SUBROUTINE TRGLOB

      USE TRCOMM, ONLY: rkind, &
           NRMAX, NRAMAX, NROMAX, NSM, NSMAX, NEQMAX, NFM, NSS, NSV, MDLUF, &
           PI, RKEV, RMU0, &
           RR, RA, RKAP, BB, RHOA, RIP, &
           DR, DVRHO, DVRHOG, ABVRHOG, RDPVRHOG, RMJRHO, &
           RG, RM, RN, RT, RW, RNF, &
           BP, EZOH, BETA, BETA0, BETAA, BETAL, BETAN, BETAP, BETAP0, BETAPA, &
           BETAPL, BETAQ, BETAQ0, &
           PA, PNSS, PTS, GT, &
           AJ, AJBS, AJBST, AJNB, AJNBT, AJOH, AJOHT, AJRF, AJRFT, AJRFV, &
           AJRFVT, AJT, AJTOR, AJTTOR, &
           ANS0, ANSAV, ANF0, ANFAV, ANLAV, &
           Q0, QF, QP, RQ1, &
           PBM, PBCL, PBCLT, PBIN, PBINT, PCX, PCXT, PEX, PEXST, PEXT, &
           PFCL, PFCLT, PFIN, PFINT, PIE, PIET, PINT, PLT, &
           PNB, PNBT, PNF, PNFT, POH, POHT, POUT, &
           PRB, PRBT, PRC, PRCT, PRF, PRFST, PRFT, PRFV, PRFVT, PRL, PRLT, &
           PRSUM, PRSUMT, &
           SIE, SIET, SINT, SLT, SNB, SNBT, SNF, SNFT, SOUT, SPE, SPET, &
           SPSC, SPSCT, &
           T, TPRE, TS0, TSAV, TF0, TFAV, &
           TAUE1, TAUE2, TAUE89, TAUE98, H98Y2, &
           VLOOP, VV, ALI, &
           WBULKT, WFT, WPDOT, WPPRE, WPT, WST, WTAILT, &
           ZEFF, ZEFF0, DD
      USE trexec
      USE libitp
      IMPLICIT NONE
      INTEGER:: NEQ, NF, NMK, NR, NRL, NS, NSSN, NSSN1, NSVN, NSVN1, NSW, NW
      REAL(rkind)   :: ANFSUM, C83, DRH, DV53, PAI, PLST, RNSUM, RNTSUM, &
           & RTSUM, RWSUM, SLST, SUMM, SUML, SUMP, VOL, WPOL
      REAL(rkind),DIMENSION(NRMAX):: DSRHO

      IF(RHOA.NE.1.D0) NRMAX=NROMAX

!     *** Local beta ***
!        BETAL : toroidal beta
!        BETA  : volume-averaged toroidal beta
!        BETAPL: poloidal beta
!        BETAP : volume-averaged poloidal beta
!        BETAQ : toroidal beta for reaction rate
!               (ref. TOKAMAKS 3rd, p115)

      SUMM=0.D0
      SUMP=0.D0
      VOL =0.D0
      DO NR=1,NRMAX-1
         SUML = (SUM(RN(NR,1:NSM)*RT(NR,1:NSM)) + SUM(RW(NR,1:NFM)))*RKEV*1.D20

!!         DSRHO(NR)=DVRHO(NR)/(2.D0*PI*RMJRHO(NR))
         DSRHO(NR)=DVRHO(NR)/(2.D0*PI*RR)
         VOL  = VOL  +         DVRHO(NR)*DR
         SUMM = SUMM + SUML   *DVRHO(NR)*DR
         SUMP = SUMP + SUML**2*DVRHO(NR)*DR
         BETA(NR)   = 2.D0*RMU0*SUMM     /(     VOL *BB**2)
         BETAL(NR)  = 2.D0*RMU0*SUML     /(          BB**2)
         BETAP(NR)  = 2.D0*RMU0*SUMM     /(     VOL *BP(NRMAX)**2)
         BETAPL(NR) = 2.D0*RMU0*SUML     /(          BP(NRMAX)**2)
         BETAQ(NR)  = 2.D0*RMU0*SQRT(SUMP)/(SQRT(VOL)*BB**2)
      ENDDO

      NR=NRMAX
         SUML = (SUM(RN(NR,1:NSM)*RT(NR,1:NSM)) + SUM(RW(NR,1:NFM)))*RKEV*1.D20

!!         DSRHO(NR)=DVRHO(NR)/(2.D0*PI*RMJRHO(NR))
         DSRHO(NR)=DVRHO(NR)/(2.D0*PI*RR)
         VOL  = VOL  +         DVRHO(NR)*DR
         SUMM = SUMM + SUML   *DVRHO(NR)*DR
         SUMP = SUMP + SUML**2*DVRHO(NR)*DR
         BETA(NR)   = 2.D0*RMU0*SUMM     /(     VOL *BB**2)
         BETAL(NR)  = 2.D0*RMU0*SUML     /(          BB**2)
         BETAP(NR)  = 2.D0*RMU0*SUMM     /(     VOL *BP(NRMAX)**2)
         BETAPL(NR) = 2.D0*RMU0*SUML     /(          BP(NRMAX)**2)
         BETAQ(NR)  = 2.D0*RMU0*SQRT(SUMP)/(SQRT(VOL)*BB**2)

      BETA0 =(4.D0*BETA(1)  -BETA(2)  )/3.D0
      BETAP0=(4.D0*BETAPL(1)-BETAPL(2))/3.D0
      BETAQ0=(4.D0*BETAQ(1) -BETAQ(2) )/3.D0

!     *** Global beta ***
!        BETAPA: poloidal beta at separatrix
!        BETAA : toroidal beta at separatrix
!        BETAN : normalized toroidal beta (Troyon beta)

      BETAPA=BETAP(NRMAX)
      BETAA =BETA(NRMAX)
      BETAN =BETAA*1.D2/(RIP/(RA*BB))

!     *** Volume-averaged density and temperature ***
!     *** Central density and temperature         ***
!     *** Stored energy                           ***

!     +++ for electron and bulk ions +++
      DO NS=1,NSM
         RNSUM = SUM(RN(1:NRMAX,NS)*DVRHO(1:NRMAX))
         RTSUM = SUM(RN(1:NRMAX,NS)*RT(1:NRMAX,NS)*DVRHO(1:NRMAX))
         ANSAV(NS) = RNSUM*DR/VOL
         ANS0(NS) = FCTR(RM(1),RM(2),RN(1,NS),RN(2,NS))
         IF(RNSUM.GT.0.D0) THEN
            TSAV(NS) = RTSUM/RNSUM
         ELSE
            TSAV(NS) = 0.D0
         ENDIF
         TS0(NS) = FCTR(RM(1),RM(2),RT(1,NS),RT(2,NS))
         WST(NS) = 1.5D0*RTSUM*DR*RKEV*1.D14
      ENDDO

!     +++ for fast particles +++
      IF(MDLUF.NE.0) THEN
         ANFSUM = SUM(RNF(1:NRMAX,1)*DVRHO(1:NRMAX))
         RNTSUM = SUM(RNF(1:NRMAX,1)*RT(1:NRMAX,2)*DVRHO(1:NRMAX))
         RWSUM  = SUM(PBM(1:NRMAX)  *DVRHO(1:NRMAX))
         NF=1
            WFT(NF) = RWSUM*DR*1.D-6-1.5D0*RNTSUM*DR*RKEV*1.D14
            ANFAV(NF) = ANFSUM*DR/VOL
            ANF0(NF)  = FCTR(RM(1),RM(2),RNF(1,1),RNF(2,1))
            IF(ANFSUM.GT.0.D0) THEN
               TFAV(NF)  = RWSUM/(RKEV*1.D20)/ANFSUM
            ELSE
               TFAV(NF)  = 0.D0
            ENDIF
            IF(RNF(1,1).GT.0.D0) THEN
               TF0(NF)  = FCTR(RM(1),RM(2),PBM(1),PBM(2))/(RKEV*1.D20)/ANF0(NF)
            ELSE
               TF0(NF)  = 0.D0
            ENDIF
         NF=2
            WFT(NF) = 0.D0
            ANFAV(NF) = 0.D0
            ANF0(NF)  = 0.D0
            TFAV(NF)  = 0.D0
            TF0(NF)   = 0.D0
      ELSE
         DO NF=1,NFM
            ANFSUM=0.D0
            RWSUM=0.D0
            DO NR=1,NRMAX
               ANFSUM = ANFSUM+RNF(NR,NF)*DVRHO(NR)
               RWSUM  = RWSUM +RW (NR,NF)*DVRHO(NR)
            ENDDO
            WFT(NF) = 1.5D0*RWSUM*DR*RKEV*1.D14
            ANFAV(NF) = ANFSUM*DR/VOL
            ANF0(NF)  = FCTR(RM(1),RM(2),RNF(1,NF),RNF(2,NF))
            IF(ANFSUM.GT.0.D0) THEN
               TFAV(NF)  = RWSUM/ANFSUM
            ELSE
               TFAV(NF)  = 0.D0
            ENDIF
            IF(RNF(1,NF).GT.0.D0) THEN
               TF0(NF)  = FCTR(RM(1),RM(2),RW(1,NF),RW(2,NF))/ANF0(NF)
            ELSE
               TF0(NF)  = 0.D0
            ENDIF
         ENDDO
      ENDIF

!     *** Line-averaged densities ***

      DO NS=1,NSM
         ANLAV(NS)=SUM(RN(1:NRMAX,NS))*DR
      ENDDO

!     *** Particle source ***

      DO NS=1,NSMAX
         SPSCT(NS) = SUM(SPSC(1:NRMAX,NS)*DVRHO(1:NRMAX))*DR
      END DO

!     *** Ohmic, NBI and fusion powers ***

      POHT = SUM(POH(1:NRMAX)*DVRHO(1:NRMAX))*DR/1.D6
      PNBT = SUM(PNB(1:NRMAX)*DVRHO(1:NRMAX))*DR/1.D6
      PNFT = SUM(PNF(1:NRMAX)*DVRHO(1:NRMAX))*DR/1.D6

!     *** External power typically for NBI from exp. data ***

      DO NS=1,NSM
         PEXT(NS) = SUM(PEX(1:NRMAX,NS)*DVRHO(1:NRMAX))*DR/1.D6
      ENDDO

!     *** RF power ***

      DO NS=1,NSM
         PRFVT(NS,1) = SUM(PRFV(1:NRMAX,NS,1)*DVRHO(1:NRMAX))*DR/1.D6
         PRFVT(NS,2) = SUM(PRFV(1:NRMAX,NS,2)*DVRHO(1:NRMAX))*DR/1.D6
         PRFVT(NS,3) = SUM(PRFV(1:NRMAX,NS,3)*DVRHO(1:NRMAX))*DR/1.D6
         PRFT (NS  ) = SUM(PRF (1:NRMAX,NS)  *DVRHO(1:NRMAX))*DR/1.D6
      ENDDO

!     *** Total NBI power distributed on electrons and bulk ions ***

      PBINT = SUM(PBIN(1:NRMAX)*DVRHO(1:NRMAX))*DR/1.D6
      DO NS=1,NSM
         PBCLT(NS) = SUM(PBCL(1:NRMAX,NS)*DVRHO(1:NRMAX))*DR/1.D6
      ENDDO

!     *** Total RF power distributed on electrons and bulk ions ***

      PFINT = SUM(PFIN(1:NRMAX)*DVRHO(1:NRMAX))*DR/1.D6
      DO NS=1,NSM
         PFCLT(NS) = SUM(PFCL(1:NRMAX,NS)*DVRHO(1:NRMAX))*DR/1.D6
      ENDDO

!     *** Radiation, charge exchange and ionization losses ***

      PRBT  = SUM(PRB(1:NRMAX)*DVRHO(1:NRMAX))*DR/1.D6
      PRCT  = SUM(PRC(1:NRMAX)*DVRHO(1:NRMAX))*DR/1.D6
      PRLT  = SUM(PRL(1:NRMAX)*DVRHO(1:NRMAX))*DR/1.D6
      PRSUMT= SUM(PRSUM(1:NRMAX)*DVRHO(1:NRMAX))*DR/1.D6
      PCXT  = SUM(PCX(1:NRMAX)*DVRHO(1:NRMAX))*DR/1.D6
      PIET  = SUM(PIE(1:NRMAX)*DVRHO(1:NRMAX))*DR/1.D6

!     *** Current densities ***

      AJNBT     = SUM(AJNB (1:NRMAX)  *DSRHO(1:NRMAX))*DR/1.D6
      AJRFVT(1) = SUM(AJRFV(1:NRMAX,1)*DSRHO(1:NRMAX))*DR/1.D6
      AJRFVT(2) = SUM(AJRFV(1:NRMAX,2)*DSRHO(1:NRMAX))*DR/1.D6
      AJRFVT(3) = SUM(AJRFV(1:NRMAX,3)*DSRHO(1:NRMAX))*DR/1.D6
      AJRFT     = SUM(AJRF (1:NRMAX)  *DSRHO(1:NRMAX))*DR/1.D6
      AJBST     = SUM(AJBS (1:NRMAX)  *DSRHO(1:NRMAX))*DR/1.D6

      AJT    = SUM(AJ   (1:NRMAX)*DSRHO(1:NRMAX))*DR/1.D6
      ! Plasma current, AJTTOR
      AJTTOR = SUM(AJTOR(1:NRMAX)*DSRHO(1:NRMAX))*DR/1.D6
      AJOHT  = SUM(AJOH (1:NRMAX)*DSRHO(1:NRMAX))*DR/1.D6

!     *** Output source and power ***
!        evaluate output power using flux at NR=NRMAX

      IF(RHOA.EQ.1.D0) THEN
         NRL=NRMAX
      ELSE
         NRL=NRAMAX
      ENDIF
      NSW=3
      NRMAX=NRAMAX
      ! #142 B4: TR_COEF_DECIDE now returns IERR. In TRGLOB this is a
      ! result-aggregation context (output power computation) — not a
      ! critical path. Log and continue rather than abort, so a single
      ! bad cell does not halt the diagnostic post-step.
      BLOCK
         INTEGER :: tcd_ierr
         CALL TR_COEF_DECIDE(NRL,NSW,DV53,tcd_ierr)
         IF(tcd_ierr.NE.0) THEN
            WRITE(6,'(A,I3,A,I3)') &
                 '## TRGLOB: TR_COEF_DECIDE returned IERR=', tcd_ierr, &
                 ' at NRL=', NRL
         END IF
      END BLOCK
      NRMAX=NROMAX
      NMK=2
      DRH=DR/DVRHO(NRL)**(2.D0/3.D0)
      C83=8.D0/3.D0
      DO NEQ=1,NEQMAX
         NSSN=NSS(NEQ)
         NSVN=NSV(NEQ)
         SUML=0.D0
         DO NW=1,NEQMAX
            NSSN1=NSS(NW)
            NSVN1=NSV(NW)
            IF(NSVN1.EQ.1) THEN
               SUML=SUML+(-DD(NEQ,NW,NMK,NSW)/3.D0)*DRH *RN(NRL-1,NSSN1) &
     &                  +  DD(NEQ,NW,NMK,NSW)*3.D0 *DRH *RN(NRL  ,NSSN1) &
     &                  +( VV(NEQ,NW,NMK,NSW)      *DRH &
     &                    -DD(NEQ,NW,NMK,NSW)*C83 )*DRH *PNSS(NSSN1)
            ELSEIF(NSVN1.EQ.2) THEN
               SUML=SUML+(-DD(NEQ,NW,NMK,NSW)/3.D0)*DRH *RN(NRL-1,NSSN1)*RT(NRL-1,NSSN1) &
     &                  +  DD(NEQ,NW,NMK,NSW)*3.D0 *DRH *RN(NRL  ,NSSN1)*RT(NRL  ,NSSN1) &
     &                  +( VV(NEQ,NW,NMK,NSW)      *DRH &
     &                    -DD(NEQ,NW,NMK,NSW)*C83  *DRH)*PNSS(NSSN1)*PTS (NSSN1)
            ENDIF
         ENDDO
         IF(NSVN.EQ.1) THEN
            SLT(NSSN)=SUML*RKEV*1.D14
         ELSEIF(NSVN.EQ.2) THEN
            PLT(NSSN)=SUML*RKEV*1.D14
         ENDIF
      ENDDO

!     *** Ionization, fusion and NBI fuelling ***

      SIET = SUM(SIE(1:NRMAX)*DVRHO(1:NRMAX))*DR
      SNFT = SUM(SNF(1:NRMAX)*DVRHO(1:NRMAX))*DR
      SNBT = SUM(SNB(1:NRMAX)*DVRHO(1:NRMAX))*DR

!     *** Pellet injection fuelling ***

      DO NS=1,NSM
         SPET(NS) = SUM(SPE(1:NRMAX,NS)*DVRHO(1:NRMAX))*DR/RKAP
      ENDDO

!     *** Input and output sources and powers ***

      WBULKT=SUM(WST(1:NSM))
      PEXST =SUM(PEXT(1:NSM))
      PRFST =SUM(PRFT(1:NSM))
      PLST  =SUM(PLT(1:NSM))
      SLST  =SUM(SLT(1:NSM))
      WTAILT=SUM(WFT(1:NFM))

      WPT =WBULKT+WTAILT
      PINT=POHT+PNBT+PRFST+PNFT+PEXST
      POUT=PLST+PCXT+PIET+PRBT+PRCT+PRLT
      SINT=SIET+SNBT
      SOUT=SLST

!     *** Energy confinement times ***
!        TAUE1: steady state
!        TAUE2: transient

      IF(ABS(T-TPRE).LE.1.D-70) THEN
         WPDOT=0.D0
      ELSE
         WPDOT=(WPT-WPPRE)/(T-TPRE)
      ENDIF
      WPPRE=WPT
      TPRE=T

      TAUE1=WPT/PINT
      TAUE2=WPT/(PINT-WPDOT)

!     *** Inductance and one-turn voltage ***

      WPOL=SUM(ABVRHOG(1:NRMAX)*RDPVRHOG(1:NRMAX)**2*DVRHOG(1:NRMAX))*DR/(2.D0*RMU0)
      ALI=4.D0*WPOL/(RMU0*RR*(AJTTOR*1.D6)**2)

      VLOOP = EZOH(NRMAX)*2.D0*PI*RR

!     *** Confinement scalings (TOKAMAKS 3rd p183,184) ***
!        TAUE89: ITER89-P L-mode scaling
!        TAUE98: IPB98(y,2) H-mode scaling with ELMs
!        H98Y2: H-mode factor

!     volume-averaged isotopic mass number
      PAI = (PA(2)*ANSAV(2)+PA(3)*ANSAV(3)+PA(4)*ANSAV(4))  /(ANSAV(2)+ANSAV(3)+ANSAV(4))

      TAUE89=4.8D-2*(ABS(RIP)**0.85D0)    *(RR**1.2D0) *(RA**0.3D0)  *(RKAP**0.5D0) &
     &             *(ANLAV(1)**0.1D0)*(ABS(BB)**0.2D0) *(PAI**0.5D0) *(PINT**(-0.5D0))
      TAUE98=0.145D0*(ABS(RIP)**0.93D0)   *(RR**1.39D0)*(RA**0.58D0) *(RKAP**0.78D0) &
     &            *(ANLAV(1)**0.41D0)*(ABS(BB)**0.15D0)*(PAI**0.19D0)*(PINT**(-0.69D0))
      H98Y2=TAUE2/TAUE98

!     *** Fusion production rate ***

      QF=5.D0*PNFT/(POHT+PNBT+PRFST+PEXST)

!     *** Distance of q=1 surface from magnetic axis ***

      IF(Q0.GE.1.D0) THEN
         RQ1=0.D0
      ELSE
         IF(QP(1).GT.1.D0) THEN
            RQ1=SQRT((1.D0-Q0)/(QP(1)-Q0))*DR
            GOTO 310
         ENDIF
         DO NR=2,NRMAX
            IF(QP(NR).GT.1.D0) THEN
              RQ1=(RG(NR)-RG(NR-1))*RA*(1.D0-QP(NR-1))/(QP(NR)-QP(NR-1))+RG(NR-1)*RA
               GOTO 310
            ENDIF
         ENDDO
         RQ1=RA
  310    CONTINUE
      ENDIF

!     *** Effective charge number at axis ***

      ZEFF0=(4.D0*ZEFF(1)-ZEFF(2))/3.D0

      IF(RHOA.NE.1.D0) NRMAX=NRAMAX
      RETURN
      END SUBROUTINE TRGLOB

!     ***********************************************************

!           SAVE DATA TO DATAT FOR GRAPHICS

!     ***********************************************************

      SUBROUTINE TRATOT

      USE TRCOMM, ONLY : &
           & AJ, AJBS, AJBST, AJNB, AJNBT, AJOH, AJOHT, AJRF, AJRFT, AJRFV, &
           & AJT, AJTTOR, AK, AKDW, ALI, ANC, ANF0, ANFAV, ANFE, ANLAV, &
           & ANS0, ANSAV, AR1RHO, AR2RHO, BB, BETA, BETA0, BETAA, BETAP, &
           & BETAP0, BETAPA, BP, DR, DVRHO, ER, ETA, EZOH, GVRT, GT, GVT, &
           & H98Y2, NGT, NRAMAX, NRMAX, NROMAX, NTM, PBCLT, PBINT, & 
           & PCX, PCXT, PEX, PEXT, PFCLT, PFINT, PI, PIE, PIET, PINT, PLT, &
           & PNB, PNBT, PNF, PNFT, POH, POHT, POUT, PRF, PRFT, PRFV, PRFVT, &
           & PRL, PRLT, Q0, QF, QP, RA, RHOA, RIP, RKAP, RKPRHO, RM, RMJRHO, &
           & RMNRHO, RN, RPSI, RQ1, RR, RT, RW, S, ALPHA, SIET, SINT, SLT, &
           & SNBT, SNFT, SOUT, T, TAUE1, TAUE2, TAUE89, TAUE98, TF0, TFAV, &
           & TS0, TSAV, VLOOP, VPOL, VTOR, WBULKT, WFT, WPDOT, WPT, WST, &
           & WTAILT, ZEFF, ZEFF0, RKCV, PRBT, PRCT, PRSUMT, rkind
      USE libspl1d
      IMPLICIT NONE
      INTEGER:: IERR, NR
      REAL(rkind)   :: RMN, F0D
      REAL(rkind),DIMENSION(NRMAX):: DERIV, U0
      REAL(rkind),DIMENSION(4,NRMAX):: U
      REAL(rkind)   :: TRCOFS
      REAL   :: GUCLIP


      IF(NGT.GE.NTM) RETURN
      NGT=NGT+1

      GT    (NGT) = GUCLIP(T)
!
      GVT(NGT, 1) = GUCLIP(ANS0(1))
      GVT(NGT, 2) = GUCLIP(ANS0(2))
      GVT(NGT, 3) = GUCLIP(ANS0(3))
      GVT(NGT, 4) = GUCLIP(ANS0(4))
      GVT(NGT, 5) = GUCLIP(ANSAV(1))
      GVT(NGT, 6) = GUCLIP(ANSAV(2))
      GVT(NGT, 7) = GUCLIP(ANSAV(3))
      GVT(NGT, 8) = GUCLIP(ANSAV(4))

      GVT(NGT, 9) = GUCLIP(TS0(1))
      GVT(NGT,10) = GUCLIP(TS0(2))
      GVT(NGT,11) = GUCLIP(TS0(3))
      GVT(NGT,12) = GUCLIP(TS0(4))
      GVT(NGT,13) = GUCLIP(TSAV(1))
      GVT(NGT,14) = GUCLIP(TSAV(2))
      GVT(NGT,15) = GUCLIP(TSAV(3))
      GVT(NGT,16) = GUCLIP(TSAV(4))

      GVT(NGT,17) = GUCLIP(WST(1))
      GVT(NGT,18) = GUCLIP(WST(2))
      GVT(NGT,19) = GUCLIP(WST(3))
      GVT(NGT,20) = GUCLIP(WST(4))

      GVT(NGT,21) = GUCLIP(ANF0(1))
      GVT(NGT,22) = GUCLIP(ANF0(2))
      GVT(NGT,23) = GUCLIP(ANFAV(1))
      GVT(NGT,24) = GUCLIP(ANFAV(2))
      GVT(NGT,25) = GUCLIP(TF0(1))
      GVT(NGT,26) = GUCLIP(TF0(2))
      GVT(NGT,27) = GUCLIP(TFAV(1))
      GVT(NGT,28) = GUCLIP(TFAV(2))

      GVT(NGT,29) = GUCLIP(WFT(1))
      GVT(NGT,30) = GUCLIP(WFT(2))
      GVT(NGT,31) = GUCLIP(WBULKT)
      GVT(NGT,32) = GUCLIP(WTAILT)
      GVT(NGT,33) = GUCLIP(WPT)

      GVT(NGT,34) = GUCLIP(AJT)
      GVT(NGT,35) = GUCLIP(AJOHT)
      GVT(NGT,36) = GUCLIP(AJNBT)
      GVT(NGT,37) = GUCLIP(AJRFT)
      GVT(NGT,38) = GUCLIP(AJBST)

      GVT(NGT,39) = GUCLIP(PINT)
      GVT(NGT,40) = GUCLIP(POHT)
      GVT(NGT,41) = GUCLIP(PNBT)
      GVT(NGT,42) = GUCLIP(PRFT(1))
      GVT(NGT,43) = GUCLIP(PRFT(2))
      GVT(NGT,44) = GUCLIP(PRFT(3))
      GVT(NGT,45) = GUCLIP(PRFT(4))
      GVT(NGT,46) = GUCLIP(PNFT)

      GVT(NGT,47) = GUCLIP(PBINT)
      GVT(NGT,48) = GUCLIP(PBCLT(1))
      GVT(NGT,49) = GUCLIP(PBCLT(2))
      GVT(NGT,50) = GUCLIP(PBCLT(3))
      GVT(NGT,51) = GUCLIP(PBCLT(4))
      GVT(NGT,52) = GUCLIP(PFINT)
      GVT(NGT,53) = GUCLIP(PFCLT(1))
      GVT(NGT,54) = GUCLIP(PFCLT(2))
      GVT(NGT,55) = GUCLIP(PFCLT(3))
      GVT(NGT,56) = GUCLIP(PFCLT(4))

      GVT(NGT,57) = GUCLIP(POUT)
      GVT(NGT,58) = GUCLIP(PCXT)
      GVT(NGT,59) = GUCLIP(PIET)
      GVT(NGT,60) = GUCLIP(PRSUMT)
      GVT(NGT,61) = GUCLIP(PLT(1))
      GVT(NGT,62) = GUCLIP(PLT(2))
      GVT(NGT,63) = GUCLIP(PLT(3))
      GVT(NGT,64) = GUCLIP(PLT(4))

      GVT(NGT,65) = GUCLIP(SINT)
      GVT(NGT,66) = GUCLIP(SIET)
      GVT(NGT,67) = GUCLIP(SNBT)
      GVT(NGT,68) = GUCLIP(SNFT)
      GVT(NGT,69) = GUCLIP(SOUT)
      GVT(NGT,70) = GUCLIP(SLT(1))
      GVT(NGT,71) = GUCLIP(SLT(2))
      GVT(NGT,72) = GUCLIP(SLT(3))
      GVT(NGT,73) = GUCLIP(SLT(4))

      GVT(NGT,74) = GUCLIP(VLOOP)
      GVT(NGT,75) = GUCLIP(ALI)
      GVT(NGT,76) = GUCLIP(RQ1)
      GVT(NGT,77) = GUCLIP(Q0)

      GVT(NGT,78) = GUCLIP(WPDOT)
      GVT(NGT,79) = GUCLIP(TAUE1)
      GVT(NGT,80) = GUCLIP(TAUE2)
      GVT(NGT,81) = GUCLIP(TAUE89)

      GVT(NGT,82) = GUCLIP(BETAP0)
      GVT(NGT,83) = GUCLIP(BETAPA)
      GVT(NGT,84) = GUCLIP(BETA0)
      GVT(NGT,85) = GUCLIP(BETAA)

      GVT(NGT,86) = GUCLIP(ZEFF0)
      GVT(NGT,87) = GUCLIP(QF)
      GVT(NGT,88) = GUCLIP(RIP)
!
      GVT(NGT,89) = GUCLIP(PEXT(1))
      GVT(NGT,90) = GUCLIP(PEXT(2))
      GVT(NGT,91) = GUCLIP(PRFVT(1,1)) ! ECH  to electron
      GVT(NGT,92) = GUCLIP(PRFVT(2,1)) ! ECH  to ions
      GVT(NGT,93) = GUCLIP(PRFVT(1,2)) ! LH   to electron
      GVT(NGT,94) = GUCLIP(PRFVT(2,2)) ! LH   to ions
      GVT(NGT,95) = GUCLIP(PRFVT(1,3)) ! ICRH to electron
      GVT(NGT,96) = GUCLIP(PRFVT(2,3)) ! ICRH to ions

      GVT(NGT,97) = GUCLIP(RR)
      GVT(NGT,98) = GUCLIP(RA)
      GVT(NGT,99) = GUCLIP(BB)
      GVT(NGT,100)= GUCLIP(RKAP)
      GVT(NGT,101)= GUCLIP(AJTTOR)

      GVT(NGT,102)= GUCLIP(TAUE98)
      GVT(NGT,103)= GUCLIP(H98Y2)
      GVT(NGT,104)= GUCLIP(ANLAV(1))
      GVT(NGT,105)= GUCLIP(ANLAV(2))
      GVT(NGT,106)= GUCLIP(ANLAV(3))
      GVT(NGT,107)= GUCLIP(ANLAV(4))

      GVT(NGT,108)= GUCLIP(PRBT)
      GVT(NGT,109)= GUCLIP(PRCT)
      GVT(NGT,110)= GUCLIP(PRLT)

!     *** FOR 3D ***

      IF(RHOA.NE.1.D0) NRMAX=NROMAX
      CALL SPL1D  (RM,DVRHO,DERIV,U,NRMAX,0,IERR)
      CALL SPL1DI0(RM,U,U0,NRMAX,IERR)
      DO NR=1,NRMAX
         GVRT(NR,NGT, 1) = GUCLIP(RT(NR,1))
         GVRT(NR,NGT, 2) = GUCLIP(RT(NR,2))
         GVRT(NR,NGT, 3) = GUCLIP(RT(NR,3))
         GVRT(NR,NGT, 4) = GUCLIP(RT(NR,4))

         GVRT(NR,NGT, 5) = GUCLIP(RN(NR,1))
         GVRT(NR,NGT, 6) = GUCLIP(RN(NR,2))
         GVRT(NR,NGT, 7) = GUCLIP(RN(NR,3))
         GVRT(NR,NGT, 8) = GUCLIP(RN(NR,4))

         GVRT(NR,NGT, 9) = GUCLIP(AJ  (NR))
         GVRT(NR,NGT,10) = GUCLIP(AJOH(NR))
         GVRT(NR,NGT,11) = GUCLIP(AJNB(NR))
         GVRT(NR,NGT,12) = GUCLIP(AJRF(NR))
         GVRT(NR,NGT,13) = GUCLIP(AJBS(NR))

         GVRT(NR,NGT,14) = GUCLIP(POH(NR)+PNB(NR)+PNF(NR) &
     &                         +PEX(NR,1)+PEX(NR,2)+PEX(NR,3)+PEX(NR,4) &
     &                         +PRF(NR,1)+PRF(NR,2)+PRF(NR,3)+PRF(NR,4))
         GVRT(NR,NGT,15) = GUCLIP(POH(NR))
         GVRT(NR,NGT,16) = GUCLIP(PNB(NR))
         GVRT(NR,NGT,17) = GUCLIP(PNF(NR))
         GVRT(NR,NGT,18) = GUCLIP(PRF(NR,1))
         GVRT(NR,NGT,19) = GUCLIP(PRF(NR,2))
         GVRT(NR,NGT,20) = GUCLIP(PRF(NR,3))
         GVRT(NR,NGT,21) = GUCLIP(PRF(NR,4))
         GVRT(NR,NGT,22) = GUCLIP(PRL(NR))
         GVRT(NR,NGT,23) = GUCLIP(PCX(NR))
         GVRT(NR,NGT,24) = GUCLIP(PIE(NR))
         GVRT(NR,NGT,25) = GUCLIP(PEX(NR,1))
         GVRT(NR,NGT,26) = GUCLIP(PEX(NR,2))

!         IF (NR.EQ.1) THEN
!            GVRT(NR,NGT,27) = GUCLIP(Q0)
!         ELSE
            GVRT(NR,NGT,27) = GUCLIP(QP(NR))
!         ENDIF
         GVRT(NR,NGT,28) = GUCLIP(EZOH(NR))
         GVRT(NR,NGT,29) = GUCLIP(BETA(NR))
         GVRT(NR,NGT,30) = GUCLIP(BETAP(NR))
         GVRT(NR,NGT,31) = GUCLIP(EZOH(NR)*2.D0*PI*RR)
         GVRT(NR,NGT,32) = GUCLIP(ETA(NR))
         GVRT(NR,NGT,33) = GUCLIP(ZEFF(NR))
         GVRT(NR,NGT,34) = GUCLIP(AK(NR,1))
         GVRT(NR,NGT,35) = GUCLIP(AK(NR,2))

         GVRT(NR,NGT,36) = GUCLIP(PRFV(NR,1,1))
         GVRT(NR,NGT,37) = GUCLIP(PRFV(NR,1,2))
         GVRT(NR,NGT,38) = GUCLIP(PRFV(NR,1,3))
         GVRT(NR,NGT,39) = GUCLIP(PRFV(NR,2,1))
         GVRT(NR,NGT,40) = GUCLIP(PRFV(NR,2,2))
         GVRT(NR,NGT,41) = GUCLIP(PRFV(NR,2,3))

         GVRT(NR,NGT,42) = GUCLIP(AJRFV(NR,1))
         GVRT(NR,NGT,43) = GUCLIP(AJRFV(NR,2))
         GVRT(NR,NGT,44) = GUCLIP(AJRFV(NR,3))

         GVRT(NR,NGT,45) = GUCLIP(RW(NR,1)+RW(NR,2))
         GVRT(NR,NGT,46) = GUCLIP(ANC(NR)+ANFE(NR))
         GVRT(NR,NGT,47) = GUCLIP(BP(NR))
         GVRT(NR,NGT,48) = GUCLIP(RPSI(NR))

         GVRT(NR,NGT,49) = GUCLIP(RMJRHO(NR))
         GVRT(NR,NGT,50) = GUCLIP(RMNRHO(NR))
         RMN=(DBLE(NR)-0.5D0)*DR
         CALL SPL1DI(RMN,F0D,RM,U,U0,NRMAX,IERR)
         GVRT(NR,NGT,51) = GUCLIP(F0D)
         GVRT(NR,NGT,52) = GUCLIP(RKPRHO(NR))
         GVRT(NR,NGT,53) = GUCLIP(1.D0) ! DELTAR
         GVRT(NR,NGT,54) = GUCLIP(AR1RHO(NR))
         GVRT(NR,NGT,55) = GUCLIP(AR2RHO(NR))
         GVRT(NR,NGT,56) = GUCLIP(AKDW(NR,1))
         GVRT(NR,NGT,57) = GUCLIP(AKDW(NR,2))
         GVRT(NR,NGT,58) = GUCLIP(RN(NR,1)*RT(NR,1))
         GVRT(NR,NGT,59) = GUCLIP(RN(NR,2)*RT(NR,2))

         GVRT(NR,NGT,60) = GUCLIP(VTOR(NR))
         GVRT(NR,NGT,61) = GUCLIP(VPOL(NR))

         GVRT(NR,NGT,62) = GUCLIP(S(NR)-ALPHA(NR))
         GVRT(NR,NGT,63) = GUCLIP(ER(NR))
         GVRT(NR,NGT,64) = GUCLIP(S(NR))
         GVRT(NR,NGT,65) = GUCLIP(ALPHA(NR))
         GVRT(NR,NGT,66) = GUCLIP(TRCOFS(S(NR),ALPHA(NR),RKCV(NR)))
         GVRT(NR,NGT,67) = GUCLIP(2.D0*PI/QP(NR))

      ENDDO
      IF(RHOA.NE.1.D0) NRMAX=NRAMAX
!
      RETURN
      END SUBROUTINE TRATOT

!     ***********************************************************

!           SAVE DATA TO DATA FOR GRAPHICS

!     ***********************************************************

      SUBROUTINE TRATOG

      USE TRCOMM, ONLY : AJ, AJBS, AJNB, AJOH, AJRF, AK, BP, EZOH, GTR, GVR, NGM, NGR, NRAMAX, NRMAX , NROMAX, &
     &                   PIN, POH, Q0, QP, RHOA, RN, RPSI, RT, T, VGR1
      IMPLICIT NONE
      INTEGER:: NR
      REAL   :: GUCLIP


      IF(NGR.GE.NGM) RETURN
      NGR=NGR+1
      GTR(NGR)=GUCLIP(T)

      IF(RHOA.NE.1.D0) NRMAX=NROMAX
      DO NR=1,NRMAX
         GVR(NR,NGR, 1)  = GUCLIP(RN(NR,1))
         GVR(NR,NGR, 2)  = GUCLIP(RN(NR,2))
         GVR(NR,NGR, 3)  = GUCLIP(RN(NR,3))
         GVR(NR,NGR, 4)  = GUCLIP(RN(NR,4))
         GVR(NR,NGR, 5)  = GUCLIP(RT(NR,1))
         GVR(NR,NGR, 6)  = GUCLIP(RT(NR,2))
         GVR(NR,NGR, 7)  = GUCLIP(RT(NR,3))
         GVR(NR,NGR, 8)  = GUCLIP(RT(NR,4))
         GVR(NR+1,NGR, 9)  = GUCLIP(QP(NR))
         GVR(NR,NGR,10)  = GUCLIP(AJ(NR)*1.D-6)
         GVR(NR,NGR,11)  = GUCLIP(EZOH(NR))
         GVR(NR,NGR,12)  = GUCLIP(AJOH(NR)*1.D-6)
         GVR(NR,NGR,13)  = GUCLIP((AJNB(NR)+AJRF(NR))*1.D-6)
         GVR(NR,NGR,14)  = GUCLIP(AJBS(NR)*1.D-6)
         GVR(NR,NGR,15)  = GUCLIP((PIN(NR,1)+PIN(NR,2) &
     &                           +PIN(NR,3)+PIN(NR,4))*1.D-6)
         GVR(NR,NGR,16)  = GUCLIP(POH(NR)*1.D-6)
         GVR(NR,NGR,17)  = GUCLIP(VGR1(NR,2))
         GVR(NR,NGR,18)  = GUCLIP(VGR1(NR,1))
         GVR(NR,NGR,19)  = GUCLIP(VGR1(NR,3))
!         GVR(NR,NGR,19)  = GUCLIP(VGR3(NR,1))
         GVR(NR,NGR,20)  = GUCLIP(AK(NR,1))
         GVR(NR,NGR,21)  = GUCLIP(AK(NR,2))
!         GVR(NR,NGR,17)  = GUCLIP(RW(NR,1)*1.D-6*1.5D0)
!         GVR(NR,NGR,18)  = GUCLIP(RW(NR,2)*1.D-6*1.5D0)
!         GVR(NR,NGR,19)  = GUCLIP(PNB(NR)*1.D-6)
!         GVR(NR,NGR,20)  = GUCLIP(PNF(NR)*1.D-6)
         GVR(NR,NGR,22)  = GUCLIP(BP(NR))
         GVR(NR,NGR,23)  = GUCLIP(RPSI(NR))
      ENDDO
         GVR(1,NGR, 9)  = GUCLIP(Q0)
      IF(RHOA.NE.1.D0) NRMAX=NRAMAX

      RETURN
      END SUBROUTINE TRATOG

