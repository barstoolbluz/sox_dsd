# Copyright (C) 2006 Reuben Thomas <rrt@sc3d.org>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

## Process this file with automake to produce Makefile.in

ACLOCAL_AMFLAGS = -I m4

SUBDIRS = libdolbyb libebur128 lpc10 libgsm src test
DIST_SUBDIRS = libdolbyb libebur128 lpc10 libgsm src test

RM = rm -f

# man pages are not considered to be sources, so need to add "dist_"
# prefix to ensure they are added to the distribution.
dist_man_MANS = sox_ng.1 soxi_ng.1 soxeffect_ng.7 soxformat_ng.7 \
                libsox_ng.3 libsoxeffect_ng.3 libsoxformat_ng.3
EXTRA_DIST = sox_ng.txt soxi_ng.txt soxeffect_ng.txt soxformat_ng.txt \
             libsox_ng.txt libsoxeffect_ng.txt libsoxformat_ng.txt \
             sox_ng.pdf soxi_ng.pdf soxeffect_ng.pdf soxformat_ng.pdf \
             libsox_ng.pdf libsoxeffect_ng.pdf libsoxformat_ng.pdf \
	     sox_ng.pc.in COPYING AUTHORS INSTALL \
	     README.win32 scripts/batch-example.bat \
	     README.md RULES.md RULES-issues.md RULES-wiki.md \
	     README.sh FEATURES.in test/* issues wiki/*

if HAVE_PKGCONFIG
pkgconfig_DATA = sox_ng.pc
endif

play_ng.1 rec_ng.1: sox_ng.1
	@$(RM) $@ && $(LN_S) $< $@

README: README.sh FEATURES.in
	./README.sh

# Rule for making text man pages.  Uses GNU nroff's -c so not portable.
.1.txt:
	tbl $(srcdir)/$< | LANG=C LC_ALL=C nroff -man -c | sed 's/.\x08//g' > $@
.3.txt:
	tbl $(srcdir)/$< | LANG=C LC_ALL=C nroff -man -c | sed 's/.\x08//g' > $@
.7.txt:
	tbl $(srcdir)/$< | LANG=C LC_ALL=C nroff -man -c | sed 's/.\x08//g' > $@

DOCTXT = sox_ng.txt soxi_ng.txt soxeffect_ng.txt soxformat_ng.txt \
         libsox_ng.txt libsoxeffect_ng.txt libsoxformat_ng.txt README
txt: $(DOCTXT)

# Rule for making PDF man pages
.1.pdf:
	pdfroff -t -man --no-toc-relocation -Tps $(srcdir)/$< > $@
.3.pdf:
	pdfroff -t -man --no-toc-relocation -Tps $(srcdir)/$< > $@
.7.pdf:
	pdfroff -t -man --no-toc-relocation -Tps $(srcdir)/$< > $@

DOCPDF = sox_ng.pdf soxi_ng.pdf soxeffect_ng.pdf soxformat_ng.pdf \
         libsox_ng.pdf libsoxeffect_ng.pdf libsoxformat_ng.pdf
pdf: $(DOCPDF)

install-pdf: pdf
	@$(NORMAL_INSTALL)
	test -z "$(pdfdir)" || $(MKDIR_P) "$(DESTDIR)$(pdfdir)"
	@list='$(DOCPDF)'; for p in $$list; do \
	  if test -f "$$p"; then d=; else d="$(srcdir)/"; fi; \
	  f=$(am__strip_dir) \
	  echo " $(INSTALL_DATA) '$$d$$p' '$(DESTDIR)$(pdfdir)/$$f'"; \
	  $(INSTALL_DATA) "$$d$$p" "$(DESTDIR)$(pdfdir)/$$f"; \
	  done

uninstall-pdf:
	@$(NORMAL_UNINSTALL)
	@list='$(DOCPDF)'; for p in $$list; do \
	  f=$(am__strip_dir) \
	  echo " $(RM) '$(DESTDIR)$(pdfdir)/$$f'"; \
	  $(RM) "$(DESTDIR)$(pdfdir)/$$f"; \
	  done

clean-local:
	$(RM) -r -f cmake_install.cmake CMakeFiles */CMakeFiles CMakeCache.txt

distclean-local:
	$(RM) mingw32-config.cache
	$(RM) -r -f soxpng

CLEANFILES = $(DOCTXT) $(DOCPDF) README

