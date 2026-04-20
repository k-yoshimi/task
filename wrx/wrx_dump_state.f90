! wrx_dump_state.f90
!
! Optional dump of selected wrcomm state to a text file.
!
! Activated by setting the environment variable ``WRX_DUMP_STATE`` to the
! output file path. When unset (or empty), all entry points are no-ops so
! production runs pay zero cost.
!
! Designed for side-by-side diff of the binary wrx vs the libwrxapi.so
! (Python) execution paths to localise NSTPMAX/NSAMAX_WR-class uninit /
! shape-mismatch bugs.
!
! Format: append-only text, key=value, one per line. Reals are written with
! ES23.15E3. The file is opened with ``POSITION='APPEND'`` so multiple
! callers (e.g. before-prep and after-calc) can co-exist; sections are
! framed by ``# === wrx_dump_state begin: <label> ===`` markers.

MODULE wrx_dump_state_mod

  USE wrcomm, ONLY: rkind
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: wrx_dump_state, wrx_dump_state_if_requested

CONTAINS

  ! Convenience wrapper: dumps only when WRX_DUMP_STATE is set.
  SUBROUTINE wrx_dump_state_if_requested(label)
    CHARACTER(LEN=*), INTENT(IN) :: label
    CHARACTER(LEN=512) :: env_path
    INTEGER :: status, length

    CALL get_environment_variable('WRX_DUMP_STATE', env_path, &
         LENGTH=length, STATUS=status)
    IF (status /= 0) RETURN
    IF (length == 0) RETURN

    CALL wrx_dump_state(env_path(1:length), label)
  END SUBROUTINE wrx_dump_state_if_requested

  SUBROUTINE wrx_dump_state(path, label)
    USE wrcomm, ONLY: NRAYMAX, NSTPMAX, NRSMAX, NRLMAX, &
                      nsamax_wr, NSMAX, NEQ, &
                      NSTPMAX_NRAY, pos_nrs, pos_nrl, &
                      pwr_nsa_nstp_nray, pwr_nrl_nsa_nray, &
                      pwr_nrs_nsa_nray, pwr_nsa_nstp, &
                      RAYS, &
                      RFIN, RPIN, ZPIN, PHIIN, ANGTIN, ANGPIN, UUIN, &
                      MODEWIN, &
                      SMAX, DELS, RR, RA, RKAP, BB, &
                      MDLWRI, MDLWRG, MDLWRP, MDLWRQ, MDLWRW

    CHARACTER(LEN=*), INTENT(IN) :: path, label
    INTEGER :: u, ios, nray, nsa

    OPEN(NEWUNIT=u, FILE=path, STATUS='UNKNOWN', POSITION='APPEND', &
         ACTION='WRITE', FORM='FORMATTED', IOSTAT=ios)
    IF (ios /= 0) RETURN

    WRITE(u, '(A)') '# === wrx_dump_state begin: '//TRIM(label)//' ==='

    ! ---- runtime sizes ----
    WRITE(u, '(A,I0)') 'NRAYMAX=',   NRAYMAX
    WRITE(u, '(A,I0)') 'NSTPMAX=',   NSTPMAX
    WRITE(u, '(A,I0)') 'NRSMAX=',    NRSMAX
    WRITE(u, '(A,I0)') 'NRLMAX=',    NRLMAX
    WRITE(u, '(A,I0)') 'nsamax_wr=', nsamax_wr
    WRITE(u, '(A,I0)') 'NSMAX=',     NSMAX
    WRITE(u, '(A,I0)') 'NEQ=',       NEQ

    ! ---- mode flags ----
    WRITE(u, '(A,I0)') 'MDLWRI=', MDLWRI
    WRITE(u, '(A,I0)') 'MDLWRG=', MDLWRG
    WRITE(u, '(A,I0)') 'MDLWRP=', MDLWRP
    WRITE(u, '(A,I0)') 'MDLWRQ=', MDLWRQ
    WRITE(u, '(A,I0)') 'MDLWRW=', MDLWRW

    ! ---- geometry / scalar params ----
    CALL emit_scalar(u, 'RR',   RR)
    CALL emit_scalar(u, 'RA',   RA)
    CALL emit_scalar(u, 'RKAP', RKAP)
    CALL emit_scalar(u, 'BB',   BB)
    CALL emit_scalar(u, 'SMAX', SMAX)
    CALL emit_scalar(u, 'DELS', DELS)

    ! ---- per-ray launch parameters (1..NRAYMAX) ----
    DO nray = 1, NRAYMAX
       CALL emit_idx1(u, 'RFIN',    nray, RFIN(nray))
       CALL emit_idx1(u, 'RPIN',    nray, RPIN(nray))
       CALL emit_idx1(u, 'ZPIN',    nray, ZPIN(nray))
       CALL emit_idx1(u, 'PHIIN',   nray, PHIIN(nray))
       CALL emit_idx1(u, 'ANGTIN',  nray, ANGTIN(nray))
       CALL emit_idx1(u, 'ANGPIN',  nray, ANGPIN(nray))
       CALL emit_idx1(u, 'UUIN',    nray, UUIN(nray))
       WRITE(u, '(A,"(",I0,")=",I0)') 'MODEWIN', nray, MODEWIN(nray)
    END DO

    ! ---- allocatable shapes + first/last/MAXVAL element ----
    CALL emit_alloc1d_int(u, 'NSTPMAX_NRAY', NSTPMAX_NRAY)
    CALL emit_alloc1d(u, 'pos_nrs', pos_nrs)
    CALL emit_alloc1d(u, 'pos_nrl', pos_nrl)

    ! ---- 3D arrays: shape + selected probes ----
    CALL emit_alloc3d_summary(u, 'pwr_nsa_nstp_nray', pwr_nsa_nstp_nray)
    CALL emit_alloc3d_summary(u, 'pwr_nrs_nsa_nray',  pwr_nrs_nsa_nray)
    CALL emit_alloc3d_summary(u, 'pwr_nrl_nsa_nray',  pwr_nrl_nsa_nray)

    ! ---- 2D arrays: shape + selected probes ----
    CALL emit_alloc2d_summary(u, 'pwr_nsa_nstp', pwr_nsa_nstp)
    CALL emit_alloc3d_summary(u, 'RAYS',         RAYS)

    ! ---- key derived values used as loop bounds ----
    IF (ALLOCATED(NSTPMAX_NRAY) .AND. NRAYMAX >= 1 .AND. &
        SIZE(NSTPMAX_NRAY) >= NRAYMAX) THEN
       DO nray = 1, NRAYMAX
          WRITE(u, '(A,"(",I0,")=",I0)') 'NSTPMAX_NRAY', nray, &
               NSTPMAX_NRAY(nray)
       END DO
       WRITE(u, '(A,I0)') 'MAXVAL_NSTPMAX_NRAY=', &
            MAXVAL(NSTPMAX_NRAY(1:NRAYMAX))
       WRITE(u, '(A,I0)') 'NSTPMAX_ALL_PLUS1=', &
            MAXVAL(NSTPMAX_NRAY(1:NRAYMAX)) + 1
    END IF

    WRITE(u, '(A)') '# === wrx_dump_state end: '//TRIM(label)//' ==='
    CLOSE(u)
  END SUBROUTINE wrx_dump_state

  ! ---------- helpers ----------

  SUBROUTINE emit_scalar(u, name, value)
    INTEGER, INTENT(IN) :: u
    CHARACTER(LEN=*), INTENT(IN) :: name
    REAL(rkind), INTENT(IN) :: value
    CHARACTER(LEN=128) :: line
    WRITE(line, '(A,"=",ES23.15E3)') name, value
    WRITE(u, '(A)') TRIM(line)
  END SUBROUTINE emit_scalar

  SUBROUTINE emit_idx1(u, name, idx, value)
    INTEGER, INTENT(IN) :: u, idx
    CHARACTER(LEN=*), INTENT(IN) :: name
    REAL(rkind), INTENT(IN) :: value
    CHARACTER(LEN=128) :: line
    WRITE(line, '(A,"(",I0,")=",ES23.15E3)') name, idx, value
    WRITE(u, '(A)') TRIM(line)
  END SUBROUTINE emit_idx1

  SUBROUTINE emit_alloc1d(u, name, arr)
    INTEGER, INTENT(IN) :: u
    CHARACTER(LEN=*), INTENT(IN) :: name
    REAL(rkind), ALLOCATABLE, INTENT(IN) :: arr(:)
    INTEGER :: n
    IF (.NOT. ALLOCATED(arr)) THEN
       WRITE(u, '(A,A)') name, '=<unallocated>'
       RETURN
    END IF
    n = SIZE(arr)
    WRITE(u, '(A,A,I0)') name, '_size=', n
    IF (n >= 1) CALL emit_idx1(u, name, 1, arr(1))
    IF (n >= 2) CALL emit_idx1(u, name, n, arr(n))
  END SUBROUTINE emit_alloc1d

  SUBROUTINE emit_alloc1d_int(u, name, arr)
    INTEGER, INTENT(IN) :: u
    CHARACTER(LEN=*), INTENT(IN) :: name
    INTEGER, ALLOCATABLE, INTENT(IN) :: arr(:)
    INTEGER :: i, n
    IF (.NOT. ALLOCATED(arr)) THEN
       WRITE(u, '(A,A)') name, '=<unallocated>'
       RETURN
    END IF
    n = SIZE(arr)
    WRITE(u, '(A,A,I0)') name, '_size=', n
    DO i = 1, n
       WRITE(u, '(A,"(",I0,")=",I0)') name, i, arr(i)
    END DO
  END SUBROUTINE emit_alloc1d_int

  SUBROUTINE emit_alloc2d_summary(u, name, arr)
    INTEGER, INTENT(IN) :: u
    CHARACTER(LEN=*), INTENT(IN) :: name
    REAL(rkind), ALLOCATABLE, INTENT(IN) :: arr(:,:)
    INTEGER :: lb1, ub1, lb2, ub2
    IF (.NOT. ALLOCATED(arr)) THEN
       WRITE(u, '(A,A)') name, '=<unallocated>'
       RETURN
    END IF
    lb1 = LBOUND(arr,1); ub1 = UBOUND(arr,1)
    lb2 = LBOUND(arr,2); ub2 = UBOUND(arr,2)
    WRITE(u, '(A,A,I0,":",I0,",",I0,":",I0,A)') &
         name, '_bounds=(', lb1, ub1, lb2, ub2, ')'
    WRITE(u, '(A,A,ES23.15E3)') name, '(lb,lb)=', arr(lb1,lb2)
    WRITE(u, '(A,A,ES23.15E3)') name, '(ub,ub)=', arr(ub1,ub2)
  END SUBROUTINE emit_alloc2d_summary

  SUBROUTINE emit_alloc3d_summary(u, name, arr)
    INTEGER, INTENT(IN) :: u
    CHARACTER(LEN=*), INTENT(IN) :: name
    REAL(rkind), ALLOCATABLE, INTENT(IN) :: arr(:,:,:)
    INTEGER :: lb1, ub1, lb2, ub2, lb3, ub3
    IF (.NOT. ALLOCATED(arr)) THEN
       WRITE(u, '(A,A)') name, '=<unallocated>'
       RETURN
    END IF
    lb1 = LBOUND(arr,1); ub1 = UBOUND(arr,1)
    lb2 = LBOUND(arr,2); ub2 = UBOUND(arr,2)
    lb3 = LBOUND(arr,3); ub3 = UBOUND(arr,3)
    WRITE(u, '(A,A,I0,":",I0,",",I0,":",I0,",",I0,":",I0,A)') &
         name, '_bounds=(', lb1, ub1, lb2, ub2, lb3, ub3, ')'
    WRITE(u, '(A,A,ES23.15E3)') name, '(lb,lb,lb)=', arr(lb1,lb2,lb3)
    WRITE(u, '(A,A,ES23.15E3)') name, '(ub,ub,ub)=', arr(ub1,ub2,ub3)
  END SUBROUTINE emit_alloc3d_summary

END MODULE wrx_dump_state_mod
