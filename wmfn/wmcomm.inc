C     $Id$
C
      USE libmpi 
      USE commpi
      USE libmtx 
      USE dpcomm,pt_dp=>PT  ! renamed: dpcomm_parm re-exports plcomm_parm's PT, which would hide wm's local scalar PT
      IMPLICIT COMPLEX*16(C),REAL*8(A-B,D-F,H,O-Z)
C     
      include 'wmcom0.inc'
      include 'wmcom1.inc'
