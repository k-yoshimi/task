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

FFLAGS=$(OFLAGS)
#FFLAGS=$(DFLAGS)

OBJDIR=./obj

MODINCLUDE=-I$(MOD) -I../eq/$(MOD) -I../mtxp/$(MOD) \
           -I../lib/$(MOD) -I../../bpsd/$(MOD)

${OBJDIR}/%.o:%.f
	$(FCFIXED) $(FFLAGS) -c $< -o $@ $(MODDIR) $(MODINCLUDE)
${OBJDIR}/%.o:%.f90
	$(FCFREE) $(FFLAGS) -c $< -o $@ $(MODDIR) $(MODINCLUDE)

SRCS_NOEQ = plvmec.f90 plcomm.f90 plinit.f90 plparm.f90 \
            platmd.f90 plcoll.f90 \
            plprof_TOTAL.f90 plprof_travis.f90 plload.f90 plprep.f90

SRCS_EQ=plprof2d.f90 \
     plprof.f90 plprofw.f90  \
     plgout.f90 plmenu.f90


OBJS_NOEQ=$(addprefix $(OBJDIR)/, $(SRCS_NOEQ:.f90=.o))
OBJS_EQ=$(addprefix $(OBJDIR)/, $(SRCS_EQ:.f90=.o))

LIBS = libpl.a ../eq/libeq.a ../lib/libgrf.a ../lib/libtask.a ../../bpsd/libbpsd.a

all : libs pl

../../bpsd/libbpsd.a:
	(cd ../../bpsd; make libbpsd.a)
../lib/libtask.a:
	(cd ../lib; make libtask.a)
../lib/libgrf.a:
	(cd ../lib; make libgrf.a)
../eq/libeq.a:
	(cd ../eq; make libeq.a)

libpl.a: $(OBJS_NOEQ) $(OBJS_EQ)
	$(LD) $(LDFLAGS) libpl.a $(OBJS_NOEQ)
	(cd ../eq; make clean; make libeq.a)
	$(LD) $(LDFLAGS) libpl.a $(OBJS_EQ)

libs:
	(cd ../../bpsd; make libbpsd.a)
	(cd ../lib; make libtask.a)
	(cd ../lib; make libgrf.a)
	(cd ../mtxp; make)

pl : libs $(LIB_MTX) libpl.a $(OBJDIR)/plmain.o
	$(FLINKER) $(OBJDIR)/plmain.o $(LIBS) -o $@ $(FFLAGS) $(FLIBS) $(LIBX_MTX)

clean:
	-rm -f core a.out *.o $(OBJDIR)/*.o *.mod ./*~ ./#* *.a $(MOD)/*.mod

veryclean: clean
	-rm -f pl

# ---------------------------------------------------------------------
# PIC build (Phase L-4) - opt-in target for libtiapi.so / libtrapi.so.
# ---------------------------------------------------------------------
OBJDIR_PIC=obj/pic
MODDIR_PIC=mod_pic
PIC_FLAGS=-fPIC -J$(MODDIR_PIC) -I$(MODDIR_PIC)
MODINCLUDE_PIC=-I$(MODDIR_PIC) -I../eq/mod_pic -I../mtxp/mod_pic -I../lib/mod_pic -I../../bpsd/$(MOD)

OBJS_NOEQ_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCS_NOEQ:.f90=.o))
# libtiapi.so / libtrapi.so exclude graphics; plgout/plmenu pull in
# libgrf/gsaf calls so we drop them from libpl_pic.a. plprof/plprofw/
# plprof2d only touch plcomm/plload, keeping those is safe.
SRCS_EQ_NOGR = plprof2d.f90 plprof.f90 plprofw.f90
OBJS_EQ_PIC=$(addprefix $(OBJDIR_PIC)/, $(SRCS_EQ_NOGR:.f90=.o))

${OBJDIR_PIC}/%.o:%.f
	@mkdir -p $(OBJDIR_PIC) $(MODDIR_PIC)
	$(FCFIXED) $(FFLAGS) $(PIC_FLAGS) -c $< -o $@ $(MODINCLUDE_PIC)
${OBJDIR_PIC}/%.o:%.f90
	@mkdir -p $(OBJDIR_PIC) $(MODDIR_PIC)
	$(FCFREE) $(FFLAGS) $(PIC_FLAGS) -c $< -o $@ $(MODINCLUDE_PIC)

# Note: libpl.a's recipe runs (cd ../eq && make clean; make libeq.a)
# between the two ar steps to break a cyclic dependency. For the PIC
# variant we expose the NOEQ half as a separate target so the caller
# (ti/Makefile / tr/Makefile) can build it first, then build eq_pic,
# then come back for libpl_pic.a.
libpl_noeq_pic: $(OBJS_NOEQ_PIC)
libpl_pic.a: $(OBJS_NOEQ_PIC) $(OBJS_EQ_PIC)
	$(AR) rcs libpl_pic.a $(OBJS_NOEQ_PIC) $(OBJS_EQ_PIC)

clean_pic:
	-rm -rf $(OBJDIR_PIC) $(MODDIR_PIC) libpl_pic.a

$(OBJDIR)/plvmec.o: plvmec.f90 ../../bpsd/bpsd_kinds.f90 ../../bpsd/bpsd_constants.f90
$(OBJDIR)/plcomm.o: plcomm.f90 ../../bpsd/bpsd_kinds.f90 ../../bpsd/bpsd_constants.f90
$(OBJDIR)/plinit.o: plinit.f90 plcomm.f90
$(OBJDIR)/plparm.o: plparm.f90 plcomm.f90
$(OBJDIR)/plprep.o: plprep.f90 plcomm.f90
$(OBJDIR)/platmd.o: platmd.f90 plcomm.f90
$(OBJDIR)/plcoll.o: plcoll.f90 plcomm.f90 platmd.f90
$(OBJDIR)/plload.o: plload.f90 plcomm.f90
$(OBJDIR)/plprep.o: plprep.f90 plcomm.f90
$(OBJDIR)/plprof_TOTAL.o: plprof_TOTAL.f90 plcomm.f90
$(OBJDIR)/plprof_travis.o: plprof_travis.f90 plcomm.f90
$(OBJDIR)/plprof2d.o: plprof2d.f90 plcoll.f90 plload.f90 plcomm.f90
$(OBJDIR)/plprof.o: plprof.f90 plcomm.f90 plload.f90 \
          plprof2d.f90 plcoll.f90 plprof_travis.f90
$(OBJDIR)/plprofw.o: plprofw.f90 plcomm.f90 plprof.f90
$(OBJDIR)/plgout.o: plgout.f90 plcomm.f90 plprof.f90
$(OBJDIR)/plmenu.o: plmenu.f90 plcomm.f90 plparm.f90 plgout.f90 plload.f90 plvmec.f90
$(OBJDIR)/plmain.o: plmain.f90 plcomm.f90 plinit.f90 plparm.f90 plmenu.f90
