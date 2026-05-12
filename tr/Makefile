### Makefile
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

FFLAGS = $(OFLAGS)
#FFLAGS = $(DFLAGS)

OBJDIR=./obj

${OBJDIR}/%.o:%.f
	$(FCFIXED) $(FFLAGS) -c $< -o $@ $(MODDIR) $(MODINCLUDE)
${OBJDIR}/%.o:%.f90
	$(FCFREE) $(FFLAGS) -c $< -o $@ $(MODDIR) $(MODINCLUDE)

MODINCLUDE= -I./$(MOD) -I../pl/$(MOD) -I../eq/$(MOD) \
            -I../lib/$(MOD) -I../mtxp/$(MOD) \
            -I../../bpsd/$(MOD)

SRCM=trcom0.f90 trcom1.f90 \
     trcomm_const.f90 trcomm_param.f90 trcomm_ctrl.f90 \
     trcomm_mtx.f90 trcomm_profile.f90 trcomm_globals.f90 \
     trcomm.f90 trbpsd.f90

# Core computation sources (no graphics, no interactive menu).
# This subset will be linked into libtrapi.so in Phase L-4.
SRCS_CORE=trcdbm.f90 trmodels.f90 \
     trcoef_turbulence.f90 trcoef_neoclassical.f90 \
     trcoef_resistivity.f90 trcoef_adhoc.f90 \
     trinit.f90 trparm.f90 trview.f90 \
     tr_dump_state.f90 \
     trmetric.f90 trprof.f90 trprep.f90 \
     trufsub.f90 tr_ufile_task.f90 tr_ufile_topics.f90 trufile.f90 \
     trfile.f90 trhelp.f90 \
     trrslt_files.f90 \
     trexec.f90 trcalc.f90 \
     tradat.f90 trcoef.f90 tritg.f90 \
     trrslt_globals.f90 trrslt_print.f90 \
     trpnb.f90 trprf.f90 trpnf.f90 trpel.f90 trpsc.f90 trmdlt.f90 \
     trfout.f90 trregress.f90 \
     trloop.f90

# Graphics sources (gsaf/grafix dependent). Excluded from libtrapi.so.
SRCS_GRAPHICS=trgout.f90 trgrar.f90 trgrat.f90 trgrap.f90 trgrae.f90 \
     trgrad.f90 trgram.f90 trgsub.f90

# Interactive menu (only used by the tr2 binary).
SRCS_MENU=trmenu.f90

# C ABI sources (Phase L-2+). Compiled via the tr_api_check target only;
# NOT part of $(SRCS) and NOT linked into libtr2.a / tr2. The full
# libtrapi.so build arrives in Phase L-4.
SRCS_API=tr_state.f90 tr_param_registry.f90 tr_api.f90

SRCS=$(SRCS_CORE) $(SRCS_GRAPHICS) $(SRCS_MENU)

SRC2D=trg2d.f90
SRC3S=trg3d.f90

SRCITG= glf/callglf2d.f \
        itg/ifspppl_model.f itg/weiland.f
SRCITGF=glf/glf2d.F glf/r8tomsqz.F
SRCNC=trncls.f nclass/nclass_mod.f nclass/rarray_sum.f \
      nclass/rarray_copy.f nclass/rarray_zero.f nclass/u_erf.f \
      nclass/u_lu_backsub.f nclass/u_lu_decomp.f nclass/write_mod.f
INCNC=trncls.inc nclass/pamx_mi.inc nclass/pamx_ms.inc nclass/pamx_mz.inc
INCGLF=trglf.inc glf/glf.m
SRCCYT=cytran/cytran_mod.f90 cytran/tr_cytran_mod.f90
SRCMMM95=mmm95/stripx.f mmm95/tomsqz.f mmm95/weiland14.f mmm95/mmm95.f
SRCMMM7=libmmm7_1/w20mod.f90 libmmm7_1/modmmm7_1.f90
SRCMBGB=mbgb/mixed_Bohm_gyro_Bohm.f

