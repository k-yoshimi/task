### Madefile for wr

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

# --- Source groups (Phase L-1 split) ---
# SRCS_CORE: pure computation; will be reused for libwrapi.so in Phase L-4.
# SRCS_GRAPHICS: GSAF-based plot output; excluded from libwrapi.so.
# SRCS_MENU: interactive stdin menu; excluded from libwrapi.so.
#
# When Phase L-4 lands, libwrapi.so will be built from:
#   SRCS_LIB = $(SRCS_CORE) $(SRCS_API)
# where SRCS_API = wr_state.f90 wr_param_registry.f90 wr_api.f90
# (no graphics, no menu).
SRCS_CORE = wrcomm.f90 wrinit.f90 wrparm.f90 wrview.f90 \
            wrsub.f90 \
            wrsetupr.f90 wrexecr.f90 wrsetupb.f90 wrexecb.f90 \
            wrsetup.f90 wrregress.f90 wrexec.f90 \
            wrfile.f90

SRCS_GRAPHICS = wrgout.f90

SRCS_MENU = wrmenu.f90

# C ABI sources (Phase L-2+). Compiled via the wr_api_check target only;
# NOT part of $(SRCS) and NOT linked into libwr.a / wr. The full
# libwrapi.so build arrives in Phase L-4.
SRCS_API = wr_state.f90 wr_param_registry.f90 wr_api.f90

SRCS = $(SRCS_CORE) $(SRCS_GRAPHICS) $(SRCS_MENU)

OBJS = $(addprefix $(OBJDIR)/, $(SRCS:.f90=.o))
OBJ_API = $(addprefix $(OBJDIR)/, $(SRCS_API:.f90=.o))

LIBS = libwr.a  ../dp/libdp.a ../eq/libeq.a ../pl/libpl.a \
       ../lib/libtask.a ../lib/libgrf.a ../../bpsd/libbpsd.a

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

# ---------------------------------------------------------------------
# Phase L-2/L-3: C ABI check
#
# `make wr_api_check` builds the new API objects (wr_state.o,
# wr_param_registry.o, wr_api.o) and three small C drivers linked
# against wr_api.h:
#
#   test_smoke  : 4 entry points return WR_OK           (sanity)
#   test_param  : wr_set_param + wr_get_state dispatch  (L-3)
#   test_run    : wr_run executes wr_setup + wr_exec    (L-3)
#
# The API objects are NOT linked into libwr.a / wr and the wr binary
# remains byte-for-byte identical with or without this target being
# invoked. L-3 drivers depend on libwr.a (for WRCOMM, wr_setup,
# wr_exec, ...) so we link it in after the API objects. The full
# libwrapi.so build arrives in Phase L-4.
#
# CC defaults to gcc; override on the command line if necessary
# (e.g. `make wr_api_check CC=clang`).
# ---------------------------------------------------------------------
CC ?= gcc
CFLAGS_API ?= -Wall -Wextra -O2

WR_API_SMOKE_DIR=tests/c_abi
WR_API_SMOKE_C=$(WR_API_SMOKE_DIR)/test_smoke.c
WR_API_SMOKE_O=$(WR_API_SMOKE_DIR)/test_smoke.o
WR_API_SMOKE_BIN=$(WR_API_SMOKE_DIR)/test_smoke

WR_API_PARAM_C=$(WR_API_SMOKE_DIR)/test_param.c
WR_API_PARAM_O=$(WR_API_SMOKE_DIR)/test_param.o
WR_API_PARAM_BIN=$(WR_API_SMOKE_DIR)/test_param

WR_API_RUN_C=$(WR_API_SMOKE_DIR)/test_run.c
WR_API_RUN_O=$(WR_API_SMOKE_DIR)/test_run.o
WR_API_RUN_BIN=$(WR_API_SMOKE_DIR)/test_run

WR_API_REINIT_C=$(WR_API_SMOKE_DIR)/test_reinit.c
WR_API_REINIT_O=$(WR_API_SMOKE_DIR)/test_reinit.o
WR_API_REINIT_BIN=$(WR_API_SMOKE_DIR)/test_reinit

# At L-3 the API drivers pull in WRCOMM, wr_setup, wr_exec, ... so we
# need the full wr + dp + eq + pl + bpsd + mtx link just like wr.
WR_API_DEPS=$(LIBS) $(LIBX_MTX)

