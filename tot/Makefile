###### $Id$ ###
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

.SUFFIXES:
.SUFFIXES: .f .f90 .mod .o .a

.f.o :
	$(FCFIXED) $(FFLAGS) -c $< -o $@ $(MODDIR) $(MODINCLUDE)
.f90.o :
	$(FCFREE) $(FFLAGS) -cpp $(EXTRA_DEFS) -c $< -o $@ $(MODDIR) $(MODINCLUDE)

MODINCLUDE= -I$(MOD) -I../open-adas/adf11/adf11-lib/$(MOD) \
            -I../adpost/$(MOD) -I../eq/$(MOD) -I../pl/$(MOD) \
            -I../dp/$(MOD) -I../wrx/$(MOD) -I../wmx/$(MOD) \
            -I../fp/$(MOD) -I../ob/$(MOD) \
            -I../tr/$(MOD) -I../ti/$(MOD) \
            -I../mtxp/$(MOD) -I../lib/$(MOD) \
            -I../../bpsd/$(MOD) 

EQLIBS= ../pl/noequlib.o ../eq/libeq.a

# Source layout (logical groups; SRCS still single list for now):
#   SRCS_CORE  : files needed by both `tot` binary and future libtotapi.so
#                (regression dump goes here so library users can also dump).
#   SRCS_MENU  : interactive dispatcher only used by `tot` binary.
#   SRCS_API   : added in L-2 (tot_state.f90, tot_api.f90). Orchestrator
#                stubs. NOT part of $(SRCS); compiled only via the
#                independent `tot_api_check` target so the default
#                `tot` binary has no hard build dependency on any
#                per-module L-2 (tr_state, ti_state, ...).
SRCS_CORE = totregress.f90
SRCS_MENU = totmenu.f90
# Phase L-3: tot_param_registry.f90 is a pure dispatcher that USEs the
# six per-module registries (eq, tr, fp, ti, wrx) and MUST sit between
# tot_state.f90 and tot_api.f90 in dependency order (tot_api USEs
# tot_param_registry).
SRCS_API  = tot_state.f90 tot_param_registry.f90 tot_api.f90
SRCS      = $(SRCS_CORE) $(SRCS_MENU)

OBJS     = $(SRCS:.f90=.o)
OBJ_API  = $(SRCS_API:.f90=.o)

# Phase L-6 (Layer 2 follow-up): static-link C driver targets need
# graphics-symbol stubs that cover the ~100 GSAF primitives the full
# archive chain (libgrf.a + per-module libX.a) references. tot_graphics_
# stubs.f90 (already linked into libtotapi.so) only ships the minimal
# 7-stub safety net; tot_static_stubs.f90 is the orchestrator-level
# union of every static-link-only stub. NOT linked into libtotapi.so —
# only into the four C ABI driver binaries below.
TOT_STATIC_STUBS_OBJ = tot_static_stubs.o

# Phase L-3: per-module param_registry .o files (NOT in the static
# libs, because every per-module Makefile keeps SRCS_API out of its
# libX.a). The tot_api_check link needs them explicitly.
#
# Paths follow each module's OBJDIR convention:
#   tr  : ./obj (OBJDIR)
#   fp  : ./obj (OBJDIR)
#   ti  : flat  (no OBJDIR)
#   wrx : ./obj (OBJDIR) -- tot links wrx/libwr.a, so we route wr:/wrx:
#                           to wrx_param_registry (see tot_param_registry.f90)
#   eq  : flat
TOT_L3_DEPS_OBJ = \
    ../tr/obj/tr_param_registry.o \
    ../fp/obj/fp_param_registry.o \
    ../ti/ti_param_registry.o \
    ../wrx/obj/wrx_param_registry.o \
    ../eq/eq_param_registry.o

# Phase L-6: per-module API .o files. tot_api.f90 now USEs tr_api /
# ti_api / fp_api / wrx_api so the orchestrator lifecycle can fan out
# to each per-module *_api_init / *_api_run / *_api_finalize. Each
# per-module SRCS_API objects are built by the owning Makefile via
# the same delegated sub-makes used for the param_registry .o above.
# Ordering matters: state before param_registry before api (tr_api
# USEs tr_state; similarly for ti/fp/wrx).
TOT_L6_API_OBJ = \
    ../tr/obj/tr_state.o \
    ../tr/obj/tr_api.o \
    ../ti/ti_state.o \
    ../ti/ti_api.o \
    ../fp/obj/fp_state.o \
    ../fp/obj/fp_api.o \
    ../wrx/obj/wrx_state.o \
    ../wrx/obj/wrx_api.o