OBJM=$(addprefix $(OBJDIR)/, $(SRCM:.f90=.o))
OBJE=$(addprefix $(OBJDIR)/, $(SRCE:.f=.o))
OBJL=$(addprefix $(OBJDIR)/, $(SRCL:.f=.o))
OBJNC=$(addprefix $(OBJDIR)/, $(SRCNC:.f=.o))
OBJCYT=$(addprefix $(OBJDIR)/, $(SRCCYT:.f90=.o))
OBJMMM=$(addprefix $(OBJDIR)/, $(SRCMMM95:.f=.o) $(SRCMMM7:.f90=.o))
OBJMBGB=$(addprefix $(OBJDIR)/, $(SRCMBGB:.f=.o))
OBJITG=$(addprefix $(OBJDIR)/, $(SRCITG:.f=.o) $(SRCITGF:.F=.o))
OBJS=$(addprefix $(OBJDIR)/, $(SRCS:.f90=.o))
OBJ_API=$(addprefix $(OBJDIR)/, $(SRCS_API:.f90=.o))
OBJ2D=$(addprefix $(OBJDIR)/, $(SRC2D:.f90=.o))
OBJ3D=$(addprefix $(OBJDIR)/, $(SRC3D:.f90=.o))

OBJTR=$(OBJM) $(OBJE) $(OBJL) $(OBJNC) $(OBJCYT) $(OBJMMM) \
      $(OBJMBGB) $(OBJITG) $(OBJS)

LIBS=../eq/libeq.a ../pl/libpl.a ../lib/libmds.a ../lib/libtask.a \
     ../lib/libgrf.a  ../../bpsd/libbpsd.a
LIBS2=libtr2.a $(LIBS)
LIBS3=libtr3.a $(LIBS)

#all: libs tr2 tr3
all: libs tr2

libtr2.a: $(OBJTR) $(OBJ2D) $(INCNC) $(INCGLF)
	$(LD) $(LDFLAGS) libtr2.a $(OBJTR) $(OBJ2D)

libtr3.a: $(OBJTR) $(OBJ3D) $(INCNC) $(INCGLF)
	$(LD) $(LDFLAGS) libtr3.a $(OBJTR) $(OBJ3D)

../../bpsd/libbpsd.a:
	(cd ../../bpsd; make libbpsd.a)
../lib/libtask.a:
	(cd ../lib; make libtask.a)
../lib/libgrf.a:
	(cd ../lib; make libgrf.a)
../lib/libmds.a:
	(cd ../lib; make libmds.a)
../pl/libpl.a:
	(cd ../pl; make libpl.a)
../eq/libeq.a:
	(cd ../eq; make libeq.a)

libs:
	(cd ../../bpsd; make libbpsd.a)
	(cd ../lib; make libtask.a)
	(cd ../lib; make libgrf.a)
	(cd ../lib; make libmds.a)
	(cd ../mtxp; make)
	(cd ../pl; make libpl.a)
	(cd ../eq; make libeq.a)

# Issue #197: link tr_static_stubs.o into the standalone `tr2` binary
# when GFLIBS is empty (CI / no-graphics build). Mirrors
# tot/Makefile:64-70 and eq/Makefile's analogous gate.
# Note: tr's compile rule is OBJDIR-prefixed (${OBJDIR}/%.o:%.f90), so
# the stub object lives at $(OBJDIR)/tr_static_stubs.o.
ifeq ($(strip $(GFLIBS)),)
TR_STATIC_STUBS_OBJ = $(OBJDIR)/tr_static_stubs.o
else
TR_STATIC_STUBS_OBJ =
endif

tr2: $(LIBS2) $(OBJDIR)/trmain.o $(TR_STATIC_STUBS_OBJ)
	$(FLINKER) $(OBJDIR)/trmain.o $(TR_STATIC_STUBS_OBJ) $(LIBS2) -o $@ $(FFLAGS) $(FLIBS) $(LIBX_MTX)

tr3: $(LIBS3) $(OBJDIR)/trmain.o
	$(FLINKER) $(OBJDIR)/trmain.o $(LIBS3) -o $@ $(FFLAGS) $(FLIBS) $(LIBX_MTX)

# ---------------------------------------------------------------------
# Phase L-2/L-3: C ABI check
#
# `make tr_api_check` builds the new API objects (tr_state.o,
# tr_param_registry.o, tr_api.o) and three small C drivers linked
# against tr_api.h:
#
#   test_smoke  : 4 entry points return TR_OK           (sanity)
#   test_param  : tr_set_param + tr_get_state dispatch  (L-3)
#   test_run    : tr_run advances T by N*DT             (L-3)
#
# The API objects are NOT linked into libtr2.a / tr2 and the tr2 binary
# remains byte-for-byte identical with or without this target being
# invoked. L-3 drivers depend on libtr2.a (for TRCOMM, tr_loop, ...) so
# we link it in after the API objects. The full libtrapi.so build
# arrives in Phase L-4.
#
# CC defaults to gcc; override on the command line if necessary
# (e.g. `make tr_api_check CC=clang`).
# ---------------------------------------------------------------------
CC ?= gcc
CFLAGS_API ?= -Wall -Wextra -O2