# Rule for making HTML man pages
#
# Get rid on unneeded Content-Type, man directory and manpage index in extension.
# e.g. ../man1/soxi_ng.1.html becomes ../soxi_ng.html
# Return to Main Contents and link to man2html are also modified.
FIXHTML = sed 's,<head>,&<link rel="stylesheet" href="http://sox.sourceforge.net/pub/skins/sox/sox.css" type="text/css"></link>,' 

.1.html:
	groff -t -man -Thtml -P -Dsoxpng $(srcdir)/$< | $(FIXHTML) > $@
.3.html:
	groff -t -man -Thtml -P -Dsoxpng $(srcdir)/$< | $(FIXHTML) > $@
.7.html:
	groff -t -man -Thtml -P -Dsoxpng $(srcdir)/$< | $(FIXHTML) > $@

DOCHTML = sox_ng.html soxi_ng.html soxeffect_ng.html soxformat_ng.html \
          libsox_ng.html libsoxeffect_ng.html libsoxformat_ng.html
html: $(DOCHTML)

install-html: html 	 
	@$(NORMAL_INSTALL) 	 
	test -z "$(htmldir)/soxpng" || $(MKDIR_P) "$(DESTDIR)$(htmldir)/soxpng"
	@list='$(DOCHTML)'; for p in $$list; do \
	if test -f "$$p"; then d=; else d="$(srcdir)/"; fi; \
	f=$(am__strip_dir) \
	echo " $(INSTALL_DATA) '$$d$$p' '$(DESTDIR)$(htmldir)//$$f'"; \
	$(INSTALL_DATA) "$$d$$p" "$(DESTDIR)$(htmldir)/$$f"; \
	done; \
	@for p in soxpng/*; do \
	if test -f "$$p"; then d=; else d="$(srcdir)"; fi; \
	f=$(am__strip_dir) \
	echo " $(INSTALL_DATA) '$$d$$p' '$(DESTDIR)$(htmldir)/soxpng/$$f'"; \
	$(INSTALL_DATA) "$$d$$p" "$(DESTDIR)$(htmldir)/soxpng/$$f"; \
	done

uninstall-html: 	 
	@$(NORMAL_UNINSTALL)
	@list='$(DOCHTML)'; for p in $$list; do \
	f=$(am__strip_dir) \
	echo " $(RM) '$(DESTDIR)$(htmldir)/$$f'"; \
	$(RM) "$(DESTDIR)$(htmldir)/$$f"; \
	done; \
	$(RM) -fr "$(DESTDIR)$(htmldir)/soxpng";

DISTCLEANFILES = $(DOCHTML) $(DOCPDF)
MAINTAINERCLEANFILES = $(DOCTXT)

install-data-hook:
	@if test "$(PLAYRECLINKS)" = "yes"; then	\
	    cd $(DESTDIR)$(mandir)/man1 && $(RM) play_ng.1 && $(LN_S) sox_ng.1 play_ng.1; \
	    cd $(DESTDIR)$(mandir)/man1 && $(RM) rec_ng.1 && $(LN_S) sox_ng.1 rec_ng.1; \
	fi
	@if test "$(REPLACE)" = "yes"; then \
		cd $(DESTDIR)$(mandir)/man1 && $(RM) sox.1 && $(LN_S) sox_ng.1 sox.1; \
		cd $(DESTDIR)$(mandir)/man3 && $(RM) libsox.3 && $(LN_S) libsox_ng.3 libsox.3; \
		cd $(DESTDIR)$(mandir)/man3 && $(RM) libsoxeffect.3 && $(LN_S) libsoxeffect_ng.3 libsoxeffect.3; \
		cd $(DESTDIR)$(mandir)/man3 && $(RM) libsoxformat.3 && $(LN_S) libsoxformat_ng.3 libsoxformat.3; \
		cd $(DESTDIR)$(mandir)/man7 && $(RM) soxeffect.7 && $(LN_S) soxeffect_ng.7 soxeffect.7; \
		cd $(DESTDIR)$(mandir)/man7 && $(RM) soxformat.7 && $(LN_S) soxformat_ng.7 soxformat.7; \
		if test "$(PLAYRECLINKS)" = "yes"; then	\
			cd $(DESTDIR)$(mandir)/man1 && $(RM) play.1 rec.1 && \
			    $(LN_S) play_ng.1 play.1 && \
			    $(LN_S) rec_ng.1 rec.1; \
		fi; \
		if test "$(SYMLINKS)" = "yes"; then \
			cd $(DESTDIR)$(mandir)/man1 && $(RM) soxi.1 && \
			    $(LN_S) soxi_ng.1 soxi.1; \
		fi; \
		if test "$(pkgconfigdir)"; then \
			cd $(DESTDIR)$(pkgconfigdir); \
			$(RM) "sox.pc"; $(LN_S) sox_ng.pc sox.pc; \
		fi; \
	fi

uninstall-hook:
	@if test "$(PLAYRECLINKS)" = "yes"; then	\
		$(RM) $(DESTDIR)$(mandir)/man1/play_ng.1; \
		$(RM) $(DESTDIR)$(mandir)/man1/rec_ng.1; \
	fi
	@if test "$(REPLACE)" = "yes"; then \
		$(RM) $(DESTDIR)$(mandir)/man1/sox.1; \
		$(RM) $(DESTDIR)$(mandir)/man3/libsox.3; \
		$(RM) $(DESTDIR)$(mandir)/man3/libsoxeffect.3; \
		$(RM) $(DESTDIR)$(mandir)/man3/libsoxformat.3; \
		$(RM) $(DESTDIR)$(mandir)/man7/soxformat.7; \
		$(RM) $(DESTDIR)$(mandir)/man7/soxeffect.7; \
		if test "$(PLAYRECLINKS)" = "yes"; then	\
			$(RM) $(DESTDIR)$(mandir)/man1/play.1; \
			$(RM) $(DESTDIR)$(mandir)/man1/rec.1; \
		fi; \
		if test "$(SYMLINKS)" = "yes"; then \
			$(RM) $(DESTDIR)$(mandir)/man1/soxi.1; \
		fi; \
		if test "$(pkgconfigdir)"; then \
			cd $(DESTDIR)$(pkgconfigdir); \
			$(RM) "sox.pc"; \
		fi; \
	fi

# Automatically update libtool script if it gets out-of-date
libtool: $(LIBTOOL_DEPS)
	$(SHELL) ./config.status --recheck

winexe-prepare:
	test -d mxe || git clone https://github.com/mxe/mxe
	rm -f *.tar.gz
	$(MAKE) -s dist
	cp sox_ng-*.tar.gz mxe/pkg/
	sed "/_VERSION *:= /s/:=.*/:= $(PACKAGE_VERSION)/" sox_ng.mk | \
	sed '/_CHECKSUM *:= /s/:=.*/:= '\
"`sha256sum sox_ng-*.tar.gz | sed 's/[ \t].*//'`"/ > mxe/src/sox_ng.mk

