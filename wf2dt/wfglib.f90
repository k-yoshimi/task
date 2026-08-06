! wfglib.f90

MODULE wfglib

  USE wfcomm,ONLY: rkind
  INTEGER:: nmax_a,nmax_b,nmax_c
  REAL(rkind),ALLOCATABLE:: &
       f_a(:),urgb_ar(:,:),urgb_ag(:,:),urgb_ab(:,:),rgb_a(:,:), &
       f_b(:),urgb_br(:,:),urgb_bg(:,:),urgb_bb(:,:),rgb_b(:,:), &
       f_c(:),urgb_cr(:,:),urgb_cg(:,:),urgb_cb(:,:),rgb_c(:,:)

  PRIVATE
  PUBLIC set_rgbd
  PUBLIC rgb_bard
  PUBLIC rgbf_a
  PUBLIC rgbf_b
  PUBLIC rgbf_c
  PUBLIC wfclip
  PUBLIC kline_to_kword
  PUBLIC kword_to_kid_id
  PUBLIC setup_fmin_fmax
  PUBLIC setup_fmin_fmax_2d
  PUBLIC setup_fmin_fmax_2f
  PUBLIC setup_fmin_fmax_2fx
  PUBLIC convert_fmin_fmax

CONTAINS

  ! --- set RGB by array rgb(3) ---
  
  SUBROUTINE set_rgbd(rgb)
    USE wfcomm,ONLY: rkind
    IMPLICIT NONE
    REAL(rkind),INTENT(IN):: rgb(3)
    EXTERNAL setrgb

    CALL setrgb(REAL(RGB(1)),REAL(RGB(2)),REAL(RGB(3)))
  END SUBROUTINE set_rgbd

  ! --- RGB COLOR PATERN ---

  SUBROUTINE rgb_bard(X1,X2,Y1,Y2,RGB,nmax,ind)

    USE wfcomm,ONLY: rkind
    IMPLICIT NONE
    REAL,INTENT(IN):: X1,X2,Y1,Y2
    INTEGER,INTENT(IN):: nmax,ind
    REAL(rkind),INTENT(IN):: RGB(3,nmax)
    REAL(rkind):: DX,DY,DXL,DYL
    REAL:: X(5),Y(5)
    INTEGER:: n
    EXTERNAL SETRGB,POLY,LINES

    IF(IND.EQ.0) THEN
       DX=(X2-X1)/DBLE(nmax)
       DY=0.0
       DXL=0.0
       DYL=Y2-Y1
    ELSE
       DX=0.0
       DY=(Y2-Y1)/DBLE(nmax)
       DXL=X2-X1
       DYL=0.0
    ENDIF
    DO n=1,nmax
       X(1)=wfclip(X1+DX*(n-1))
       Y(1)=wfclip(Y1+DY*(n-1))
       X(2)=wfclip(X1+DX*n+DXL)
       Y(2)=Y(1)
       X(3)=X(2)
       Y(3)=wfclip(Y1+DY*n+DYL)
       X(4)=X(1)
       Y(4)=Y(3)
       X(5)=X(1)
       Y(5)=Y(1)
       CALL set_rgbd(rgb(1:3,n))
       CALL POLY(X,Y,5)
    END DO

    X(1)=X1
    Y(1)=Y1
    X(2)=X2
    Y(2)=Y1
    X(3)=X2
    Y(3)=Y2
    X(4)=X1
    Y(4)=Y2
    X(5)=X1
    Y(5)=Y1
    CALL SETRGB(0.0,0.0,0.0)
    CALL LINES(X,Y,5)

    RETURN
  END SUBROUTINE rgb_bard

