### $Id$ ###
include ../make.header
include ../mtxp/make.mtxp

#LIB_MTX=$(LIB_MTX_BND)
#LIBX_MTX=$(LIBX_MTX_BND)
#LIB_MTX=$(LIB_MTX_PCG)
#LIBX_MTX=$(LIBX_MTX_PCG)
LIB_MTX=$(LIB_MTX_MUMPS)
LIBX_MTX=$(LIBX_MTX_MUMPS)
#LIB_MTX=$(LIBXMTX_KSP)
#LIBX_MTX=$(LIBX_MTX_KSP)

FFLAGS = $(OFLAGS)
#FFLAGS = $(DFLAGS)

.SUFFIXES:
.SUFFIXES: .f .f90 .mod .o .a

.f.o :
	$(FCFIXED) $(FFLAGS) -c $< -o $@ $(MODDIR) $(MODINCLUDE)
.f90.o :
	$(FCFREE) $(FFLAGS) -c $< -o $@ $(MODDIR) $(MODINCLUDE)

MODINCLUDE= -I./$(MOD) -I../open-adas/adf11/adf11-lib/$(MOD) \
            -I../adpost/$(MOD) -I../eq/$(MOD) -I../pl/$(MOD) \
            -I../mtxp/$(MOD) -I../lib/$(MOD) -I../../bpsd/$(MOD) 

# Core sources: included in both `ti` binary and (later) libtiapi.so.
# Graphics and menu are split out so libtiapi.so can be built without them.
SRCS_CORE=   ticomm.f90 tiadas.f90 \
	tiinit.f90 tiparm.f90 \
	ticoef.f90 tisource.f90 ticalc.f90 tirecord.f90 \
        tiprep.f90 tiregress.f90 tiexec.f90

SRCS_GRAPHICS= tigout.f90

SRCS_MENU=     timenu.f90

# C ABI sources (Phase L-2+). Compiled via the ti_api_check target only;
# NOT part of $(SRCS) and NOT linked into libti.a / ti. The full
# libtiapi.so build arrives in Phase L-4.
SRCS_API=ti_state.f90 ti_param_registry.f90 ti_api.f90

SRCS=$(SRCS_CORE) $(SRCS_GRAPHICS) $(SRCS_MENU)

#      trprof.f90 trufsub.f90 trufile.f90 trfile.f90 trhelp.f90 \
#      trexec.f90 trcalc.f90 \
#      tradat.f90 cdbm.f90 trmodels.f90 trcoef.f90 tritg.f90 \
#      trrslt.f90 \
#      trpnb.f90 trprf.f90 trpnf.f90 trpel.f90 trpsc.f90 trmdlt.f90 \
#      trgout.f90 trgrar.f90 trgrat.f90 trgrap.f90 trgrae.f90 \
#      trgrad.f90 trgram.f90 trgsub.f90 trfout.f90 \
#      trunit.f90 trloop.f90 trmenu.f90 tr_bpsd.f90

OBJS=$(SRCS:.f90=.o)
OBJ_API=$(SRCS_API:.f90=.o)

LIBS=libti.a ../adpost/lib-adpost.a ../open-adas/adf11/adf11-lib/lib-adf11.a ../eq/libeq.a ../pl/libpl.a ../lib/libtask.a ../lib/libgrf.a ../../bpsd/libbpsd.a


all: libs ti

libti.a: $(OBJS)
	$(LD) $(LDFLAGS) $@ $(OBJS)

../../bpsd/libbpsd.a:
	(cd ../../bpsd; make libbpsd.a)
../lib/libtask.a:
	(cd ../lib; make libtask.a)
../lib/libgrf.a:
	(cd ../lib; make libgrf.a)
../open-adas/adf11/adf11-lib/lib-adf11.a: 
	(cd ../open-adas/adf11/adf11-lib; make lib-adf11.a)
../adpost/lib-adpost.a: 
	(cd ../adpost; make lib-adpost.a)
../pl/libpl.a:
	(cd ../pl; make libpl.a)
../eq/libeq.a:
	(cd ../eq; make libeq.a)


