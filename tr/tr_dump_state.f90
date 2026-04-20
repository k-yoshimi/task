! tr_dump_state.f90
!
! Optional dump of selected TRCOMM state to a text file.
!
! Activated by setting the environment variable ``TR_DUMP_STATE`` to the
! output file path. When unset (or empty), all entry points are no-ops so
! production runs pay zero cost.
!
! Designed for side-by-side diff of the binary tr2 vs the libtrapi.so
! (Python) execution paths to localise NSM/NSMAX-class uninit bugs.
!
! Format: append-only text, key=value, one per line. Reals are written with
! ES23.15E3. The file is opened with ``POSITION='APPEND'`` so multiple
! callers (e.g. before-prep and after-prep) can co-exist; sections are
! framed by ``# === tr_dump_state begin: <label> ===`` markers.

MODULE tr_dump_state_mod

  USE TRCOM0, ONLY: rkind
  IMPLICIT NONE
  PRIVATE
  PUBLIC :: tr_dump_state, tr_dump_state_if_requested

CONTAINS

  ! Convenience wrapper: dumps only when TR_DUMP_STATE is set.
  ! Callers can sprinkle this in init/prep paths without guard logic.
  SUBROUTINE tr_dump_state_if_requested(label)
    CHARACTER(LEN=*), INTENT(IN) :: label
    CHARACTER(LEN=512) :: env_path
    INTEGER :: status, length

    CALL get_environment_variable('TR_DUMP_STATE', env_path, &
         LENGTH=length, STATUS=status)
    IF (status /= 0) RETURN
    IF (length == 0) RETURN

    CALL tr_dump_state(env_path(1:length), label)
  END SUBROUTINE tr_dump_state_if_requested

  SUBROUTINE tr_dump_state(path, label)
    USE trcom0,         ONLY: NSM, NSTM, NSMM, NRMP, NSMAX, NRMAX
    USE trcomm_param,   ONLY: MDLIMP, MODELG, NTMAX,    &
                              RR, RA, RKAP, BB, RIPS,   &
                              PA, PZ, PN, PNS, PT, PTS, &
                              PNC, PNFE, DT
    USE trcomm_ctrl,    ONLY: NT, T, RIP, DR, &
                              MDLEQB, MDLEQN, MDLEQT, MDLEQU, MDLUF, &
                              PNSS
    USE trcomm_profile, ONLY: RN, RT, RM, RG, BP, ANC, ANFE, PZC, PZFE, &
                              ZEFF, AJ, QP, EZOH, &
                              PNSA, PNSSA, PTSA, &
                              PNSSO, PTSO, PNSSAO, PTSAO

    CHARACTER(LEN=*), INTENT(IN) :: path, label
    INTEGER :: u, ns, nr, ios, mid_nr

    OPEN(NEWUNIT=u, FILE=path, STATUS='UNKNOWN', POSITION='APPEND', &
         ACTION='WRITE', FORM='FORMATTED', IOSTAT=ios)
    IF (ios /= 0) RETURN

    WRITE(u, '(A)') '# === tr_dump_state begin: '//TRIM(label)//' ==='

    ! ---- compile-time constants ----
    WRITE(u, '(A,I0)') 'NSM=',  NSM
    WRITE(u, '(A,I0)') 'NSTM=', NSTM
    WRITE(u, '(A,I0)') 'NSMM=', NSMM
    WRITE(u, '(A,I0)') 'NRMP=', NRMP

    ! ---- runtime sizes ----
    WRITE(u, '(A,I0)') 'NSMAX=',  NSMAX
    WRITE(u, '(A,I0)') 'NRMAX=',  NRMAX
    WRITE(u, '(A,I0)') 'NTMAX=',  NTMAX
    WRITE(u, '(A,I0)') 'NT=',     NT

    ! ---- mode flags ----
    WRITE(u, '(A,I0)') 'MDLIMP=', MDLIMP
    WRITE(u, '(A,I0)') 'MODELG=', MODELG
    WRITE(u, '(A,I0)') 'MDLUF=',  MDLUF
    WRITE(u, '(A,I0)') 'MDLEQB=', MDLEQB
    WRITE(u, '(A,I0)') 'MDLEQN=', MDLEQN
    WRITE(u, '(A,I0)') 'MDLEQT=', MDLEQT
    WRITE(u, '(A,I0)') 'MDLEQU=', MDLEQU

    ! ---- geometry / scalar params ----
    CALL emit_scalar(u, 'RR',   RR)
    CALL emit_scalar(u, 'RA',   RA)
    CALL emit_scalar(u, 'RKAP', RKAP)
    CALL emit_scalar(u, 'BB',   BB)
    CALL emit_scalar(u, 'RIPS', RIPS)
    CALL emit_scalar(u, 'RIP',  RIP)
    CALL emit_scalar(u, 'PNC',  PNC)
    CALL emit_scalar(u, 'PNFE', PNFE)
    CALL emit_scalar(u, 'DR',   DR)
    CALL emit_scalar(u, 'DT',   DT)
    CALL emit_scalar(u, 'T',    T)

    ! ---- per-species namelist arrays (NSMM=100, dump 1..NSTM only) ----
    DO ns = 1, NSTM
       CALL emit_idx1(u, 'PA',  ns, PA(ns))
       CALL emit_idx1(u, 'PZ',  ns, PZ(ns))
       CALL emit_idx1(u, 'PN',  ns, PN(ns))
       CALL emit_idx1(u, 'PNS', ns, PNS(ns))
       CALL emit_idx1(u, 'PT',  ns, PT(ns))
       CALL emit_idx1(u, 'PTS', ns, PTS(ns))
    END DO

    ! ---- allocatable NSTM-bounded sister arrays ----
    CALL emit_alloc1d(u, 'PNSS',   PNSS)
    CALL emit_alloc1d(u, 'PNSSA',  PNSSA)
    CALL emit_alloc1d(u, 'PNSA',   PNSA)
    CALL emit_alloc1d(u, 'PTSA',   PTSA)
    CALL emit_alloc1d(u, 'PNSSO',  PNSSO)
    CALL emit_alloc1d(u, 'PTSO',   PTSO)
    CALL emit_alloc1d(u, 'PNSSAO', PNSSAO)
    CALL emit_alloc1d(u, 'PTSAO',  PTSAO)

    ! ---- 2D profile arrays at NR=1, mid, NRMAX over species 1..NSTM ----
    IF (NRMAX > 0) THEN
       mid_nr = MAX(1, NRMAX / 2)
       CALL emit_alloc2d_slices(u, 'RN', RN, NRMAX, mid_nr)
       CALL emit_alloc2d_slices(u, 'RT', RT, NRMAX, mid_nr)
    END IF

    ! ---- 1D NRMAX profile arrays at NR=1, mid, NRMAX ----
    IF (NRMAX > 0) THEN
       mid_nr = MAX(1, NRMAX / 2)
       CALL emit_alloc1d_slice(u, 'RM',   RM,   1, mid_nr, NRMAX)
       CALL emit_alloc1d_slice(u, 'RG',   RG,   1, mid_nr, NRMAX)
       CALL emit_alloc1d_slice(u, 'BP',   BP,   1, mid_nr, NRMAX)
       CALL emit_alloc1d_slice(u, 'ANC',  ANC,  1, mid_nr, NRMAX)
       CALL emit_alloc1d_slice(u, 'ANFE', ANFE, 1, mid_nr, NRMAX)
       CALL emit_alloc1d_slice(u, 'PZC',  PZC,  1, mid_nr, NRMAX)
       CALL emit_alloc1d_slice(u, 'PZFE', PZFE, 1, mid_nr, NRMAX)
       CALL emit_alloc1d_slice(u, 'ZEFF', ZEFF, 1, mid_nr, NRMAX)
       CALL emit_alloc1d_slice(u, 'AJ',   AJ,   1, mid_nr, NRMAX)
       CALL emit_alloc1d_slice(u, 'QP',   QP,   1, mid_nr, NRMAX)
       CALL emit_alloc1d_slice(u, 'EZOH', EZOH, 1, mid_nr, NRMAX)
    END IF

    WRITE(u, '(A)') '# === tr_dump_state end: '//TRIM(label)//' ==='
    CLOSE(u)
  END SUBROUTINE tr_dump_state

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

  SUBROUTINE emit_idx2(u, name, i1, i2, value)
    INTEGER, INTENT(IN) :: u, i1, i2
    CHARACTER(LEN=*), INTENT(IN) :: name
    REAL(rkind), INTENT(IN) :: value
    CHARACTER(LEN=128) :: line
    WRITE(line, '(A,"(",I0,",",I0,")=",ES23.15E3)') name, i1, i2, value
    WRITE(u, '(A)') TRIM(line)
  END SUBROUTINE emit_idx2

  SUBROUTINE emit_alloc1d(u, name, arr)
    INTEGER, INTENT(IN) :: u
    CHARACTER(LEN=*), INTENT(IN) :: name
    REAL(rkind), ALLOCATABLE, INTENT(IN) :: arr(:)
    INTEGER :: i, n
    IF (.NOT. ALLOCATED(arr)) THEN
       WRITE(u, '(A,A)') name, '=<unallocated>'
       RETURN
    END IF
    n = SIZE(arr)
    DO i = 1, n
       CALL emit_idx1(u, name, i, arr(i))
    END DO
  END SUBROUTINE emit_alloc1d

  SUBROUTINE emit_alloc1d_slice(u, name, arr, i1, i2, i3)
    INTEGER, INTENT(IN) :: u, i1, i2, i3
    CHARACTER(LEN=*), INTENT(IN) :: name
    REAL(rkind), ALLOCATABLE, INTENT(IN) :: arr(:)
    IF (.NOT. ALLOCATED(arr)) THEN
       WRITE(u, '(A,A)') name, '=<unallocated>'
       RETURN
    END IF
    IF (i1 >= 1 .AND. i1 <= SIZE(arr)) CALL emit_idx1(u, name, i1, arr(i1))
    IF (i2 /= i1 .AND. i2 >= 1 .AND. i2 <= SIZE(arr)) &
         CALL emit_idx1(u, name, i2, arr(i2))
    IF (i3 /= i1 .AND. i3 /= i2 .AND. i3 >= 1 .AND. i3 <= SIZE(arr)) &
         CALL emit_idx1(u, name, i3, arr(i3))
  END SUBROUTINE emit_alloc1d_slice

  SUBROUTINE emit_alloc2d_slices(u, name, arr, nrmax_in, mid_nr)
    INTEGER, INTENT(IN) :: u, nrmax_in, mid_nr
    CHARACTER(LEN=*), INTENT(IN) :: name
    REAL(rkind), ALLOCATABLE, INTENT(IN) :: arr(:,:)
    INTEGER :: ns, nspec
    IF (.NOT. ALLOCATED(arr)) THEN
       WRITE(u, '(A,A)') name, '=<unallocated>'
       RETURN
    END IF
    nspec = SIZE(arr, 2)
    DO ns = 1, nspec
       CALL emit_idx2(u, name, 1,        ns, arr(1,        ns))
       IF (mid_nr /= 1) &
            CALL emit_idx2(u, name, mid_nr, ns, arr(mid_nr, ns))
       IF (nrmax_in /= 1 .AND. nrmax_in /= mid_nr) &
            CALL emit_idx2(u, name, nrmax_in, ns, arr(nrmax_in, ns))
    END DO
  END SUBROUTINE emit_alloc2d_slices

END MODULE tr_dump_state_mod