! --- rgb color pattern - positive ---

  SUBROUTINE rgbf_a(f,rgb)
    USE wfcomm,ONLY: rkind
    USE libspl1d
    IMPLICIT NONE
    REAL(rkind),INTENT(IN):: f
    REAL(rkind),INTENT(OUT):: rgb(3)
    REAL(rkind),ALLOCATABLE:: dummy(:)
    INTEGER,SAVE:: init=0
    INTEGER:: ierr1,ierr2,ierr3

    IF(init.EQ.0) THEN
       nmax_a=11
       ALLOCATE(f_a(nmax_a),rgb_a(nmax_a,3),dummy(nmax_a))
       ALLOCATE(urgb_ar(4,nmax_a),urgb_ag(4,nmax_a),urgb_ab(4,nmax_a))
       f_a( 1)=0.0D0; rgb_a( 1,1:3)=(/0.20D0,0.80D0,0.20D0/)
       f_a( 2)=0.1D0; rgb_a( 2,1:3)=(/0.50D0,0.90D0,0.20D0/)
       f_a( 3)=0.2D0; rgb_a( 3,1:3)=(/0.70D0,1.00D0,0.20D0/)
       f_a( 4)=0.3D0; rgb_a( 4,1:3)=(/0.85D0,1.00D0,0.20D0/)
       f_a( 5)=0.4D0; rgb_a( 5,1:3)=(/0.95D0,1.00D0,0.20D0/)
       f_a( 6)=0.5D0; rgb_a( 6,1:3)=(/1.00D0,1.00D0,0.20D0/)
       f_a( 7)=0.6D0; rgb_a( 7,1:3)=(/1.00D0,0.95D0,0.20D0/)
       f_a( 8)=0.7D0; rgb_a( 8,1:3)=(/1.00D0,0.85D0,0.20D0/)
       f_a( 9)=0.8D0; rgb_a( 9,1:3)=(/1.00D0,0.70D0,0.20D0/)
       f_a(10)=0.9D0; rgb_a(10,1:3)=(/1.00D0,0.5D00,0.20D0/)
       f_a(11)=1.0D0; rgb_a(11,1:3)=(/1.00D0,0.20D0,0.20D0/)
       CALL SPL1D(f_a,rgb_a(1:nmax_a,1),dummy,urgb_ar,nmax_a,0,ierr1)
       CALL SPL1D(f_a,rgb_a(1:nmax_a,2),dummy,urgb_ag,nmax_a,0,ierr2)
       CALL SPL1D(f_a,rgb_a(1:nmax_a,3),dummy,urgb_ab,nmax_a,0,ierr3)
       IF(ierr1+ierr2+ierr3.NE.0) THEN
          WRITE(6,'(A,3I5)') &
               'XX rgb_a: SPL1D error: ierr1/2/3=',ierr1,ierr2,ierr3
!         #228 finding 31: unwind fully so INIT stays 0 and a retry re-enters
!         cleanly instead of re-ALLOCATEing already-allocated arrays (abort).
          DEALLOCATE(f_a,rgb_a,dummy,urgb_ar,urgb_ag,urgb_ab)
          rgb(1:3)=0.D0
          RETURN
       END IF
!      #228 finding 12: rgb_a must SURVIVE — the clamp branches below read it.
!      Mirrors rgbf_c, which already deallocates only the scratch array.
       DEALLOCATE(dummy)
       INIT=1
    END IF

    IF(f.LT.f_a(1)) THEN
       rgb(1:3)=rgb_a(1,1:3)
    ELSE IF(f.GT.f_a(nmax_a)) THEN
       rgb(1:3)=rgb_a(nmax_a,1:3)
    ELSE
       CALL SPL1DF(f,rgb(1),f_a,urgb_ar,nmax_a,ierr1)
       CALL SPL1DF(f,rgb(2),f_a,urgb_ag,nmax_a,ierr2)
       CALL SPL1DF(f,rgb(3),f_a,urgb_ab,nmax_a,ierr3)
       IF(ierr1+ierr2+ierr3.NE.0) THEN
          WRITE(6,'(A,3I5)') &
               'XX rgb_a: SPL1DF error: ierr1/2/3=',ierr1,ierr2,ierr3
          WRITE(6,*) 'f,f_a(1),f_a(nmax_a)=',f,f_a(1),f_a(nmax_a)
          RETURN
       END IF
    END IF
  END SUBROUTINE rgbf_a


