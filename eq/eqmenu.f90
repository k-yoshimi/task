!     $Id$
!
! Phase F-3 (MED tier): free-form F90 conversion of eqmenu.f.
! Interactive menu driver (EQMENU). Preserves exact numerical
! semantics of the original fixed-form source.
!
! NOTE: IMPLICIT NONE is NOT added here because the INCLUDEd shim
!       'eqcomc.inc' already supplies an IMPLICIT statement
!       (IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)) and USEs the
!       F-1 MODULEs for the COMMON symbols.
!
!   ***** TASK/EQ MENU *****
!
      SUBROUTINE EQMENU

      USE libkio
      USE plcomm
      USE eqcom0_mod
      USE eqcom1_mod
      USE eqcom2_mod
      IMPLICIT COMPLEX*16(C),REAL*8(A,B,D-F,H,O-Z)

      EXTERNAL EQPARM
      CHARACTER KNAM*80,KPNAME*80
      CHARACTER KID*1,LINE*80
      SAVE INIT,MSTAT,KPNAME
      DATA INIT/0/

      IF(INIT.EQ.0) THEN
         MSTAT=0
         KPNAME='eqparm'
         INIT=1
      ENDIF

    1 CONTINUE
         IERR=0
         WRITE(6,601)
         WRITE(6,602)
  601    FORMAT('## EQ MENU: R/RUN  C/CONT  P,V,I/PARM  G/GRAPH', &
                            '  M/MULT  S,L,K,F/FILE')
 602     FORMAT('            H/RPPL  Q/QUIT')

         CALL TASK_KLIN(LINE,KID,MODE,EQPARM)
      IF(MODE.NE.1) GOTO 1

      IF(KID.EQ.'R') THEN
         MSTAT=0
         CALL EQCALC(IERR)
            IF(IERR.NE.0) GOTO 1
         MSTAT=1
         CALL EQCALQ(IERR)
            IF(IERR.NE.0) GOTO 1

      ELSEIF(KID.EQ.'C') THEN
         IF(MSTAT.GE.1) THEN
  101       WRITE(6,*) '#EQ> INPUT PP0,PP1,PP2,PJ0,PJ1,PJ2,RIP,HM:'
            READ(5,*,ERR=101,END=1) PP0,PP1,PP2,PJ0,PJ1,PJ2,RIP,HM

            CALL EQLOOP(IERR)
               IF(IERR.NE.0) GO TO 101
            CALL EQTORZ
            CALL EQCALP
            MSTAT=1
            CALL EQCALQ(IERR)
               IF(IERR.NE.0) GOTO 1
         ELSE
            WRITE(6,*) 'XX No data for continuing calculation!'
         ENDIF

      ELSEIF(KID.EQ.'P') THEN
         CALL EQPARM(0,'EQ',IERR)

      ELSEIF(KID.EQ.'V') THEN
         CALL EQVIEW

      ELSEIF(KID.EQ.'I') THEN
   20    WRITE(6,'(A,A)') '#EQ> INPUT : EQPARM FILE NAME : ',KPNAME
         READ(5,'(A80)',ERR=20,END=9000) KPNAME
         CALL EQPARM(1,KPNAME,IERR)

      ELSEIF(KID.EQ.'G') THEN
         CALL EQGOUT(MSTAT)

      ELSEIF(KID.EQ.'M') THEN
  102    WRITE(6,*) '#EQ> INPUT WHAT IS YOUR NUMBER OF TIMES? (1-5):'
         READ(5,*,ERR=102,END=1) NTIMES
         IF (NTIMES.LT.5) THEN
  103    WRITE(6,*) '#EQ> INPUT NEXT PV0:'
         READ(5,*,ERR=103,END=1) PV0
         ENDIF
         DO NSG=1,NSGMAX
         DO NTG=1,NTGMAX
            PSIO(NTG,NSG,NTIMES) = PSI(NTG,NSG)
         ENDDO
         ENDDO

      ELSEIF(KID.EQ.'S') THEN
         CALL EQSAVE(IERR)

      ELSEIF(KID.EQ.'L') THEN
         IF(MODELG.EQ.2) MODELG=3
         CALL EQ_READ(IERR)
         IF(IERR.NE.0) GO TO 1
         CALL EQCALQ(IERR)
         IF(IERR.NE.0) GO TO 1
         IF(modelg.EQ.3) THEN
            MSTAT=1
         ELSE
            MSTAT=2
         END IF

      ELSEIF(KID.EQ.'K') THEN
   11    WRITE(6,*) '#EQ> INPUT : EQDSK FILE NAME : ',TRIM(KNAMEQ)
         READ(5,'(A80)',ERR=11,END=9000) KNAM
         IF(KNAM(1:2).NE.'/ ') KNAMEQ=KNAM

         MODELG=5
         CALL EQ_READ(IERR)
         IF(IERR.NE.0) GOTO 11
         CALL EQCALQ(IERR)
         MSTAT=2

      ELSEIF(KID.EQ.'F') THEN
         IF(MSTAT.NE.0) CALL EQMETRIC(IERR)

      ELSEIF(KID.EQ.'H') THEN
         if(MSTAT .eq. 0) return
         call read_rppl(ierr)
         if(ierr .eq. 0) call eqrppl(IERR)
         MSTAT=3

      ELSE IF(KID.EQ.'X'.OR.KID.EQ.'#') THEN
         CONTINUE
      ELSEIF(KID.EQ.'Q') THEN
         GOTO 9000
      ELSE
         WRITE(6,*) 'XX EQMENU: UNKNOWN KID'
      ENDIF
      GOTO 1

 9000 RETURN
      END SUBROUTINE EQMENU