# Step 1: header-only C compile (matches the documented user-level check
#         `gcc -Wall -Wextra -c -o test_smoke.o test_smoke.c`).
$(WR_API_SMOKE_O): $(WR_API_SMOKE_C) wr_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(WR_API_SMOKE_O) $(WR_API_SMOKE_C)
$(WR_API_PARAM_O): $(WR_API_PARAM_C) wr_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(WR_API_PARAM_O) $(WR_API_PARAM_C)
$(WR_API_RUN_O):   $(WR_API_RUN_C)   wr_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(WR_API_RUN_O)   $(WR_API_RUN_C)
$(WR_API_REINIT_O): $(WR_API_REINIT_C) wr_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(WR_API_REINIT_O) $(WR_API_REINIT_C)

# Step 2: link against API objects + wr/dp/eq/pl/bpsd/mtx. gfortran
# drives the link so libgfortran is pulled in automatically.
$(WR_API_SMOKE_BIN): $(WR_API_SMOKE_O) $(OBJ_API) $(LIBS) $(LIB_MTX)
	$(FLINKER) -o $(WR_API_SMOKE_BIN) $(WR_API_SMOKE_O) $(OBJ_API) \
	    $(WR_API_DEPS) $(FFLAGS) $(FLIBS)
$(WR_API_PARAM_BIN): $(WR_API_PARAM_O) $(OBJ_API) $(LIBS) $(LIB_MTX)
	$(FLINKER) -o $(WR_API_PARAM_BIN) $(WR_API_PARAM_O) $(OBJ_API) \
	    $(WR_API_DEPS) $(FFLAGS) $(FLIBS)
$(WR_API_RUN_BIN):   $(WR_API_RUN_O)   $(OBJ_API) $(LIBS) $(LIB_MTX)
	$(FLINKER) -o $(WR_API_RUN_BIN)   $(WR_API_RUN_O)   $(OBJ_API) \
	    $(WR_API_DEPS) $(FFLAGS) $(FLIBS)
$(WR_API_REINIT_BIN): $(WR_API_REINIT_O) $(OBJ_API) $(LIBS) $(LIB_MTX)
	$(FLINKER) -o $(WR_API_REINIT_BIN) $(WR_API_REINIT_O) $(OBJ_API) \
	    $(WR_API_DEPS) $(FFLAGS) $(FLIBS)

.PHONY: wr_api_check
wr_api_check: $(OBJ_API) $(WR_API_SMOKE_BIN) $(WR_API_PARAM_BIN) \
              $(WR_API_RUN_BIN) $(WR_API_REINIT_BIN)
	@echo "Phase L-3 wr_api_check: running smoke / param / run / reinit ..."
	@$(WR_API_SMOKE_BIN)
	@$(WR_API_PARAM_BIN)
	@$(WR_API_RUN_BIN)
	@$(WR_API_REINIT_BIN)
	@echo "Phase L-3 wr_api_check OK:"
	@echo "  - Fortran API objects : $(OBJ_API)"
	@echo "  - C drivers executed  : test_smoke, test_param, test_run, test_reinit"