libs:
	(cd ../../bpsd; make libbpsd.a)
	(cd ../lib; make libtask.a)
	(cd ../lib; make libgrf.a)
	(cd ../mtxp; make)
	(cd ../open-adas/adf11/adf11-lib; make lib-adf11.a)
	(cd ../adpost; make lib-adpost.a)
	(cd ../pl; make libpl.a)
	(cd ../eq; make libeq.a)

ti: libs libti.a timain.o 
	$(FLINKER) timain.o $(LIBS) -o $@ $(FFLAGS) $(FLIBS) $(LIBX_MTX)

.PHONY: srcs-core-list srcs-graphics-list srcs-menu-list

srcs-core-list:
	@echo $(SRCS_CORE)

srcs-graphics-list:
	@echo $(SRCS_GRAPHICS)

srcs-menu-list:
	@echo $(SRCS_MENU)

# ---------------------------------------------------------------------
# Phase L-2 / L-3: C ABI check
#
# `make ti_api_check` builds the new API objects (ti_state.o,
# ti_param_registry.o, ti_api.o) and three small C drivers linked
# against ti_api.h:
#
#   test_smoke  : 4 entry points return TI_OK           (sanity)
#   test_param  : ti_set_param + ti_get_state dispatch  (L-3)
#   test_run    : ti_run advances T by N*DT             (L-3)
#
# The API objects are NOT linked into libti.a / ti and the ti binary
# remains byte-for-byte identical with or without this target being
# invoked. L-3 drivers depend on libti.a (for TICOMM, ti_exec, ti_prep,
# ...) so we link it in after the API objects. The full libtiapi.so
# build arrives in Phase L-4.
#
# CC defaults to gcc; override on the command line if necessary
# (e.g. `make ti_api_check CC=clang`).
# ---------------------------------------------------------------------
CC ?= gcc
CFLAGS_API ?= -Wall -Wextra -O2

TI_API_SMOKE_DIR=tests/c_abi
TI_API_SMOKE_C=$(TI_API_SMOKE_DIR)/test_smoke.c
TI_API_SMOKE_O=$(TI_API_SMOKE_DIR)/test_smoke.o
TI_API_SMOKE_BIN=$(TI_API_SMOKE_DIR)/test_smoke

TI_API_PARAM_C=$(TI_API_SMOKE_DIR)/test_param.c
TI_API_PARAM_O=$(TI_API_SMOKE_DIR)/test_param.o
TI_API_PARAM_BIN=$(TI_API_SMOKE_DIR)/test_param

TI_API_RUN_C=$(TI_API_SMOKE_DIR)/test_run.c
TI_API_RUN_O=$(TI_API_SMOKE_DIR)/test_run.o
TI_API_RUN_BIN=$(TI_API_SMOKE_DIR)/test_run

# At L-3 the API drivers pull in TICOMM, ti_exec, ti_prep, ... so we
# need the full ti + eq + pl + bpsd + mtx link just like ti.
TI_API_DEPS=$(LIBS) $(LIBX_MTX)

# Step 1: header-only C compile (matches the documented user-level check
#         `gcc -Wall -Wextra -c -o test_smoke.o test_smoke.c`).
$(TI_API_SMOKE_O): $(TI_API_SMOKE_C) ti_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(TI_API_SMOKE_O) $(TI_API_SMOKE_C)
$(TI_API_PARAM_O): $(TI_API_PARAM_C) ti_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(TI_API_PARAM_O) $(TI_API_PARAM_C)
$(TI_API_RUN_O):   $(TI_API_RUN_C)   ti_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(TI_API_RUN_O)   $(TI_API_RUN_C)

# Step 2: link against API objects + ti/eq/pl/bpsd/mtx. gfortran drives
# the link so libgfortran is pulled in automatically.
$(TI_API_SMOKE_BIN): $(TI_API_SMOKE_O) $(OBJ_API) libti.a
	$(FLINKER) -o $(TI_API_SMOKE_BIN) $(TI_API_SMOKE_O) $(OBJ_API) \
	   $(TI_API_DEPS) $(FFLAGS) $(FLIBS)
