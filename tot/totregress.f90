! totregress.f90
!
! High-precision regression dump for the integrated tot simulator (Phase L-0).
! Emits tot_regress.dat (1PE24.16 format) when TOT_REGRESS_DUMP=1.
! Otherwise does nothing; normal tot runs are unaffected.
!
! Schema (format v1):
!   - TR scalars/profile (always written if TR's allocatable arrays are
!     allocated; otherwise TR_PRESENT=0 and the scalar/profile blocks are
!     skipped).
!   - TI/FP/WR "presence" flags (1 if the module's representative
!     allocatable array is ALLOCATED, else 0). Richer numeric dumps for
!     these modules are deferred to Phase L-6.
!
! The dump is MPI-safe: only nrank == 0 writes.

MODULE totregress

  PRIVATE
  PUBLIC :: tot_regress_dump_if_enabled

CONTAINS

  SUBROUTINE tot_regress_dump_if_enabled
    USE TRCOMM, ONLY: &
         NRMAX, NSMAX, NT, T, &
         WPT, AJT, AJRFT, Q0, BETA0, BETAP0, BETAA, BETAN, &
         TAUE1, TAUE2, ZEFF0, ALI, RQ1, &
         RN, RT, AJ, QP
    USE commpi, ONLY: nrank
    IMPLICIT NONE
    INTEGER, PARAMETER :: UNIT_DUMP = 78
    CHARACTER(LEN=16) :: ENV_VAL
    INTEGER :: STAT, NR, NS, IOERR
    LOGICAL :: ENABLED, TR_OK

    IF (nrank /= 0) RETURN

    CALL GET_ENVIRONMENT_VARIABLE('TOT_REGRESS_DUMP', ENV_VAL, STATUS=STAT)
    ENABLED = (STAT == 0 .AND. TRIM(ENV_VAL) == '1')
    IF (.NOT. ENABLED) RETURN

    OPEN(UNIT=UNIT_DUMP, FILE='tot_regress.dat', &
         STATUS='REPLACE', ACTION='WRITE', IOSTAT=IOERR)
    IF (IOERR /= 0) THEN
       WRITE(6,*) 'XX totregress: cannot open tot_regress.dat, IOSTAT=', IOERR
       RETURN
    END IF

    WRITE(UNIT_DUMP, '(A)') '# TASK/TOT regression dump (format v1)'

    ! TR scalars + profile (only when TR has been allocated; e.g. via tr_menu)
    TR_OK = ALLOCATED(RN) .AND. ALLOCATED(RT) .AND. &
            ALLOCATED(AJ) .AND. ALLOCATED(QP)
    IF (TR_OK) THEN
       WRITE(UNIT_DUMP, '(A)')           'TR_PRESENT=1'
       WRITE(UNIT_DUMP, '(A,I0)')        'NT=',     NT
       WRITE(UNIT_DUMP, '(A,I0)')        'NRMAX=',  NRMAX
       WRITE(UNIT_DUMP, '(A,I0)')        'NSMAX=',  NSMAX
       WRITE(UNIT_DUMP, '(A,1PE24.16)')  'T=',      T
       WRITE(UNIT_DUMP, '(A,1PE24.16)')  'WPT=',    WPT
       WRITE(UNIT_DUMP, '(A,1PE24.16)')  'AJT=',    AJT
       WRITE(UNIT_DUMP, '(A,1PE24.16)')  'AJRFT=',  AJRFT
       WRITE(UNIT_DUMP, '(A,1PE24.16)')  'Q0=',     Q0
       WRITE(UNIT_DUMP, '(A,1PE24.16)')  'BETA0=',  BETA0
       WRITE(UNIT_DUMP, '(A,1PE24.16)')  'BETAP0=', BETAP0
       WRITE(UNIT_DUMP, '(A,1PE24.16)')  'BETAA=',  BETAA
       WRITE(UNIT_DUMP, '(A,1PE24.16)')  'BETAN=',  BETAN
       WRITE(UNIT_DUMP, '(A,1PE24.16)')  'TAUE1=',  TAUE1
       WRITE(UNIT_DUMP, '(A,1PE24.16)')  'TAUE2=',  TAUE2
       WRITE(UNIT_DUMP, '(A,1PE24.16)')  'ZEFF0=',  ZEFF0
       WRITE(UNIT_DUMP, '(A,1PE24.16)')  'ALI=',    ALI
       WRITE(UNIT_DUMP, '(A,1PE24.16)')  'RQ1=',    RQ1

       WRITE(UNIT_DUMP, '(A)') &
            '# profile columns: NR RN(NR,1:NSMAX) RT(NR,1:NSMAX) AJ(NR) QP(NR)'
       DO NR = 1, NRMAX
          WRITE(UNIT_DUMP, '(I5)', ADVANCE='NO') NR
          DO NS = 1, NSMAX
             WRITE(UNIT_DUMP, '(1X,1PE24.16)', ADVANCE='NO') RN(NR,NS)
          END DO
          DO NS = 1, NSMAX
             WRITE(UNIT_DUMP, '(1X,1PE24.16)', ADVANCE='NO') RT(NR,NS)
          END DO
          WRITE(UNIT_DUMP, '(1X,1PE24.16,1X,1PE24.16)') AJ(NR), QP(NR)
       END DO
    ELSE
       WRITE(UNIT_DUMP, '(A)') 'TR_PRESENT=0'
    END IF

    ! TI/FP/WR presence flags. WR is part of the tot integration scope
    ! (totmain.f90 calls wr_init), so L-0 emits WR_PRESENT for parity with
    ! later L-2 tot_get_state and L-6 metrics_from_state work.
    CALL dump_module_presence(UNIT_DUMP, 'TI_PRESENT', ti_is_allocated())
    CALL dump_module_presence(UNIT_DUMP, 'FP_PRESENT', fp_is_allocated())
    CALL dump_module_presence(UNIT_DUMP, 'WR_PRESENT', wr_is_allocated())

    CLOSE(UNIT_DUMP)
  END SUBROUTINE tot_regress_dump_if_enabled

  SUBROUTINE dump_module_presence(unit, label, present)
    INTEGER, INTENT(IN) :: unit
    CHARACTER(LEN=*), INTENT(IN) :: label
    LOGICAL, INTENT(IN) :: present
    IF (present) THEN
       WRITE(unit, '(A,A)') TRIM(label), '=1'
    ELSE
       WRITE(unit, '(A,A)') TRIM(label), '=0'
    END IF
  END SUBROUTINE dump_module_presence

  ! ---- Module-presence helpers ------------------------------------------
  !
  ! Each helper checks whether a representative ALLOCATABLE array of the
  ! corresponding module has been allocated. We use the module's primary
  ! state-carrying array to be robust against alternative initialization
  ! paths within tot's menu loop.

  LOGICAL FUNCTION ti_is_allocated()
    USE ticomm, ONLY: RNA
    ti_is_allocated = ALLOCATED(RNA)
  END FUNCTION ti_is_allocated

  LOGICAL FUNCTION fp_is_allocated()
    USE fpcomm, ONLY: FNS
    fp_is_allocated = ALLOCATED(FNS)
  END FUNCTION fp_is_allocated

  LOGICAL FUNCTION wr_is_allocated()
    USE wrcomm, ONLY: RAYRB1
    wr_is_allocated = ALLOCATED(RAYRB1)
  END FUNCTION wr_is_allocated

END MODULE totregress
