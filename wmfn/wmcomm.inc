C     $Id$
C
      USE libmpi 
      USE commpi
      USE libmtx 
      USE dpcomm,pt_dp=>PT  ! merge: dpcomm_parm re-exports plcomm_parm's PT; wm uses PT as an implicit local scalar
      IMPLICIT COMPLEX*16(C),REAL*8(A-B,D-F,H,O-Z)
C     
      include 'wmcom0.inc'
      include 'wmcom1.inc'