! --- rgb color pattern - negative ---

  SUBROUTINE rgbf_b(f,rgb)
    USE wfcomm,ONLY: rkind
    USE libspl1d
    IMPLICIT NONE
    REAL(rkind),INTENT(IN):: f
    REAL(rkind),INTENT(OUT):: rgb(3)
    REAL(rkind),ALLOCATABLE:: dummy(:)
    INTEGER,SAVE:: init=0
    INTEGER:: ierr1,ierr2,ierr3

    IF(init.EQ.0) THEN
       nmax_b=11
       ALLOCATE(f_b(nmax_b),rgb_b(nmax_b,3),dummy(nmax_b))
       ALLOCATE(urgb_br(4,nmax_b),urgb_bg(4,nmax_b),urgb_bb(4,nmax_b))
       f_b( 1)=0.0D0; rgb_b( 1,1:3)=(/0.20D0,0.20D0,1.00D0/)
       f_b( 2)=0.1D0; rgb_b( 2,1:3)=(/0.20D0,0.50D0,1.00D0/)
       f_b( 3)=0.2D0; rgb_b( 3,1:3)=(/0.20D0,0.70D0,1.00D0/)
       f_b( 4)=0.3D0; rgb_b( 4,1:3)=(/0.20D0,0.85D0,1.00D0/)
       f_b( 5)=0.4D0; rgb_b( 5,1:3)=(/0.20D0,0.95D0,1.00D0/)
       f_b( 6)=0.5D0; rgb_b( 6,1:3)=(/0.20D0,1.00D0,1.00D0/)
       f_b( 7)=0.6D0; rgb_b( 7,1:3)=(/0.20D0,1.00D0,0.95D0/)
       f_b( 8)=0.7D0; rgb_b( 8,1:3)=(/0.20D0,1.00D0,0.85D0/)
       f_b( 9)=0.8D0; rgb_b( 9,1:3)=(/0.20D0,1.00D0,0.70D0/)
       f_b(10)=0.9D0; rgb_b(10,1:3)=(/0.20D0,0.90D0,0.50D0/)
       f_b(11)=1.0D0; rgb_b(11,1:3)=(/0.20D0,0.80D0,0.20D0/)
       CALL SPL1D(f_b,rgb_b(1:nmax_b,1),dummy,urgb_br,nmax_b,0,ierr1)
       CALL SPL1D(f_b,rgb_b(1:nmax_b,2),dummy,urgb_bg,nmax_b,0,ierr2)
       CALL SPL1D(f_b,rgb_b(1:nmax_b,3),dummy,urgb_bb,nmax_b,0,ierr3)
       IF(ierr1+ierr2+ierr3.NE.0) THEN
          WRITE(6,'(A,3I5)') &
               'XX rgb_b: SPL1D error: ierr1/2/3=',ierr1,ierr2,ierr3
!         #228 finding 31: unwind fully so INIT stays 0 and a retry re-enters
!         cleanly instead of re-ALLOCATEing already-allocated arrays (abort).
          DEALLOCATE(f_b,rgb_b,dummy,urgb_br,urgb_bg,urgb_bb)
          rgb(1:3)=0.D0
          RETURN
       END IF
!      #228 finding 12: rgb_b must SURVIVE — the clamp branches below read it.
!      Mirrors rgbf_c, which already deallocates only the scratch array.
       DEALLOCATE(dummy)
       INIT=1
    END IF

    IF(f.LT.f_b(1)) THEN
       rgb(1:3)=rgb_b(1,1:3)
    ELSE IF(f.GT.f_b(nmax_b)) THEN
       rgb(1:3)=rgb_b(nmax_b,1:3)
    ELSE
       CALL SPL1DF(f,rgb(1),f_b,urgb_br,nmax_b,ierr1)
       CALL SPL1DF(f,rgb(2),f_b,urgb_bg,nmax_b,ierr2)
       CALL SPL1DF(f,rgb(3),f_b,urgb_bb,nmax_b,ierr3)
       IF(ierr1+ierr2+ierr3.NE.0) THEN
          WRITE(6,'(A,3I5)') &
               'XX rgb_b: SPL1DF error: ierr1/2/3=',ierr1,ierr2,ierr3
          RETURN
       END IF
    END IF
  END SUBROUTINE rgbf_b