LIBS = ../lib/libmds.a ../lib/libgrf.a ../lib/libtask.a ../../bpsd/libbpsd.a \
       ../adpost/lib-adpost.a ../open-adas/adf11/adf11-lib/lib-adf11.a \
       ../pl/libpl.a \
       $(EQLIBS) \
       ../tr/libtr2.a ../dp/libdp.a ../wrx/libwr.a ../wmx/libwm.a \
       ../fp/libfp.a ../ob/libob.a ../ti/libti.a


all : libs tot

../open-adas/adf11/adf11-lib/lib-adf11.a:
	(cd ../open-adas/adf11/adf11-lib; make lib-adf11.a)
../adpost/lib-adpost.a:
	(cd ../adpost; make lib-adpost.a)
../lib/libtask.a:
	(cd ../lib; make libtask.a)
../lib/libgrf.a:
	(cd ../lib; make libgrf.a)
../lib/libmds.a:
	(cd ../lib; make libmds.a)
$(LIB_MTX):
	(cd ../mtxp; make)
../../bpsd/libbpsd.a:
	(cd ../../bpsd; make libbpsd.a)
../pl/libpl.a:
	(cd ../pl; make libpl.a)
../pl/noeqlib.o:
	(cd ../pl; make noeqlib.o)
../pl/noequlib.o:
	(cd ../pl; make noequlib.o)
../eq/libeq.a:
	(cd ../eq; make libeq.a)
../tr/libtr2.a:
	(cd ../tr; make libtr2.a)
../dp/libdp.a:
	(cd ../dp; make libdp.a)
../wrx/libwr.a:
	(cd ../wrx; make libwr.a)
../wmx/libwm.a:
	(cd ../wmx; make libwm.a)
../fp/libfp.a:
	(cd ../fp; make libfp.a)
../ob/libob.a:
	(cd ../ob; make libob.a)
../ti/libti.a:
	(cd ../ti; make libti.a)

libs:
	(cd ../../bpsd; make libbpsd.a)
	(cd ../lib; make libtask.a)
	(cd ../lib; make libgrf.a)
	(cd ../lib; make libmds.a)
	(cd ../mtxp; make)
	(cd ../adpost; make lib-adpost.a)
	(cd ../open-adas/adf11/adf11-lib; make lib-adf11.a)
	(cd ../pl; make libpl.a)
	(cd ../pl; make noeqlib.o)
	(cd ../pl; make noequlib.o)
	(cd ../eq; make libeq.a)
	(cd ../tr; make libtr2.a)
	(cd ../dp; make libdp.a)
	(cd ../wrx; make libwr.a)
	(cd ../wmx; make libwm.a)
	(cd ../ob; make libob.a)
	(cd ../fp; make libfp.a)
	(cd ../ti; make libti.a)
	make totmenu.o
	make totregress.o

tot : $(LIB_MTX) $(LIBS) totmenu.o totregress.o totmain.o
	$(FLINKER) totmenu.o totregress.o totmain.o -o $@ $(FFLAGS) $(LIBS) $(FLIBS) $(LIBX_MTX)

# ---------------------------------------------------------------------
# Phase L-3: orchestrator C ABI check (independent of default `tot`)
#
# `make tot_api_check` builds the API objects (tot_state.o,
# tot_param_registry.o, tot_api.o) plus two C drivers linked against
# tot_api.h:
#
#   test_smoke  : init/run/get_state/finalize stubs + dispatcher error
#                 paths (no-prefix, bad-prefix reject -> INVALID)
#   test_param  : namespaced success paths + per-module error paths
#                 (tr:RR, fp:NRMAX, ti:DT, wrx:RF, wr: alias)
#
# The API objects are NOT linked into the `tot` binary; the default
# `tot` target therefore stays byte-for-byte identical with or without
# this target being invoked. SRCS_API is kept out of $(SRCS) for the
# same reason.
#
# tot_param_registry USEs five per-module registries (tr, fp, ti, wrx,
# eq). Those modules keep their SRCS_API objects out of libX.a, so we
# must link each *_param_registry.o explicitly via TOT_L3_DEPS_OBJ;
# the supporting libs (libtr2.a, libeq.a, libfp.a, libti.a,
# wrx/libwr.a, ...) are pulled in after to resolve the indirect
# TRCOMM / PLCOMM / ... symbols those registries touch.
#
# CC defaults to gcc; override on the command line if necessary
# (e.g. `make tot_api_check CC=clang`).
# ---------------------------------------------------------------------
CC ?= gcc
CFLAGS_API ?= -Wall -Wextra -O2

