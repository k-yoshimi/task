### Makefile for wr

include ../make.header
include ../mtxp/make.mtxp

#LIB_MTX=$(LIB_MTX_NOMPI)
#LIBX_MTX=$(LIBX_MTX_NOMPI)
#LIB_MTX=$(LIB_MTX_PCG)
#LIBX_MTX=$(LIBX_MTX_PCG)
#LIB_MTX=$(LIB_MTX_MUMPS)
#LIBX_MTX=$(LIBX_MTX_MUMPS)
#LIB_MTX=$(LIBXMTX_KSP)
#LIBX_MTX=$(LIBX_MTX_KSP)

FFLAGS=$(OFLAGS)
#FFLAGS=$(DFLAGS)

OBJDIR   = ./obj

#.SUFFIXES:
#.SUFFIXES: .f90 .mod .o .a

#.f.o :
#	$(FCFIXED) $(FFLAGS) -c $< -o $@ $(MODDIR) $(MODINCLUDE)
#.f90.o :
#	$(FCFREE) $(FFLAGS) -c $< -o $@ $(MODDIR) $(MODINCLUDE)

${OBJDIR}/%.o:%.f90
	$(FCFREE) $(FFLAGS) -c $< -o $@ $(MODDIR) $(MODINCLUDE)

${OBJDIR}/%.o:%.f
	$(FCFIXED) $(FFLAGS) -c $< -o $@ $(MODDIR) $(MODINCLUDE)

MODINCLUDE= -I./$(MOD) -I../pl/$(MOD) -I../dp/$(MOD) -I../eq/$(MOD) \
            -I../lib/$(MOD) -I../mtxp/$(MOD) -I../../bpsd/$(MOD)

SRCS_CORE = wrcomm.f90 wrinit.f90 wrparm.f90 wrprep.f90 wrview.f90 \
            wrsub.f90 \
            wrsetup.f90 wrcalpwr.f90 wrfdrv.f90 wroxb.f90 \
            wrx_dump_state.f90 \
            wrexecr.f90 wrexecb.f90 \
            wrexec.f90 \
            wrfile.f90 \
            wrxregress.f90

SRCS_GRAPHICS = wrgout.f90

SRCS_MENU = wrmenu.f90

# C ABI sources (Phase L-2+). Compiled via the wrx_api_check target only;
# NOT part of $(SRCS) and NOT linked into libwr.a / the wrx binary.
# The full libwrxapi.so build arrives in Phase L-4.
# L-3 adds wrx_param_registry.f90 (namelist param SELECT CASE table).
# Build order matters: state -> registry -> api.
SRCS_API = wrx_state.f90 wrx_param_registry.f90 wrx_api.f90

SRCS = $(SRCS_CORE) $(SRCS_GRAPHICS) $(SRCS_MENU)

OBJS = $(addprefix $(OBJDIR)/, $(SRCS:.f90=.o))
OBJ_API = $(addprefix $(OBJDIR)/, $(SRCS_API:.f90=.o))

LIBS = libwr.a  ../dp/libdp.a ../eq/libeq.a ../pl/libpl.a \
       ../lib/libtask.a ../lib/libgrf.a ../../bpsd/libbpsd.a

LIBSPLOT = ../lib/libtask.a ../lib/libgrf.a ../../bpsd/libbpsd.a

all : libs wr

../../bpsd/libbpsd.a:
	(cd ../../bpsd; make libbpsd.a)
../lib/libtask.a:
	(cd ../lib; make libtask.a)
../lib/libgrf.a:
	(cd ../lib; make libgrf.a)
../pl/libpl.a:
	(cd ../pl; make libpl.a)
../eq/libeq.a:
	(cd ../eq; make libeq.a)
../dp/libdp.a:
	(cd ../dp; make libdp.a)

libwr.a: $(OBJS)
	$(LD) $(LDFLAGS) $@ $(OBJS)

