###
### This Makefile should be located at task/ti/adpost
###
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

.SUFFIXES:
.SUFFIXES: .f .for .f90 .mod .o .a

FFLAGS=$(OFLAGS)
#FFLAGS=$(DFLAGS)

MODINCLUDE= -I./$(MOD) -I../../bpsd/$(MOD) -I../mtxp/$(MOD) -I../lib/$(MOD)

SRCS = lib-adpost.f90

OBJS = $(SRCS:.f90=.o)

LIBS = lib-adpost.a ../lib/libtask.a ../lib/libgrf.a ../../bpsd/libbpsd.a

.f90.o :
	$(FCFREE) $(FFLAGS) -c $< -o $@ $(MODDIR) $(MODINCLUDE)

all : libs test-adpost

lib-adpost.a: $(OBJS)
	$(LD) $(LDFLAGS) $@ $(OBJS)

../../bpsd/libbpsd.a:
	(cd ../../bpsd; make libbpsd.a)
../lib/libtask.a:
	(cd ../lib; make libtask.a)
../lib/libgrf.a:
	(cd ../lib; make libgrf.a)

libs:
	(cd ../../bpsd; make libbpsd.a)
	(cd ../mtxp; make)
	(cd ../lib; make libtask.a)
	(cd ../lib; make libgrf.a)

test-adpost : $(LIBS) test-adpost.o
	$(FLINKER) test-adpost.o $(LIBS) -o $@ $(FFLAGS) $(FLIBS) $(MODDIR) $(MODINCLUDE)  $(LIBX_MTX)

clean:
	-rm -f core *.o *.a ./*~ $(MOD)/*.mod

veryclean: clean
	-rm -f test-adpost

# ---------------------------------------------------------------------
# PIC build (Phase L-4) - opt-in target for libtiapi.so.
# ---------------------------------------------------------------------
OBJDIR_PIC=obj/pic
MODDIR_PIC=mod_pic
PIC_FLAGS=-fPIC -J$(MODDIR_PIC) -I$(MODDIR_PIC)
MODINCLUDE_PIC=-I$(MODDIR_PIC) -I../../bpsd/$(MOD) -I../mtxp/mod_pic -I../lib/mod_pic

OBJS_PIC = $(addprefix $(OBJDIR_PIC)/, $(SRCS:.f90=.o))

$(OBJDIR_PIC)/%.o: %.f90
	@mkdir -p $(OBJDIR_PIC) $(MODDIR_PIC)
	$(FCFREE) $(FFLAGS) $(PIC_FLAGS) -c $< -o $@ $(MODINCLUDE_PIC)

lib-adpost_pic.a: $(OBJS_PIC)
	$(AR) rcs lib-adpost_pic.a $(OBJS_PIC)

clean_pic:
	-rm -rf $(OBJDIR_PIC) $(MODDIR_PIC) lib-adpost_pic.a

lib-adpost.o: lib-adpost.f90
test-adpost.o: test-adpost.f90 lib-adpost.f90
