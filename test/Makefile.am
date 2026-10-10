EXTRA_DIST = samples.c \
  BUG-libsndfile-float-level/README \
  BUG-libsndfile-float-level/run \
  BUG-libsndfile-float-level/sox-f32-minus20.caf \
  BUG-libsndfile-float-level/sox-f32-minus20.w64 \
  BUG-libsndfile-float-level/sox-f64-minus20.caf \
  BUG-libsndfile-float-level/sox-f64-minus20.w64

EXTRA_PROGRAMS = wav_size_state_test
wav_size_state_test_SOURCES = wav-size-state.c
wav_size_state_test_CPPFLAGS = -I$(top_srcdir)/src

CLEANFILES = samples$(EXEEXT) samples.o

samples$(EXEEXT): samples.c
	$(CC) -o samples$(EXEEXT) samples.c

check-am: samples$(EXEEXT) wav_size_state_test$(EXEEXT)
	sox=../../src/sox_ng \
	wav_size_state_test='$(abs_builddir)/wav_size_state_test$(EXEEXT)' \
	sh $(srcdir)/check.sh -n

dist-hook:
	rm -f $(distdir)/samples$(EXEEXT) $(distdir)/samples.o
	rm -rf $(distdir)/.deps

# P00 independent DSD test probe: check-dsd builds it explicitly.
# Register it as an optional program so Automake does not generate a second
# check-am recipe; retain the existing wav_size_state_test registration.
# The probe links the configured libtool library instead of guessing codecs.
EXTRA_PROGRAMS += dsd_test_io
dsd_test_io_SOURCES = ../tests/dsd/test_io.c
dsd_test_io_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_io_LDADD = $(top_builddir)/src/libsox_ng.la

# P01 unit tests exercise the actual private writer, with failing I/O wrappers.
EXTRA_PROGRAMS += dsd_test_dff_writer
dsd_test_dff_writer_SOURCES = ../tests/dsd/test_dff_writer.c
dsd_test_dff_writer_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_dff_writer_LDADD = $(top_builddir)/src/libsox_ng.la

# P02 direct effect contract probe, including zero-capacity backpressure.
EXTRA_PROGRAMS += dsd_test_dop_capacity
dsd_test_dop_capacity_SOURCES = ../tests/dsd/test_dop_capacity.c
dsd_test_dop_capacity_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_dop_capacity_LDADD = $(top_builddir)/src/libsox_ng.la

# P03 public seek contract probe: build on demand, not part of check_PROGRAMS.
EXTRA_PROGRAMS += dsd_test_seek_contract
dsd_test_seek_contract_SOURCES = ../tests/dsd/test_seek_contract.c
dsd_test_seek_contract_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_seek_contract_LDADD = $(top_builddir)/src/libsox_ng.la

# P04 layout API contract probe, built by check-dsd without redefining check-am.
EXTRA_PROGRAMS += dsd_test_layout
dsd_test_layout_SOURCES = ../tests/dsd/test_layout.c
dsd_test_layout_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_layout_LDADD = $(top_builddir)/src/libsox_ng.la

# P05 numeric and domain state-machine probe, built only by check-dsd.
EXTRA_PROGRAMS += dsd_test_plan
dsd_test_plan_SOURCES = ../tests/dsd/test_plan.c
dsd_test_plan_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_plan_LDADD = $(top_builddir)/src/libsox_ng.la

# P06 private intermediate scalar decoder; opt-in test binary, not check-am.
EXTRA_PROGRAMS += dsd_test_decode
dsd_test_decode_SOURCES = ../tests/dsd/test_decode.c
dsd_test_decode_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_decode_LDADD = $(top_builddir)/src/libsox_ng.la

# Include production decoder source with deterministic calloc failure injection.
EXTRA_PROGRAMS += dsd_test_decode_faults
dsd_test_decode_faults_SOURCES = ../tests/dsd/test_decode_faults.c
dsd_test_decode_faults_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_decode_faults_LDADD = $(top_builddir)/src/libsox_ng.la

# P07 final SRC + public binary64 decoder contract (opt-in, not generic).
EXTRA_PROGRAMS += dsd_test_p07
dsd_test_p07_SOURCES = ../tests/dsd/test_p07.c
dsd_test_p07_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_p07_LDADD = $(top_builddir)/src/libsox_ng.la

# P07 double SRC numerical exporter for an independent SciPy windowed-sinc test.
EXTRA_PROGRAMS += dsd_test_p07_reference
dsd_test_p07_reference_SOURCES = ../tests/dsd/test_p07_reference.c
dsd_test_p07_reference_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_p07_reference_LDADD = $(top_builddir)/src/libsox_ng.la

# P09 strict profile registry and independent coefficient-bit oracle.
EXTRA_PROGRAMS += dsd_test_p09
dsd_test_p09_SOURCES = ../tests/dsd/test_p09.c
dsd_test_p09_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_p09_LDADD = $(top_builddir)/src/libsox_ng.la