TR_API_SMOKE_DIR=tests/c_abi
TR_API_SMOKE_C=$(TR_API_SMOKE_DIR)/test_smoke.c
TR_API_SMOKE_O=$(TR_API_SMOKE_DIR)/test_smoke.o
TR_API_SMOKE_BIN=$(TR_API_SMOKE_DIR)/test_smoke

TR_API_PARAM_C=$(TR_API_SMOKE_DIR)/test_param.c
TR_API_PARAM_O=$(TR_API_SMOKE_DIR)/test_param.o
TR_API_PARAM_BIN=$(TR_API_SMOKE_DIR)/test_param

TR_API_RUN_C=$(TR_API_SMOKE_DIR)/test_run.c
TR_API_RUN_O=$(TR_API_SMOKE_DIR)/test_run.o
TR_API_RUN_BIN=$(TR_API_SMOKE_DIR)/test_run

# At L-3 the API drivers pull in TRCOMM, tr_loop, tr_prep, ... so we
# need the full tr + eq + pl + bpsd + mtx link just like tr2.
TR_API_DEPS=$(LIBS2) $(LIBX_MTX)

# Step 1: header-only C compile (matches the documented user-level check
#         `gcc -Wall -Wextra -c -o test_smoke.o test_smoke.c`).
$(TR_API_SMOKE_O): $(TR_API_SMOKE_C) tr_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(TR_API_SMOKE_O) $(TR_API_SMOKE_C)
$(TR_API_PARAM_O): $(TR_API_PARAM_C) tr_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(TR_API_PARAM_O) $(TR_API_PARAM_C)
$(TR_API_RUN_O):   $(TR_API_RUN_C)   tr_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(TR_API_RUN_O)   $(TR_API_RUN_C)

# Step 2: link against API objects + tr/eq/pl/bpsd/mtx. gfortran drives
# the link so libgfortran is pulled in automatically.
$(TR_API_SMOKE_BIN): $(TR_API_SMOKE_O) $(OBJ_API) $(LIBS2)
	$(FLINKER) -o $(TR_API_SMOKE_BIN) $(TR_API_SMOKE_O) $(OBJ_API) \
	   $(TR_API_DEPS) $(FFLAGS) $(FLIBS)
$(TR_API_PARAM_BIN): $(TR_API_PARAM_O) $(OBJ_API) $(LIBS2)
	$(FLINKER) -o $(TR_API_PARAM_BIN) $(TR_API_PARAM_O) $(OBJ_API) \
	   $(TR_API_DEPS) $(FFLAGS) $(FLIBS)
$(TR_API_RUN_BIN):   $(TR_API_RUN_O)   $(OBJ_API) $(LIBS2)
	$(FLINKER) -o $(TR_API_RUN_BIN)   $(TR_API_RUN_O)   $(OBJ_API) \
	   $(TR_API_DEPS) $(FFLAGS) $(FLIBS)

.PHONY: tr_api_check
tr_api_check: $(OBJ_API) $(TR_API_SMOKE_BIN) $(TR_API_PARAM_BIN) $(TR_API_RUN_BIN)
	@echo "Phase L-3 tr_api_check: running smoke / param / run ..."
	@$(TR_API_SMOKE_BIN)
	@$(TR_API_PARAM_BIN)
	@$(TR_API_RUN_BIN)
	@echo "Phase L-3 tr_api_check OK:"
	@echo "  - Fortran API objects : $(OBJ_API)"
	@echo "  - C drivers executed  : test_smoke, test_param, test_run"

clean :
	-rm -f ./#* ./*~ $(OBJDIR)/*.o $(OBJDIR)/*/*.o $(MOD)/*.mod $(MOD)/*/*.mod core *.a
	-rm -f $(TR_API_SMOKE_O) $(TR_API_SMOKE_BIN)
	-rm -f $(TR_API_PARAM_O) $(TR_API_PARAM_BIN)
	-rm -f $(TR_API_RUN_O)   $(TR_API_RUN_BIN)
	-rm -f $(TR_API_SO_O)    $(TR_API_SO_BIN)
	-rm -f $(TR_API_NEG_O)   $(TR_API_NEG_BIN)

veryclean : clean
	-rm -f tr2 tr3

distclean: clean
	cd ../pl && make clean
	cd ../eq && make clean
	cd ../lib && make clean

