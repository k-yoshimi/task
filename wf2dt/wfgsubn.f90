! wfgsubn.f90

MODULE wfgsubn

  PUBLIC wf_gsube
  PUBLIC wf_gsubp

CONTAINS

  !     ****** plot all electric field ******

  SUBROUTINE wf_gsube(ngpos,n1,n2,rmin,rmax,zmin,zmax)

    use wfcomm
    USE wfglib
    USE libgrf
    implicit none

    INTEGER,INTENT(IN) :: ngpos,n1,n2
    REAL(rkind),INTENT(IN):: rmin,rmax,zmin,zmax
    REAL(rkind):: rgb(3)
    REAL:: xa(3),ya(3)
    REAL(rkind):: fmax,del_local,delr_local,delz_local
    COMPLEX(rkind):: CER(nemax),CEZ(nemax),CEP(nemax),CE
    INTEGER:: nelm,i,nside,node,nseg,node1,node2
    CHARACTER(LEN=4):: L1,L2
    CHARACTER(LEN=10):: title

    SELECT CASE(n1)
    CASE(1)
       L1='ER  '
    CASE(2)
       L1='EZ  '
    CASE(3)
       L1='EPhi'
    END SELECT
    SELECT CASE(n2)
    CASE(1)
       L2='real'
    CASE(2)
       L2='imag'
    CASE(3)
       L2='abs '
    END SELECT
    title='@'//L1//L2//'@'
    CALL grd2d_frame_start(ngpos,rmin,rmax,zmin,zmax,title)

    fmax=0.D0
    DO nelm=1,nemax
       CER(nelm)=(0.D0,0.D0)
       CEZ(nelm)=(0.D0,0.D0)
       CEP(nelm)=(0.D0,0.D0)
       DO nside=1,3
          nseg=ABS(nsdelm(nside,nelm))
          node1=ndsid(1,nseg)
          node2=ndsid(2,nseg)
          delr_local=rnode(node2)-rnode(node1)
          delz_local=znode(node2)-znode(node1)
          del_local=SQRT(delr_local**2+delz_local**2)
!          IF(nsdelm(nside,nelm).LT.0.D0) THEN
!             del_local=-del_local
!             WRITE(6,*) nelm,rnode(node1),znode(node1)
!          END IF
          CER(nelm)=CER(nelm)+(delr_local/del_local)*CESD(nseg)
          CEZ(nelm)=CEZ(nelm)+(delz_local/del_local)*CESD(nseg)
          CEP(nelm)=CEP(nelm)+CEND(node1)
       END DO
       CER(nelm)=CER(nelm)/3.D0
       CEZ(nelm)=CEZ(nelm)/3.D0
       CEP(nelm)=CEP(nelm)/3.D0
       fmax=MAX(fmax,SQRT(ABS(CER(nelm))**2+ABS(CEZ(nelm))**2 &
                         +ABS(CEP(nelm))**2))
    END DO

    IF(fmax.LE.0.D0) THEN
       WRITE(6,'(A,ES12.4)') &
            'XX MAX of E is not positive:',fmax
       RETURN
    END IF

    DO nelm=1,nemax
       DO i=1,3
          node=ndelm(i,nelm)
          xa(i)=gdclip(rnode(node))
          ya(i)=gdclip(znode(node))
       END DO
       SELECT CASE(n1)
       CASE(1)
          CE=CER(nelm)
       CASE(2)
          CE=CEZ(nelm)
       CASE(3)
          CE=CEP(nelm)
       CASE(4)
          nseg=ABS(nsdelm(1,nelm))
          CE=CESD(nseg)
       CASE(5)
          nseg=ABS(nsdelm(2,nelm))
          CE=CESD(nseg)
       CASE(6)
          nseg=ABS(nsdelm(3,nelm))
          CE=CESD(nseg)
       CASE(7)
          CE=(CEND(ndelm(1,nelm)) &
             +CEND(ndelm(2,nelm)) &
             +CEND(ndelm(3,nelm)))/3.D0
       END SELECT
       SELECT CASE(n2)
       CASE(1)
          CALL rgbf_c(0.5D0*REAL(CE)/fmax+0.5D0,rgb)
       CASE(2)
          CALL rgbf_c(0.5D0*AIMAG(CE)/fmax+0.5D0,rgb)
       CASE(3)
          CALL rgbf_c(0.5D0*ABS(CE)/fmax+0.5D0,rgb)
       END SELECT
       CALL set_rgbd(rgb)
       CALL poly2D(xa,ya,3)
    END DO
    CALL grd2d_frame_end
    RETURN
  END SUBROUTINE wf_gsube
  
  !     ****** plot power absorption ******

  SUBROUTINE wf_gsubp(ngpos,ns,rmin,rmax,zmin,zmax)

    use wfcomm
    USE wfglib
    USE libgrf
    implicit none

    INTEGER,INTENT(IN) :: ngpos,ns
    REAL(rkind),INTENT(IN):: rmin,rmax,zmin,zmax
    REAL(rkind):: rgb(3)
    REAL:: xa(3),ya(3)
    REAL(rkind):: fmax
    INTEGER:: nelm,i,node
    CHARACTER(LEN=8):: title

    WRITE(title,'(A,I2,A)') 'PABS(',ns,')'
    CALL grd2d_frame_start(ngpos,rmin,rmax,zmin,zmax,title)

    fmax=pabs(ns,1)
    DO nelm=2,nemax
       fmax=MAX(fmax,pabs(ns,nelm))
    END DO
    IF(fmax.LE.0.D0) THEN
       WRITE(6,'(A,I2,A,ES12.4)') &
            'XX MAX of pabs(',ns,') is not positive:',fmax
       RETURN
    END IF
  
    DO nelm=1,nemax
       DO i=1,3
          node=ndelm(i,nelm)
          xa(i)=gdclip(rnode(node))
          ya(i)=gdclip(znode(node))
       END DO
       CALL rgbf_a(pabs(ns,nelm)/fmax,rgb)
       CALL set_rgbd(rgb)
       CALL poly2D(xa,ya,3)
    END DO
    CALL grd2d_frame_end
    RETURN
  END SUBROUTINE wf_gsubp
END MODULE wfgsubn