$(TI_API_PARAM_BIN): $(TI_API_PARAM_O) $(OBJ_API) libti.a
	$(FLINKER) -o $(TI_API_PARAM_BIN) $(TI_API_PARAM_O) $(OBJ_API) \
	   $(TI_API_DEPS) $(FFLAGS) $(FLIBS)
$(TI_API_RUN_BIN):   $(TI_API_RUN_O)   $(OBJ_API) libti.a
	$(FLINKER) -o $(TI_API_RUN_BIN)   $(TI_API_RUN_O)   $(OBJ_API) \
	   $(TI_API_DEPS) $(FFLAGS) $(FLIBS)

.PHONY: ti_api_check
ti_api_check: $(OBJ_API) $(TI_API_SMOKE_BIN) $(TI_API_PARAM_BIN) $(TI_API_RUN_BIN)
	@echo "Phase L-3 ti_api_check: running smoke / param / run ..."
	@$(TI_API_SMOKE_BIN)
	@$(TI_API_PARAM_BIN)
	@$(TI_API_RUN_BIN)
	@echo "Phase L-3 ti_api_check OK:"
	@echo "  - Fortran API objects : $(OBJ_API)"
	@echo "  - C drivers executed  : test_smoke, test_param, test_run"

clean :
	rm -f ./#* ./*~ *.o nclass/*.o itg/*.o glf/*.o cytran/*.o mmm95/*.o mbgb/*.o a.out core *.a *.mod $(MOD)/*.mod
	rm -f $(TI_API_SMOKE_O) $(TI_API_SMOKE_BIN)
	rm -f $(TI_API_PARAM_O) $(TI_API_PARAM_BIN)
	rm -f $(TI_API_RUN_O)   $(TI_API_RUN_BIN)
	-rm -f $(TI_API_SO_O)   $(TI_API_SO_BIN)

veryclean : clean
	rm -f ti

distclean: clean
	cd ../tr && make clean
	cd ../pl && make clean
	cd ../eq && make clean
	cd ../lib && make clean

clean_pic:
	-rm -rf $(OBJDIR_PIC) $(MODDIR_PIC) libtiapi.so
	-rm -f $(TI_API_SO_O) $(TI_API_SO_BIN)

# =====================================================================
# Phase L-4: libtiapi.so shared library build
#
# Builds a position-independent shared object that exposes the 5 C ABI
# entry points (ti_init, ti_run, ti_set_param, ti_get_state, ti_finalize)
# and links in SRCS_CORE + SRCS_API plus the (non-graphics) supporting
# libraries (libpl_pic, libeq_pic, libtask_pic, libmds_pic, lib-adpost_pic,
# lib-adf11_pic, libmtxnompi_pic, libmtxbnd_pic, bpsd PIC).
#
# The PIC build is a *separate* tree at obj/pic/ + mod_pic/ so the
# existing non-PIC ti build is unaffected. Dependent libraries are
# PIC-rebuilt via opt-in targets added in eq/pl/lib/mtxp/adpost/adf11
# Makefiles (libeq_pic.a, libpl_pic.a, libtask_pic.a, libmds_pic.a,
# lib-adpost_pic.a, lib-adf11_pic.a, libmtxnompi_pic.o, libmtxbnd_pic.o).
#
# The bpsd sources live in the parent ../../bpsd/ repo which is outside
# our worktree; we PIC-rebuild bpsd objects in-tree (obj/pic/bpsd/) so
# we don't need to modify bpsd/Makefile.
#
# Note: this Makefile selects LIB_MTX=LIB_MTX_MUMPS by default, but the
# libtiapi.so link path uses libmtxnompi_pic.o + libmtxbnd_pic.o (BND
# backend) because the MUMPS backend is not currently built as PIC and
# is unreachable from the C ABI happy path.
# =====================================================================