win32.exe: winexe-prepare
	cd mxe && make MXE_TARGETS=i686-w64-mingw32.static sox_ng
	cp mxe/usr/i686-w64-mingw32.static/bin/sox_ng.exe win32.exe

win64.exe: winexe-prepare
	cd mxe && make MXE_TARGETS=x86_64-w64-mingw32.static sox_ng
	cp mxe/usr/x86_64-w64-mingw32.static/bin/sox_ng.exe win64.exe

# P00 and subsequent DSD phases use one runner and one named make target.
# The original 'make check' target is unchanged.
.PHONY: check-dsd
DSD_PHASE ?= P02
DSD_RESULTS ?= $(abs_builddir)/tests/dsd/results/$(DSD_PHASE)
check-dsd: all
	$(MAKE) -C test dsd_test_io$(EXEEXT)
	$(MAKE) -C test dsd_test_dff_writer$(EXEEXT)
	python3 $(srcdir)/tests/dsd/run.py --phase $(DSD_PHASE) --results $(DSD_RESULTS) --sox $(abs_builddir)/src/sox_ng --probe $(abs_builddir)/test/dsd_test_io$(EXEEXT) --writer-unit $(abs_builddir)/test/dsd_test_dff_writer$(EXEEXT)
	@if test "$(DSD_PHASE)" = "P02"; then \
	  $(MAKE) -C test dsd_test_dop_capacity$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_dop_capacity$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/test_streaming.py \
	    --probe $(abs_builddir)/test/dsd_test_io$(EXEEXT) \
	    --sox $(abs_builddir)/src/sox_ng \
	    --results $(DSD_RESULTS)/streaming; \
	fi