TOT_API_SMOKE_DIR=tests/c_abi
TOT_API_SMOKE_C=$(TOT_API_SMOKE_DIR)/test_smoke.c
TOT_API_SMOKE_O=$(TOT_API_SMOKE_DIR)/test_smoke.o
TOT_API_SMOKE_BIN=$(TOT_API_SMOKE_DIR)/test_smoke

TOT_API_PARAM_C=$(TOT_API_SMOKE_DIR)/test_param.c
TOT_API_PARAM_O=$(TOT_API_SMOKE_DIR)/test_param.o
TOT_API_PARAM_BIN=$(TOT_API_SMOKE_DIR)/test_param

# Libraries the per-module registries transitively depend on. Matches
# the $(LIBS) set used by the `tot` binary link so that references to
# TRCOMM / PLCOMM / EQCOMM / ... from each *_param_registry.o resolve.
TOT_L3_DEPS_LIB = $(LIBS)

# Step 1: header-only C compile (matches the documented user-level check
#         `gcc -Wall -Wextra -c -o test_smoke.o test_smoke.c`).
$(TOT_API_SMOKE_O): $(TOT_API_SMOKE_C) tot_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(TOT_API_SMOKE_O) $(TOT_API_SMOKE_C)
$(TOT_API_PARAM_O): $(TOT_API_PARAM_C) tot_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(TOT_API_PARAM_O) $(TOT_API_PARAM_C)

# Step 2: link each C driver against the API objects + per-module
# param_registry + per-module api/state .o files + backing libs.
# gfortran drives the link so the libgfortran runtime is pulled in
# automatically.
$(TOT_API_SMOKE_BIN): $(TOT_API_SMOKE_O) $(OBJ_API) $(TOT_STATIC_STUBS_OBJ) $(TOT_L3_DEPS_OBJ) $(TOT_L6_API_OBJ) $(TOT_L3_DEPS_LIB)
	$(FLINKER) -o $(TOT_API_SMOKE_BIN) $(TOT_API_SMOKE_O) $(OBJ_API) $(TOT_STATIC_STUBS_OBJ) \
	    $(TOT_L3_DEPS_OBJ) $(TOT_L6_API_OBJ) $(TOT_L3_DEPS_LIB) $(FFLAGS) $(FLIBS) $(LIBX_MTX)
$(TOT_API_PARAM_BIN): $(TOT_API_PARAM_O) $(OBJ_API) $(TOT_STATIC_STUBS_OBJ) $(TOT_L3_DEPS_OBJ) $(TOT_L6_API_OBJ) $(TOT_L3_DEPS_LIB)
	$(FLINKER) -o $(TOT_API_PARAM_BIN) $(TOT_API_PARAM_O) $(OBJ_API) $(TOT_STATIC_STUBS_OBJ) \
	    $(TOT_L3_DEPS_OBJ) $(TOT_L6_API_OBJ) $(TOT_L3_DEPS_LIB) $(FFLAGS) $(FLIBS) $(LIBX_MTX)

# Each per-module registry .o / api .o / state .o is built by the
# owning module's Makefile (part of its SRCS_API target). Delegate so
# that `make tot_api_check` from a clean tree is self-bootstrapping.
../tr/obj/tr_param_registry.o:
	(cd ../tr; make obj/tr_param_registry.o)
../fp/obj/fp_param_registry.o:
	(cd ../fp; make obj/fp_param_registry.o)
../ti/ti_param_registry.o:
	(cd ../ti; make ti_param_registry.o)
../wrx/obj/wrx_param_registry.o:
	(cd ../wrx; make obj/wrx_param_registry.o)
../eq/eq_param_registry.o:
	(cd ../eq; make eq_param_registry.o)

# L-6: per-module api/state .o files.
../tr/obj/tr_state.o:
	(cd ../tr; make obj/tr_state.o)
