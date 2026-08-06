! plview.f90

MODULE plview

CONTAINS

  !     ****** SHOW PARAMETERS ******

  SUBROUTINE pl_view

      use plcomm_parm
      implicit none
      integer:: NS,i,NCOIL

      WRITE(6,601) 'BB    ',BB    ,'RR    ',RR    , &
                   'RA    ',RA    ,'RB    ',RB
      WRITE(6,601) 'RKAP  ',RKAP  ,'RDLT  ',RDLT  , &
                   'Q0    ',Q0    ,'QA    ',QA
      WRITE(6,601) 'RIP   ',RIP   ,'PROFJ ',PROFJ

      IF(MODELG.EQ.0) THEN
         WRITE(6,601) 'RMIR  ',RMIR  ,'ZBB   ',ZBB
      ENDIF
      IF(MODELG.EQ.11) THEN
         WRITE(6,601) 'Hpitc1',Hpitch1,'Hpitc2',Hpitch2, &
                      'RRCH  ',RRCH
      END IF
      IF(MODELG.EQ.0.AND.MOD(MODELB,2).EQ.1) THEN
         WRITE(6,'(A)') '     NCOIL   RCOIL       ZCOIL       BCOIL'
         DO NCOIL=1,NCOILMAX
            WRITE(6,'(I10,1P3E12.4)') &
                 NCOIL,RCOIL(NCOIL),ZCOIL(NCOIL),BCOIL(NCOIL)
         END DO
      END IF

      WRITE(6,601) 'RHOEDG',RHOEDG,'RHOGMN',RHOGMN, &
                   'RHOGMX',RHOGMX
      WRITE(6,604) 'MODELG',MODELG,'MODELB',MODELB, &
                   'MODELQ',MODELQ
      WRITE(6,604) 'MODEFR',MODEFR,'MODEFW',MODEFW, &
                   'mdlplw',mdlplw
      WRITE(6,'(A,I5)') ' model_prof      =',model_prof
      WRITE(6,'(A,I5)') ' model_prof_time =',model_prof_time
      WRITE(6,'(A,I5)') ' MODEL_NPROF     =',MODEL_NPROF
      WRITE(6,'(A,I5)') ' model_eqdsk_psi =',model_eqdsk_psi
      WRITE(6,'(A,I5)') ' model_coll      =',model_coll
      WRITE(6,'(A,I5)') ' model_sigv      =',model_sigv

      WRITE(6,'(A)') &
           '  NS         NPA          PA          PZ          ID         KID'
      DO NS=1,NSMAX
         WRITE(6,612) NS,NPA(NS),PA(NS),PZ(NS),ID_NS(NS),KID_NS(NS)
      END DO
      WRITE(6,'(A)') &
           '  NS          PN         PNS         PNM        PZCL        PNUC'
      DO NS=1,NSMAX
         WRITE(6,613) NS,PN(NS),PNS(NS),PNM(NS),PZCL(NS),PNUC(NS)
      END DO
      WRITE(6,'(A)') &
           '  NS          PT         PTS         PTM        PTPR        PTPP'
      DO NS=1,NSMAX
         WRITE(6,613) NS,PT(NS),PTS(NS),PTM(NS),PTPR(NS),PTPP(NS)
      END DO
      WRITE(6,'(A)') &
           '  NS          PU         PUS         PUM        PUPR        PUPP'
      DO NS=1,NSMAX
         WRITE(6,613) NS,PU(NS),PUS(NS),PUM(NS),PUPR(NS),PUPP(NS)
      END DO
      WRITE(6,'(A)') &
           '  NS      PROFN1      PROFN2      PROFN3'
      DO NS=1,NSMAX
         WRITE(6,613) NS,PROFN1(NS),PROFN2(NS),PROFN3(NS)
      END DO
      WRITE(6,'(A)') &
           '  NS      PROFT1      PROFT2      PROFT3'
      DO NS=1,NSMAX
         WRITE(6,613) NS,PROFT1(NS),PROFT2(NS),PROFT3(NS)
      END DO
      WRITE(6,'(A)') &
           '  NS      PROFU1      PROFU2      PROFU3'
      DO NS=1,NSMAX
         WRITE(6,613) NS,PROFU1(NS),PROFU2(NS),PROFU3(NS)
      END DO
      WRITE(6,'(A)') &
           '  NS      RHOITB       PNITB       PTITB       PUITB'
      DO NS=1,NSMAX
         WRITE(6,613) NS,RHOITB(NS),PNITB(NS),PTITB(NS),PUITB(NS)
      END DO

      WRITE(6,601) 'PPN0  ',PPN0  ,'PTN0  ',PTN0  , &
                   'RF_PL ',RF_PL

      IF(MODELG.EQ.11.OR.MODELG.EQ.13) THEN
         WRITE(6,606) 'r_corner:  ',(r_corner(i),i=1,3)
         WRITE(6,606) 'z_corner:  ',(z_corner(i),i=1,3)
         WRITE(6,606) 'br_corner: ',(br_corner(i),i=1,3)
         WRITE(6,606) 'bz_corner: ',(bz_corner(i),i=1,3)
         WRITE(6,606) 'bt_corner: ',(bt_corner(i),i=1,3)
         DO ns=1,NSMAX
            WRITE(6,'(A,I3)') 'ns=',ns
            WRITE(6,606) 'pn_corner: ',(pn_corner(i,ns),i=1,3)
            WRITE(6,606) 'ptpr_corner:',(ptpr_corner(i,ns),i=1,3)
            WRITE(6,606) 'ptpp_corner:',(ptpp_corner(i,ns),i=1,3)
         END DO
      END IF

      WRITE(6,'(A,A)') 'KNAMEQ  = ',TRIM(KNAMEQ)
      WRITE(6,'(A,A)') 'KNAMWR  = ',TRIM(KNAMWR)
      WRITE(6,'(A,A)') 'KNAMFP  = ',TRIM(KNAMFP)
      WRITE(6,'(A,A)') 'KNAMWM  = ',TRIM(KNAMWM)
      WRITE(6,'(A,A)') 'KNAMPF  = ',TRIM(KNAMPF)
      WRITE(6,'(A,A)') 'KNAMFO  = ',TRIM(KNAMFO)
      WRITE(6,'(A,A)') 'KNAMTR  = ',TRIM(KNAMTR)
      WRITE(6,'(A,A)') 'KNAMEQ2 = ',TRIM(KNAMEQ2)
      WRITE(6,'(A,A)') 'knam_profg_TOTAL = ',TRIM(knam_profg_TOTAL)
      WRITE(6,'(A,A)') 'knam_profm_TOTAL = ',TRIM(knam_profm_TOTAL)
      RETURN

  100 FORMAT(' ','NS    NPA         PA          PZ          ', &
                       'PN          PNS')
  110 FORMAT(' ',I3,' ',I5,7X,4ES12.4)
  120 FORMAT(' ','NS    PTPR        PTPP        PTS         ', &
                       'PU          PUS')
  130 FORMAT(' ',I2,' ',1P5E12.4)
  131 FORMAT(' ','NS    PUPR        PUPP        PNUC        PZCL')
  132 FORMAT(' ',I3,' ',1P4E12.4)
  140 FORMAT(' ','NS    RHOITB      PNITB       PTITB       PUITB')
  150 FORMAT(' ',I3,' ',1P4E12.4)
  160 FORMAT(' ','NS    PROFN1      PROFN2      PROFT1      ', &
                       'PROFT2      PROFU1      PROFU2')
  170 FORMAT(' ',I3,' ',1P6E12.4)
  601 FORMAT(' ',A6,'=',1PE11.3:2X,A6,'=',1PE11.3: &
              2X,A6,'=',1PE11.3:2X,A6,'=',1PE11.3)
  604 FORMAT(' ',A6,'=',I7,4X  :2X,A6,'=',I7,4X  : &
              2X,A6,'=',I7,4X  :2X,A6,'=',I7)
  606 FORMAT(' ',A12,1P3E12.4)
  612 FORMAT(I4,I12,F12.4,F12.4,I12,8X,A4)
  613 FORMAT(I4,5F12.4)
  END SUBROUTINE pl_view
END MODULE plview