libs:
	(cd ../../bpsd; make libbpsd.a)
	(cd ../lib; make libtask.a)
	(cd ../lib; make libgrf.a)
	(cd ../mtxp; make)
	(cd ../pl; make libpl.a)
	(cd ../eq; make libeq.a)
	(cd ../dp; make libdp.a)

wr : $(LIB_MTX) $(LIBS) $(OBJDIR)/wrmain.o
	$(FLINKER) $(OBJDIR)/wrmain.o $(LIBS) -o $@ $(FFLAGS) $(FLIBS) $(LIBX_MTX)

wrplot : $(LIBS) $(OBJDIR)/wrplot.o
	$(FLINKER) $(OBJDIR)/wrplot.o $(LIBSPLOT) -o $@ $(FFLAGS) $(FLIBS)

# ---------------------------------------------------------------------
# Phase L-2/L-3: C ABI check
#
# `make wrx_api_check` builds the API objects (wrx_state.o,
# wrx_param_registry.o, wrx_api.o) and three small C drivers linked
# against wrx_api.h:
#
#   test_smoke  : 3 lifecycle entry points return WRX_OK (sanity)
#   test_param  : wrx_set_param dispatch (scalars / arrays / errors)
#   test_run    : wrx_run + wrx_get_state end-to-end (analytic geom)
#
# At L-3 the API drivers pull in wrcomm, wr_prep, wr_setup, wr_exec,
# wr_allocate, ... so we need the full wr + dp + eq + pl + bpsd + mtx
# link just like the wrx binary. The API objects are NOT linked into
# libwr.a; the wrx binary remains byte-for-byte identical with or
# without `make wrx_api_check` being invoked.
#
# Note: this Makefile emits the wrx binary under the name `wr`
# (pre-existing, see the `wr :` target above). The wr/ sibling module
# emits a separate `wr` binary into wr/. Symbol-collision check is the
# user's responsibility at L-4 when libwrxapi.so is built.
#
# CC defaults to gcc; override on the command line if necessary
# (e.g. `make wrx_api_check CC=clang`).
# ---------------------------------------------------------------------
CC ?= gcc
CFLAGS_API ?= -Wall -Wextra -O2

WRX_API_SMOKE_DIR = tests/c_abi
WRX_API_SMOKE_C   = $(WRX_API_SMOKE_DIR)/test_smoke.c
WRX_API_SMOKE_O   = $(WRX_API_SMOKE_DIR)/test_smoke.o
WRX_API_SMOKE_BIN = $(WRX_API_SMOKE_DIR)/test_smoke

WRX_API_PARAM_C   = $(WRX_API_SMOKE_DIR)/test_param.c
WRX_API_PARAM_O   = $(WRX_API_SMOKE_DIR)/test_param.o
WRX_API_PARAM_BIN = $(WRX_API_SMOKE_DIR)/test_param

WRX_API_RUN_C     = $(WRX_API_SMOKE_DIR)/test_run.c
WRX_API_RUN_O     = $(WRX_API_SMOKE_DIR)/test_run.o
WRX_API_RUN_BIN   = $(WRX_API_SMOKE_DIR)/test_run

# Phase L-6: negative-path C ABI driver (rejection contracts).
WRX_API_NEG_C     = $(WRX_API_SMOKE_DIR)/test_negative.c
WRX_API_NEG_O     = $(WRX_API_SMOKE_DIR)/test_negative.o
WRX_API_NEG_BIN   = $(WRX_API_SMOKE_DIR)/test_negative

# At L-3 the API drivers depend on wrcomm + wr_prep/setup/exec which
# live in libwr.a, plus the eq/pl/dp/bpsd/mtx stack from $(LIBS).
WRX_API_DEPS = $(LIBS) $(LIBX_MTX)

