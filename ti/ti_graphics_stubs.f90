! ti_graphics_stubs.f90
!
! Phase L-4: minimal stand-ins for the few GSAF / graphics entry points
! that TICORE may reference at run-time even though libtiapi.so excludes
! all real graphics output.
!
! Background: the non-graphics ti core (SRCS_CORE in ti/Makefile) does
! not call GUCLIP/PAGES/PAGEE/GUDATE/GUTIME/GUFLSH directly, but
! transitive dependencies pulled in from libpl_pic / libeq_pic or from
! the bpsd / adpost / adf11 libraries may reference them. The real
! GUCLIP lives in libgsp/libgsaf which are non-PIC and cannot be linked
! into a shared object; we therefore provide in-library replacements so
! dlopen() succeeds without dragging libg3d/libgsp into the .so.
!
! The stubs are no-ops (or, for GUCLIP, a simple REAL(X) cast). None of
! them are exercised by ti_init -> ti_run -> ti_finalize so the no-op
! behaviour is safe; if a future caller needs real output the right
! answer is to add a libtigrf_pic.a rather than to extend these stubs.
! Mirrors tr_graphics_stubs.f90 (PR #35).

REAL FUNCTION GUCLIP(X)
  IMPLICIT NONE
  DOUBLE PRECISION, INTENT(IN) :: X
  GUCLIP = REAL(X)
END FUNCTION GUCLIP

SUBROUTINE PAGES
  IMPLICIT NONE
END SUBROUTINE PAGES

SUBROUTINE PAGEE
  IMPLICIT NONE
END SUBROUTINE PAGEE

SUBROUTINE GUDATE(KK)
  IMPLICIT NONE
  CHARACTER(LEN=*), INTENT(OUT) :: KK
  KK = ' '
END SUBROUTINE GUDATE

SUBROUTINE GUTIME(KK)
  IMPLICIT NONE
  CHARACTER(LEN=*), INTENT(OUT) :: KK
  KK = ' '
END SUBROUTINE GUTIME

SUBROUTINE GUFLSH
  IMPLICIT NONE
END SUBROUTINE GUFLSH
