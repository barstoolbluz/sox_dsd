EXTRA_DIST = samples.c run_check_staged.py \
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

samples$(EXEEXT): $(srcdir)/samples.c
	$(CC) -o samples$(EXEEXT) $(srcdir)/samples.c

# Legacy BUG/CVE tests write output into their working directories.  A
# source-tree invocation fails with immutable/VPATH sources.  Stage fixture
# copies under the build directory so all cases execute with writable scratch
# space, while references such as ../../src/monkey.wav still resolve.
check-am: samples$(EXEEXT) wav_size_state_test$(EXEEXT)
	python3 '$(abs_srcdir)/run_check_staged.py' \
	  --source-test '$(abs_srcdir)' \
	  --source-monkey '$(abs_top_srcdir)/src/monkey.wav' \
	  --build-test '$(abs_builddir)' \
	  --sox '$(abs_top_builddir)/src/sox$(EXEEXT)' \
	  --samples '$(abs_builddir)/samples$(EXEEXT)' \
	  --wav-size-state-test '$(abs_builddir)/wav_size_state_test$(EXEEXT)'

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

# P15 source-bound stage coefficients/clock dump (test-only; no production API).
EXTRA_PROGRAMS += dsd_test_p15_src_stage_export
dsd_test_p15_src_stage_export_SOURCES = ../tests/dsd/test_p15_src_stage_export.c
dsd_test_p15_src_stage_export_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_p15_src_stage_export_LDADD = $(top_builddir)/src/libsox_ng.la

# P09 strict profile registry and independent coefficient-bit oracle.
EXTRA_PROGRAMS += dsd_test_p09
dsd_test_p09_SOURCES = ../tests/dsd/test_p09.c ../src/sdm.c
dsd_test_p09_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_p09_LDADD = $(top_builddir)/src/libsox_ng.la

# P10 private candidate renderer and streaming/overload contracts.
EXTRA_PROGRAMS += dsd_test_p10
# Compile the unmodified private SDM implementation into this uninstalled
# test executable. Those symbols are deliberately hidden from the shared
# libsox_ng ABI, while this test needs to call them directly. This works
# with shared-only, static-only and combined builds without exporting SDM.
dsd_test_p10_SOURCES = ../tests/dsd/test_p10.c ../src/sdm.c
dsd_test_p10_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_p10_LDADD = $(top_builddir)/src/libsox_ng.la

# P11 executable mocked CPUID and real per-ISA FIR/SDM contract tests.
# Rate-aware auto dispatch and scalar-bitwise equivalence regression.
EXTRA_PROGRAMS += dsd_test_sdm_auto
dsd_test_sdm_auto_SOURCES = ../tests/dsd/test_sdm_auto.c ../src/sdm.c
dsd_test_sdm_auto_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_sdm_auto_LDADD = $(top_builddir)/src/libsox_ng.la

EXTRA_PROGRAMS += dsd_test_p11
dsd_test_p11_SOURCES = ../tests/dsd/test_p11.c ../src/sdm.c
dsd_test_p11_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_p11_LDADD = $(top_builddir)/src/libsox_ng.la

# Explicit, uninstalled qualification CLI, supported on GNU-linker hosts.
# Never substitutes for the production binary or its fail-closed certificate.
EXTRA_PROGRAMS += sox_p10_candidate
sox_p10_candidate_SOURCES = ../src/sox_ng.c ../tests/dsd/p10_candidate_cli.c
sox_p10_candidate_CPPFLAGS = -I$(top_srcdir)/src
sox_p10_candidate_LDFLAGS = -Wl,--wrap=lsx_pcmdsd_qualified -Wl,--wrap=lsx_pcmdsd_start
sox_p10_candidate_LDADD = $(top_builddir)/src/libsox_ng.la

# P12 protected-page exact FIR span validation (POSIX; clean UNRUN elsewhere).
EXTRA_PROGRAMS += dsd_test_p12_bounds
dsd_test_p12_bounds_SOURCES = ../tests/dsd/test_p12_bounds.c
dsd_test_p12_bounds_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_p12_bounds_LDADD = $(top_builddir)/src/libsox_ng.la

# P13 masked AVX-512F exact-span FIR and eight-coordinate SDM executable gate.
EXTRA_PROGRAMS += dsd_test_p13
dsd_test_p13_SOURCES = ../tests/dsd/test_p13.c ../src/sdm.c
dsd_test_p13_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_p13_LDADD = $(top_builddir)/src/libsox_ng.la

# P14 native-bit invariant and fifth-order SOS numerical probe.
EXTRA_PROGRAMS += dsd_test_p14
dsd_test_p14_SOURCES = ../tests/dsd/test_p14.c
dsd_test_p14_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_p14_LDADD = $(top_builddir)/src/libsox_ng.la

# Optional investigation executable: -pg at LINK only. Optimized production
# objects are not instrumented; gprof -Q reads samples without call counts.
# Requires a GNU-compatible profiling toolchain. Not part of the release build.
EXTRA_PROGRAMS += sox_dsd_profile
sox_dsd_profile_SOURCES = ../src/sox_ng.c
sox_dsd_profile_CPPFLAGS = -I$(top_srcdir)/src
sox_dsd_profile_LDFLAGS = -pg
sox_dsd_profile_LDADD = $(top_builddir)/src/libsox_ng.la

# Fixed-order production half-band and public streaming/count regression.
EXTRA_PROGRAMS += dsd_test_decode_optimization
dsd_test_decode_optimization_SOURCES = ../tests/dsd/test_decode_optimization.c
dsd_test_decode_optimization_CPPFLAGS = -I$(top_srcdir)/src -DDSD_OPTIMIZATION=1
dsd_test_decode_optimization_LDADD = $(top_builddir)/src/libsox_ng.la

# P15 independent numerical matrix: production public F64 output exporter.
# Qualification-only; no executable reference mathematics in this C probe.
EXTRA_PROGRAMS += dsd_test_p15_instrument
dsd_test_p15_instrument_SOURCES = ../tests/dsd/test_p15_instrument.c
dsd_test_p15_instrument_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_p15_instrument_LDADD = $(top_builddir)/src/libsox_ng.la

# P17 private high-rate decimator/SDM candidate tests; no writer interface.
EXTRA_PROGRAMS += dsd_test_p17
dsd_test_p17_SOURCES = ../tests/dsd/test_p17.c ../src/sdm.c
dsd_test_p17_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_p17_LDADD = $(top_builddir)/src/libsox_ng.la

# P16 optional borrowed packed reader and same-FIR finite parity matrix.
EXTRA_PROGRAMS += dsd_test_p16
dsd_test_p16_SOURCES = ../tests/dsd/test_p16.c
dsd_test_p16_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_p16_LDADD = $(top_builddir)/src/libsox_ng.la

# P18 capability-matrix and checked uint64 accounting, high rates disabled.
EXTRA_PROGRAMS += dsd_test_p18
dsd_test_p18_SOURCES = ../tests/dsd/test_p18.c
dsd_test_p18_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_p18_LDADD = $(top_builddir)/src/libsox_ng.la

# P17 qualification-only full-file DSF probe; production read gate stays shut.
EXTRA_PROGRAMS += dsd_test_p17_dsf
dsd_test_p17_dsf_SOURCES = ../tests/dsd/p17_dsf_probe.c
dsd_test_p17_dsf_CPPFLAGS = -I$(top_srcdir)/src
dsd_test_p17_dsf_LDADD = $(top_builddir)/src/libsox_ng.la