! --- rgb color pattern - positive and negative ---

  SUBROUTINE rgbf_c(f,rgb)
    USE wfcomm,ONLY: rkind
    USE libspl1d
    IMPLICIT NONE
    REAL(rkind),INTENT(IN):: f
    REAL(rkind),INTENT(OUT):: rgb(3)
    REAL(rkind),ALLOCATABLE,save:: dummy(:)
    INTEGER,SAVE:: init=0
    INTEGER:: ierr1,ierr2,ierr3

    IF(init.EQ.0) THEN
       nmax_c=21
       ALLOCATE(f_c(nmax_c),rgb_c(nmax_c,3),dummy(nmax_c))
       ALLOCATE(urgb_cr(4,nmax_c),urgb_cg(4,nmax_c),urgb_cb(4,nmax_c))
       f_c( 1)=0.00D0; rgb_c( 1,1:3)=(/0.20D0,0.20D0,1.00D0/)
       f_c( 2)=0.05D0; rgb_c( 2,1:3)=(/0.20D0,0.50D0,1.00D0/)
       f_c( 3)=0.10D0; rgb_c( 3,1:3)=(/0.20D0,0.70D0,1.00D0/)
       f_c( 4)=0.15D0; rgb_c( 4,1:3)=(/0.20D0,0.85D0,1.00D0/)
       f_c( 5)=0.20D0; rgb_c( 5,1:3)=(/0.20D0,0.95D0,1.00D0/)
       f_c( 6)=0.25D0; rgb_c( 6,1:3)=(/0.20D0,1.00D0,1.00D0/)
       f_c( 7)=0.30D0; rgb_c( 7,1:3)=(/0.20D0,1.00D0,0.95D0/)
       f_c( 8)=0.35D0; rgb_c( 8,1:3)=(/0.20D0,1.00D0,0.85D0/)
       f_c( 9)=0.40D0; rgb_c( 9,1:3)=(/0.20D0,1.00D0,0.70D0/)
       f_c(10)=0.45D0; rgb_c(10,1:3)=(/0.20D0,0.90D0,0.50D0/)
       f_c(11)=0.50D0; rgb_c(11,1:3)=(/0.20D0,0.80D0,0.20D0/)
       f_c(12)=0.55D0; rgb_c(12,1:3)=(/0.50D0,0.90D0,0.20D0/)
       f_c(13)=0.60D0; rgb_c(13,1:3)=(/0.70D0,1.00D0,0.20D0/)
       f_c(14)=0.65D0; rgb_c(14,1:3)=(/0.85D0,1.00D0,0.20D0/)
       f_c(15)=0.70D0; rgb_c(15,1:3)=(/0.95D0,1.00D0,0.20D0/)
       f_c(16)=0.75D0; rgb_c(16,1:3)=(/1.00D0,1.00D0,0.20D0/)
       f_c(17)=0.8D00; rgb_c(17,1:3)=(/1.00D0,0.95D0,0.20D0/)
       f_c(18)=0.85D0; rgb_c(18,1:3)=(/1.00D0,0.85D0,0.20D0/)
       f_c(19)=0.90D0; rgb_c(19,1:3)=(/1.00D0,0.70D0,0.20D0/)
       f_c(20)=0.95D0; rgb_c(20,1:3)=(/1.00D0,0.50D0,0.20D0/)
       f_c(21)=1.00D0; rgb_c(21,1:3)=(/1.00D0,0.20D0,0.20D0/)
          
       CALL SPL1D(f_c,rgb_c(1:nmax_c,1),dummy,urgb_cr,nmax_c,0,ierr1)
       CALL SPL1D(f_c,rgb_c(1:nmax_c,2),dummy,urgb_cg,nmax_c,0,ierr2)
       CALL SPL1D(f_c,rgb_c(1:nmax_c,3),dummy,urgb_cb,nmax_c,0,ierr3)
       IF(ierr1+ierr2+ierr3.NE.0) THEN
          WRITE(6,'(A,3I5)') &
               'XX rgb_c: SPL1D error: ierr1/2/3=',ierr1,ierr2,ierr3
!         #228 finding 31: unwind fully so INIT stays 0 (see rgbf_a).
          DEALLOCATE(f_c,rgb_c,dummy,urgb_cr,urgb_cg,urgb_cb)
          rgb(1:3)=0.D0
          RETURN
       END IF
       DEALLOCATE(dummy)
       INIT=1
    END IF

    IF(f.LT.f_c(1)) THEN
       rgb(1:3)=rgb_c(1,1:3)
    ELSE IF(f.GT.f_c(nmax_c)) THEN
       rgb(1:3)=rgb_c(nmax_c,1:3)
    ELSE
       CALL SPL1DF(f,rgb(1),f_c,urgb_cr,nmax_c,ierr1)
       CALL SPL1DF(f,rgb(2),f_c,urgb_cg,nmax_c,ierr2)
       CALL SPL1DF(f,rgb(3),f_c,urgb_cb,nmax_c,ierr3)
       IF(ierr1+ierr2+ierr3.NE.0) THEN
          WRITE(6,'(A,3I5)') &
               'XX rgb_c: SPL1DF error: ierr1/2/3=',ierr1,ierr2,ierr3
          WRITE(6,'(4ES12.4)') f,rgb(1),rgb(2),rgb(3)
          RETURN
       END IF
    END IF
  END SUBROUTINE rgbf_c