../tr/obj/tr_api.o:
	(cd ../tr; make obj/tr_api.o)
../ti/ti_state.o:
	(cd ../ti; make ti_state.o)
../ti/ti_api.o:
	(cd ../ti; make ti_api.o)
../fp/obj/fp_state.o:
	(cd ../fp; make obj/fp_state.o)
../fp/obj/fp_api.o:
	(cd ../fp; make obj/fp_api.o)
../wrx/obj/wrx_state.o:
	(cd ../wrx; make obj/wrx_state.o)
../wrx/obj/wrx_api.o:
	(cd ../wrx; make obj/wrx_api.o)

.PHONY: tot_api_check tot_api_compile_check
# A cheaper target that only proves the Fortran side compiles (no
# link of the C drivers). Useful during local iteration.
tot_api_compile_check: $(OBJ_API)
	@echo "Phase L-3 tot_api_compile_check: Fortran API objects built"
	@echo "  $(OBJ_API)"

tot_api_check: $(OBJ_API) $(TOT_API_SMOKE_BIN) $(TOT_API_PARAM_BIN)
	@echo "Phase L-3 tot_api_check: running smoke / param ..."
	@$(TOT_API_SMOKE_BIN)
	@$(TOT_API_PARAM_BIN)
	@echo "Phase L-3 tot_api_check OK:"
	@echo "  - Fortran API objects       : $(OBJ_API)"
	@echo "  - C drivers executed        : test_smoke, test_param"