OBJDIR_PIC=obj/pic
MODDIR_PIC=mod_pic
PIC_FLAGS=-fPIC -J$(MODDIR_PIC) -I$(MODDIR_PIC)
MODINCLUDE_PIC= -I./$(MODDIR_PIC) \
                -I../open-adas/adf11/adf11-lib/mod_pic \
                -I../adpost/mod_pic \
                -I../pl/mod_pic -I../eq/mod_pic \
                -I../lib/mod_pic -I../mtxp/mod_pic

# Pattern rules for PIC compilation. Each rule creates its output dir
# on demand so we don't need an explicit mkdir phase.
$(OBJDIR_PIC)/%.o: %.f90
	@mkdir -p $(@D) $(MODDIR_PIC)
	$(FCFREE) $(FFLAGS) $(PIC_FLAGS) -c $< -o $@ $(MODINCLUDE_PIC)
$(OBJDIR_PIC)/%.o: %.f
	@mkdir -p $(@D) $(MODDIR_PIC)
	$(FCFIXED) $(FFLAGS) $(PIC_FLAGS) -c $< -o $@ $(MODINCLUDE_PIC)

# BPSD PIC rebuild (out-of-tree source, in-tree object/mod).
# We replicate bpsd/Makefile's build order here.
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
$(OBJDIR_PIC)/bpsd/bpsd_constants.o:     $(OBJDIR_PIC)/bpsd/bpsd_kinds.o
$(OBJDIR_PIC)/bpsd/bpsd_flags.o:          $(OBJDIR_PIC)/bpsd/bpsd_kinds.o
$(OBJDIR_PIC)/bpsd/bpsd_libchar.o:        $(OBJDIR_PIC)/bpsd/bpsd_kinds.o
$(OBJDIR_PIC)/bpsd/bpsd_libfio.o:         $(OBJDIR_PIC)/bpsd/bpsd_kinds.o
$(OBJDIR_PIC)/bpsd/bpsd_libspl.o:         $(OBJDIR_PIC)/bpsd/bpsd_kinds.o
$(OBJDIR_PIC)/bpsd/bpsd_types.o:          $(OBJDIR_PIC)/bpsd/bpsd_kinds.o $(OBJDIR_PIC)/bpsd/bpsd_constants.o
$(OBJDIR_PIC)/bpsd/bpsd_types_internal.o: $(OBJDIR_PIC)/bpsd/bpsd_types.o
$(OBJDIR_PIC)/bpsd/bpsd_subs.o:           $(OBJDIR_PIC)/bpsd/bpsd_types_internal.o $(OBJDIR_PIC)/bpsd/bpsd_libchar.o $(OBJDIR_PIC)/bpsd/bpsd_libfio.o $(OBJDIR_PIC)/bpsd/bpsd_libspl.o $(OBJDIR_PIC)/bpsd/bpsd_flags.o
$(OBJDIR_PIC)/bpsd/bpsd_shot.o:           $(OBJDIR_PIC)/bpsd/bpsd_subs.o
$(OBJDIR_PIC)/bpsd/bpsd_device.o:         $(OBJDIR_PIC)/bpsd/bpsd_subs.o
$(OBJDIR_PIC)/bpsd/bpsd_species.o:        $(OBJDIR_PIC)/bpsd/bpsd_subs.o
$(OBJDIR_PIC)/bpsd/bpsd_equ1D.o:          $(OBJDIR_PIC)/bpsd/bpsd_subs.o
$(OBJDIR_PIC)/bpsd/bpsd_metric1D.o:       $(OBJDIR_PIC)/bpsd/bpsd_subs.o
$(OBJDIR_PIC)/bpsd/bpsd_plasmaf.o:        $(OBJDIR_PIC)/bpsd/bpsd_subs.o
$(OBJDIR_PIC)/bpsd/bpsd_trmatrix.o:       $(OBJDIR_PIC)/bpsd/bpsd_subs.o
$(OBJDIR_PIC)/bpsd/bpsd_trsource.o:       $(OBJDIR_PIC)/bpsd/bpsd_subs.o
$(OBJDIR_PIC)/bpsd/bpsd_base.o:           $(OBJDIR_PIC)/bpsd/bpsd_shot.o $(OBJDIR_PIC)/bpsd/bpsd_device.o $(OBJDIR_PIC)/bpsd/bpsd_species.o $(OBJDIR_PIC)/bpsd/bpsd_equ1D.o $(OBJDIR_PIC)/bpsd/bpsd_metric1D.o $(OBJDIR_PIC)/bpsd/bpsd_plasmaf.o $(OBJDIR_PIC)/bpsd/bpsd_trmatrix.o $(OBJDIR_PIC)/bpsd/bpsd_trsource.o

