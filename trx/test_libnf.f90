PROGRAM test_libnf
  USE plcomm
  USE libnf
  USE libgrf
  IMPLICIT NONE
  REAL(rkind),ALLOCATABLE:: X(:),Y(:,:)
  REAL(rkind):: Es,Ee,delE,En
  INTEGER:: nmax,n

  CALL GSOPEN
  
  Es=LOG10(0.1D3)  ! start energy in keV
  Ee=LOG10(10.D3)  ! end energy in keV
  nmax=201
  delE=(Ee-Es)/(nmax-1)

  ALLOCATE(X(nmax),Y(nmax,2))

  DO n=1,nmax
     En=Es+(n-1)*delE
     X(n)=En
     Y(n,1)=LOG10(S_nf_PB_NS(10.D0**En))
     Y(n,2)=LOG10(S_nf_PB_SW(10.D0**En))
  END DO

  CALL PAGES
  CALL GRD1D(0,X,Y,nmax,nmax,2,'S_PB vs EkeV@',3)
  CALL PAGEE

  DO n=1,nmax
     En=Es+(n-1)*delE
     X(n)=En
     Y(n,1)=LOG10(sigma_nf_PB_NS(10.D0**En*1.D-3))
     Y(n,2)=LOG10(sigma_nf_PB_SW(10.D0**En*1.D-3))
  END DO

  CALL PAGES
  CALL GRD1D(0,X,Y,nmax,nmax,2,'@sigma_PB vs EkeV@',3)
  CALL PAGEE

  DO n=1,nmax
     En=Es+(n-1)*delE
     X(n)=En
     Y(n,1)=sigma_nf_PB_NS(10.D0**En*1.D-3)
     Y(n,2)=sigma_nf_PB_SW(10.D0**En*1.D-3)
  END DO

  CALL PAGES
  CALL GRD1D(0,X,Y,nmax,nmax,2,'@sigma_PB vs EkeV@',1)
  CALL PAGEE

  CALL GSCLOS
  STOP
END PROGRAM test_libnf