clean_pic:
	-rm -rf $(OBJDIR_PIC) $(MODDIR_PIC) libtrapi.so
	-rm -f $(TR_API_SO_O) $(TR_API_SO_BIN)
	-rm -f $(TR_API_NEG_O) $(TR_API_NEG_BIN)

# =====================================================================
# Phase L-4: libtrapi.so shared library build
#
# Builds a position-independent shared object that exposes the 5 C ABI
# entry points (tr_init, tr_run, tr_set_param, tr_get_state, tr_finalize)
# and links in SRCS_CORE + SRCM + SRCS_API plus all non-graphics
# supporting code (nclass, cytran, mmm95, mmm7_1, mbgb, itg, glf, trncls).
#
# The PIC build is a *separate* tree at obj/pic/ + mod_pic/ so the
# existing non-PIC tr2 build is unaffected. Dependent libraries are
# PIC-rebuilt via opt-in targets added in eq/pl/lib/mtxp Makefiles
# (libeq_pic.a, libpl_pic.a, libtask_pic.a, libmds_pic.a, libgrf_pic.a,
# libmtxnompi_pic.o, libmtxbnd_pic.o).
#
# The bpsd sources live in the parent ../../bpsd/ repo which is outside
# our worktree; we PIC-rebuild bpsd objects in-tree (obj/pic/bpsd/) so
# we don't need to modify bpsd/Makefile.
# =====================================================================

OBJDIR_PIC=obj/pic
MODDIR_PIC=mod_pic
PIC_FLAGS=-fPIC -J$(MODDIR_PIC) -I$(MODDIR_PIC)
MODINCLUDE_PIC= -I./$(MODDIR_PIC) -I../pl/mod_pic -I../eq/mod_pic \
                -I../lib/mod_pic -I../mtxp/mod_pic

# Pattern rules for PIC compilation. Each rule creates its output dir
# on demand so we don't need an explicit mkdir phase.
$(OBJDIR_PIC)/%.o: %.f90
	@mkdir -p $(@D) $(MODDIR_PIC)
	$(FCFREE) $(FFLAGS) $(PIC_FLAGS) -c $< -o $@ $(MODINCLUDE_PIC)
$(OBJDIR_PIC)/%.o: %.f
	@mkdir -p $(@D) $(MODDIR_PIC)
	$(FCFIXED) $(FFLAGS) $(PIC_FLAGS) -c $< -o $@ $(MODINCLUDE_PIC)

# glf has a couple of fixed-form .F sources that need the same -Iglf
# treatment as the non-PIC rules above.
$(OBJDIR_PIC)/glf/callglf2d.o: glf/callglf2d.f glf/glf.m
	@mkdir -p $(@D) $(MODDIR_PIC)
	$(FCFIXED) $(FFLAGS) $(PIC_FLAGS) -c -o $@ -Iglf glf/callglf2d.f
$(OBJDIR_PIC)/glf/glf2d.o: glf/glf2d.F glf/glf.m glf/f77_dcomplx.h
	@mkdir -p $(@D) $(MODDIR_PIC)
	$(FCFIXED) $(FFLAGS) $(PIC_FLAGS) -c -o $@ -Iglf glf/glf2d.F
$(OBJDIR_PIC)/glf/r8tomsqz.o: glf/r8tomsqz.F glf/f77_dcomplx.h
	@mkdir -p $(@D) $(MODDIR_PIC)
	$(FCFIXED) $(FFLAGS) $(PIC_FLAGS) -c -o $@ glf/r8tomsqz.F

# nclass sources use -Inclass for .inc files.
$(OBJDIR_PIC)/nclass/nclass_mod.o: nclass/nclass_mod.f nclass/pamx_mi.inc nclass/pamx_ms.inc nclass/pamx_mz.inc
	@mkdir -p $(@D) $(MODDIR_PIC)
	$(FCFIXED) $(FFLAGS) $(PIC_FLAGS) -c -o $@ -Inclass nclass/nclass_mod.f $(MODINCLUDE_PIC)

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

# Object sets for libtrapi.so. Mirror OBJTR (minus graphics/menu) plus
# the API objects.
OBJM_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCM:.f90=.o))
OBJNC_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCNC:.f=.o))
OBJCYT_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCCYT:.f90=.o))
OBJMMM_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCMMM95:.f=.o) $(SRCMMM7:.f90=.o))
OBJMBGB_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCMBGB:.f=.o))
OBJITG_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCITG:.f=.o) $(SRCITGF:.F=.o))
OBJ_CORE_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCS_CORE:.f90=.o))
OBJ_API_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCS_API:.f90=.o))