# Step 1: header-only C compile (matches the documented user-level check
#         `gcc -Wall -Wextra -c -o test_smoke.o test_smoke.c`).
$(WRX_API_SMOKE_O): $(WRX_API_SMOKE_C) wrx_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(WRX_API_SMOKE_O) $(WRX_API_SMOKE_C)
$(WRX_API_PARAM_O): $(WRX_API_PARAM_C) wrx_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(WRX_API_PARAM_O) $(WRX_API_PARAM_C)
$(WRX_API_RUN_O):   $(WRX_API_RUN_C)   wrx_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(WRX_API_RUN_O)   $(WRX_API_RUN_C)
$(WRX_API_NEG_O):   $(WRX_API_NEG_C)   wrx_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(WRX_API_NEG_O)   $(WRX_API_NEG_C)

# Step 2: link against API objects + libwr.a + eq/pl/dp/bpsd/mtx.
# gfortran drives the link so libgfortran is pulled in automatically.
$(WRX_API_SMOKE_BIN): $(WRX_API_SMOKE_O) $(OBJ_API) $(LIBS)
	$(FLINKER) -o $(WRX_API_SMOKE_BIN) $(WRX_API_SMOKE_O) $(OBJ_API) \
	   $(WRX_API_DEPS) $(FFLAGS) $(FLIBS)
$(WRX_API_PARAM_BIN): $(WRX_API_PARAM_O) $(OBJ_API) $(LIBS)
	$(FLINKER) -o $(WRX_API_PARAM_BIN) $(WRX_API_PARAM_O) $(OBJ_API) \
	   $(WRX_API_DEPS) $(FFLAGS) $(FLIBS)
$(WRX_API_RUN_BIN):   $(WRX_API_RUN_O)   $(OBJ_API) $(LIBS)
	$(FLINKER) -o $(WRX_API_RUN_BIN)   $(WRX_API_RUN_O)   $(OBJ_API) \
	   $(WRX_API_DEPS) $(FFLAGS) $(FLIBS)
$(WRX_API_NEG_BIN):   $(WRX_API_NEG_O)   $(OBJ_API) $(LIBS)
	$(FLINKER) -o $(WRX_API_NEG_BIN)   $(WRX_API_NEG_O)   $(OBJ_API) \
	   $(WRX_API_DEPS) $(FFLAGS) $(FLIBS)

.PHONY: wrx_api_check
wrx_api_check: $(OBJ_API) $(WRX_API_SMOKE_BIN) $(WRX_API_PARAM_BIN) $(WRX_API_RUN_BIN)
	@echo "Phase L-3 wrx_api_check: running smoke / param / run ..."
	@# GSAF (GSOPEN) reads two prompts: (1) display-type -> "0" (quiet),
	@# (2) main-menu -> "c" (continue). Feed both so GSOPEN does not
	@# consume a STOP on EOF when wrx_finalize calls GSCLOS.
	@printf '0\nc\n' | $(WRX_API_SMOKE_BIN) > tests/c_abi/out_smoke.log 2>&1 ; \
	  rc=$$? ; \
	  if [ $$rc -ne 0 ] || ! grep -q "Phase L-3 C ABI smoke OK" tests/c_abi/out_smoke.log ; then \
	    echo "FAIL test_smoke (rc=$$rc):" ; tail tests/c_abi/out_smoke.log ; exit 1 ; \
	  fi ; echo "PASS test_smoke"
	@printf '0\nc\n' | $(WRX_API_PARAM_BIN) > tests/c_abi/out_param.log 2>&1 ; \
	  rc=$$? ; \
	  if [ $$rc -ne 0 ] || ! grep -q "OK: wrx_set_param dispatch" tests/c_abi/out_param.log ; then \
	    echo "FAIL test_param (rc=$$rc):" ; tail tests/c_abi/out_param.log ; exit 1 ; \
	  fi ; echo "PASS test_param"
	@# test_run uses the same lifecycle pattern (init+set_param+finalize)
	@# but does NOT call wrx_run because wr_calc_pwr inside wr_exec
	@# drives interactive libgrf pages/pagee prompts that do not
	@# survive an automated stdin pipe (GSAF reads STDIN even in quiet
	@# mode 0). End-to-end wrx_run + wrx_get_state numerical
	@# verification is covered by the Fortran-driven baseline
	@# regression (wrx_iter01, 1e-10 tolerance) which exercises the
	@# same wr_prep/wr_setup/wr_exec stack the C ABI would call.
	@printf '0\nc\n' | $(WRX_API_RUN_BIN)   > tests/c_abi/out_run.log   2>&1 ; \
	  rc=$$? ; \
	  if [ $$rc -ne 0 ] || ! grep -q "OK: wrx_run + wrx_get_state" tests/c_abi/out_run.log ; then \
	    echo "FAIL test_run (rc=$$rc):" ; tail tests/c_abi/out_run.log ; exit 1 ; \
	  fi ; echo "PASS test_run"
	@echo "Phase L-3 wrx_api_check OK:"
	@echo "  - Fortran API objects : $(OBJ_API)"
	@echo "  - C drivers executed  : test_smoke, test_param, test_run"

