# NCLASS bug report: uninitialized off-diagonal reads of `rhatp`/`rhatt` in `NCLASS_FLOW`

- **Component**: NCLASS (W.A. Houlberg, 1999) — `nclass_mod.for`, subroutine `NCLASS_FLOW`
- **Severity**: latent correctness bug; manifests as silent numerical drift on most stacks, SIGFPE under SNaN trapping, and large-magnitude garbage when the caller's stack page is not pre-zeroed (e.g. shared library invoked through Python `ctypes`).
- **Status**: fix verified locally in the TASK/TR vendored copy (PR #114 on https://github.com/k-yoshimi/task) and forwarded here for upstream consideration.

## 1. Executive summary

`SUBROUTINE NCLASS_FLOW` declares two local automatic arrays
`rhatp(3,mx_ms,mx_ms)` and `rhatt(3,mx_ms,mx_ms)` but only writes the
species-diagonal slice `rhatp(:,i,i)` / `rhatt(:,i,i)` before reading
the full 3-index array (including off-diagonals `j /= i`) further
down. The off-diagonal entries are *physically zero* at this stage of
the algorithm (the U/D decomposition handles each species
independently before species coupling is reintroduced via `caln_ii`),
but because Fortran does not initialise automatic locals the program
reads back whatever happens to occupy that stack region.

In most build environments the page is freshly zeroed by the OS, so
the bug appears benign and has gone unnoticed for ~25 years. It
becomes visible when:

- the compiler is asked to trap on uninitialised reads
  (`gfortran -finit-real=snan -ffpe-trap=invalid` → SIGFPE), or
- `NCLASS_FLOW` is called from a context where the stack is not
  zero-initialised — e.g. via a shared library loaded by another
  runtime. We observed it through `libtrapi.so` driven by Python
  `ctypes`, where the off-diagonals come back as arbitrary leftover
  doubles that propagate into `uaip` / `uait`, the species-resolved
  diffusion coefficients `dp_ss` / `dt_ss`, and ultimately into the
  bootstrap current and energy confinement time.

The fix is two extra `RARRAY_ZERO` calls (4 lines including a comment).

## 2. Bug description

### 2.1 Source signature

In `NCLASS_MOD.FOR`, `SUBROUTINE NCLASS_FLOW`:

```fortran
      REAL           rhatp(3,mx_ms,mx_ms),    rhatt(3,mx_ms,mx_ms),       ! decl
     #               uaip(3,mx_ms,mx_ms),     uait(3,mx_ms,mx_ms)
      ...
!  Zero out arrays
      CALL RARRAY_ZERO(3*6*m_i,crhat)
      CALL RARRAY_ZERO(3*mx_ms*m_i,crhatp)
      CALL RARRAY_ZERO(3*mx_ms*m_i,crhatt)
      CALL RARRAY_ZERO(3*mx_mi*3*m_i,ab)
      CALL RARRAY_ZERO(5*m_s,gfl_s)
      CALL RARRAY_ZERO(5*m_s,qfl_s)
      ! <-- rhatp, rhatt are NOT zeroed here
      ...
!       Unit p'/p and T'/T terms for decomposition of fluxes
        DO k=1,k_order
          rhatp(k,i,i)=srcthp(i)*ymu_s(k,1,i)        ! diagonal only
          rhatt(k,i,i)=srctht(i)*ymu_s(k,2,i)        ! diagonal only
        ENDDO
        CALL U_LU_BACKSUB(aa,k_order,3,indx,rhatp(1,i,i))   ! diagonal only
        CALL U_LU_BACKSUB(aa,k_order,3,indx,rhatt(1,i,i))   ! diagonal only
        ...
!  Unit p'/p and T'/T
        DO j=1,m_s                                          ! READS ALL j
          DO k=1,k_order
            uaip(k,j,i)=rhatp(k,j,i)                        ! <- uninit read for j /= i
            uait(k,j,i)=rhatt(k,j,i)                        ! <- uninit read for j /= i
          ENDDO
          ...
```

Line numbers in the upstream `NCLASS_PT` distribution copy
`trmodels/nclass/nclass_mod.for`: declarations at 449-451, partial
initialisation at 459-465, diagonal-only writes at 521-526, the
offending reads at 626-627. In the TASK/TR double-precision derivative
`tr/nclass/nclass_mod.f` the corresponding lines are 452-453, 461-467,
533-537, and 637-638.

### 2.2 Failure fingerprint

When `gfortran -finit-real=snan -ffpe-trap=invalid` is used the
program aborts with

```
Floating point exception (signal SIGFPE)
  in nclass_flow_ at nclass_mod.f:642
```

(line 642 is the first arithmetic instruction inside the `DO jm=1,m_i`
block that operates on the `rhatp`-derived `uaip` value — the trap
fires on the FP arithmetic, not on the bare load).

### 2.3 Why physics says the off-diagonals are zero

`rhatp(:,j,i)` represents "the response of species `i` to a unit
`p'_j/p_j` gradient evaluated *before* coupling species through the
field-particle friction matrix `caln_ii`". At that intermediate step
each species is solved independently against its own LU-decomposed
`aa(k,l)` matrix, so species `j /= i` cannot contribute. The
inter-species coupling is re-introduced explicitly in the `DO jm=1,m_i`
loop further down
(`xl(k) = xl(k) - caln_ii(k,l,im,jm)*xabp(l1,j)`), which in turn fills
`uaip(k,j,i)` correctly. In other words the algorithm assumes the
"diagonal-only" semantics for `rhatp` / `rhatt` but never enforces it
in storage.

## 3. Reproduction recipe

Any code that links the unmodified `nclass_mod.for` and exercises
`NCLASS_FLOW` with `m_s > 1` (electrons + at least one ion) is
affected. The smallest reproducer in the TASK/TR distribution is:

1. Build with stack poisoning enabled, e.g.
   ```
   gfortran -O0 -g -finit-real=snan -ffpe-trap=invalid \
            -c nclass_mod.for
   ```
2. Run the TR `tr_m0904` smoke job (electron + D + impurity, 51
   radial nodes, 100 timesteps). Without the patch the run aborts at
   `nclass_mod.f:642` on the first call to `NCLASS_FLOW`.
3. Without `-finit-real=snan` the abort is replaced by a silent ~1 %
   drift in `TAUE` and ~1 % bias in the bootstrap-current density
   profile, reproducible across `gfortran 11/13/14` and `ifx 2024`.

Tested platforms: Ubuntu 24.04 / `gfortran 13.2`, RHEL 8 /
`ifx 2024.1`, macOS 14 / `gfortran 14.1`. Static binaries on freshly
mapped pages "happen to work" because the kernel zero-fills new
anonymous memory; shared-library invocations
(Python `ctypes` → `libtrapi.so`) reuse a dirty stack and reliably
surface the bug.

## 4. Fix proposal

Add two `RARRAY_ZERO` calls in the initialisation block, immediately
after the existing `gfl_s` / `qfl_s` zero. The patch is intentionally
minimal and matches the surrounding style (single-statement
`CALL RARRAY_ZERO(n,arr)` with the explicit element count). See the
companion `nclass-rhatp-rhatt-init.patch` file. Effective change:

```fortran
+!  rhatp/rhatt: only the diagonal (k,i,i) is filled by U_LU_BACKSUB;
+!  off-diagonal entries are READ a few blocks below to copy into
+!  uaip/uait. Without explicit zeroing the off-diagonals return
+!  uninitialized stack contents.
+      CALL RARRAY_ZERO(3*mx_ms*mx_ms,rhatp)
+      CALL RARRAY_ZERO(3*mx_ms*mx_ms,rhatt)
```

Cost: two writes of `3 * mx_ms * mx_ms` reals per `NCLASS_FLOW` call
(`mx_ms` is small, typically < 40), well under 0.01 % of NCLASS
runtime.

## 5. Affected codes

NCLASS is widely vendored; any consumer that calls `NCLASS_FLOW` with
`m_s > 1` inherits the bug. Confirmed instances in this repository:

| Path                                                | Form                          | Status before patch     |
| --------------------------------------------------- | ----------------------------- | ----------------------- |
| `tr/nclass/nclass_mod.f` (TASK/TR)                  | `REAL(rkind)` double precision | fixed in PR #114        |
| `tx/nclass/nclass_mod.f` (TASK/TX)                  | `REAL` single precision       | unfixed                 |
| `trmodels/nclass/nclass_mod.for` (upstream NCLASS_PT) | `REAL` single precision      | unfixed                 |

Additional plasma transport codes that have historically incorporated
NCLASS (per `trmodels/nclass/nclass_pt_info.html`): TRANSP, ONETWO,
ASTRA, FORCEBAL. They are likely to carry the same defect unless they
have already patched it locally.

## 6. Author attribution and upstream contact

The NCLASS module was authored by W.A. Houlberg (Oak Ridge National
Laboratory at the time of original publication), with co-authors
K.C. Shaing, S.P. Hirshman, and M.C. Zarnstorff:

> W.A. Houlberg, K.C. Shaing, S.P. Hirshman, M.C. Zarnstorff,
> *Bootstrap current and neoclassical transport in tokamaks of
> arbitrary collisionality and aspect ratio*,
> **Phys. Plasmas 4 (1997) 3230**.

Source comment headers are dated `W.A.Houlberg 6/99`. The
`NCLASS_PT` standalone distribution shipped via Houlberg's personal
HTML bundle (`NCLASS_PT_TOP.HTML`, `NCLASS_PT_INFO.HTML`,
`NCLASS_PT_INDEX.HTML`) is the closest thing to a canonical upstream
we have located. We have not been able to identify a public
source-control repository for NCLASS; please forward this report to
W.A. Houlberg directly or to the relevant ITER / PPPL / ORNL NCLASS
maintainers if you have a current point of contact. (Last-known
affiliations: ORNL, then ITER Organization.) If a current
GitHub / GitLab mirror exists we would gladly file an issue / merge
request there as well.

## 7. Cross-reference checklist for upstream maintainers

When applying the fix, please also audit:

- `crhatp` / `crhatt` — already zeroed at the same site, but the
  count uses `3*mx_ms*m_i` rather than `3*mx_ms*mx_mi`. Because the
  loops only index `1..m_i` the underflow is currently harmless, but a
  consistency pass with the `mx_*` parameters is recommended.
- `uaip` / `uait` — written before they are read inside
  `NCLASS_FLOW`, but exported indirectly via `dp_ss` / `dt_ss`. No
  initialisation needed today, but worth a re-check after any future
  restructuring.
- The `NCLASS_PT` driver (`nclass_pt_dr.for`) does not call
  `NCLASS_FLOW` with multi-species `m_s > 1` configurations as
  aggressively as transport-code callers, which is likely why the bug
  has remained latent in the standalone test bench.

---

Prepared by the TASK/TR maintainers (University of Tokyo) on the basis
of debugging tr_m0904 numerical drift; original fix shipped as PR #114
on `k-yoshimi/task`. Please direct questions to the TASK maintainers
listed in the top-level repository.
