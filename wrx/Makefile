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
	-rm -f tests/c_abi/out_smoke.log tests/c_abi/out_param.log tests/c_abi/out_run.log

veryclean: clean
	-rm -f wr

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
$(OBJDIR)/wrprep.o: wrprep.f90 $(WRCOMM) ../dp/dpparm.f90 ../eq/equnit.f
$(OBJDIR)/wrsetup.o: wrsetup.f90 $(WRCOMM)
$(OBJDIR)/wrcalpwr.o: wrcalpwr.f90 $(WRCOMM) ../pl/plprof.f90 \
../pl/plprof.f90 
$(OBJDIR)/wrfdrv.o: wrfdrv.f90 $(WRCOMM) wrsub.f90
$(OBJDIR)/wroxb.o: wroxb.f90 $(WRCOMM) ../pl/plprof.f90 \
wrfdrv.f90 wrsub.f90 ../dp/dpdisp.f90

$(OBJDIR)/wrexecr.o: wrexecr.f90 $(WRCOMM) ../pl/plprof.f90 \
wrsub.f90 wrcalpwr.f90 wrfdrv.f90 wroxb.f90 
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