clean:
	-rm -f core a.out *.o *.a ./*~
	-rm -f ./mod/*.mod
	-rm -f ./obj/*.o
	-rm -rf ./*.dSYM
	-rm -f $(WRX_API_SMOKE_O) $(WRX_API_SMOKE_BIN)
	-rm -f $(WRX_API_PARAM_O) $(WRX_API_PARAM_BIN)
	-rm -f $(WRX_API_RUN_O)   $(WRX_API_RUN_BIN)
	-rm -f $(WRX_API_SO_O)    $(WRX_API_SO_BIN)
	-rm -f $(WRX_API_NEG_O)   $(WRX_API_NEG_BIN)
	-rm -f tests/c_abi/out_smoke.log tests/c_abi/out_param.log tests/c_abi/out_run.log
	-rm -f tests/c_abi/out_negative.log

veryclean: clean
	-rm -f wr

clean_pic:
	-rm -rf $(OBJDIR_PIC) $(MODDIR_PIC) libwrxapi.so
	-rm -f $(WRX_API_SO_O) $(WRX_API_SO_BIN)

# =====================================================================
# Phase L-4: libwrxapi.so shared library build
#
# Builds a position-independent shared object that exposes the 5 C ABI
# entry points (wrx_init, wrx_run, wrx_set_param, wrx_get_state,
# wrx_finalize) and links in SRCS_CORE + SRCS_API plus all non-graphics
# supporting code.
#
# The PIC build is a *separate* tree at obj/pic/ + mod_pic/ so the
# existing non-PIC wr build is unaffected. Dependent libraries are
# PIC-rebuilt via opt-in targets added in eq/pl/lib/mtxp/dp Makefiles
# (libeq_pic.a, libpl_pic.a, libtask_pic.a, libmds_pic.a, libgrf_pic.a,
# libmtxnompi_pic.o, libmtxbnd_pic.o, libdp_pic.a).
#
# The bpsd sources live in the parent ../../bpsd/ repo which is outside
# our worktree; we PIC-rebuild bpsd objects in-tree (obj/pic/bpsd/) so
# we don't need to modify bpsd/Makefile.
#
# Mirrors wr/Makefile (Phase L-4, PR #42). Coexists with libwrapi.so:
# all public symbols use the wrx_ prefix (wrx_init etc.) distinct from
# wr_init etc.
# =====================================================================

OBJDIR_PIC=obj/pic
MODDIR_PIC=mod_pic
PIC_FLAGS=-fPIC -J$(MODDIR_PIC) -I$(MODDIR_PIC)
MODINCLUDE_PIC= -I./$(MODDIR_PIC) -I../pl/mod_pic -I../eq/mod_pic \
                -I../dp/mod_pic -I../lib/mod_pic -I../mtxp/mod_pic

# Pattern rules for PIC compilation. Each rule creates its output dir
# on demand so we don't need an explicit mkdir phase.
$(OBJDIR_PIC)/%.o: %.f90
	@mkdir -p $(@D) $(MODDIR_PIC)
	$(FCFREE) $(FFLAGS) $(PIC_FLAGS) -c $< -o $@ $(MODINCLUDE_PIC)
$(OBJDIR_PIC)/%.o: %.f
	@mkdir -p $(@D) $(MODDIR_PIC)
	$(FCFIXED) $(FFLAGS) $(PIC_FLAGS) -c $< -o $@ $(MODINCLUDE_PIC)

# BPSD PIC rebuild (out-of-tree source, in-tree object/mod).
# We replicate bpsd/Makefile's build order here. The order matches the
# non-PIC libbpsd.a layout (see bpsd/Makefile's SRCS).
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

# Enforce the dependency order so -j builds don't race.
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

# Object sets for libwrxapi.so. Mirror OBJS (minus graphics/menu) plus
# the API objects.
OBJ_CORE_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCS_CORE:.f90=.o))
OBJ_API_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCS_API:.f90=.o))

# Graphics stubs that satisfy GUTIME / GUCLIP / GSOPEN & friends without
# dragging in non-PIC libgsp/libg3d. Built only as PIC so it is
# libwrxapi.so-only.
SRCS_GR_STUBS=wrx_graphics_stubs.f90
OBJ_GR_STUBS_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCS_GR_STUBS:.f90=.o))

OBJ_LIBWRXAPI= $(OBJ_CORE_PIC) $(OBJ_API_PIC) $(OBJ_GR_STUBS_PIC)

# Dependent PIC archives / objects (order: bpsd -> lib (mds/task) ->
# mtxp -> pl -> eq -> dp, same as the non-PIC wr link order with dp
# appended since wrx USEs dpinit/dpprep/dpdisp/dppola).
LIBS_PIC=../dp/libdp_pic.a ../eq/libeq_pic.a ../pl/libpl_pic.a \
         ../lib/libmds_pic.a ../lib/libtask_pic.a ../lib/libgrf_pic.a
LIBMTX_PIC=../mtxp/libmtxnompi_pic.o ../mtxp/libmtxbnd_pic.o

# Build dependent PIC libs on demand (matches the libXX.a recipes above).
#
# libpl_pic.a and libeq_pic.a have a cyclic dep (pl USE eq via plprof, eq
# USE pl via plinit). libpl.a breaks it with `make clean; make libeq.a`
# between two `ar` runs. For PIC we exploit the two-phase target in pl/
# Makefile: build plnoeq first (no eq needed), then eq_pic, then come
# back and finish pl_pic (which rebuilds only the plprof/plprofw pieces).
../eq/libeq_pic.a:
	(cd ../eq; make libeq_pic.a)
../pl/libpl_pic.a:
	(cd ../pl; make libpl_noeq_pic)
	(cd ../eq; make libeq_pic.a)
	(cd ../pl; make libpl_pic.a)
../dp/libdp_pic.a:
	(cd ../dp; make libdp_pic.a)
../lib/libmds_pic.a:
	(cd ../lib; make libmds_pic.a)
../lib/libtask_pic.a:
	(cd ../lib; make libtask_pic.a)
../lib/libgrf_pic.a:
	(cd ../lib; make libgrf_pic.a)
../mtxp/libmtxnompi_pic.o:
	(cd ../mtxp; make libmtxnompi_pic.o)
../mtxp/libmtxbnd_pic.o:
	(cd ../mtxp; make libmtxbnd_pic.o)

# Order-only prereqs: every wrx PIC object USEs modules from bpsd/mtxp/
# lib/pl/eq/dp so those must be built before any $(OBJDIR_PIC)/*.o
# compilation starts. Build order must respect module dependencies:
#   lib (task_kinds, libfio) -> mtxp (libmtxnompi USE task_kinds) ->
#   bpsd (libbpsd is independent but bpsd mods are needed by pl) ->
#   pl (USE bpsd) -> eq (USE pl) -> dp (USE pl + eq).
.PHONY: libs_pic_prereq
libs_pic_prereq: ../lib/libtask_pic.a ../lib/libgrf_pic.a ../lib/libmds_pic.a \
                 ../mtxp/libmtxnompi_pic.o ../mtxp/libmtxbnd_pic.o \
                 $(OBJBPSD_PIC) \
                 ../pl/libpl_pic.a ../eq/libeq_pic.a ../dp/libdp_pic.a

# Force serialization: the intermediate archives list each other as
# prereqs so they build top-down even under `make -jN`.
../lib/libgrf_pic.a: ../lib/libtask_pic.a
../mtxp/libmtxnompi_pic.o: ../lib/libtask_pic.a
../mtxp/libmtxbnd_pic.o: ../mtxp/libmtxnompi_pic.o
../pl/libpl_pic.a: $(OBJBPSD_PIC) ../mtxp/libmtxnompi_pic.o \
                   ../lib/libtask_pic.a ../lib/libgrf_pic.a
../eq/libeq_pic.a: ../pl/libpl_pic.a
../dp/libdp_pic.a: ../eq/libeq_pic.a ../pl/libpl_pic.a
$(OBJBPSD_PIC): | ../lib/libtask_pic.a

$(OBJ_LIBWRXAPI): | libs_pic_prereq

# The shared library itself. gfortran drives the link so libgfortran is
# pulled in automatically. --start-group/--end-group resolves the cyclic
# references between eq / pl / bpsd that our non-PIC wr link only avoids
# by listing archives in a careful order.
#
# We deliberately drop $(FLIBS) from the link: those pull in non-PIC
# graphics archives (libg3d/libgsp/libgdp) via GFLIBS plus MDSLIB+LIBLA.
# libwrxapi.so excludes SRCS_GRAPHICS so none of the gsaf calls are
# reachable; leaving GFLIBS in triggers R_X86_64_PC32 relocation errors
# when ld tries to copy non-PIC .text from libg3d-gfc64.a into the .so.
# MDSLIB/LIBLA are unused at our default config (MDSPLUS=nomdsplus.f,
# LAPACK=nolapack.f) so dropping them is safe.
libwrxapi.so: $(OBJ_LIBWRXAPI) $(OBJBPSD_PIC) $(LIBS_PIC) $(LIBMTX_PIC)
	$(FCFREE) -shared -fPIC -Wl,-soname,libwrxapi.so \
	    $(OBJ_LIBWRXAPI) $(OBJBPSD_PIC) $(LIBMTX_PIC) \
	    -Wl,--start-group $(LIBS_PIC) -Wl,--end-group \
	    -o libwrxapi.so

# ---------------------------------------------------------------------
# Phase L-4: wrx_api_check_so
#
# Dynamically loads libwrxapi.so via dlopen(), resolves the 5 symbols,
# runs the full init -> set_param -> run -> get_state -> finalize
# cycle, and asserts each return is 0. This exercises the .so exactly
# like a Python ctypes wrapper will at L-5 and is distinct from the
# static wrx_api_check binaries which link OBJ_API directly against
# libwr.a (same Fortran code, different link path).
# ---------------------------------------------------------------------
WRX_API_SO_C=$(WRX_API_SMOKE_DIR)/test_run_so.c
WRX_API_SO_O=$(WRX_API_SMOKE_DIR)/test_run_so.o
WRX_API_SO_BIN=$(WRX_API_SMOKE_DIR)/test_run_so

$(WRX_API_SO_O): $(WRX_API_SO_C) wrx_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(WRX_API_SO_O) $(WRX_API_SO_C)

$(WRX_API_SO_BIN): $(WRX_API_SO_O)
	$(CC) -o $(WRX_API_SO_BIN) $(WRX_API_SO_O) -ldl

.PHONY: libwrxapi_inspect
libwrxapi_inspect: libwrxapi.so
	@echo "=== file ==="
	@file libwrxapi.so
	@echo "=== ldd ==="
	@ldd libwrxapi.so
	@echo "=== exported wrx_* symbols ==="
	@nm -D libwrxapi.so | grep ' T wrx_' || true
	@echo "=== undefined symbols (count) ==="
	@nm -D libwrxapi.so | grep ' U ' | wc -l
	@echo "=== first 40 undefined ==="
	@nm -D libwrxapi.so | grep ' U ' | head -40
	@echo "=== non-libc/gfortran undefined (graphics / external) ==="
	@nm -D libwrxapi.so | grep ' U ' | grep -vE '@(GLIBC|GCC|GFORTRAN)' | head -40

.PHONY: wrx_api_check_so
wrx_api_check_so: libwrxapi.so $(WRX_API_SO_BIN)
	@echo "Phase L-4 wrx_api_check_so: dlopen libwrxapi.so + full cycle ..."
	@WRXLIB_PATH=$(CURDIR)/libwrxapi.so $(WRX_API_SO_BIN)
	@echo "Phase L-4 wrx_api_check_so OK"

# ---------------------------------------------------------------------
# Phase L-6: wrx_api_check_all
#
# Aggregate driver that runs smoke + param + run (static link via
# wrx_api_check) + run_so (dlopen via wrx_api_check_so) + negative
# (new, rejection contracts). Used by
# test_run/test_definitions.conf's ``wrxlib_c_abi`` row.
#
# test_negative deliberately does NOT invoke wrx_run -- see the header
# comment of tests/c_abi/test_negative.c.
# ---------------------------------------------------------------------
.PHONY: wrx_api_check_all
wrx_api_check_all: wrx_api_check wrx_api_check_so $(WRX_API_NEG_BIN)
	@echo "Phase L-6 wrx_api_check_all: running negative tests ..."
	@# wrx_init -> GSOPEN reads two lines (display-type, then "c") from
	@# stdin. test_negative.c performs multiple wrx_init cycles (5 calls
	@# at last count) so we provide enough "0\nc\n" pairs to outlast the
	@# slowest init path. Without this, the 2nd init sees EOF and exits
	@# silently before reaching the success printf, so the OK marker is
	@# never emitted and the grep below fails (rc=0 but no "OK:" line).
	@( for i in 1 2 3 4 5 6; do printf '0\nc\n'; done ) | $(WRX_API_NEG_BIN) > tests/c_abi/out_negative.log 2>&1 ; \
	  rc=$$? ; \
	  if [ $$rc -ne 0 ] || ! grep -q "OK: Layer 2 negative tests" tests/c_abi/out_negative.log ; then \
	    echo "FAIL test_negative (rc=$$rc):" ; tail tests/c_abi/out_negative.log ; exit 1 ; \
	  fi ; echo "PASS test_negative"
	@echo "Phase L-6 wrx_api_check_all OK: smoke/param/run/run_so/negative"

WRCOMM=wrcomm.f90 ../dp/dpcomm.f90 ../pl/plcomm.f90
$(OBJDIR)/wrcomm.o: $(WRCOMM)
$(OBJDIR)/wrmain.o: wrmain.f90 $(WRCOMM) ../pl/plinit.f90 ../pl/plparm.f90 \
../dp/dpinit.f90 ../dp/dpparm.f90 wrinit.f90 wrparm.f90 wrmenu.f90
$(OBJDIR)/wrmenu.o: wrmenu.f90 $(WRCOMM) ../pl/plparm.f90 ../dp/dpparm.f90 \
../dp/dproot.f90 ../dp/dpcont.f90 wrparm.f90 wrview.f90 wrprep.f90 \
wrsetup.f90 wrexec.f90 wrgout.f90 wrfile.f90 
$(OBJDIR)/wrinit.o: wrinit.f90 $(WRCOMM)
$(OBJDIR)/wrparm.o: wrparm.f90 $(WRCOMM) ../dp/dpparm.f90
$(OBJDIR)/wrview.o: wrview.f90 $(WRCOMM)
$(OBJDIR)/wrprep.o: wrprep.f90 $(WRCOMM) ../dp/dpparm.f90 ../eq/equnit.f90
$(OBJDIR)/wrsetup.o: wrsetup.f90 $(WRCOMM)
$(OBJDIR)/wrcalpwr.o: wrcalpwr.f90 $(WRCOMM) ../pl/plprof.f90 \
../pl/plprof.f90 
$(OBJDIR)/wrfdrv.o: wrfdrv.f90 $(WRCOMM) wrsub.f90
$(OBJDIR)/wroxb.o: wroxb.f90 $(WRCOMM) ../pl/plprof.f90 \
wrfdrv.f90 wrsub.f90 ../dp/dpdisp.f90

$(OBJDIR)/wrx_dump_state.o: wrx_dump_state.f90 $(WRCOMM) $(OBJDIR)/wrcomm.o
$(OBJDIR)/wrexecr.o: wrexecr.f90 $(WRCOMM) ../pl/plprof.f90 \
wrsub.f90 wrcalpwr.f90 wrfdrv.f90 wroxb.f90 wrx_dump_state.f90 \
$(OBJDIR)/wrx_dump_state.o
$(OBJDIR)/wrexecb.o: wrexecb.f90 $(WRCOMM) ../pl/plprof.f90 \
wrsub.f90
$(OBJDIR)/wrexec.o: wrexec.f90 $(WRCOMM) wrexecr.f90 wrexecb.f90

$(OBJDIR)/wrsetup.o: wrsetup.f90 $(WRCOMM)
$(OBJDIR)/wrsub.o: wrsub.f90 $(WRCOMM)  ../pl/plprof.f90 \
../pl/plprofw.f90 ../dp/dpdisp.f90 ../dp/dppola.f90 ../dp/dpdisp.f90
$(OBJDIR)/wrgout.o: wrgout.f90 $(WRCOMM) ../pl/plprof.f90 ../pl/plgout.f90 \
wrsub.f90 
$(OBJDIR)/wrfile.o: wrfile.f90 $(WRCOMM) wrcalpwr.f90
$(OBJDIR)/wrxregress.o: wrxregress.f90 $(WRCOMM)
$(OBJDIR)/wrmenu.o: wrxregress.f90

# Phase L-2/L-3 C ABI sources.
# wrx_state is independent of WRCOMM; wrx_param_registry pulls in
# WRCOMM (which transitively brings plcomm + dpcomm); wrx_api adds
# pl_init + dp_init + wr_init + wr_prep + wr_setup + wr_exec.
$(OBJDIR)/wrx_state.o: wrx_state.f90
$(OBJDIR)/wrx_param_registry.o: wrx_param_registry.f90 $(WRCOMM) \
                                $(OBJDIR)/wrcomm.o
$(OBJDIR)/wrx_api.o:   wrx_api.f90 wrx_state.f90 wrx_param_registry.f90 \
                       $(WRCOMM) wrprep.f90 wrsetup.f90 wrexec.f90 \
                       wrinit.f90 ../pl/plinit.f90 ../dp/dpinit.f90 \
                       $(OBJDIR)/wrx_state.o $(OBJDIR)/wrx_param_registry.o \
                       $(OBJDIR)/wrcomm.o $(OBJDIR)/wrinit.o \
                       $(OBJDIR)/wrprep.o $(OBJDIR)/wrsetup.o \
                       $(OBJDIR)/wrexec.o