! ****** AVOID REAL*4 UNDERFLOW ******

  FUNCTION wfclip(D)

    USE wfcomm,ONLY: rkind
    IMPLICIT NONE
    REAL(rkind),INTENT(IN):: D
    REAL:: wfclip

    IF(ABS(D).LT.1.D-30) then
       wfclip=0.0
    ELSEIF(D.GT. 1.D30) THEN
       wfclip= 1.E30
    ELSEIF(D.lT.-1.D30) THEN
       wfclip=-1.E30
    ELSE
       wfclip=SNGL(D)
    ENDIF
    RETURN
  END FUNCTION wfclip

  !   --- separate a line to words separated by space or comma ---
    
  SUBROUTINE kline_to_kword(nch_line,kline,nch_word,nword_m,kword,nword_max)
    IMPLICIT NONE
    INTEGER,INTENT(IN):: nch_line,nch_word,nword_m
    CHARACTER(LEN=*),INTENT(IN):: kline
    CHARACTER(LEN=nch_word),INTENT(OUT):: kword(nword_m)
    INTEGER,INTENT(OUT):: nword_max
    INTEGER:: nloc,nword,nch,nchs

    nloc=1
    nword=0
    nchs=1
1   CONTINUE
    IF(kline(nchs:nchs).EQ.' ') THEN
       nchs=nchs+1
       GO TO 1
    END IF
    DO nch=nchs,nch_line
!       WRITE(6,'(I5,4X,A1,4I5)') nch,kline(nch:nch),nloc,nword
       IF(nloc.EQ.0) THEN
          IF(kline(nch:nch).NE.' ' .AND. kline(nch:nch).NE.',') THEN
             IF(nword.NE.0) THEN
                nloc=nch
             END IF
          END IF
       ELSE
          IF(kline(nch:nch).EQ.' ' .OR. kline(nch:nch).EQ.',') THEN
             nword=nword+1
             IF(nword.GT.nword_m) GO TO 8000
             kword(nword)=kline(nloc:nch)
             nloc=0
          END IF
       END IF
    END DO
    IF(nloc.NE.0) THEN
       nword=nword+1
       kword(nword)=kline(nloc:nch)
    END IF
    nword_max=nword
    RETURN

8000 CONTINUE
    WRITE(6,*) 'XX kline_to_kword: nword exceeds nword_m: nword_m'
    WRITE(6,'(A)') kline
    nword_max=nword-1
    RETURN
  END SUBROUTINE kline_to_kword

  ! --- convert a word to a char and an integer
  !        mode 0 : k
  !        mode 1 : n
  !        mode 2 : n-n
  !        mode 3 : kn
  !        mode 4 : kn-n
  !        mode 9 : error

  SUBROUTINE kword_to_kid_id(nch_word,kword,mode,kid,id1,id2)

    IMPLICIT NONE
    INTEGER,INTENT(IN):: nch_word
    CHARACTER(LEN=nch_word),INTENT(IN):: kword
    INTEGER,INTENT(OUT):: mode,id1,id2
    CHARACTER(LEN=1),INTENT(OUT):: kid
    INTEGER:: ich,l,l_max,l_pos
    CHARACTER(LEN=nch_word):: ktemp,ktemp1,ktemp2

    ! --- capitalize the first char ---

    ich=ICHAR(kword(1:1))
    IF(ich.GE.97.AND.ich.LE.122) ich=ich-32
    kid=CHAR(ich)

    ! --- if necessary, retrieve a char ---
    
    SELECT CASE(kid)
    CASE('A':'Z','?') 
       ktemp=kword(2:nch_word)
       mode=0
    CASE DEFAULT
       kid=' '
       ktemp=kword
       mode=1
    END SELECT
    l_max=LEN_TRIM(ktemp)
    IF(l_max.EQ.0.and.mode.EQ.0) THEN
       id1=0
       id2=0
       RETURN  ! mode=0
    END IF

    l_pos=0
    DO l=1,l_max
       IF(ktemp(l:l).EQ.'-') l_pos=l
    END DO
    IF(l_pos.EQ.0) THEN
       READ(ktemp,*,ERR=901,END=901) id1
       id2=0
       IF(mode.EQ.0) THEN
          mode=3
       ELSE
          mode=1
       END IF
    ELSE
       ktemp1=ktemp(1:l_pos-1)
       ktemp2=ktemp(l_pos+1:l_max)
       READ(ktemp1,*,ERR=902,END=902) id1
       READ(ktemp2,*,ERR=903,END=903) id2
       IF(mode.eq.0) THEN
          mode=4
       ELSE
          mode=2
       END IF
    END IF
    RETURN