.PHONY: bpsd_pic
bpsd_pic: $(OBJBPSD_PIC)

# Object sets for libtiapi.so. Mirror ti SRCS_CORE + API sources.
OBJ_CORE_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCS_CORE:.f90=.o))
OBJ_API_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCS_API:.f90=.o))

# Graphics stubs that satisfy any residual GUCLIP / PAGES / ... calls
# coming from libpl_pic / libeq_pic without dragging in non-PIC
# libgsp/libg3d. Built only as PIC so it is libtiapi.so-only.
SRCS_GR_STUBS=ti_graphics_stubs.f90
OBJ_GR_STUBS_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCS_GR_STUBS:.f90=.o))

OBJ_LIBTIAPI= $(OBJ_CORE_PIC) $(OBJ_API_PIC) $(OBJ_GR_STUBS_PIC)

# Dependent PIC archives / objects (order: bpsd -> lib (mds/task) ->
# mtxp -> adpost -> adf11 -> pl -> eq, same logical order as the ti
# non-PIC link).
LIBS_PIC=../eq/libeq_pic.a ../pl/libpl_pic.a \
         ../lib/libmds_pic.a ../lib/libtask_pic.a \
         ../open-adas/adf11/adf11-lib/lib-adf11_pic.a \
         ../adpost/lib-adpost_pic.a
LIBMTX_PIC=../mtxp/libmtxnompi_pic.o ../mtxp/libmtxbnd_pic.o

# Build dependent PIC libs on demand (matches the libXX.a recipes above).
../eq/libeq_pic.a:
	(cd ../eq; make libeq_pic.a)
../pl/libpl_pic.a:
	(cd ../pl; make libpl_pic.a)
../lib/libmds_pic.a:
	(cd ../lib; make libmds_pic.a)
../lib/libtask_pic.a:
	(cd ../lib; make libtask_pic.a)
../mtxp/libmtxnompi_pic.o:
	(cd ../mtxp; make libmtxnompi_pic.o)
../mtxp/libmtxbnd_pic.o:
	(cd ../mtxp; make libmtxbnd_pic.o)
../adpost/lib-adpost_pic.a:
	(cd ../adpost; make lib-adpost_pic.a)
../open-adas/adf11/adf11-lib/lib-adf11_pic.a:
	(cd ../open-adas/adf11/adf11-lib; make lib-adf11_pic.a)

# The shared library itself. gfortran drives the link so libgfortran is
# pulled in automatically. --start-group/--end-group resolves any cyclic
# references between eq / pl / bpsd that our non-PIC ti link only avoids
# by listing archives in a careful order.
#
# We deliberately drop $(FLIBS) from the link: those pull in non-PIC
# graphics archives (libg3d/libgsp/libgdp) via GFLIBS. libtiapi.so
# excludes SRCS_GRAPHICS so none of the gsaf calls are reachable;
# leaving GFLIBS in triggers R_X86_64_PC32 relocation errors when ld
# tries to copy non-PIC .text from libg3d-gfc64.a into the .so.
# MDSLIB/LIBLA are unused at our default config (MDSPLUS=nomdsplus.f,
# LAPACK=nolapack.f) so dropping them is safe.
libtiapi.so: $(OBJ_LIBTIAPI) $(OBJBPSD_PIC) $(LIBS_PIC) $(LIBMTX_PIC)
	$(FCFREE) -shared -fPIC -Wl,-soname,libtiapi.so \
	    $(OBJ_LIBTIAPI) $(OBJBPSD_PIC) $(LIBMTX_PIC) \
	    -Wl,--start-group $(LIBS_PIC) -Wl,--end-group \
	    -o libtiapi.so

