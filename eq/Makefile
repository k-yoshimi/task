### $Id$ ###
include ../make.header
include ../mtxp/make.mtxp
#LIB_MTX=$(LIB_MTX_BND)
#LIBX_MTX=$(LIBX_MTX_BND)
#LIB_MTX=$(LIB_MTX_PCG)
#LIBX_MTX=$(LIBX_MTX_PCG)
#LIB_MTX=$(LIB_MTX_MUMPS)
#LIBX_MTX=$(LIBX_MTX_MUMPS)
#LIB_MTX=$(LIBXMTX_KSP)
#LIBX_MTX=$(LIBX_MTX_KSP)

FFLAGS=-g $(OFLAGS)
#FFLAGS=$(DFLAGS)

MODINCLUDE=-I$(MOD) -I../../bpsd/$(MOD) -I../mtxp/$(MOD) -I../pl/$(MOD) -I../lib/$(MOD)

# Phase L-1 + F-1 + F-5: SRCS split into CORE / GRAPHICS / MENU groups.
# SRCS_CORE leads with the Phase F-1 F90 MODULEs (eqcom{0,1,2,3}_mod.f90)
# that mirror the eqcom{0..3}.inc COMMON bundles; they must compile first
# so their .mod files are available to every file that USEs them.
#
# Phase F-5 retired the eqcom{c,m,q,x}.inc shim headers; every consumer
# now USEs the F-1 MODULEs directly. The raw eqcom{0..5}.inc files are
# still present for the few sites (eqcalx, eqgoutx) that pull eqcom5.inc
# (matrix-solver COMMONs not yet F90-modernized).
#
# libeq_pic.a / libeqapi.so link SRCS_CORE only (no graphics / no menu).
# The eq / pl / ak binaries still build from the full union.

# --- core: F-1 MODULEs + equilibrium physics + file I/O + regression hook ---
# Phase F-2: newton / invematrix / eqgetp / eqgsub converted to free-form .f90.
# Phase F-3 (MED tier): eqinit / equnit / equintf / eqrppl / eqcalv /
#   eqfunc / eqintf / eqmenu / eqgout converted to free-form .f90.
SRCS_CORE = eqcom0_mod.f90 eqcom1_mod.f90 eqcom2_mod.f90 eqcom3_mod.f90 \
            equcom.f90 equread.f90 eqlib.f90 \
            eqbpsd.f90 eqinit.f90 eqcalc.f90 eqcalq.f90 eqcalv.f90 \
            eqsub.f90 eqfunc.f90 eqintf.f90 eqsplf.f90 equintf.f90 \
            eq-eqdsk.f90 eq-qst.f90 eqgetp.f90 eqregress.f \
            newton.f90 invematrix.f90 equnit.f90 eqrppl.f90 \
            eqfile.f90

# --- graphics (GSAF plotting, contour) ---
# Note: eqg2d.f / eqg3d.f remain in SRC2D / SRC3D below.
# eqfile.f90 used to live here because draw_cross calls MOVE2D / DRAW2D,
# but EQLOAD / EQSAVE / EQ_READ are needed by libeqapi.so (eq_api_run
# routes MODE=1 through equnit::eq_load -> eqload). draw_cross's two
# graphics calls are stubbed in eq_graphics_stubs.f90 as no-ops.
# Phase F-2: eqgsub converted to free-form .f90.
SRCS_GRAPHICS = eqgout.f90 eqgsub.f90

# --- interactive menu driver (depends on graphics) ---
SRCS_MENU = eqmenu.f90

# --- final SRCS for the existing eq / pl / ak binaries (unchanged behaviour) ---
SRCS = $(SRCS_CORE) $(SRCS_GRAPHICS) $(SRCS_MENU)

# Legacy alias for the module group (kept for any ad-hoc references).
SRCX = equcom.f90 equread.f90 eqlib.f90

# Phase L-2: C ABI sources. Compiled via the eq_api_compile_check /
# eq_api_check targets only; NOT part of $(SRCS) and NOT linked into
# libeq.a or the eq / pl / ak binaries so their behavior is unchanged.
# The full libeqapi.so build arrives in Phase L-4.
SRCS_API = eq_state.f90 eq_param_registry.f90 eq_api.f90
OBJ_API  = $(SRCS_API:.f90=.o) eq_api_common.o

SRCT = trtest.f treqin.f
SRCP = pltest.f
SRCA = aktest.f akeqin.f
SRC2D= eqg2d.f
SRC3D= eqg3d.f

