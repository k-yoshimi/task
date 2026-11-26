Program wim_gconv
  USE bpsd_kinds
  USE bpsd_constants
  IMPLICIT NONE

  interface
     integer function NGULEN(Y)
       real:: Y
     end function NGULEN
  end interface

  INTEGER:: id_wave_dump,fid_wave_dump
  CHARACTER(LEN=256):: kid_wave_dump
  REAL,ALLOCATABLE:: gx(:),gwr(:,:),gwi(:,:),gw(:,:)
  REAL,ALLOCATABLE:: gwmin(:),gwmax(:),gwscal(:)
  CHARACTER(LEN=2),ALLOCATABLE:: kid(:)
  INTEGER:: ndim,nx,nx_in,nxmax,nd,nd_in,ndmax,nt
  REAL:: gxmin,gxmax,gxscal,gxmin_a,gxmax_a
  REAL:: gwmin_a,gwmax_a
  REAL:: phase,ntmax
  INTEGER,SAVE:: ndmax_save=0,nxmax_save=0

  fid_wave_dump=28    ! file id of wave dump data file
  kid_wave_dump='wim.data' ! file name of wave dump data file
  ntmax=16

  WRITE(6,*) '## GSOPEN: set 0 for no screen output'
  CALL GSOPEN
  
1 CONTINUE
  WRITE(6,*) '## Input wave_dump file name:'
  READ(5,*,ERR=1) kid_wave_dump
  OPEN(fid_wave_dump,FILE=kid_wave_dump)
  WRITE(6,'(A,A,A)') 'wave_dump file (',TRIM(kid_wave_dump),'): open'
  
2 CONTINUE
  READ(fid_wave_dump,'(2I6)',END=9000) id_wave_dump,ndim
  WRITE(6,'(A,2I6)') '## id_wave_dump,ndim=',id_wave_dump,ndim
  IF(ndim.NE.1) THEN
     WRITE(6,*) 'XX wrong data dimension: 1D data required: nid=',ndim
     GO TO 1
  END IF

  READ(fid_wave_dump,'(2I6)') ndmax,nxmax
  WRITE(6,'(A,2I6)') '## ndmax,nxmax=',ndmax,nxmax
  IF(ALLOCATED(kid)) THEN
     IF(ndmax.NE.ndmax_save.OR.nxmax.NE.nxmax_save) THEN
        DEALLOCATE(kid,gwmin,gwmax,gwscal,gx,gwr,gwi,gw)
        ALLOCATE(kid(ndmax))
        ALLOCATE(gwmin(ndmax),gwmax(ndmax),gwscal(ndmax))
        ALLOCATE(gx(nxmax),gwr(nxmax,ndmax),gwi(nxmax,ndmax),gw(nxmax,ndmax))
        ndmax_save=ndmax
        nxmax_save=nxmax
     END IF
  ELSE
     ALLOCATE(kid(ndmax))
     ALLOCATE(gwmin(ndmax),gwmax(ndmax),gwscal(ndmax))
     ALLOCATE(gx(nxmax),gwr(nxmax,ndmax),gwi(nxmax,ndmax),gw(nxmax,ndmax))
     ndmax_save=ndmax
     nxmax_save=nxmax
  END IF

  DO nd=1,ndmax
     READ(fid_wave_dump,'(I6,A)') nd_in,kid(nd)
     IF(nd_in.NE.nd) THEN
        WRITE(6,*) 'XX wim_gconv: nd_in.NE.nd:',nd_in,nd,ndmax
        STOP
     END IF
     WRITE(6,'(A,I6,A)') '## nd, data name:',nd,TRIM(kid(nd))
     DO nx=1,nxmax
        READ(fid_wave_dump,'(I6,3ES12.4)') nx_in,gx(nx),gwr(nx,nd),gwi(nx,nd)
        IF(nd_in.NE.nd) THEN
           WRITE(6,'(A,3I6)') 'XX wim_gconv: nd_in.NE.nd:',nd_in,nd,ndmax
           STOP
        END IF
     END DO
  END DO

  CALL GMNMX1(gx,1,nxmax,1,gxmin_a,gxmax_a)
  CALL GQSCAL(gxmin_a,gxmax_a,gxmin,gxmax,gxscal)
  DO nd=1,ndmax
     DO nx=1,nxmax
        gw(nx,nd)=SQRT(gwr(nx,nd)**2+gwi(nx,nd)**2)
     END DO
     CALL GMNMX1(gw,1,nxmax,1,gwmin_a,gwmax_a)
     CALL GQSCAL(gwmin_a,gwmax_a,gwmin(nd),gwmax(nd),gwscal(nd))
  END DO

  DO nt=1,ntmax
     phase=2.D0*PI*REAL(nt-1)/REAL(ntmax)
     CALL PAGES
     DO nd=1,ndmax
        IF(ndmax.EQ.3) THEN
           SELECT CASE(nd)
           CASE(1)
              CALL GDEFIN(2.5,12.5,12.0,17.5,gxmin,gxmax,-gwmax(nd),gwmax(nd))
              CALL MOVE(12.7,17.0)
              CALL TEXT(KID(1),2)
           CASE(2)
              CALL GDEFIN(2.5,12.5, 6.5,12.0,gxmin,gxmax,-gwmax(nd),gwmax(nd))
              CALL MOVE(12.7,11.5)
              CALL TEXT(KID(2),2)
           CASE(3)
              CALL GDEFIN(2.5,12.5, 1.0, 6.5,gxmin,gxmax,-gwmax(nd),gwmax(nd))
              CALL MOVE(12.7,6.0)
              CALL TEXT(KID(3),2)
           END SELECT
        ELSE
           WRITE(6,'(A,2I6)') 'XX wim_gconv: unsupported ndmax: ',ndmax
           STOP
        END IF
        CALL GFRAME
        CALL GSCALE(0.,0.,0.,2.*gwscal(nd),0.1,9)
        CALL GSCALE(0.,2.*gwscal(nd),0.,0.,0.2,9)
        CALL GSCALE(0.,0.,0.,13.*gwscal(nd),0.1,0)
        CALL GVALUE(0.,0.,0.,4*gwscal(nd),NGULEN(4*gwscal(nd)))
        IF(nd.EQ.ndmax) CALL GVALUE(0.,4*gxscal,0.,0.,NGULEN(4*gxscal))
        DO nx=1,nxmax
           gw(nx,nd)=gwr(nx,nd)*COS(phase)+gwi(nx,nd)*SIN(phase)
        END DO
        CALL SETLIN(0,2,6)
        CALL GPLOTP(gx,gw(1:nxmax,nd),1,nxmax,1,0,0,0)
        CALL SETLIN(0,2,7)
     END DO
     CALL PAGEE
  END DO
  GO TO 2

9000 CONTINUE
  CALL GSCLOS
  STOP
END Program wim_gconv