# Graphics stubs that satisfy TRGLOB / GUCLIP & friends without dragging
# in non-PIC libgsp/libg3d. Built only as PIC so it is libtrapi.so-only.
SRCS_GR_STUBS=tr_graphics_stubs.f90
OBJ_GR_STUBS_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCS_GR_STUBS:.f90=.o))

OBJ_LIBTRAPI= $(OBJM_PIC) $(OBJNC_PIC) $(OBJCYT_PIC) $(OBJMMM_PIC) \
              $(OBJMBGB_PIC) $(OBJITG_PIC) $(OBJ_CORE_PIC) $(OBJ_API_PIC) \
              $(OBJ_GR_STUBS_PIC)

# Dependent PIC archives / objects (order: bpsd -> lib (mds/task) ->
# mtxp -> pl -> eq, same as the non-PIC tr2 link order).
LIBS_PIC=../eq/libeq_pic.a ../pl/libpl_pic.a \
         ../lib/libmds_pic.a ../lib/libtask_pic.a
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

# The shared library itself. gfortran drives the link so libgfortran is
# pulled in automatically. --start-group/--end-group resolves the cyclic
# references between eq / pl / bpsd that our non-PIC tr2 link only
# avoids by listing archives in a careful order.
#
# We deliberately drop $(FLIBS) from the link: those pull in non-PIC
# graphics archives (libg3d/libgsp/libgdp) via GFLIBS plus MDSLIB+LIBLA.
# libtrapi.so excludes SRCS_GRAPHICS so none of the gsaf calls are
# reachable; leaving GFLIBS in triggers R_X86_64_PC32 relocation errors
# when ld tries to copy non-PIC .text from libg3d-gfc64.a into the .so.
# MDSLIB/LIBLA are unused at our default config (MDSPLUS=nomdsplus.f,
# LAPACK=nolapack.f) so dropping them is safe.
#
# Platform-aware ld flags: Apple ld (macOS) rejects GNU-ld-only flags
# (-soname / --start-group / --end-group) but resolves cycles
# automatically and uses -install_name for the SONAME equivalent.
# `-undefined dynamic_lookup` defers unresolved symbols (e.g. VIEWRTLIST
# from trgrad.f90 in SRCS_GRAPHICS, called from trfout.f90 but never
# actually reached in the libtrapi.so init/run/finalize path) to
# runtime — matching Linux's default behaviour for shared libraries.
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
  SO_SONAME = -Wl,-install_name,@rpath/libtrapi.so
  SO_GROUP_BEGIN =
  SO_GROUP_END =
  SO_UNDEFINED = -Wl,-undefined,dynamic_lookup
else
  SO_SONAME = -Wl,-soname,libtrapi.so
  SO_GROUP_BEGIN = -Wl,--start-group
  SO_GROUP_END = -Wl,--end-group
  SO_UNDEFINED =
endif

libtrapi.so: $(OBJ_LIBTRAPI) $(OBJBPSD_PIC) $(LIBS_PIC) $(LIBMTX_PIC)
	$(FCFREE) -shared -fPIC $(SO_SONAME) $(SO_UNDEFINED) \
	    $(OBJ_LIBTRAPI) $(OBJBPSD_PIC) $(LIBMTX_PIC) \
	    $(SO_GROUP_BEGIN) $(LIBS_PIC) $(SO_GROUP_END) \
	    -o libtrapi.so

# ---------------------------------------------------------------------
# Phase L-4: tr_api_check_so
#
# Dynamically loads libtrapi.so via dlopen(), resolves the 5 symbols,
# runs the full init -> set_param -> run -> get_state -> finalize
# cycle, and asserts each return is 0. This exercises the .so exactly
# like a Python ctypes wrapper will at L-5 and is distinct from the
# static tr_api_check binaries which link OBJ_API directly against
# libtr2.a (same Fortran code, different link path).
# ---------------------------------------------------------------------
TR_API_SO_C=$(TR_API_SMOKE_DIR)/test_run_so.c
TR_API_SO_O=$(TR_API_SMOKE_DIR)/test_run_so.o
TR_API_SO_BIN=$(TR_API_SMOKE_DIR)/test_run_so

$(TR_API_SO_O): $(TR_API_SO_C) tr_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(TR_API_SO_O) $(TR_API_SO_C)