# P00 distributable design/test inputs (generated raw runs live in the continuation archive).
EXTRA_DIST += \
  docs/dsd/BASELINE.md docs/dsd/DSD_DESIGN.md docs/dsd/DSD_HANDOFF.md \
  docs/dsd/IMPLEMENTATION_PLAN.md docs/dsd/README.md docs/dsd/evidence/README.md \
  docs/dsd/evidence/autoreconf.log docs/dsd/evidence/build.log docs/dsd/evidence/candidate_filter_coefficients.npz \
  docs/dsd/evidence/configure.log docs/dsd/evidence/environment.json docs/dsd/evidence/filter_feasibility.json \
  docs/dsd/evidence/make-check.log docs/dsd/evidence/probe_filters.py docs/dsd/evidence/probe_io.c \
  docs/dsd/evidence/probe_remodulation.py docs/dsd/evidence/probe_sdm.c docs/dsd/evidence/remodulation_level.json \
  docs/dsd/evidence/replay_sdm_probe.py docs/dsd/evidence/reproduce.py docs/dsd/evidence/reproductions.json \
  docs/dsd/evidence/sdm_short_stress.json docs/dsd/handoffs/P00.md docs/dsd/handoffs/P00_CHECKPOINT.txt \
  docs/dsd/phase_manifest.json docs/dsd/sows/P00.md docs/dsd/sows/P01.md \
  docs/dsd/sows/P02.md docs/dsd/sows/P03.md docs/dsd/sows/P04.md \
  docs/dsd/sows/P05.md docs/dsd/sows/P06.md docs/dsd/sows/P07.md \
  docs/dsd/sows/P08.md docs/dsd/sows/P09.md docs/dsd/sows/P10.md \
  docs/dsd/sows/P11.md docs/dsd/sows/P12.md docs/dsd/sows/P13.md \
  docs/dsd/sows/P14.md docs/dsd/sows/P15.md docs/dsd/sows/P16.md \
  docs/dsd/sows/P17.md docs/dsd/sows/P18.md tests/dsd/README.md \
  tests/dsd/bench.py tests/dsd/fixtures/block_minus_1.dsf tests/dsd/fixtures/block_plus_1.dsf \
  tests/dsd/fixtures/dop_stereo_1.pcm24le tests/dsd/fixtures/dop_stereo_15.pcm24le tests/dsd/fixtures/dop_stereo_16.pcm24le \
  tests/dsd/fixtures/dop_stereo_17.pcm24le tests/dsd/fixtures/dop_stereo_32.pcm24le tests/dsd/fixtures/dop_stereo_33.pcm24le \
  tests/dsd/fixtures/empty.dsf tests/dsd/fixtures/five_16.dff tests/dsd/fixtures/five_96.dsf \
  tests/dsd/fixtures/four_16.dff tests/dsd/fixtures/manifest.json tests/dsd/fixtures/mono_128_manf.dff \
  tests/dsd/fixtures/mono_16.dff tests/dsd/fixtures/mono_16.wsd tests/dsd/fixtures/mono_32_dop.dsf \
  tests/dsd/fixtures/mono_9.dff tests/dsd/fixtures/mono_96.dsf tests/dsd/fixtures/msb_stereo_96.dsf \
  tests/dsd/fixtures/nine.dsf tests/dsd/fixtures/one.dsf tests/dsd/fixtures/one_cluster.dff \
  tests/dsd/fixtures/pcm_sine_352800.wav tests/dsd/fixtures/pcm_sine_705600.wav tests/dsd/fixtures/pcm_sine_88200.wav \
  tests/dsd/fixtures/seven.dsf tests/dsd/fixtures/six_16.dff tests/dsd/fixtures/six_96.dsf \
  tests/dsd/fixtures/stereo_128.dff tests/dsd/fixtures/stereo_32.wsd tests/dsd/fixtures/stereo_96.dsf \
  tests/dsd/fixtures/type4_quad_96.dsf tests/dsd/fixtures/type5_quad_96.dsf tests/dsd/measure.py \
  tests/dsd/reference/__init__.py tests/dsd/reference/fixtures.py tests/dsd/reference/metrology.py \
  tests/dsd/reference/verify.py tests/dsd/run.py tests/dsd/test_io.c \
  tests/dsd/test_dff_writer.c tests/dsd/reference/writer.py \
  tests/dsd/fixtures/p01_writer_vectors.json tests/dsd/bench_dff.py \
  docs/dsd/handoffs/P01.md docs/dsd/handoffs/P01_CHECKPOINT.md \
  tests/dsd/BENCHMARKING.md tests/dsd/benchprep.sh \
  tests/dsd/test_streaming.py tests/dsd/test_dop_capacity.c \
  tests/dsd/bench_read_p02.py docs/dsd/handoffs/P02.md \
  docs/dsd/handoffs/P02_CHECKPOINT.md