clean:
	-rm -f core a.out *.o *.a ./*~
	-rm -f ./mod/*.mod
	-rm -f ./obj/*.o
	-rm -rf ./*.dSYM
	-rm -f $(WR_API_SMOKE_O) $(WR_API_SMOKE_BIN)
	-rm -f $(WR_API_PARAM_O) $(WR_API_PARAM_BIN)
	-rm -f $(WR_API_RUN_O)   $(WR_API_RUN_BIN)
	-rm -f $(WR_API_REINIT_O) $(WR_API_REINIT_BIN)
	-rm -f $(WR_API_SO_O)    $(WR_API_SO_BIN)

veryclean: clean
	-rm -f wr

clean_pic:
	-rm -rf $(OBJDIR_PIC) $(MODDIR_PIC) libwrapi.so
	-rm -f $(WR_API_SO_O) $(WR_API_SO_BIN)

# =====================================================================
# Phase L-4: libwrapi.so shared library build
#
# Builds a position-independent shared object that exposes the 5 C ABI
# entry points (wr_init, wr_run, wr_set_param, wr_get_state, wr_finalize)
# and links in SRCS_CORE + SRCS_API plus all non-graphics supporting
# code.
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
# Mirrors tr/Makefile (Phase L-4, PR #35). Coexists with a future
# libwrxapi.so: all public symbols use the wr_ prefix (wr_init etc.)
# distinct from wrx_init etc.
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

# Object sets for libwrapi.so. Mirror OBJS (minus graphics/menu) plus
# the API objects.
OBJ_CORE_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCS_CORE:.f90=.o))
OBJ_API_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCS_API:.f90=.o))

# Graphics stubs that satisfy GUTIME / GUCLIP & friends without dragging
# in non-PIC libgsp/libg3d. Built only as PIC so it is libwrapi.so-only.
SRCS_GR_STUBS=wr_graphics_stubs.f90
OBJ_GR_STUBS_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCS_GR_STUBS:.f90=.o))

OBJ_LIBWRAPI= $(OBJ_CORE_PIC) $(OBJ_API_PIC) $(OBJ_GR_STUBS_PIC)

# Dependent PIC archives / objects (order: bpsd -> lib (mds/task) ->
# mtxp -> pl -> eq -> dp, same as the non-PIC wr link order with dp
# appended since wr USEs dpinit/dpprep/dpdisp/dppola).
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

# Order-only prereqs: every wr PIC object USEs modules from bpsd/mtxp/
# lib/pl/eq/dp so those must be built before any $(OBJDIR_PIC)/*.o
# compilation starts. Build order must respect module dependencies:
#   lib (task_kinds, libfio) -> mtxp (libmtxnompi USE task_kinds) ->
#   bpsd (libbpsd is independent but bpsd mods are needed by pl) ->
#   pl (USE bpsd) -> eq (USE pl) -> dp (USE pl + eq).
# The `|` syntax below makes these ORDER-ONLY (no rebuild cascade).
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

$(OBJ_LIBWRAPI): | libs_pic_prereq

# The shared library itself. gfortran drives the link so libgfortran is
# pulled in automatically. --start-group/--end-group resolves the cyclic
# references between eq / pl / bpsd that our non-PIC wr link only avoids
# by listing archives in a careful order.
#
# We deliberately drop $(FLIBS) from the link: those pull in non-PIC
# graphics archives (libg3d/libgsp/libgdp) via GFLIBS plus MDSLIB+LIBLA.
# libwrapi.so excludes SRCS_GRAPHICS so none of the gsaf calls are
# reachable; leaving GFLIBS in triggers R_X86_64_PC32 relocation errors
# when ld tries to copy non-PIC .text from libg3d-gfc64.a into the .so.
# MDSLIB/LIBLA are unused at our default config (MDSPLUS=nomdsplus.f,
# LAPACK=nolapack.f) so dropping them is safe.
libwrapi.so: $(OBJ_LIBWRAPI) $(OBJBPSD_PIC) $(LIBS_PIC) $(LIBMTX_PIC)
	$(FCFREE) -shared -fPIC -Wl,-soname,libwrapi.so \
	    $(OBJ_LIBWRAPI) $(OBJBPSD_PIC) $(LIBMTX_PIC) \
	    -Wl,--start-group $(LIBS_PIC) -Wl,--end-group \
	    -o libwrapi.so

# ---------------------------------------------------------------------
# Phase L-4: wr_api_check_so
#
# Dynamically loads libwrapi.so via dlopen(), resolves the 5 symbols,
# runs the full init -> set_param -> run -> get_state -> finalize
# cycle, and asserts each return is 0. This exercises the .so exactly
# like a Python ctypes wrapper will at L-5 and is distinct from the
# static wr_api_check binaries which link OBJ_API directly against
# libwr.a (same Fortran code, different link path).
# ---------------------------------------------------------------------
WR_API_SO_C=$(WR_API_SMOKE_DIR)/test_run_so.c
WR_API_SO_O=$(WR_API_SMOKE_DIR)/test_run_so.o
WR_API_SO_BIN=$(WR_API_SMOKE_DIR)/test_run_so

$(WR_API_SO_O): $(WR_API_SO_C) wr_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(WR_API_SO_O) $(WR_API_SO_C)

$(WR_API_SO_BIN): $(WR_API_SO_O)
	$(CC) -o $(WR_API_SO_BIN) $(WR_API_SO_O) -ldl

.PHONY: libwrapi_inspect
libwrapi_inspect: libwrapi.so
	@echo "=== file ==="
	@file libwrapi.so
	@echo "=== ldd ==="
	@ldd libwrapi.so
	@echo "=== exported wr_* symbols ==="
	@nm -D libwrapi.so | grep ' T wr_' || true
	@echo "=== undefined symbols (count) ==="
	@nm -D libwrapi.so | grep ' U ' | wc -l
	@echo "=== first 40 undefined ==="
	@nm -D libwrapi.so | grep ' U ' | head -40
	@echo "=== non-libc/gfortran undefined (graphics / external) ==="
	@nm -D libwrapi.so | grep ' U ' | grep -vE '@(GLIBC|GCC|GFORTRAN)' | head -40

.PHONY: wr_api_check_so
wr_api_check_so: libwrapi.so $(WR_API_SO_BIN)
	@echo "Phase L-4 wr_api_check_so: dlopen libwrapi.so + full cycle ..."
	@WRLIB_PATH=$(CURDIR)/libwrapi.so $(WR_API_SO_BIN)
	@echo "Phase L-4 wr_api_check_so OK"

WRCOMM=wrcomm.f90 ../dp/dpcomm.f90 ../pl/plcomm.f90
$(OBJDIR)/wrcomm.o: $(WRCOMM)
$(OBJDIR)/wrmain.o: wrmain.f90 $(WRCOMM) ../pl/plinit.f90 ../pl/plparm.f90 \
../dp/dpinit.f90 ../dp/dpparm.f90 wrinit.f90 wrparm.f90 wrmenu.f90
$(OBJDIR)/wrmenu.o: wrmenu.f90 $(WRCOMM) ../pl/plparm.f90 ../dp/dpparm.f90 \
../dp/dpcont.f90 wrparm.f90 wrsetup.f90 wrexec.f90 wrgout.f90 wrfile.f90 
$(OBJDIR)/wrinit.o: wrinit.f90 $(WRCOMM)
$(OBJDIR)/wrparm.o: wrparm.f90 $(WRCOMM) ../dp/dpparm.f90 
$(OBJDIR)/wrview.o: wrview.f90 $(WRCOMM)
$(OBJDIR)/wrsetupr.o:wrsetupr.f90 $(WRCOMM)
$(OBJDIR)/wrsetupb.o:wrsetupb.f90 $(WRCOMM)
$(OBJDIR)/wrsetup.o:wrsetup.f90 $(WRCOMM) wrsetupr.f90 wrsetupb.f90

$(OBJDIR)/wrexecr.o:wrexecr.f90 $(WRCOMM) ../pl/plprof.f90 ../dp/dpdisp.f90 \
wrsub.f90
$(OBJDIR)/wrexecb.o:wrexecb.f90 $(WRCOMM) ../pl/plprof.f90 ../dp/dpdisp.f90 \
wrsub.f90
$(OBJDIR)/wrregress.o: wrregress.f90 $(WRCOMM)
$(OBJDIR)/wrexec.o:wrexec.f90 $(WRCOMM) wrexecr.f90 wrexecb.f90 wrregress.f90

$(OBJDIR)/wrsetup.o:wrsetup.f90 $(WRCOMM) wrsetupr.f90 wrsetupb.f90
$(OBJDIR)/wrsub.o:  wrsub.f90 $(WRCOMM) ../pl/plprof.f90 ../dp/dppola.f90 \
../dp/dpdisp.f90
$(OBJDIR)/wrgout.o: wrgout.f90 $(WRCOMM) ../pl/plprof.f90 ../pl/plgout.f90 \
wrsub.f90 
$(OBJDIR)/wrfile.o: wrfile.f90 $(WRCOMM)

# Phase L-2 / L-3 C ABI sources. wr_state is independent of WRCOMM;
# wr_param_registry and wr_api pull in WRCOMM plus wr_setup / wr_exec.
$(OBJDIR)/wr_state.o : wr_state.f90
$(OBJDIR)/wr_param_registry.o : wr_param_registry.f90 $(WRCOMM) \
                     $(OBJDIR)/wrcomm.o
$(OBJDIR)/wr_api.o   : wr_api.f90 wr_state.f90 \
                     $(OBJDIR)/wr_state.o $(OBJDIR)/wr_param_registry.o \
                     $(OBJDIR)/wrcomm.o $(OBJDIR)/wrinit.o \
                     $(OBJDIR)/wrsetup.o $(OBJDIR)/wrexec.o
