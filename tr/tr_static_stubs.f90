! tr_static_stubs.f90
!
! Phase L-? (issue #197 follow-up): graphics-symbol stubs for the
! standalone `tr2` Fortran binary path. tr/Makefile's `tr2` target links
! the full TASK archive chain (libgrf.a + libtr2.a + libeq.a + libpl.a +
! ...), which transitively references ~100 GSAF graphics primitives
! (GSCALE, GFRAME, GPLOTP, CONTF*, ...) that the per-module
! *_graphics_stubs.f90 files only partially cover. With CI's GFLIBS=
! (no graphics linkage), those references go unresolved and the
! standalone `tr2` binary fails to link.
!
! This file provides no-op stubs for every graphics symbol that the
! standalone-link path requires. None are exercised by the tr lifecycle
! that produces tr_regress + metrics regression dumps — the tr solver
! does not call into the GR* / EQGS* output paths during a regression-mode
! run — so no-op behaviour is safe.
!
! Scope:
!   - tr_graphics_stubs.f90 (existing) stays as the minimal stub set
!     baked into libtrapi.so for the dlopen / Python wrapper path.
!   - tr_static_stubs.f90 (this file) is linked ONLY into the
!     standalone `tr2` binary when GFLIBS is empty (CI / no-graphics
!     build), NEVER into libtrapi.so. The two stub sets coexist without
!     symbol conflict because their object files target distinct binaries.
!
! Mirrors tot/tot_static_stubs.f90; the stub body is identical (the
! GSAF symbol set is shared across modules). Files are duplicated rather
! than shared to preserve per-module isolation that the existing
! *_graphics_stubs.f90 PIC variants already follow. A future refactor
! to a single shared `lib/graphics_stubs.f90` is tracked as a follow-up
! per spec section 3 non-goals.
!
! Two of the ~100 entries are functions whose return value the callers
! consume; the rest are subroutines used as side-effecting calls and
! return immediately. See `tot/tot_static_stubs.f90`'s header for the
! detailed audit notes that apply identically here.

! ---------------------------------------------------------------------
! Functions (callers consume return value)
! ---------------------------------------------------------------------

REAL FUNCTION GUCLIP(X)
  IMPLICIT NONE
  DOUBLE PRECISION, INTENT(IN) :: X
  GUCLIP = REAL(X)
END FUNCTION GUCLIP

INTEGER FUNCTION NGULEN(X)
  IMPLICIT NONE
  REAL, INTENT(IN) :: X
  NGULEN = 0
END FUNCTION NGULEN

! ---------------------------------------------------------------------
! Subroutines — minimal no-op stubs, no formal arguments.
!
! Callers that pass arguments via the standard Fortran ABI still
! resolve at link time on symbol name alone (no implicit interface
! checking from a USE'd module is involved here). The stubs ignore
! the passed arguments and return immediately.
!
! Why this is safe under gfortran on x86_64 Linux / macOS arm64
! (the only CI / dev targets):
!   * The Fortran ABI used by gfortran follows the C SysV / AAPCS64
!     caller-cleans convention. The stub's prologue saves the frame
!     pointer and returns; it never references the caller's args, so
!     they are silently discarded.
!   * Per Fortran 2008 §12.4.3.4 this is technically undefined when
!     the caller's actual-argument list does not match the stub's
!     dummy-argument list, but no test path in tot_api_check_all
!     reaches a graphics output routine — init / run(0) / get_state /
!     finalize never invoke GR* / GS*. The stubs exist solely to
!     satisfy link-time symbol resolution; they are never executed.
!   * If a future test path were to actually call into one of these
!     stubs, the worst-case outcome is a no-op return rather than a
!     crash (because the args are passed but unread). That is the
!     desired CI behaviour anyway.
!
! For a stricter (but tedious) alternative, harvest each call site's
! signature from libgrf / libtr2 / ... and declare matching dummy
! arguments. Tracked as a future tightening; not required for the L-6
! Layer 2 CI gate.
! ---------------------------------------------------------------------

SUBROUTINE BLACK
END SUBROUTINE BLACK

SUBROUTINE CHMODE
END SUBROUTINE CHMODE

SUBROUTINE CONTF1
END SUBROUTINE CONTF1

SUBROUTINE CONTF2
END SUBROUTINE CONTF2

SUBROUTINE CONTF3
END SUBROUTINE CONTF3

SUBROUTINE CONTF4
END SUBROUTINE CONTF4

SUBROUTINE CONTFX
END SUBROUTINE CONTFX

SUBROUTINE CONTG1
END SUBROUTINE CONTG1

SUBROUTINE CONTG2
END SUBROUTINE CONTG2

SUBROUTINE CONTG3
END SUBROUTINE CONTG3

SUBROUTINE CONTG4
END SUBROUTINE CONTG4

SUBROUTINE CONTP1
END SUBROUTINE CONTP1

SUBROUTINE CONTP2
END SUBROUTINE CONTP2

SUBROUTINE CONTP4
END SUBROUTINE CONTP4

SUBROUTINE CONTP5
END SUBROUTINE CONTP5

SUBROUTINE CONTP6
END SUBROUTINE CONTP6

SUBROUTINE CONTQ1
END SUBROUTINE CONTQ1

SUBROUTINE CONTQ2
END SUBROUTINE CONTQ2

SUBROUTINE CONTQ3
END SUBROUTINE CONTQ3

SUBROUTINE CONTQ3D1
END SUBROUTINE CONTQ3D1

SUBROUTINE CONTQ4
END SUBROUTINE CONTQ4

SUBROUTINE CONTQ5
END SUBROUTINE CONTQ5

SUBROUTINE CONTV1
END SUBROUTINE CONTV1

SUBROUTINE CPLOT3D1
END SUBROUTINE CPLOT3D1

SUBROUTINE DRAW
END SUBROUTINE DRAW

SUBROUTINE DRAW2D
END SUBROUTINE DRAW2D

SUBROUTINE DRAWPT
END SUBROUTINE DRAWPT

SUBROUTINE DRAWPT2D
END SUBROUTINE DRAWPT2D

SUBROUTINE GAXIS3D
END SUBROUTINE GAXIS3D

SUBROUTINE GDATA3D1
END SUBROUTINE GDATA3D1

SUBROUTINE GDATA3D3
END SUBROUTINE GDATA3D3

SUBROUTINE GDEFIN
END SUBROUTINE GDEFIN

SUBROUTINE GDEFIN3D
END SUBROUTINE GDEFIN3D

SUBROUTINE GFRAME
END SUBROUTINE GFRAME

SUBROUTINE GMNMX1
END SUBROUTINE GMNMX1

SUBROUTINE GMNMX2
END SUBROUTINE GMNMX2

SUBROUTINE GNUMBI2D
END SUBROUTINE GNUMBI2D

SUBROUTINE GPLOTP
END SUBROUTINE GPLOTP

SUBROUTINE GPLOTPE
END SUBROUTINE GPLOTPE

SUBROUTINE GPLOTPG
END SUBROUTINE GPLOTPG

SUBROUTINE GQSCAL
END SUBROUTINE GQSCAL

SUBROUTINE GRMODE
END SUBROUTINE GRMODE

SUBROUTINE GSCALE
END SUBROUTINE GSCALE

SUBROUTINE GSCALE3DX
END SUBROUTINE GSCALE3DX

SUBROUTINE GSCALE3DY
END SUBROUTINE GSCALE3DY

SUBROUTINE GSCALE3DZ
END SUBROUTINE GSCALE3DZ

SUBROUTINE GSCALL
END SUBROUTINE GSCALL

SUBROUTINE GSCLOS
END SUBROUTINE GSCLOS

SUBROUTINE GSOPEN
END SUBROUTINE GSOPEN

SUBROUTINE GTEXT
END SUBROUTINE GTEXT

SUBROUTINE GTEXTX
END SUBROUTINE GTEXTX

SUBROUTINE GTTTA
END SUBROUTINE GTTTA

SUBROUTINE GUDATE
END SUBROUTINE GUDATE

SUBROUTINE GUFLSH
END SUBROUTINE GUFLSH

SUBROUTINE GUSRGB
END SUBROUTINE GUSRGB

SUBROUTINE GUTIME
END SUBROUTINE GUTIME

SUBROUTINE GVALUE
END SUBROUTINE GVALUE

SUBROUTINE GVALUE3DX
END SUBROUTINE GVALUE3DX

SUBROUTINE GVALUE3DY
END SUBROUTINE GVALUE3DY

SUBROUTINE GVALUE3DZ
END SUBROUTINE GVALUE3DZ

SUBROUTINE GVALUL
END SUBROUTINE GVALUL

SUBROUTINE GVIEW3D
END SUBROUTINE GVIEW3D

SUBROUTINE INQGDEFIN
END SUBROUTINE INQGDEFIN

SUBROUTINE INQLIN
END SUBROUTINE INQLIN

SUBROUTINE INQLNW
END SUBROUTINE INQLNW

SUBROUTINE INQPOS
END SUBROUTINE INQPOS

SUBROUTINE INQRGB
END SUBROUTINE INQRGB

SUBROUTINE INQTSZ
END SUBROUTINE INQTSZ

SUBROUTINE LINES
END SUBROUTINE LINES

SUBROUTINE MARK
END SUBROUTINE MARK

SUBROUTINE MARK2D
END SUBROUTINE MARK2D

SUBROUTINE MOVE
END SUBROUTINE MOVE

SUBROUTINE MOVE2D
END SUBROUTINE MOVE2D

SUBROUTINE MOVEPT
END SUBROUTINE MOVEPT

SUBROUTINE MOVEPT2D
END SUBROUTINE MOVEPT2D

SUBROUTINE NUMBD
END SUBROUTINE NUMBD

SUBROUTINE NUMBI
END SUBROUTINE NUMBI

SUBROUTINE NUMBR
END SUBROUTINE NUMBR

SUBROUTINE OFFCLP
END SUBROUTINE OFFCLP

SUBROUTINE OFFVEW
END SUBROUTINE OFFVEW

SUBROUTINE PAGEE
END SUBROUTINE PAGEE

SUBROUTINE PAGES
END SUBROUTINE PAGES

SUBROUTINE PERSE1
END SUBROUTINE PERSE1

SUBROUTINE PERSE3D
END SUBROUTINE PERSE3D

SUBROUTINE POLY
END SUBROUTINE POLY

SUBROUTINE R2G2B
END SUBROUTINE R2G2B

SUBROUTINE R2W2B
END SUBROUTINE R2W2B

SUBROUTINE R2Y2W
END SUBROUTINE R2Y2W

SUBROUTINE RGBBAR
END SUBROUTINE RGBBAR

SUBROUTINE SETCHS
END SUBROUTINE SETCHS

SUBROUTINE SETCLP
END SUBROUTINE SETCLP

SUBROUTINE SETFNT
END SUBROUTINE SETFNT

SUBROUTINE SETLIN
END SUBROUTINE SETLIN

SUBROUTINE SETLNW
END SUBROUTINE SETLNW

SUBROUTINE SETMKS
END SUBROUTINE SETMKS

SUBROUTINE SETRGB
END SUBROUTINE SETRGB

SUBROUTINE SETVEW
END SUBROUTINE SETVEW

SUBROUTINE TEXT
END SUBROUTINE TEXT

SUBROUTINE TEXTX
END SUBROUTINE TEXTX

SUBROUTINE W2G2B
END SUBROUTINE W2G2B