OBJS = $(patsubst %.f,%.o,$(patsubst %.f90,%.o,$(SRCS)))
OBJT = $(SRCT:.f=.o)
OBJP = $(SRCP:.f=.o)
OBJA = $(SRCA:.f=.o)
OBJ2D=$(SRC2D:.f=.o)
OBJ3D=$(SRC3D:.f=.o)

LIBS2 = libeq.a ../pl/libpl.a ../lib/libgrf.a ../lib/libtask.a ../../bpsd/libbpsd.a
LIBS3 = ../pl/libpl.a libeq3.a ../lib/libgrf.a ../lib/libtask.a ../../bpsd/libbpsd.a

.SUFFIXES: .f90

.f.o :
	$(FCFIXED) $(FFLAGS) -c $< -o $@ $(MODDIR) $(MODINCLUDE)
.f90.o :
	$(FCFREE) $(FFLAGS) -c $< -o $@ $(MODDIR) $(MODINCLUDE)

all : libs eq


../../bpsd/libbpsd.a:
	(cd ../../bpsd; make libbpsd.a)
../lib/libtask.a:
	(cd ../lib; make libtask.a)
../lib/libgrf.a:
	(cd ../lib; make libgr.a)
../pl/libpl.a:
	(cd ../mtxp; make)
	(cd ../pl; make libpl.a)

libeq.a: $(OBJS) $(OBJ2D)
	$(LD) $(LDFLAGS) libeq.a $(OBJS) $(OBJ2D) ../pl/libpl.a
libeq3.a: $(OBJS) $(OBJ3D)
	$(LD) $(LDFLAGS) libeq3.a $(OBJS) $(OBJ3D)

libs:
	(cd ../../bpsd; make libbpsd.a)
	(cd ../lib; make libtask.a)
	(cd ../lib; make libgrf.a)
	(cd ../mtxp; make)
	(cd ../pl; make libpl.a)

# Issue #197: link eq_static_stubs.o into the standalone `eq` binary
# when GFLIBS is empty (CI / no-graphics build), so the GSAF symbol
# references in the archive chain (libgrf.a / libtask.a / etc.) resolve.
# Mirrors tot/Makefile:64-70's TOT_STATIC_STUBS_OBJ gate.
ifeq ($(strip $(GFLIBS)),)
EQ_STATIC_STUBS_OBJ = eq_static_stubs.o
else
EQ_STATIC_STUBS_OBJ =
endif

eq: libs libeq.a eqmain.o $(EQ_STATIC_STUBS_OBJ)
	$(FLINKER) eqmain.o $(EQ_STATIC_STUBS_OBJ) $(LIBS2) -o $@ $(FFLAGS) $(FLIBS) $(LIBX_MTX)

eq3: libs libeq3.a eqmain.o
	$(FLINKER) eqmain.o $(LIBS3) -o $@ $(FFLAGS) $(FLIBS) $(LIBX_MTX)

tr : libs libeq.a $(OBJT)
	$(FLINKER) $(OBJT) $(LIBS2) -o $@ $(FFLAGS) $(FLIBS) $(LIBX_MTX)

pl : libs libeq.a $(OGJP)
	$(FLINKER) $(OBJP) $(LIBS2) -o $@ $(FFLAGS) $(FLIBS) $(LIBX_MTX)

ak : libs libeq.a $(OBJA)
	$(FLINKER) $(OBJA) $(LIBS2) -o $@ $(FFLAGS) $(FLIBS) $(LIBX_MTX)