$(TR_API_SO_BIN): $(TR_API_SO_O)
	$(CC) -o $(TR_API_SO_BIN) $(TR_API_SO_O) -ldl

.PHONY: libtrapi_inspect
libtrapi_inspect: libtrapi.so
	@echo "=== file ==="
	@file libtrapi.so
	@echo "=== ldd ==="
	@ldd libtrapi.so
	@echo "=== exported tr_* symbols ==="
	@nm -D libtrapi.so | grep ' T tr_' || true
	@echo "=== undefined symbols (count) ==="
	@nm -D libtrapi.so | grep ' U ' | wc -l
	@echo "=== first 40 undefined ==="
	@nm -D libtrapi.so | grep ' U ' | head -40
	@echo "=== non-libc/gfortran undefined (graphics / external) ==="
	@nm -D libtrapi.so | grep ' U ' | grep -vE '@(GLIBC|GCC|GFORTRAN)' | head -40

.PHONY: tr_api_check_so
tr_api_check_so: libtrapi.so $(TR_API_SO_BIN)
	@echo "Phase L-4 tr_api_check_so: dlopen libtrapi.so + full cycle ..."
	@TRLIB_PATH=$(CURDIR)/libtrapi.so $(TR_API_SO_BIN)
	@echo "Phase L-4 tr_api_check_so OK"

# ---------------------------------------------------------------------
# Phase L-6: Layer 2 (C ABI) test suite
#
# Builds + runs the full C ABI test set in one shot so CI (via
# test_run/run_tests.sh) can invoke a single target. Consists of:
#
#   test_smoke     - 4 entry points return TR_OK          (L-3)
#   test_param     - set_param + get_state dispatch       (L-3)
#   test_run       - tr_run advances T by N*DT            (L-3)
#   test_run_so    - dlopen libtrapi.so + full cycle      (L-4)
#   test_negative  - rejection contracts (L-6, new)
#
# The L-3 trio links against OBJ_API + libtr2.a; the dlopen driver uses
# libdl and loads libtrapi.so at runtime. The negative driver shares
# the L-3 link path.
# ---------------------------------------------------------------------
TR_API_NEG_C=$(TR_API_SMOKE_DIR)/test_negative.c
TR_API_NEG_O=$(TR_API_SMOKE_DIR)/test_negative.o
TR_API_NEG_BIN=$(TR_API_SMOKE_DIR)/test_negative

$(TR_API_NEG_O): $(TR_API_NEG_C) tr_api.h
	$(CC) $(CFLAGS_API) -I. -c -o $(TR_API_NEG_O) $(TR_API_NEG_C)

$(TR_API_NEG_BIN): $(TR_API_NEG_O) $(OBJ_API) $(LIBS2)
	$(FLINKER) -o $(TR_API_NEG_BIN) $(TR_API_NEG_O) $(OBJ_API) \
	   $(TR_API_DEPS) $(FFLAGS) $(FLIBS)

.PHONY: tr_api_check_all
tr_api_check_all: tr_api_check tr_api_check_so $(TR_API_NEG_BIN)
	@echo "Phase L-6 tr_api_check_all: running negative tests ..."
	@$(TR_API_NEG_BIN)
	@echo "Phase L-6 tr_api_check_all OK: smoke/param/run/run_so/negative"

$(OBJDIR)/trcomm_const.o   : trcomm_const.f90
$(OBJDIR)/trcomm_param.o   : trcomm_param.f90 trcomm_const.f90 trcom0.f90
$(OBJDIR)/trcomm_ctrl.o    : trcomm_ctrl.f90 trcom0.f90
$(OBJDIR)/trcomm_mtx.o     : trcomm_mtx.f90 trcom0.f90
$(OBJDIR)/trcomm_profile.o : trcomm_profile.f90 trcom0.f90
$(OBJDIR)/trcomm_globals.o : trcomm_globals.f90 trcom0.f90
$(OBJDIR)/trcomm.o : trcomm.f90 trcom0.f90 trcom1.f90 \
                     trcomm_const.f90 trcomm_param.f90 trcomm_ctrl.f90 \
                     trcomm_mtx.f90 trcomm_profile.f90 trcomm_globals.f90