clean:
	-rm -f core a.out *.o *.mod ./*~ *.a $(MOD)/*.mod
	-rm -f $(TOT_API_SMOKE_O) $(TOT_API_SMOKE_BIN)
	-rm -f $(TOT_API_PARAM_O) $(TOT_API_PARAM_BIN)
	-rm -f $(TOT_API_SO_O) $(TOT_API_SO_BIN)
	-rm -f $(TOT_API_NEG_O) $(TOT_API_NEG_BIN)
	-rm -f $(TOT_API_FULL_O) $(TOT_API_FULL_BIN)

clean_pic:
	-rm -rf $(OBJDIR_PIC) $(MODDIR_PIC) libtotapi.so
	-rm -f $(TOT_API_SO_O) $(TOT_API_SO_BIN)

veryclean: clean
	-rm -f tot

totmain.o: totmain.f90 totregress.o
totmenu.o: totmenu.f90
totregress.o: totregress.f90

# Phase L-2 C ABI sources (independent of any *COMM at this stage).
tot_state.o : tot_state.f90
# Phase L-3: tot_param_registry USEs tr_param_registry, fp_param_registry,
# ti_param_registry, wrx_param_registry, eq_param_registry. Those .mod
# files are produced under ../tr/mod, ../fp/mod, ../ti/mod, ../wrx/mod
# and ../eq/mod respectively (all already on MODINCLUDE). We therefore
# depend on the owning module's libX.a so the .mod files are present
# before this source is compiled.
tot_param_registry.o : tot_param_registry.f90 \
                       ../tr/libtr2.a ../fp/libfp.a ../ti/libti.a \
                       ../wrx/libwr.a ../eq/libeq.a
# tot_api.o USEs tr_api / ti_api / fp_api / wrx_api (in addition to
# tot_state + tot_param_registry). Those .mod files are emitted by
# each per-module Makefile's SRCS_API target into ../<mod>/mod/ — the
# same tree MODINCLUDE already pulls in. Depending on each owner's
# static archive is the cheapest way to force the .mod files to be
# present before this compile step.
tot_api.o   : tot_api.f90 tot_state.f90 tot_state.o tot_param_registry.o \
              ../tr/libtr2.a ../ti/libti.a ../fp/libfp.a ../wrx/libwr.a

# =====================================================================
# Phase L-4: libtotapi.so composite shared library build
#
# tot is the orchestrator; libtotapi.so is the COMPOSITE shared object
# that exposes the 6 tot_* C ABI entry points (tot_init, tot_run,
# tot_set_param, tot_set_param_str, tot_get_state, tot_finalize) and
# transitively re-exports every per-module *_param_set / *_param_set_str
# symbol the dispatcher in tot_param_registry hands off to.
#
# Architecture: instead of rebuilding each per-module's PIC tree in
# tot/, we delegate to each per-module Makefile via sub-make and link
# the produced libXXapi.so / libXX_pic.a archives directly into
# libtotapi.so. The result is a single .so that any Python/C wrapper
# can dlopen() and drive without needing to know the per-module layout.
#
# tot's own PIC objects (totregress, tot_state, tot_param_registry,
# tot_api, tot_graphics_stubs) live under obj/pic/ + mod_pic/ so the
# existing libX.a-based `tot` binary build is untouched.
#
# We use --start-group/--end-group around the per-module .so list so ld
# resolves any cyclic references (eq <-> pl, tr <-> eq, ...) without
# requiring a hand-crafted topological order. We also pass
# --unresolved-symbols=ignore-all because each per-module .so still has
# unresolved graphics symbols on the happy path (handled at runtime by
# RTLD_LAZY); the test_run_so driver dlopen's libtotapi.so with
# RTLD_LAZY for the same reason.
# =====================================================================

OBJDIR_PIC=obj/pic
MODDIR_PIC=mod_pic
PIC_FLAGS=-fPIC -J$(MODDIR_PIC) -I$(MODDIR_PIC)
# tot's PIC compile needs every per-module mod_pic dir on the include
# path: tot_param_registry USEs eq_param_registry / tr_param_registry /
# fp_param_registry / ti_param_registry / wrx_param_registry, and each
# of those .mod files is emitted into its module's mod_pic/ dir by the
# per-module libXXapi.so build (sub-make below).
MODINCLUDE_PIC= -I$(MODDIR_PIC) \
                -I../eq/mod_pic -I../tr/mod_pic -I../fp/mod_pic \
                -I../ti/mod_pic -I../wrx/mod_pic \
                -I../pl/mod_pic -I../lib/mod_pic \
                -I../mtxp/mod_pic \
                -I../../bpsd/$(MOD)

$(OBJDIR_PIC)/%.o: %.f90
	@mkdir -p $(@D) $(MODDIR_PIC)
	$(FCFREE) $(FFLAGS) $(PIC_FLAGS) -c $< -o $@ $(MODINCLUDE_PIC)

# Tot's own PIC objects. totregress is part of SRCS_CORE so library
# users that wire their own dump path can still call it; the four
# api/state/registry objects implement the C ABI surface; the graphics
# stub provides GUCLIP / PAGES no-ops in case any code path inside the
# linked .so list reaches one and the per-module stubs are not picked
# up by ld first.
OBJS_PIC = $(OBJDIR_PIC)/totregress.o \
           $(OBJDIR_PIC)/tot_state.o \
           $(OBJDIR_PIC)/tot_param_registry.o \
           $(OBJDIR_PIC)/tot_api.o \
           $(OBJDIR_PIC)/tot_graphics_stubs.o

# Inter-module PIC dependency order. Mirrors the non-PIC deps above.
$(OBJDIR_PIC)/tot_state.o          : tot_state.f90
$(OBJDIR_PIC)/tot_param_registry.o : tot_param_registry.f90 \
                                     $(OBJDIR_PIC)/tot_state.o \
                                     ../eq/libeqapi.so ../tr/libtrapi.so \
                                     ../fp/libfpapi.so ../ti/libtiapi.so \
                                     ../wrx/libwrxapi.so
$(OBJDIR_PIC)/tot_api.o            : tot_api.f90 \
                                     $(OBJDIR_PIC)/tot_state.o \
                                     $(OBJDIR_PIC)/tot_param_registry.o \
                                     ../tr/libtrapi.so ../ti/libtiapi.so \
                                     ../fp/libfpapi.so ../wrx/libwrxapi.so
$(OBJDIR_PIC)/totregress.o         : totregress.f90
$(OBJDIR_PIC)/tot_graphics_stubs.o : tot_graphics_stubs.f90

# --- bpsd in-tree PIC rebuild (mirrors eq/Makefile L-4) ---
# tot's own PIC objects do not directly USE bpsd (only tot_state +
# tot_api + tot_param_registry + totregress + stubs), but listing the
# bpsd PIC objects keeps a parallel hook available in case future tot
# orchestrator state slots need bpsd types. Currently bpsd PIC objects
# are reached transitively via the per-module .so files, so this block
# stays as a comment-only hook to mirror eq/tr Makefiles' shape.
#
# (Intentionally left blank: bpsd PIC is rebuilt by each per-module
#  sub-make below; tot does not need a second copy.)

# --- Per-module .so prereqs ---
# Each per-module Makefile's libXXapi.so target builds:
#   - the module's own SRCS_CORE + SRCS_API PIC objects under
#     <module>/obj/pic/
#   - the .mod files under <module>/mod_pic/
#   - all transitive PIC archives (libpl_pic.a, libeq_pic.a, ...,
#     libtask_pic.a, libgrf_pic.a, libmds_pic.a, libmtxnompi_pic.o,
#     libmtxbnd_pic.o) and bpsd PIC objects under each module's
#     obj/pic/bpsd/
#
# We delegate to each per-module sub-make so the build order, mod
# emission, and PIC archive shape stay owned by the per-module
# Makefile — tot only needs the final .so.
../eq/libeqapi.so:
	(cd ../eq; $(MAKE) libeqapi.so)
../tr/libtrapi.so:
	(cd ../tr; $(MAKE) libtrapi.so)
../fp/libfpapi.so:
	(cd ../fp; $(MAKE) libfpapi.so)
../ti/libtiapi.so:
	(cd ../ti; $(MAKE) libtiapi.so)
../wrx/libwrxapi.so:
	(cd ../wrx; $(MAKE) libwrxapi.so)

# List of per-module .so files linked into libtotapi.so. We link the
# wrx .so (and not wr/) because tot_param_registry routes BOTH `wr:`
# and `wrx:` prefixes to wrx_param_set (the tot binary likewise links
# wrx/libwr.a, not wr/libwr.a; see tot_param_registry.f90 doc).
LIBS_PIC_SO = ../eq/libeqapi.so ../tr/libtrapi.so ../fp/libfpapi.so \
              ../ti/libtiapi.so ../wrx/libwrxapi.so

# tot's PIC objects must wait until every per-module .so has finished
# building (so the .mod files are present in each mod_pic/ dir before
# tot_param_registry.f90 is compiled).
$(OBJS_PIC): | $(LIBS_PIC_SO)

# --- The composite shared library itself ---
# gfortran drives the link so libgfortran is pulled in automatically.
# --start-group/--end-group resolves any cyclic references between the
# per-module .so files (e.g. eq <-> pl, tr <-> eq, ti <-> fp) without a
# hand-crafted order. --unresolved-symbols=ignore-all leaves any stray
# graphics symbols (PAGES, r2w2b_, ...) that one .so references but
# another doesn't satisfy as deferred to dlopen time. The test_run_so
# driver uses RTLD_LAZY so those are only resolved if actually called,
# which never happens on the
#   tot_init -> tot_set_param(eq:RR) -> tot_set_param(tr:DT) ->
#   tot_get_state -> tot_finalize
# happy path.
#
# We deliberately drop $(FLIBS) from the link: those pull in non-PIC
# graphics archives (libg3d/libgsp/libgdp) via GFLIBS plus MDSLIB+LIBLA.
# libtotapi.so excludes graphics so none of the gsaf calls are
# reachable; leaving GFLIBS in triggers R_X86_64_PC32 relocation errors
# when ld tries to copy non-PIC .text from libg3d-gfc64.a into the .so.
# Platform-aware ld flags. macOS notes:
#   - Apple ld uses -install_name instead of -soname.
#   - Apple ld resolves archive cycles automatically (no group flags).
#   - `-undefined dynamic_lookup` is macOS's counterpart of Linux's
#     --unresolved-symbols=ignore-all (defer to runtime).
#   - `@loader_path/...` is macOS's counterpart of Linux's `$ORIGIN/...`
#     for relative rpath, telling dyld to look in sibling module dirs
#     for libtrapi.so / libeqapi.so / etc.
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
  SO_SONAME = -Wl,-install_name,@rpath/libtotapi.so
  SO_GROUP_BEGIN =
  SO_GROUP_END =
  SO_UNDEFINED = -Wl,-undefined,dynamic_lookup
  SO_RPATH = -Wl,-rpath,@loader_path/../tr -Wl,-rpath,@loader_path/../fp \
             -Wl,-rpath,@loader_path/../ti -Wl,-rpath,@loader_path/../wr \
             -Wl,-rpath,@loader_path/../wrx -Wl,-rpath,@loader_path/../eq
else
  SO_SONAME = -Wl,-soname,libtotapi.so
  SO_GROUP_BEGIN = -Wl,--start-group
  SO_GROUP_END = -Wl,--end-group
  SO_UNDEFINED = -Wl,--unresolved-symbols=ignore-all
  SO_RPATH = -Wl,-rpath,'$$ORIGIN/../tr:$$ORIGIN/../fp:$$ORIGIN/../ti:$$ORIGIN/../wr:$$ORIGIN/../wrx:$$ORIGIN/../eq'
endif

libtotapi.so: $(OBJS_PIC) $(LIBS_PIC_SO)
	$(FCFREE) -shared -fPIC $(SO_SONAME) $(SO_UNDEFINED) $(SO_RPATH) \
	    $(OBJS_PIC) \
	    $(SO_GROUP_BEGIN) $(LIBS_PIC_SO) $(SO_GROUP_END) \
	    -o libtotapi.so

.PHONY: libtotapi_inspect
libtotapi_inspect: libtotapi.so
	@echo "=== file ==="
	@file libtotapi.so
	@echo "=== ldd ==="
	@ldd libtotapi.so
	@echo "=== exported tot_* symbols ==="
	@nm -D libtotapi.so | grep ' T tot_' || true
	@echo "=== undefined symbols (count) ==="
	@nm -D libtotapi.so | grep ' U ' | wc -l
	@echo "=== non-libc/gfortran undefined ==="
	@nm -D libtotapi.so | grep ' U ' | grep -vE '@(GLIBC|GCC|GFORTRAN)' | head -40

# ---------------------------------------------------------------------
# Phase L-4: tot_api_check_so
#
# Dynamically loads libtotapi.so via dlopen(), resolves the 6 symbols,
# and runs an init -> set_param(eq:RR) -> set_param(tr:DT) ->
# get_state -> finalize cycle. tot_init / tot_run / tot_get_state /
# tot_finalize are still L-3 stubs that return TOT_ERR_NOT_IMPL; the
# driver accepts NOT_IMPL on those and asserts OK on tot_set_param.
# ---------------------------------------------------------------------
TOT_API_SO_C=$(TOT_API_SMOKE_DIR)/test_run_so.c
TOT_API_SO_O=$(TOT_API_SMOKE_DIR)/test_run_so.o
TOT_API_SO_BIN=$(TOT_API_SMOKE_DIR)/test_run_so

$(TOT_API_SO_O): $(TOT_API_SO_C) tot_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(TOT_API_SO_O) $(TOT_API_SO_C)

$(TOT_API_SO_BIN): $(TOT_API_SO_O)
	$(CC) -o $(TOT_API_SO_BIN) $(TOT_API_SO_O) -ldl

# LD_LIBRARY_PATH for tot_api_check_so:
# libtotapi.so has NEEDED entries for each per-module .so (libeqapi.so,
# libtrapi.so, libfpapi.so, libtiapi.so, libwrxapi.so) recorded with bare
# soname. We extend LD_LIBRARY_PATH so the dynamic loader can find them
# at dlopen time without requiring an `ldconfig` install step.
TOT_LD_LIBRARY_PATH=$(CURDIR)/../eq:$(CURDIR)/../tr:$(CURDIR)/../fp:$(CURDIR)/../ti:$(CURDIR)/../wrx

.PHONY: tot_api_check_so
tot_api_check_so: libtotapi.so $(TOT_API_SO_BIN)
	@echo "Phase L-4 tot_api_check_so: dlopen libtotapi.so + cycle ..."
	@LD_LIBRARY_PATH=$(TOT_LD_LIBRARY_PATH):$${LD_LIBRARY_PATH} \
	    TOTLIB_PATH=$(CURDIR)/libtotapi.so $(TOT_API_SO_BIN)
	@echo "Phase L-4 tot_api_check_so OK"

# ---------------------------------------------------------------------
# Phase L-6: Layer 2 (C ABI) test suite
#
# Adds a `test_negative` driver that pins the rejection contracts
# (pre-init stubs, unknown namespace, missing prefix, double-finalize,
# post-finalize) on top of the L-3 happy-path coverage in
# test_smoke / test_param. Mirrors eq/tests/c_abi/test_negative.c and
# tr/tests/c_abi/test_negative.c so the orchestrator-level negative
# contracts stay aligned with the per-module L-6 tests.
#
# `tot_api_check_all` wraps tot_api_check + tot_api_check_so + the new
# negative driver in a single CI-friendly target so
# test_run/run_tests.sh can invoke `make -C tot tot_api_check_all` and
# get the full Layer 2 picture from one command.
# ---------------------------------------------------------------------
TOT_API_NEG_C   = $(TOT_API_SMOKE_DIR)/test_negative.c
TOT_API_NEG_O   = $(TOT_API_SMOKE_DIR)/test_negative.o
TOT_API_NEG_BIN = $(TOT_API_SMOKE_DIR)/test_negative

$(TOT_API_NEG_O): $(TOT_API_NEG_C) tot_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(TOT_API_NEG_O) $(TOT_API_NEG_C)

# The negative driver shares the smoke link path — it talks to the
# L-3 dispatcher (for set_param/set_param_str) and the L-6 fan-out
# (for init/run/get_state/finalize) directly via OBJ_API + per-module
# *_param_registry.o + per-module api/state .o + backing libs. No
# dlopen, no libdl.
$(TOT_API_NEG_BIN): $(TOT_API_NEG_O) $(OBJ_API) $(TOT_STATIC_STUBS_OBJ) $(TOT_L3_DEPS_OBJ) $(TOT_L6_API_OBJ) $(TOT_L3_DEPS_LIB)
	$(FLINKER) -o $(TOT_API_NEG_BIN) $(TOT_API_NEG_O) $(OBJ_API) $(TOT_STATIC_STUBS_OBJ) \
	    $(TOT_L3_DEPS_OBJ) $(TOT_L6_API_OBJ) $(TOT_L3_DEPS_LIB) $(FFLAGS) $(FLIBS) $(LIBX_MTX)

# Phase L-6: full-cycle C driver that exercises the new init -> run ->
# get_state -> finalize fan-out via libtotapi.so (static link path, not
# dlopen). Proves the whole orchestrator happy path before we expose it
# to the Python wrappers.
TOT_API_FULL_C   = $(TOT_API_SMOKE_DIR)/test_full_cycle.c
TOT_API_FULL_O   = $(TOT_API_SMOKE_DIR)/test_full_cycle.o
TOT_API_FULL_BIN = $(TOT_API_SMOKE_DIR)/test_full_cycle

$(TOT_API_FULL_O): $(TOT_API_FULL_C) tot_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(TOT_API_FULL_O) $(TOT_API_FULL_C)

$(TOT_API_FULL_BIN): $(TOT_API_FULL_O) $(OBJ_API) $(TOT_STATIC_STUBS_OBJ) $(TOT_L3_DEPS_OBJ) $(TOT_L6_API_OBJ) $(TOT_L3_DEPS_LIB)
	$(FLINKER) -o $(TOT_API_FULL_BIN) $(TOT_API_FULL_O) $(OBJ_API) $(TOT_STATIC_STUBS_OBJ) \
	    $(TOT_L3_DEPS_OBJ) $(TOT_L6_API_OBJ) $(TOT_L3_DEPS_LIB) $(FFLAGS) $(FLIBS) $(LIBX_MTX)

.PHONY: tot_api_check_all
# Composite Layer 2 entry point used by test_run/run_tests.sh. Builds
# and runs every C ABI driver in topological order:
#   tot_api_check    -> test_smoke + test_param  (L-3)
#   tot_api_check_so -> test_run_so via dlopen   (L-4)
#   test_negative                                (L-6)
#   test_full_cycle                              (L-6)
tot_api_check_all: tot_api_check tot_api_check_so $(TOT_API_NEG_BIN) $(TOT_API_FULL_BIN)
	@echo "Phase L-6 tot_api_check_all: running negative tests ..."
	@LD_LIBRARY_PATH=$(TOT_LD_LIBRARY_PATH):$${LD_LIBRARY_PATH} \
	    $(TOT_API_NEG_BIN)
	@echo "Phase L-6 tot_api_check_all: running full-cycle test ..."
	@LD_LIBRARY_PATH=$(TOT_LD_LIBRARY_PATH):$${LD_LIBRARY_PATH} \
	    $(TOT_API_FULL_BIN)
	@echo "Phase L-6 tot_api_check_all OK: smoke / param / run_so / negative / full_cycle"

