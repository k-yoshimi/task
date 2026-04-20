# Tier-2 reader-side fixes for tr/ NSM/NSMAX (NOT in Tier-1 patch)

These are reader-side fixes that arguably bound the loops to `NSMAX` instead of `NSM`. They are **not** included in the patch because they change which slots get processed, and the impurity slot (7,8) handling means a naive `1:NSMAX` substitution loses the impurity branch. Need maintainer judgment.

## Proposal R-1: trcoef_turbulence.f90:181, 220

```fortran
! current
DO NS=2, NSM
   RNTP=RNTP+PNSS(NS)*PTS(NS)
   ...
ENDDO

! proposed
DO NS=2, NSMAX
   RNTP=RNTP+PNSS(NS)*PTS(NS)
   ...
ENDDO
```

**Risk:** Loses the contribution of PNSS(3:4)*PTS(3:4) when NSMAX=2. Physically, those species are zero by default (PN/PT defaults to 0 for slots 3,4 unless namelist sets them) so the contribution is already zero — *unless* a future input sets `NSMAX=4` and uses slots 3, 4 as bulk T/A; then the loop should remain `2..NSMAX=4`. Behaviour is identical for the Tier-1 zero-init.

## Proposal R-2: trprof.f90:680-725 (TR_EDGE_SELECTOR / TR_EDGE_DETERMINER)

```fortran
! current (×6 inner loops)
DO NS=1, NSM
   PNSSO(NS) = PNSS(NS)
   ...
ENDDO

! proposed
DO NS=1, NSMAX
   PNSSO(NS) = PNSS(NS)
   ...
ENDDO
! plus loops for impurity (5,6) and neutral (7,8) slots if MDLEQZ/MDLEQ0=1
```

**Risk:** TR_EDGE_SELECTOR's slot semantics are tied to `NSM=4` (bulk). Switching to `NSMAX` is correct for bulk but ignores the case where `NSZMAX>0` adds impurity slots that also need their edge values saved/restored. A maintainer should audit whether PNSS(5:8) ever holds a value that needs to round-trip through PNSSO(5:8).

## Proposal R-3: trprep.f90:204

```fortran
! current
DO NS=1, NSM
   IF(MDLEQN.EQ.1.OR.MDLEQT.EQ.1) THEN
      ...
      CALL TR_TABLE(NS, NEQ, 1, IND, INDH, INDHD)
   ENDIF
   ...
ENDDO

! proposed
DO NS=1, NSMAX
   ...
ENDDO
```

**Risk:** This determines how many equation slots are reserved per species. Changing it to `NSMAX` correctly registers only `NSMAX` species' equations and may shrink `NEQMAX` for input decks where someone deliberately set `MDLEQN=1` to spawn ghost species at slots 3,4. Needs deck-by-deck regression.

## Proposal R-4: trrslt_globals.f90:115, 180, 198, 204, 214, 221, 297

```fortran
DO NS=1, NSM   ! → DO NS=1, NSMAX
   ...
ENDDO
```

**Risk:** The summary arrays `ANSAV(NS), TSAV(NS), ANLAV(NS), PEXT(NS), PRFVT(NS,*), PBCLT(NS), PFCLT(NS)` would only be populated for `NS=1..NSMAX`. Downstream graphics code (trrslt_print.f90) hard-codes `PEXT(1)/PEXT(2)` etc. — those are within `NSMAX` for any sensible deck, so probably safe. Defense-in-depth: keep the Tier-1 zero-init regardless.