$(OBJDIR)/trmain.o : trmain.f90 trcomm.f90 $(OBJDIR)/trrslt_print.o
$(OBJDIR)/trmenu.o : trmenu.f90 trcomm.f90 trcom1.f90 $(OBJDIR)/trrslt_files.o $(OBJDIR)/trrslt_print.o
$(OBJDIR)/trinit.o : trinit.f90 trcomm.f90 trcom1.f90
$(OBJDIR)/trparm.o : trparm.f90 trcomm.f90 trcom1.f90
$(OBJDIR)/tr_dump_state.o : tr_dump_state.f90 \
                     trcom0.f90 trcomm_param.f90 trcomm_ctrl.f90 \
                     trcomm_profile.f90 \
                     $(OBJDIR)/trcomm_param.o $(OBJDIR)/trcomm_ctrl.o \
                     $(OBJDIR)/trcomm_profile.o $(OBJDIR)/trcom0.o
$(OBJDIR)/trprep.o : trprep.f90 trcomm.f90 trcom1.f90 \
                     $(OBJDIR)/tr_dump_state.o
$(OBJDIR)/trprof.o : trprof.f90 trcomm.f90 trcom1.f90 trcoef_resistivity.f90
$(OBJDIR)/trmetric.o : trmetric.f90 trcomm.f90 trcom1.f90
$(OBJDIR)/trfile.o : trfile.f90 trcomm.f90 trcom1.f90
$(OBJDIR)/trbpsd.o : trbpsd.f90 trcomm.f90
$(OBJDIR)/tradat.o : tradat.f90 trcomm.f90
$(OBJDIR)/trufile.o : trufile.f90 trcomm.f90 trcom1.f90
$(OBJDIR)/tr_ufile_task.o : tr_ufile_task.f90 trcomm.f90 trcom1.f90
$(OBJDIR)/tr_ufile_topics.o : tr_ufile_topics.f90 trcomm.f90 trcom1.f90
$(OBJDIR)/trufsub.o : trufsub.f90 trcomm.f90 trcom1.f90
$(OBJDIR)/trloop.o : trloop.f90 trcomm.f90 trcom1.f90
$(OBJDIR)/trexec.o : trexec.f90 trcomm.f90 trcom1.f90 trcoef_neoclassical.f90 $(OBJDIR)/trrslt_files.o
$(OBJDIR)/trpl.o : trpl.f90 trcomm.f90 trcom1.f90
$(OBJDIR)/trrslt_globals.o : trrslt_globals.f90 trcomm.f90 $(OBJDIR)/trexec.o
$(OBJDIR)/trrslt_files.o   : trrslt_files.f90 trcomm.f90
$(OBJDIR)/trrslt_print.o   : trrslt_print.f90 trcomm.f90 $(OBJDIR)/trrslt_files.o
$(OBJDIR)/trcalc.o : trcalc.f90 trcomm.f90 trcom1.f90
$(OBJDIR)/trcoef_turbulence.o   : trcoef_turbulence.f90 trcomm.f90 trcdbm.f90 trmodels.f90
$(OBJDIR)/trcoef_neoclassical.o : trcoef_neoclassical.f90 trcomm.f90
$(OBJDIR)/trcoef_resistivity.o  : trcoef_resistivity.f90 trcomm.f90
$(OBJDIR)/trcoef_adhoc.o        : trcoef_adhoc.f90 trcomm.f90
$(OBJDIR)/trcoef.o : trcoef.f90 trcomm.f90 trglf.inc \
                     trcoef_turbulence.f90 trcoef_neoclassical.f90 \
                     trcoef_resistivity.f90 trcoef_adhoc.f90
$(OBJDIR)/trpnb.o  : trpnb.f90  trcomm.f90
$(OBJDIR)/trprf.o  : trprf.f90  trcomm.f90
$(OBJDIR)/trpnf.o  : trpnf.f90  trcomm.f90
$(OBJDIR)/trpel.o  : trpel.f90  trcomm.f90
$(OBJDIR)/trpsc.o  : trpsc.f90  trcomm.f90

# Phase L-2 / L-3 C ABI sources. tr_state is independent of TRCOMM;
# tr_param_registry and tr_api pull in TRCOMM plus tr_prep / tr_loop.
$(OBJDIR)/tr_state.o : tr_state.f90
$(OBJDIR)/tr_param_registry.o : tr_param_registry.f90 trcomm.f90 \
                     $(OBJDIR)/trcomm.o
$(OBJDIR)/tr_api.o   : tr_api.f90 tr_state.f90 \
                     $(OBJDIR)/tr_state.o $(OBJDIR)/tr_param_registry.o \
                     $(OBJDIR)/trcomm.o $(OBJDIR)/trinit.o \
                     $(OBJDIR)/trprep.o $(OBJDIR)/trloop.o