clean:
	-rm -f core a.out *.o *.mod ./*~ *.a $(MOD)/*.mod
	-rm -f doc/*~
	-rm -f $(EQ_API_NEG_O) $(EQ_API_NEG_BIN)

veryclean: clean
	rm -f eq pl ak

# ---------------------------------------------------------------------
# PIC build (Phase L-4) - opt-in target for libtrapi.so / libeqapi.so.
#
# `libeq_pic.a` mirrors libeq.a but uses -fPIC and a separate
# obj/pic + mod_pic tree so the existing libeq.a/eq build is untouched.
# Per Bugbot review, this uses `$(AR) rcs` instead of `$(LD)` (which is
# `ld -r -o` and would emit a non-archive object file).
# ---------------------------------------------------------------------
OBJDIR_PIC=obj/pic
MODDIR_PIC=mod_pic
PIC_FLAGS=-fPIC -J$(MODDIR_PIC) -I$(MODDIR_PIC)
MODINCLUDE_PIC=-I$(MODDIR_PIC) -I../../bpsd/$(MOD) -I../mtxp/mod_pic -I../pl/mod_pic -I../lib/mod_pic

# libtrapi.so / libeqapi.so exclude all graphics and the interactive menu,
# so libeq_pic.a is built from $(SRCS_CORE) only. After the L-1 split,
# SRCS_CORE already excludes SRCS_GRAPHICS (eqgout/eqgsub/eqfile) and
# SRCS_MENU (eqmenu). With F-1, SRCS_CORE leads with the F90 MODULEs so
# their .mod files are emitted before any consumer is compiled.
#
# Symbols still referenced from CORE that resolve into GRAPHICS
# (e.g. equread::eqdsk via eq-eqdsk/eq-qst) remain undefined in the
# resulting .so and must be linked with
# -Wl,--unresolved-symbols=ignore-in-shared-libs, failing loudly if a
# graphics path is ever reached at run-time.
SRCS_EQ_NOGR = $(SRCS_CORE)
OBJS_PIC = $(addprefix $(OBJDIR_PIC)/, $(patsubst %.f90,%.o,$(patsubst %.f,%.o,$(SRCS_EQ_NOGR))))

$(OBJDIR_PIC)/%.o: %.f
	@mkdir -p $(OBJDIR_PIC) $(MODDIR_PIC)
	$(FCFIXED) $(FFLAGS) $(PIC_FLAGS) -c $< -o $@ $(MODINCLUDE_PIC)
$(OBJDIR_PIC)/%.o: %.f90
	@mkdir -p $(OBJDIR_PIC) $(MODDIR_PIC)
	$(FCFREE) $(FFLAGS) $(PIC_FLAGS) -c $< -o $@ $(MODINCLUDE_PIC)

libeq_pic.a: $(OBJS_PIC)
	$(AR) rcs libeq_pic.a $(OBJS_PIC)

clean_pic:
	-rm -rf $(OBJDIR_PIC) $(MODDIR_PIC) libeq_pic.a libeqapi.so
	-rm -f $(EQ_API_SO_O) $(EQ_API_SO_BIN)
	-rm -f $(EQ_API_NEG_O) $(EQ_API_NEG_BIN)

# Phase F-5: shim .inc headers (eqcom{c,m,q,x}.inc) deleted. Every
# consumer now USEs the F-1 MODULEs (eqcom0/1/2/3_mod) directly. The
# raw eqcom{0..5}.inc files are kept (they are still INCLUDEd by
# eqcalx.f / eqgoutx.f for eqcom5 matrix-solver COMMONs and by
# eqfunc.f90 / treqin.f for eqcom4 inline).

# Phase F-1: dependencies for the F90 COMMON-replacement MODULEs.
# - eqcom0_mod is the root (PARAMETER-only).
# - eqcom1/2/3_mod USE eqcom0_mod, so their .mod must be available.
# - Every .f / .f90 that USEs an eqcomN_mod transitively requires the
#   corresponding .mod file. We list them here so that a parallel
#   `make -jN` cannot race past module compilation.
EQCOM_MODS = eqcom0_mod.o eqcom1_mod.o eqcom2_mod.o eqcom3_mod.o

eqcom0_mod.o: eqcom0_mod.f90
eqcom1_mod.o: eqcom1_mod.f90 eqcom0_mod.o
eqcom2_mod.o: eqcom2_mod.f90 eqcom0_mod.o
eqcom3_mod.o: eqcom3_mod.f90 eqcom0_mod.o

# Phase F-5: dep lines now reference $(EQCOM_MODS) only (the raw .inc
# files are no longer transitively included via shim headers). Files
# that still INCLUDE a raw eqcom{4,5}.inc directly keep that prereq.
eqmain.o: eqmain.f $(EQCOM_MODS)
eqinit.o: eqinit.f90 $(EQCOM_MODS)
eqcalc.o: eqcalc.f90 $(EQCOM_MODS)
eqcalx.o: eqcalx.f eqcom5.inc $(EQCOM_MODS)
eqcalq.o: eqcalq.f90 $(EQCOM_MODS)
eqcalv.o: eqcalv.f90 $(EQCOM_MODS)
eqsub.o : eqsub.f90  $(EQCOM_MODS)
eqfunc.o: eqfunc.f90 eqcom4.inc $(EQCOM_MODS)
eqsplf.o: eqsplf.f90 $(EQCOM_MODS)
eqfile.o: eqfile.f90 $(EQCOM_MODS)
eq-eqdsk.o: eq-eqdsk.f90 $(EQCOM_MODS)
eq-qst.o: eq-qst.f90 $(EQCOM_MODS)
eqintf.o: eqintf.f90 $(EQCOM_MODS)
eqgout.o: eqgout.f90 $(EQCOM_MODS)
eqbpsd.o: eqbpsd.f90 $(EQCOM_MODS)
#eqtrbpsd.o: eqtrbpsd.f $(EQCOM_MODS)
#eqtrbpsdlib.o: eqtrbpsdlib.f90
eqjft2m.o: eqjft2m.f $(EQCOM_MODS)
eqlib.o : eqlib.f90
equnit.o: equnit.f90 eqbpsd.f90 $(EQCOM_MODS)
eqgsub.o: eqgsub.f90
eqg2d.o: eqg2d.f $(EQCOM_MODS)
eqg3d.o: eqg3d.f $(EQCOM_MODS)
equcom.o: equcom.f90
equread.o: equread.f90 equcom.f90
equintf.o: equintf.f90 $(EQCOM_MODS)
eqrppl.o: eqrppl.f90 $(EQCOM_MODS)
eqgetp.o: eqgetp.f90 $(EQCOM_MODS)
eqregress.o: eqregress.f $(EQCOM_MODS)
trtest.o: trtest.f $(EQCOM_MODS)
treqin.o: treqin.f eqcom4.inc $(EQCOM_MODS)
pltest.o: pltest.f
aktest.o: aktest.f
akeqin.o: akeqin.f $(EQCOM_MODS)
newton.o: newton.f90
invematrix.o: invematrix.f90

# ---------------------------------------------------------------------
# Phase F-1 Task F-1-3: eq_commontest bootstrap program.
# Standalone test that USEs all four new MODULEs and prints the grid
# dimensions, so regressions on PARAMETER values fail loudly. Not linked
# into libeq.a / eq. Build with `make eq_commontest`.
# ---------------------------------------------------------------------
EQCOMMONTEST_OBJS = eqcom0_mod.o eqcom1_mod.o eqcom2_mod.o eqcom3_mod.o \
                   tests/eq_commontest.o

tests/eq_commontest.o: tests/eq_commontest.f90 $(EQCOM_MODS)
	$(FCFREE) $(FFLAGS) -c $< -o $@ $(MODDIR) $(MODINCLUDE)

eq_commontest: $(EQCOMMONTEST_OBJS)
	$(FLINKER) $(EQCOMMONTEST_OBJS) -o $@ $(FFLAGS)

run_commontest: eq_commontest
	./eq_commontest

clean_commontest:
	-rm -f tests/eq_commontest.o eq_commontest

# ---------------------------------------------------------------------
# Phase L-2 C ABI scaffold
#
# `make eq_api_compile_check` compiles the new API objects
# (eq_state.o / eq_param_registry.o / eq_api.o / eq_api_common.o)
# without linking. It does NOT touch libeq.a, the eq / pl / ak
# binaries, or any existing objects, so the L-0/L-1 behavior is
# bit-identical.
#
# `make eq_api_check` additionally builds a minimal C driver
# (tests/c_abi/test_smoke.c) that links libeq.a + OBJ_API and
# calls eq_init -> eq_get_state -> eq_finalize.
# ---------------------------------------------------------------------
CC ?= gcc
CFLAGS_API ?= -Wall -Wextra -O2

EQ_API_SMOKE_DIR = tests/c_abi
EQ_API_SMOKE_C   = $(EQ_API_SMOKE_DIR)/test_smoke.c
EQ_API_SMOKE_O   = $(EQ_API_SMOKE_DIR)/test_smoke.o
EQ_API_SMOKE_BIN = $(EQ_API_SMOKE_DIR)/test_smoke

eq_state.o          : eq_state.f90
eq_param_registry.o : eq_param_registry.f90
eq_api.o            : eq_api.f90 eq_state.f90 eq_param_registry.f90 equnit.f90
eq_api_common.o     : eq_api_common.f $(EQCOM_MODS)

.PHONY: eq_api_compile_check
eq_api_compile_check: libs libeq.a $(OBJ_API)
	@echo "Phase L-2 eq_api_compile_check OK: $(OBJ_API)"

$(EQ_API_SMOKE_O): $(EQ_API_SMOKE_C) eq_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(EQ_API_SMOKE_O) $(EQ_API_SMOKE_C)

$(EQ_API_SMOKE_BIN): $(EQ_API_SMOKE_O) $(OBJ_API) libeq.a
	$(FLINKER) -o $(EQ_API_SMOKE_BIN) $(EQ_API_SMOKE_O) $(OBJ_API) \
	    $(LIBS2) $(FFLAGS) $(FLIBS) $(LIBX_MTX)

.PHONY: eq_api_check
eq_api_check: libs libeq.a $(EQ_API_SMOKE_BIN)
	@echo "Phase L-2 eq_api_check: running $(EQ_API_SMOKE_BIN) ..."
	@LD_LIBRARY_PATH=.:$${LD_LIBRARY_PATH} $(EQ_API_SMOKE_BIN)
	@echo "Phase L-2 eq_api_check OK"

# =====================================================================
# Phase L-4: libeqapi.so shared library build
#
# Builds a position-independent shared object that exposes the 6 C ABI
# entry points (eq_init, eq_run, eq_set_param, eq_set_param_str,
# eq_get_state, eq_finalize) by linking SRCS_CORE + SRCS_API (plus
# eq_graphics_stubs) against PIC rebuilds of bpsd / pl / lib / mtxp.
#
# The PIC build reuses obj/pic/ + mod_pic/ defined above for libeq_pic.a.
# Dependent libraries are PIC-rebuilt via opt-in targets added in
# pl/lib/mtxp Makefiles (libpl_pic.a, libtask_pic.a, libmds_pic.a,
# libgrf_pic.a, libmtxnompi_pic.o, libmtxbnd_pic.o) by TR/TI/WR Phase L-4.
#
# The bpsd sources live in the parent ../../bpsd/ repo which is outside
# our worktree; we PIC-rebuild bpsd objects in-tree (obj/pic/bpsd/) so
# we don't need to modify bpsd/Makefile.  This mirrors tr/Makefile.
# =====================================================================

# --- bpsd in-tree PIC rebuild (mirrors tr/Makefile L-4) ---
BPSD_SRC=../../bpsd
OBJBPSD_PIC=$(OBJDIR_PIC)/bpsd/bpsd_kinds.o \
            $(OBJDIR_PIC)/bpsd/bpsd_constants.o \
            $(OBJDIR_PIC)/bpsd/bpsd_flags.o \
            $(OBJDIR_PIC)/bpsd/bpsd_libchar.o \
            $(OBJDIR_PIC)/bpsd/bpsd_libfio.o \
            $(OBJDIR_PIC)/bpsd/bpsd_libspl.o \
            $(OBJDIR_PIC)/bpsd/bpsd_types.o \
            $(OBJDIR_PIC)/bpsd/bpsd_types_internal.o \
            $(OBJDIR_PIC)/bpsd/bpsd_subs.o \
            $(OBJDIR_PIC)/bpsd/bpsd_shot.o \
            $(OBJDIR_PIC)/bpsd/bpsd_device.o \
            $(OBJDIR_PIC)/bpsd/bpsd_species.o \
            $(OBJDIR_PIC)/bpsd/bpsd_equ1D.o \
            $(OBJDIR_PIC)/bpsd/bpsd_metric1D.o \
            $(OBJDIR_PIC)/bpsd/bpsd_plasmaf.o \
            $(OBJDIR_PIC)/bpsd/bpsd_trmatrix.o \
            $(OBJDIR_PIC)/bpsd/bpsd_trsource.o \
            $(OBJDIR_PIC)/bpsd/bpsd_base.o

$(OBJDIR_PIC)/bpsd/%.o: $(BPSD_SRC)/%.f90
	@mkdir -p $(@D) $(MODDIR_PIC)
	$(FCFREE) $(FFLAGS) $(PIC_FLAGS) -c $< -o $@ $(MODINCLUDE_PIC)

# bpsd dependency order (copied verbatim from tr/Makefile L-4)
$(OBJDIR_PIC)/bpsd/bpsd_constants.o:       $(OBJDIR_PIC)/bpsd/bpsd_kinds.o
$(OBJDIR_PIC)/bpsd/bpsd_flags.o:            $(OBJDIR_PIC)/bpsd/bpsd_kinds.o
$(OBJDIR_PIC)/bpsd/bpsd_libchar.o:          $(OBJDIR_PIC)/bpsd/bpsd_kinds.o
$(OBJDIR_PIC)/bpsd/bpsd_libfio.o:           $(OBJDIR_PIC)/bpsd/bpsd_kinds.o
$(OBJDIR_PIC)/bpsd/bpsd_libspl.o:           $(OBJDIR_PIC)/bpsd/bpsd_kinds.o
$(OBJDIR_PIC)/bpsd/bpsd_types.o:            $(OBJDIR_PIC)/bpsd/bpsd_kinds.o $(OBJDIR_PIC)/bpsd/bpsd_constants.o
$(OBJDIR_PIC)/bpsd/bpsd_types_internal.o:   $(OBJDIR_PIC)/bpsd/bpsd_types.o
$(OBJDIR_PIC)/bpsd/bpsd_subs.o:             $(OBJDIR_PIC)/bpsd/bpsd_types_internal.o $(OBJDIR_PIC)/bpsd/bpsd_libchar.o $(OBJDIR_PIC)/bpsd/bpsd_libfio.o $(OBJDIR_PIC)/bpsd/bpsd_libspl.o $(OBJDIR_PIC)/bpsd/bpsd_flags.o
$(OBJDIR_PIC)/bpsd/bpsd_shot.o:             $(OBJDIR_PIC)/bpsd/bpsd_subs.o
$(OBJDIR_PIC)/bpsd/bpsd_device.o:           $(OBJDIR_PIC)/bpsd/bpsd_subs.o
$(OBJDIR_PIC)/bpsd/bpsd_species.o:          $(OBJDIR_PIC)/bpsd/bpsd_subs.o
$(OBJDIR_PIC)/bpsd/bpsd_equ1D.o:            $(OBJDIR_PIC)/bpsd/bpsd_subs.o
$(OBJDIR_PIC)/bpsd/bpsd_metric1D.o:         $(OBJDIR_PIC)/bpsd/bpsd_subs.o
$(OBJDIR_PIC)/bpsd/bpsd_plasmaf.o:          $(OBJDIR_PIC)/bpsd/bpsd_subs.o
$(OBJDIR_PIC)/bpsd/bpsd_trmatrix.o:         $(OBJDIR_PIC)/bpsd/bpsd_subs.o
$(OBJDIR_PIC)/bpsd/bpsd_trsource.o:         $(OBJDIR_PIC)/bpsd/bpsd_subs.o
$(OBJDIR_PIC)/bpsd/bpsd_base.o:             $(OBJDIR_PIC)/bpsd/bpsd_shot.o $(OBJDIR_PIC)/bpsd/bpsd_device.o $(OBJDIR_PIC)/bpsd/bpsd_species.o $(OBJDIR_PIC)/bpsd/bpsd_equ1D.o $(OBJDIR_PIC)/bpsd/bpsd_metric1D.o $(OBJDIR_PIC)/bpsd/bpsd_plasmaf.o $(OBJDIR_PIC)/bpsd/bpsd_trmatrix.o $(OBJDIR_PIC)/bpsd/bpsd_trsource.o

.PHONY: bpsd_pic
bpsd_pic: $(OBJBPSD_PIC)

# --- Object sets for libeqapi.so ---
# SRCS_API is the C ABI trio; OBJS_PIC already covers SRCS_CORE.
OBJ_API_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCS_API:.f90=.o)) $(OBJDIR_PIC)/eq_api_common.o

# Graphics stubs that satisfy GUCLIP / PAGES / ... without dragging in
# non-PIC libgsp/libg3d. PIC-only; NOT added to SRCS, so the eq / pl /
# ak binaries never see these symbols and still pick up the real GSAF.
SRCS_GR_STUBS=eq_graphics_stubs.f90
OBJ_GR_STUBS_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCS_GR_STUBS:.f90=.o))

OBJ_LIBEQAPI= $(OBJS_PIC) $(OBJ_API_PIC) $(OBJ_GR_STUBS_PIC)

# Dependent PIC archives / objects. libgrf_pic.a is NOT linked in:
# equread.f90::eqdsk has a single `call grd2d` that is unreachable from
# the C ABI happy path; linking libgrf_pic.a would drag in grdconvert.o
# which in turn calls r2w2b_ / text_ / move_ and chains of non-PIC
# GSAF symbols. Instead we rely on --unresolved-symbols=ignore-all to
# leave `grd2d_` undefined in the .so and RTLD_LAZY at dlopen time to
# defer resolution until the call actually happens (which it never
# does on the eq_init -> eq_run -> eq_get_state -> eq_finalize path).
# libgrf's .mod file (compile-time) is still reached via MODINCLUDE_PIC
# -> ../lib/mod_pic, so equread.f90 compiles fine.
LIBS_PIC=../pl/libpl_pic.a ../lib/libtask_pic.a ../lib/libmds_pic.a
LIBMTX_PIC=../mtxp/libmtxnompi_pic.o ../mtxp/libmtxbnd_pic.o

# Build dependent PIC libs on demand. libgrf_pic.a is still listed as
# a prereq because equread.f90 USEs libgrf at compile time (we need
# its .mod file in ../lib/mod_pic) even though we do not link the
# archive into libeqapi.so (see LIBS_PIC note above).
../pl/libpl_pic.a:
	(cd ../pl; $(MAKE) libpl_pic.a)
../lib/libtask_pic.a:
	(cd ../lib; $(MAKE) libtask_pic.a)
../lib/libmds_pic.a:
	(cd ../lib; $(MAKE) libmds_pic.a)
../lib/libgrf_pic.a:
	(cd ../lib; $(MAKE) libgrf_pic.a)
../mtxp/libmtxnompi_pic.o:
	(cd ../mtxp; $(MAKE) libmtxnompi_pic.o)
../mtxp/libmtxbnd_pic.o:
	(cd ../mtxp; $(MAKE) libmtxbnd_pic.o)

# Force serialization: the intermediate archives list each other as
# prereqs so they build top-down even under `make -jN`.
../lib/libgrf_pic.a: ../lib/libtask_pic.a
../mtxp/libmtxnompi_pic.o: ../lib/libtask_pic.a
../mtxp/libmtxbnd_pic.o: ../mtxp/libmtxnompi_pic.o

# eq's own PIC sources (SRCS_CORE + SRCS_API + stubs) USE plcomm/
# plprof modules via eq_param_registry and equread. Ensure all
# dependent libraries and bpsd in-tree objects build first. libgrf_pic.a
# is here so its .mod is present for equread.f90's `use libgrf`; it is
# NOT linked into libeqapi.so (see LIBS_PIC above).
.PHONY: libs_pic_prereq
libs_pic_prereq: ../lib/libtask_pic.a ../lib/libgrf_pic.a ../lib/libmds_pic.a \
                 ../mtxp/libmtxnompi_pic.o ../mtxp/libmtxbnd_pic.o \
                 $(OBJBPSD_PIC) ../pl/libpl_pic.a

$(OBJBPSD_PIC): | ../lib/libtask_pic.a
$(OBJS_PIC) $(OBJ_API_PIC) $(OBJ_GR_STUBS_PIC): | libs_pic_prereq

# Inter-module dependencies for the PIC build of SRCS_API (mirror the
# non-PIC eq_api.o / eq_param_registry.o deps below). Without these,
# `make -j` can race past eq_state's .mod file emission and fail
# eq_api.f90 / eq_param_registry.f90 compilation with "module not found".
$(OBJDIR_PIC)/eq_param_registry.o: $(OBJDIR_PIC)/eq_state.o
$(OBJDIR_PIC)/eq_api.o:            $(OBJDIR_PIC)/eq_state.o $(OBJDIR_PIC)/eq_param_registry.o

# --- The shared library itself ---
# gfortran drives the link so libgfortran is pulled in automatically.
# --start-group / --end-group resolves the cyclic eq <-> pl references.
# We deliberately drop $(FLIBS) from the link: FLIBS pulls in non-PIC
# graphics archives (libg3d/libgsp/libgdp) via GFLIBS. libeqapi.so
# excludes SRCS_GRAPHICS (eqgout/eqgsub) and SRCS_MENU so none of the
# gsaf calls are reachable; leaving GFLIBS in triggers R_X86_64_PC32
# relocation errors when ld tries to copy non-PIC .text from
# libg3d-gfc64.a into the .so. eqfile.f90 was moved into SRCS_CORE
# (only its draw_cross calls MOVE2D / DRAW2D, both stubbed in
# eq_graphics_stubs.f90) so EQLOAD is now defined in the .so.
# Platform-aware ld flags: Apple ld (macOS) rejects GNU-ld-only flags
# (-soname / --start-group / --end-group / --unresolved-symbols).
# Apple ld resolves cycles automatically; -install_name is the SONAME
# equivalent; `-undefined dynamic_lookup` is the macOS counterpart of
# Linux's --unresolved-symbols=ignore-all (defer to runtime).
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
  SO_SONAME = -Wl,-install_name,@rpath/libeqapi.so
  SO_GROUP_BEGIN =
  SO_GROUP_END =
  SO_UNDEFINED = -Wl,-undefined,dynamic_lookup
else
  SO_SONAME = -Wl,-soname,libeqapi.so
  SO_GROUP_BEGIN = -Wl,--start-group
  SO_GROUP_END = -Wl,--end-group
  SO_UNDEFINED = -Wl,--unresolved-symbols=ignore-all
endif

libeqapi.so: $(OBJ_LIBEQAPI) $(OBJBPSD_PIC) $(LIBS_PIC) $(LIBMTX_PIC)
	$(FCFREE) -shared -fPIC $(SO_SONAME) $(SO_UNDEFINED) \
	    $(OBJ_LIBEQAPI) $(OBJBPSD_PIC) $(LIBMTX_PIC) \
	    $(SO_GROUP_BEGIN) $(LIBS_PIC) $(SO_GROUP_END) \
	    -o libeqapi.so

.PHONY: libeqapi_inspect
libeqapi_inspect: libeqapi.so
	@echo "=== file ==="
	@file libeqapi.so
	@echo "=== ldd ==="
	@ldd libeqapi.so
	@echo "=== exported eq_* symbols ==="
	@nm -D libeqapi.so | grep ' T eq_' || true
	@echo "=== undefined symbols (count) ==="
	@nm -D libeqapi.so | grep ' U ' | wc -l
	@echo "=== non-libc/gfortran undefined ==="
	@nm -D libeqapi.so | grep ' U ' | grep -vE '@(GLIBC|GCC|GFORTRAN)' | head -40

# ---------------------------------------------------------------------
# Phase L-4: eq_api_check_so
#
# Dynamically loads libeqapi.so via dlopen() and runs the full cycle.
# ---------------------------------------------------------------------
EQ_API_SO_C=$(EQ_API_SMOKE_DIR)/test_run_so.c
EQ_API_SO_O=$(EQ_API_SMOKE_DIR)/test_run_so.o
EQ_API_SO_BIN=$(EQ_API_SMOKE_DIR)/test_run_so

$(EQ_API_SO_O): $(EQ_API_SO_C) eq_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(EQ_API_SO_O) $(EQ_API_SO_C)

$(EQ_API_SO_BIN): $(EQ_API_SO_O)
	$(CC) -o $(EQ_API_SO_BIN) $(EQ_API_SO_O) -ldl

.PHONY: eq_api_check_so
eq_api_check_so: libeqapi.so $(EQ_API_SO_BIN)
	@echo "Phase L-4 eq_api_check_so: dlopen libeqapi.so + full cycle ..."
	@EQLIB_PATH=$(CURDIR)/libeqapi.so $(EQ_API_SO_BIN)
	@echo "Phase L-4 eq_api_check_so OK"

# ---------------------------------------------------------------------
# Phase L-6: Layer 2 (C ABI) test suite
#
# Builds + runs the full C ABI test set in one shot so CI (via
# test_run/run_tests.sh) can invoke a single target. Consists of:
#
#   test_smoke    - 4 entry points + L-3 set_param[_str] dispatch
#                   (covers smoke + param-dispatch coverage)
#   test_run_so   - dlopen libeqapi.so + full cycle             (L-4)
#   test_negative - rejection contracts (pre-init, unknown name,
#                   malformed PSIB, double-finalize, post-finalize,
#                   re-init)                                     (L-6, new)
#
# The smoke driver links OBJ_API + libeq.a directly; the dlopen driver
# uses libdl and loads libeqapi.so at runtime. The negative driver
# shares the smoke link path (so it can call eq_init/etc. directly).
# ---------------------------------------------------------------------
EQ_API_NEG_C   = $(EQ_API_SMOKE_DIR)/test_negative.c
EQ_API_NEG_O   = $(EQ_API_SMOKE_DIR)/test_negative.o
EQ_API_NEG_BIN = $(EQ_API_SMOKE_DIR)/test_negative

$(EQ_API_NEG_O): $(EQ_API_NEG_C) eq_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(EQ_API_NEG_O) $(EQ_API_NEG_C)

$(EQ_API_NEG_BIN): $(EQ_API_NEG_O) $(OBJ_API) libeq.a
	$(FLINKER) -o $(EQ_API_NEG_BIN) $(EQ_API_NEG_O) $(OBJ_API) \
	    $(LIBS2) $(FFLAGS) $(FLIBS) $(LIBX_MTX)

.PHONY: eq_api_check_all
eq_api_check_all: eq_api_check eq_api_check_so $(EQ_API_NEG_BIN)
	@echo "Phase L-6 eq_api_check_all: running negative tests ..."
	@LD_LIBRARY_PATH=.:$${LD_LIBRARY_PATH} $(EQ_API_NEG_BIN)
	@echo "Phase L-6 eq_api_check_all OK: smoke/param/run_so/negative"