901 CONTINUE
    WRITE(6,*) 'XX kword_to_kid_id: id1 error: kword=',kword
    mode=9
    RETURN
902 CONTINUE
    WRITE(6,*) 'XX kword_to_kid_id: id1 error: kword=',kword
    mode=9
    RETURN
903 CONTINUE
    WRITE(6,*) 'XX kword_to_kid_id: id2 error: kword=',kword
    mode=9
    RETURN
  END SUBROUTINE kword_to_kid_id

  ! --- find min and max of f(1:nmax)

  SUBROUTINE setup_fmin_fmax(npmax,f,mode,fmin,fmax,fmin_exact,fmax_exact)
    USE wfcomm,ONLY: rkind
    IMPLICIT NONE
    INTEGER,INTENT(IN):: npmax
    REAL(rkind),INTENT(IN):: f(npmax)
    INTEGER,INTENT(OUT):: mode
          ! 1: change sign, 2:positive, 3:negative
    REAL(rkind),INTENT(OUT):: fmin,fmax
          ! fmax=0 for negative and varying, fmin=0 for positive and varying
          ! IF (fmax_exact-fmin_exact).LT.fplot_min,
          ! fmax=0.5*(fmin_exact+fmax_exact)+0.5D0, fmin=fmac-1.D0
    REAL(rkind),INTENT(OUT),OPTIONAL:: fmin_exact,fmax_exact
          ! exact value of min and max of f
    INTEGER:: np

    fmax=f(1)
    fmin=f(1)
    DO np=2,npmax
       fmax=MAX(f(np),fmax)
       fmin=MIN(f(np),fmin)
    END DO
    fmin_exact=fmin
    fmax_exact=fmax

    CALL convert_fmin_fmax(fmin,fmax,mode)
    RETURN
  END SUBROUTINE setup_fmin_fmax

  ! --- find min and max of f(1:npmax,1:nlmax)

  SUBROUTINE setup_fmin_fmax_2d(npmax,nlmax,f,mode,fmin,fmax, &
                                                   fmin_exact,fmax_exact)
    USE wfcomm,ONLY: rkind
    IMPLICIT NONE
    INTEGER,INTENT(IN):: npmax,nlmax
    REAL(rkind),INTENT(IN):: f(npmax,nlmax)
    INTEGER,INTENT(OUT):: mode
          ! 1: change sign, 2:positive, 3:negative
    REAL(rkind),INTENT(OUT):: fmin,fmax
          ! fmax=0 for negative and varying, fmin=0 for positive and varying
          ! IF (fmax_exact-fmin_exact).LT.fplot_min,
          ! fmax=0.5*(fmin_exact+fmax_exact)+0.5D0, fmin=fmac-1.D0
    REAL(rkind),INTENT(OUT),OPTIONAL:: fmin_exact,fmax_exact
          ! exact value of min and max of f
    INTEGER:: np,nl

    fmax=f(1,1)
    fmin=f(1,1)
    DO nl=1,nlmax
       DO np=1,npmax
          fmax=MAX(f(np,nl),fmax)
          fmin=MIN(f(np,nl),fmin)
       END DO
    END DO
    fmin_exact=fmin
    fmax_exact=fmax

    CALL convert_fmin_fmax(fmin,fmax,mode)
    RETURN
  END SUBROUTINE setup_fmin_fmax_2d

  ! --- find min and max of f_1(1:n1_max) and f_2(1:n2_max)

  SUBROUTINE setup_fmin_fmax_2f(n1_max,f_1,n2_max,f_2,mode, &
       fmin,fmax,fmin_exact,fmax_exact)
    USE wfcomm,ONLY: rkind
    IMPLICIT NONE
    INTEGER,INTENT(IN):: n1_max,n2_max
    REAL(rkind),INTENT(IN):: f_1(n1_max),f_2(n2_max)
    INTEGER,INTENT(OUT):: mode
          ! 1: change sign, 2:positive, 3:negative
    REAL(rkind),INTENT(OUT):: fmin,fmax
          ! fmax=0 for negative and varying, fmin=0 for positive and varying
          ! IF (fmax_exact-fmin_exact).LT.fplot_min,
          ! fmax=0.5*(fmin_exact+fmax_exact)+0.5D0, fmin=fmac-1.D0
    REAL(rkind),INTENT(OUT),OPTIONAL:: fmin_exact,fmax_exact
          ! exact value of min and max of f
    INTEGER:: n1,n2

    fmax=f_1(1)
    fmin=f_1(1)
    DO n1=1,n1_max
       fmax=MAX(f_1(n1),fmax)
       fmin=MIN(f_1(n1),fmin)
    END DO
    DO n2=1,n2_max
       fmax=MAX(f_2(n2),fmax)
       fmin=MIN(f_2(n2),fmin)
    END DO
    fmin_exact=fmin
    fmax_exact=fmax

    CALL convert_fmin_fmax(fmin,fmax,mode)
    RETURN
  END SUBROUTINE setup_fmin_fmax_2f

  ! --- find min and max of f(1:npmax,1:nlmax)

  SUBROUTINE setup_fmin_fmax_2fx(n1max,n2max,f1,f2,mode, &
       fmin,fmax,fmin_exact,fmax_exact)
    USE wfcomm,ONLY: rkind
    IMPLICIT NONE
    INTEGER,INTENT(IN):: n1max,n2max
    REAL(rkind),INTENT(IN):: f1(n1max,n2max),f2(n2max)
    INTEGER,INTENT(OUT):: mode
          ! 1: change sign, 2:positive, 3:negative
    REAL(rkind),INTENT(OUT):: fmin,fmax
          ! fmax=0 for negative and varying, fmin=0 for positive and varying
          ! IF (fmax_exact-fmin_exact).LT.fplot_min,
          ! fmax=0.5*(fmin_exact+fmax_exact)+0.5D0, fmin=fmac-1.D0
    REAL(rkind),INTENT(OUT),OPTIONAL:: fmin_exact,fmax_exact
          ! exact value of min and max of f
    INTEGER:: n1,n2

    fmax=f1(1,1)
    fmin=f1(1,1)
    DO n2=1,n2max
       DO n1=1,n1max
          fmax=MAX(f1(n1,n2),fmax)
          fmin=MIN(f1(n1,n2),fmin)
       END DO
       fmax=MAX(f2(n2),fmax)
       fmin=MIN(f2(n2),fmin)
    END DO
    fmin_exact=fmin
    fmax_exact=fmax

    CALL convert_fmin_fmax(fmin,fmax,mode)
    RETURN
  END SUBROUTINE setup_fmin_fmax_2fx

  SUBROUTINE convert_fmin_fmax(fmin,fmax,mode)
    USE wfcomm,ONLY: rkind
    IMPLICIT NONE
    REAL(rkind),INTENT(INOUT):: fmin,fmax
    INTEGER,INTENT(OUT):: mode
    real(rkind):: ftemp

    IF(ABS(fmax).LE.1.D-12) fmax=0.D0
    IF(ABS(fmin).LE.1.D-12) fmin=0.D0
    
    IF(fmax*fmin.LT.0.D0) THEN
       ftemp=MAX(fmax,-fmin)
       fmax=ftemp
       fmin=-ftemp
       mode=1
    ELSE
       IF(fmax.GT.0.D0) THEN
          mode=2
       ELSE  IF(fmin.LT.0.D0) THEN
          mode=3
       ELSE ! fmin=fmax=0.D0
          fmin=-0.5D0
          fmax= 0.5D0
          mode=4
       END IF
    END IF
  END SUBROUTINE convert_fmin_fmax
END MODULE wfglib
