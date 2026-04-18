! tr_graphics_stubs.f90
!
! Phase L-4: minimal stand-ins for the few GSAF / graphics entry points
! that TRCORE references at run-time even though libtrapi.so excludes
! all real graphics output.
!
! Background: SRCS_CORE includes trrslt_globals.f90 (TRGLOB) which is
! invoked every NTSTEP from tr_eval (trexec.f90 ~line 410). TRGLOB calls
! GUCLIP to truncate REAL(8) -> REAL(4) for time-series storage. The real
! GUCLIP lives in libgsp/libgsaf which are non-PIC and cannot be linked
! into a shared object; we therefore provide an in-tree replacement that
! does just the cast.
!
! The remaining stubs (PAGES, PAGEE, GUDATE, GUTIME, GUFLSH) are no-ops
! that prevent dlopen from failing if any code path eventually reaches a
! plotting hook. None of them are exercised by tr_init -> tr_run ->
! tr_finalize so the no-op behaviour is safe; if a future caller needs
! real output the right answer is to add a libtrgrf_pic.a (see design
! doc Section A.4) rather than to extend these stubs.

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