# ---------------------------------------------------------------------
# Phase L-4: ti_api_check_so
#
# Dynamically loads libtiapi.so via dlopen(), resolves the 5 symbols,
# runs the full init -> set_param -> run -> get_state -> finalize
# cycle, and asserts each return is 0. This exercises the .so exactly
# like a Python ctypes wrapper will at L-5 and is distinct from the
# static ti_api_check binaries which link OBJ_API directly against
# libti.a (same Fortran code, different link path).
# ---------------------------------------------------------------------
TI_API_SO_C=$(TI_API_SMOKE_DIR)/test_run_so.c
TI_API_SO_O=$(TI_API_SMOKE_DIR)/test_run_so.o
TI_API_SO_BIN=$(TI_API_SMOKE_DIR)/test_run_so

$(TI_API_SO_O): $(TI_API_SO_C) ti_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(TI_API_SO_O) $(TI_API_SO_C)

$(TI_API_SO_BIN): $(TI_API_SO_O)
	$(CC) -o $(TI_API_SO_BIN) $(TI_API_SO_O) -ldl

.PHONY: libtiapi_inspect
libtiapi_inspect: libtiapi.so
	@echo "=== file ==="
	@file libtiapi.so
	@echo "=== ldd ==="
	@ldd libtiapi.so
	@echo "=== exported ti_* symbols ==="
	@nm -D libtiapi.so | grep ' T ti_' || true
	@echo "=== undefined symbols (count) ==="
	@nm -D libtiapi.so | grep ' U ' | wc -l
	@echo "=== first 40 undefined ==="
	@nm -D libtiapi.so | grep ' U ' | head -40
	@echo "=== non-libc/gfortran undefined (graphics / external) ==="
	@nm -D libtiapi.so | grep ' U ' | grep -vE '@(GLIBC|GCC|GFORTRAN)' | head -40

.PHONY: tiapi_check_so ti_api_check_so
ti_api_check_so: libtiapi.so $(TI_API_SO_BIN)
	@echo "Phase L-4 ti_api_check_so: dlopen libtiapi.so + full cycle ..."
	@TILIB_PATH=$(CURDIR)/libtiapi.so $(TI_API_SO_BIN)
	@echo "Phase L-4 ti_api_check_so OK"

ticomm.o : ticomm.f90
timain.o : timain.f90 ticomm.f90  timenu.f90
timenu.o : timenu.f90 ticomm.f90
tiinit.o : tiinit.f90 ticomm.f90
tiparm.o : tiparm.f90 ticomm.f90
tiprep.o : tiprep.f90 ticomm.f90 ../adpost/lib-adpost.f90 \
           ../open-adas/adf11/adf11-lib/lib-adf11.f90
tigout.o : tigout.f90 ticomm.f90
tiregress.o : tiregress.f90 ticomm.f90
tiexec.o : tiexec.f90 ticomm.f90 tiregress.f90
ticoef.o : ticoef.f90 ticomm.f90
tisource.o : tisource.f90 ticomm.f90
ticalc.o : ticalc.f90 ticomm.f90
tirecord.o : tirecord.f90 ticomm.f90

# Phase L-2 / L-3 C ABI sources. ti_state is independent of TICOMM;
# ti_param_registry and ti_api pull in TICOMM plus ti_prep / ti_exec.
ti_state.o : ti_state.f90
ti_param_registry.o : ti_param_registry.f90 ticomm.f90 ticomm.o
ti_api.o   : ti_api.f90 ti_state.f90 ti_state.o ti_param_registry.o \
             ticomm.o tiinit.o tiprep.o tiexec.o

nclass/rarray_sum.o : nclass/rarray_sum.f
nclass/rarray_copy.o: nclass/rarray_copy.f
nclass/rarray_zero.o: nclass/rarray_zero.f
nclass/u_erf.o      : nclass/u_erf.f
nclass/u_lu_backsub.o: nclass/u_lu_backsub.f
nclass/u_lu_decomp.o : nclass/u_lu_decomp.f
nclass/write_mod.o   : nclass/write_mod.f
