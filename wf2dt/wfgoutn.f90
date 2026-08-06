! wfgoutn.f90

MODULE wfgoutn

  PUBLIC wf_goutn

CONTAINS

  SUBROUTINE wf_goutn

    USE wfcomm
    USE wfparm
    USE wfgsubn
    USE libkio
    IMPLICIT NONE
    CHARACTER(LEN=256):: kline
    CHARACTER(LEN=1):: kid
    INTEGER:: mode,ns
    REAL(rkind),SAVE:: rmin,rmax,zmin,zmax
    INTEGER,SAVE:: INIT=0

    IF(INIT.EQ.0) THEN
       rmin=bdrmin
       rmax=bdrmax
       zmin=bdzmin
       zmax=bdzmax
       INIT=1
    END IF

1   CONTINUE
    IF(nrank.EQ.0) THEN
       WRITE(6,'(A)') &
            '## gout menu: E En P Pn R C ? X'
       CALL TASK_KLIN(kline,kid,mode,wf_parm)
    END IF
    IF(mode.NE.1) GO TO 1
    IF(KID.EQ.'X') GO TO 9000

    SELECT CASE(kid(1:1))
    CASE('E')   ! Electric field plot
       CALL PAGES
       SELECT CASE(kline(2:2))
       CASE('1')
          CALL wf_gsube( 0,1,1,rmin,rmax,zmin,zmax)
       CASE('2')
          CALL wf_gsube( 0,1,2,rmin,rmax,zmin,zmax)
       CASE('3')
          CALL wf_gsube( 0,1,3,rmin,rmax,zmin,zmax)
       CASE('4')
          CALL wf_gsube( 0,2,1,rmin,rmax,zmin,zmax)
       CASE('5')
          CALL wf_gsube( 0,2,2,rmin,rmax,zmin,zmax)
       CASE('6')
          CALL wf_gsube( 0,2,3,rmin,rmax,zmin,zmax)
       CASE('7')
          CALL wf_gsube( 0,3,1,rmin,rmax,zmin,zmax)
       CASE('8')
          CALL wf_gsube( 0,3,2,rmin,rmax,zmin,zmax)
       CASE('9')
          CALL wf_gsube( 0,3,3,rmin,rmax,zmin,zmax)
       CASE('S')
          CALL wf_gsube( 5,4,1,rmin,rmax,zmin,zmax)
          CALL wf_gsube( 6,4,2,rmin,rmax,zmin,zmax)
          CALL wf_gsube( 7,4,3,rmin,rmax,zmin,zmax)
          CALL wf_gsube( 8,5,1,rmin,rmax,zmin,zmax)
          CALL wf_gsube( 9,5,2,rmin,rmax,zmin,zmax)
          CALL wf_gsube(10,5,3,rmin,rmax,zmin,zmax)
          CALL wf_gsube(11,6,1,rmin,rmax,zmin,zmax)
          CALL wf_gsube(12,6,2,rmin,rmax,zmin,zmax)
          CALL wf_gsube(13,6,3,rmin,rmax,zmin,zmax)
       CASE('N')
          CALL wf_gsube( 5,7,1,rmin,rmax,zmin,zmax)
          CALL wf_gsube( 6,7,2,rmin,rmax,zmin,zmax)
          CALL wf_gsube( 7,7,3,rmin,rmax,zmin,zmax)
       CASE DEFAULT
          CALL wf_gsube( 5,1,1,rmin,rmax,zmin,zmax)
          CALL wf_gsube( 6,1,2,rmin,rmax,zmin,zmax)
          CALL wf_gsube( 7,1,3,rmin,rmax,zmin,zmax)
          CALL wf_gsube( 8,2,1,rmin,rmax,zmin,zmax)
          CALL wf_gsube( 9,2,2,rmin,rmax,zmin,zmax)
          CALL wf_gsube(10,2,3,rmin,rmax,zmin,zmax)
          CALL wf_gsube(11,3,1,rmin,rmax,zmin,zmax)
          CALL wf_gsube(12,3,2,rmin,rmax,zmin,zmax)
          CALL wf_gsube(13,3,3,rmin,rmax,zmin,zmax)
       END SELECT
       CALL PAGEE
       GO TO 1
    CASE('P') ! Pabs plot
       CALL PAGES
       SELECT CASE(kline(2:2))
       CASE('0','1','2','3','4','5','6','7','8','9')
          READ(kline(2:4),'(I3)') ns
          IF(ns.GE.1.AND.ns.LE.nsmax) THEN
             CALL wf_gsubp(0,ns,rmin,rmax,zmin,zmax)
             GO TO 7000
          END IF
       END SELECT
       IF(nsmax.LE.4) THEN
          DO ns=1,nsmax
             CALL wf_gsubp(ns,ns,rmin,rmax,zmin,zmax)
          END DO
       ELSE IF(nsmax.LE.9) THEN
          DO ns=1,nsmax
             CALL wf_gsubp(ns+4,ns,rmin,rmax,zmin,zmax)
          END DO
       ELSE IF(nsmax.LE.16) ThEN
          DO ns=1,nsmax
             CALL wf_gsubp(ns+13,ns,rmin,rmax,zmin,zmax)
          END DO
       END IF
7000   CONTINUE
       CALL PAGEE
       Go TO 1
    CASE('R')
7100   CONTINUE
       WRITE(6,'(A)') '# Input view range: rmin,rmax,zmin,zmax:'
       READ(5,*,ERR=7100,END=1) rmin,rmax,zmin,zmax
       GO TO 1
    CASE('C')
       rmin=bdrmin
       rmax=bdrmax
       zmin=bdzmin
       zmax=bdzmax
    CASE('?')
       WRITE(6,*) 'K graphic input help:'
       WRITE(6,*) '  E:  show all E (Re/Im/Abs ER/EZ/Ephi)'
       WRITE(6,*) '  En: show n=1:Re ER, 2:Im ER, 3:Abs ER'
       WRITE(6,*) '             4:Re EZ, 5:Im EZ, 6:Abs EZ'
       WRITE(6,*) '             7:Re Ep, 8:Im Ep, 9:Abs Ep Ep=Ephi'
       WRITE(6,*) '  P:  show all Pabs'
       WRITE(6,*) '  Pn: show Pabs of species n'
       WRITE(6,*) '  R:  set view range (Rmin, Rmax, Zmin,Zmax)'
       WRITE(6,*) '  C:  reset view range (maximum range)'
       WRITE(6,*) '  ?:  show this help message'
    END SELECT
    GO TO 1

9000 CONTINUE
    RETURN
  END SUBROUTINE wf_goutn
END MODULE wfgoutn
    

  