$(OBJDIR)/trgout.o : trgout.f90 trcomm.f90
$(OBJDIR)/trgrar.o : trgrar.f90 trcomm.f90 
$(OBJDIR)/trgrat.o : trgrat.f90 trcomm.f90 trcom1.f90
$(OBJDIR)/trgrap.o : trgrap.f90 trcomm.f90 
$(OBJDIR)/trgrae.o : trgrae.f90 trcomm.f90 
$(OBJDIR)/trgrad.o : trgrad.f90 trcomm.f90 
$(OBJDIR)/trgram.o : trgram.f90 trcomm.f90 trcom1.f90 \
                     trcoef_neoclassical.f90 trcoef_resistivity.f90
$(OBJDIR)/trgsub.o : trgsub.f90 trcomm.f90 
$(OBJDIR)/trhelp.o : trhelp.f90 trcomm.f90 
$(OBJDIR)/trg2d.o  : trg2d.f90  trcomm.f90 
$(OBJDIR)/trg3d.o  : trg3d.f90  trcomm.f90 
$(OBJDIR)/tritg.o  : tritg.f90  trcomm.f90 
$(OBJDIR)/trmodels.o : trmodels.f90  trcomm.f90 
$(OBJDIR)/glf/callglf2d.o : glf/callglf2d.f glf/glf.m
	$(FCFIXED) $(FFLAGS) -c -o $(OBJDIR)/glf/callglf2d.o -Iglf glf/callglf2d.f
$(OBJDIR)/glf/glf2d.o  : glf/glf2d.F glf/glf.m glf/f77_dcomplx.h
	$(FCFIXED) $(FFLAGS) -c -o $(OBJDIR)/glf/glf2d.o -Iglf glf/glf2d.F
$(OBJDIR)/glf/r8tomsqz.o : glf/r8tomsqz.F glf/f77_dcomplx.h
	$(FCFIXED) $(FFLAGS) -c -o $(OBJDIR)/glf/r8tomsqz.o glf/r8tomsqz.F
$(OBJDIR)/glf/zgeev.o  : glf/zgeev.f
$(OBJDIR)/glf/blas_zgeev.o : glf/blas_zgeev.f
$(OBJDIR)/trncls.o : trncls.f90 trncls.inc trcomm.f90 nclass/pamx_mi.inc \
           nclass/pamx_ms.inc nclass/pamx_mz.inc
$(OBJDIR)/nclass/nclass_mod.o : nclass/nclass_mod.f nclass/pamx_mi.inc \
                      nclass/pamx_ms.inc nclass/pamx_mz.inc
	$(FCFIXED) $(FFLAGS) -c -o $(OBJDIR)/nclass/nclass_mod.o -Inclass nclass/nclass_mod.f $(MODDIR) $(MODINCLUDE)
$(OBJDIR)/itg/ifspppl_model.o : itg/ifspppl_model.f
$(OBJDIR)/itg/weiland.o: itg/weiland.f
$(OBJDIR)/nclass/rarray_sum.o : nclass/rarray_sum.f
$(OBJDIR)/nclass/rarray_copy.o: nclass/rarray_copy.f
$(OBJDIR)/nclass/rarray_zero.o: nclass/rarray_zero.f
nclass/u_erf.o      : nclass/u_erf.f
$(OBJDIR)/nclass/u_lu_backsub.o: nclass/u_lu_backsub.f
$(OBJDIR)/nclass/u_lu_decomp.o : nclass/u_lu_decomp.f
$(OBJDIR)/nclass/write_mod.o   : nclass/write_mod.f
$(OBJDIR)/cytran/cytran_mod.o: cytran/cytran_mod.f90
$(OBJDIR)/cytran/tr_cytran_mod.o: cytran/tr_cytran_mod.f90
$(OBJDIR)/mmm95/stripx.o: mmm95/stripx.f
$(OBJDIR)/mmm95/tomsqz.o: mmm95/tomsqz.f
$(OBJDIR)/mmm95/weiland14.: mmm95/weiland14.f
$(OBJDIR)/mmm95/mmm95.o: mmm95/mmm95.f
$(OBJDIR)/libmmm7_1/w20mod.o: libmmm7_1/w20mod.f90
$(OBJDIR)/libmmm7_1/modmmm7_1.o: libmmm7_1/modmmm7_1.f90 libmmm7_1/w20mod.f90
$(OBJDIR)/mbgb/mixed_Bohm_gyro_Bohm.o: mbgb/mixed_Bohm_gyro_Bohm.f
trcdbm.o: trcdbm.f90
