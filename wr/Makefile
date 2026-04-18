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

veryclean: clean
	-rm -f wr

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
