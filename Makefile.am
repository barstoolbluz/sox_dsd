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
dist_man_MANS = sox.1 soxi.1 soxeffect_ng.7 soxformat_ng.7 \
                libsox_ng.3 libsoxeffect_ng.3 libsoxformat_ng.3
EXTRA_DIST = sox.txt soxi.txt soxeffect_ng.txt soxformat_ng.txt libsox_ng.txt \
  libsoxeffect_ng.txt libsoxformat_ng.txt sox.pdf soxi.pdf soxeffect_ng.pdf soxformat_ng.pdf \
  libsox_ng.pdf libsoxeffect_ng.pdf libsoxformat_ng.pdf ltmain.sh compile missing install-sh \
  config.guess config.sub sox_ng.pc.in sox_dsd.mk COPYING AUTHORS INSTALL README.win32 \
  scripts/batch-example.bat README.md RULES.md RULES-issues.md RULES-wiki.md \
  docs/UPSTREAM.md tests/sync/test_url_process.py tests/sync/test_p10_path.py \
  tests/sync/test_p16_p18_path.py tests/sync/test_waveaudio_teardown.py README.sh \
  FEATURES.in test/* issues $(wildcard wiki/*) tests/rename_smoke.sh \
  tests/dsd/checks/test_cli_usability.py tests/dsd/checks/test_loud_encode.py \
  tests/dsd/checks/test_release_111.py tests/dsd/checks/test_unified_decode_111.py \
  tests/dsd/checks/test_111_receipt_redaction.py tests/dsd/qualification/sanitize_111_real_track_receipts.py \
  tests/dsd/release_evidence/v1_high_rate_real_tracks_redacted.jsonl \
  tests/dsd/release_evidence/v1_high_rate_soak_launcher.log \
  tests/dsd/qualification/review_111_evidence.py tests/dsd/phases/p21_independent_reader.py \
  tests/dsd/checks/test_reader_gate.py tests/dsd/phases/p17_media_qualification.py \
  tests/dsd/support/fake_decoder.py tests/dsd/support/fake_p17_probe.py tests/dsd/support/mutation-shim.py \
  tests/dsd/qualification/review_p21_offsets.py tests/dsd/checks/test_p21_reader_regression.py \
  tests/dsd/checks/test_one_encoder_111.py \
  tests/dsd/checks/test_mastering_coefficients_111.py \
  tests/dsd/checks/test_mastering_baseline_identity_111.py \
  docs/dsd/USING_SOX_DSD.md \
  docs/dsd/CLI_USABILITY_DESIGN.md docs/dsd/RELEASE_NOTES_1.1.1.md \
  docs/dsd/UNIFIED_DECODER_2026-11-09.md docs/dsd/NOISE_SHAPER_BENCH_2026-11-07.md

# Repository cleanup tools are distributed beside the evidence archive, not in-tree.

if HAVE_PKGCONFIG
pkgconfig_DATA = sox_ng.pc
endif

play.1 rec.1: sox.1
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

DOCTXT = sox.txt soxi.txt soxeffect_ng.txt soxformat_ng.txt \
         libsox_ng.txt libsoxeffect_ng.txt libsoxformat_ng.txt README
txt: $(DOCTXT)

# Rule for making PDF man pages
.1.pdf:
	pdfroff -t -man --no-toc-relocation -Tps $(srcdir)/$< > $@
.3.pdf:
	pdfroff -t -man --no-toc-relocation -Tps $(srcdir)/$< > $@
.7.pdf:
	pdfroff -t -man --no-toc-relocation -Tps $(srcdir)/$< > $@

DOCPDF = sox.pdf soxi.pdf soxeffect_ng.pdf soxformat_ng.pdf \
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
# e.g. ../man1/soxi.1.html becomes ../soxi.html
# Return to Main Contents and link to man2html are also modified.
FIXHTML = sed 's,<head>,&<link rel="stylesheet" href="http://sox.sourceforge.net/pub/skins/sox/sox.css" type="text/css"></link>,' 

.1.html:
	groff -t -man -Thtml -P -Dsoxpng $(srcdir)/$< | $(FIXHTML) > $@
.3.html:
	groff -t -man -Thtml -P -Dsoxpng $(srcdir)/$< | $(FIXHTML) > $@
.7.html:
	groff -t -man -Thtml -P -Dsoxpng $(srcdir)/$< | $(FIXHTML) > $@

DOCHTML = sox.html soxi.html soxeffect_ng.html soxformat_ng.html \
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

# These commands use the same implementation, dispatched by argv[0].
# Keep the old _ng entry points for existing users; plain names are canonical.
install-data-hook:
	@if test "$(PLAYRECLINKS)" = "yes"; then \
		cd $(DESTDIR)$(mandir)/man1 && \
		$(RM) play.1 rec.1 play_ng.1 rec_ng.1 && \
		$(LN_S) sox.1 play.1 && $(LN_S) sox.1 rec.1 && \
		$(LN_S) sox.1 play_ng.1 && $(LN_S) sox.1 rec_ng.1; \
	fi
	@if test "$(SYMLINKS)" = "yes"; then \
		cd $(DESTDIR)$(mandir)/man1 && \
		$(RM) sox_ng.1 soxi_ng.1 && \
		$(LN_S) sox.1 sox_ng.1 && $(LN_S) soxi.1 soxi_ng.1; \
	fi
	@if test "$(REPLACE)" = "yes"; then \
		cd $(DESTDIR)$(mandir)/man3 && $(RM) libsox.3 && $(LN_S) libsox_ng.3 libsox.3; \
		cd $(DESTDIR)$(mandir)/man3 && $(RM) libsoxeffect.3 && $(LN_S) libsoxeffect_ng.3 libsoxeffect.3; \
		cd $(DESTDIR)$(mandir)/man3 && $(RM) libsoxformat.3 && $(LN_S) libsoxformat_ng.3 libsoxformat.3; \
		cd $(DESTDIR)$(mandir)/man7 && $(RM) soxeffect.7 && $(LN_S) soxeffect_ng.7 soxeffect.7; \
		cd $(DESTDIR)$(mandir)/man7 && $(RM) soxformat.7 && $(LN_S) soxformat_ng.7 soxformat.7; \
		if test "$(pkgconfigdir)"; then \
			cd $(DESTDIR)$(pkgconfigdir); \
			$(RM) "sox.pc"; $(LN_S) sox_ng.pc sox.pc; \
		fi; \
	fi

uninstall-hook:
	@if test "$(PLAYRECLINKS)" = "yes"; then \
		$(RM) $(DESTDIR)$(mandir)/man1/play.1 $(DESTDIR)$(mandir)/man1/rec.1 \
			$(DESTDIR)$(mandir)/man1/play_ng.1 $(DESTDIR)$(mandir)/man1/rec_ng.1; \
	fi
	@if test "$(SYMLINKS)" = "yes"; then \
		$(RM) $(DESTDIR)$(mandir)/man1/sox_ng.1 $(DESTDIR)$(mandir)/man1/soxi_ng.1; \
	fi
	@if test "$(REPLACE)" = "yes"; then \
		$(RM) $(DESTDIR)$(mandir)/man3/libsox.3; \
		$(RM) $(DESTDIR)$(mandir)/man3/libsoxeffect.3; \
		$(RM) $(DESTDIR)$(mandir)/man3/libsoxformat.3; \
		$(RM) $(DESTDIR)$(mandir)/man7/soxformat.7; \
		$(RM) $(DESTDIR)$(mandir)/man7/soxeffect.7; \
		if test "$(pkgconfigdir)"; then \
			cd $(DESTDIR)$(pkgconfigdir); \
			$(RM) "sox.pc"; \
		fi; \
	fi

# Automatically update libtool script if it gets out-of-date
libtool: $(LIBTOOL_DEPS)
	$(SHELL) ./config.status --recheck

# MXE consumes a *local SoX DSD* dist tarball. Never substitute upstream
# SoX-NG: that would silently ship a different program without our DSD work.
winexe-prepare:
	test -d mxe || git clone https://github.com/mxe/mxe
	$(MAKE) -s dist
	cp "$(PACKAGE)-$(VERSION).tar.gz" mxe/pkg/
	sed '/_VERSION *:= /s/:=.*/:= $(PACKAGE_VERSION)/' sox_dsd.mk | \
	sed '/_CHECKSUM *:= /s/:=.*/:= '\
"`sha256sum "$(PACKAGE)-$(VERSION).tar.gz" | sed 's/[ \t].*//'`"/ > mxe/src/sox_dsd.mk

win32.exe: winexe-prepare
	cd mxe && make MXE_TARGETS=i686-w64-mingw32.static sox_dsd
	cp mxe/usr/i686-w64-mingw32.static/bin/sox.exe win32.exe

win64.exe: winexe-prepare
	cd mxe && make MXE_TARGETS=x86_64-w64-mingw32.static sox_dsd
	cp mxe/usr/x86_64-w64-mingw32.static/bin/sox.exe win64.exe

# A small rename-only smoke test independent of the historical DSD gate.
.PHONY: check-rename
check-rename: all
	$(LIBTOOL) --mode=execute -dlopen $(abs_builddir)/src/libsox_ng.la \
	  $(SHELL) $(srcdir)/tests/rename_smoke.sh $(abs_builddir)/src "$(SYMLINKS)" "$(PLAYRECLINKS)"

# Release-facing command/format acceptance independent of historic phase gates.
# Uses independently generated PCM and DSD test material; no music files needed.
.PHONY: check-dsd-cli
check-dsd-cli: all
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$(abs_srcdir)/tests/dsd" \
	  python3 "$(abs_srcdir)/tests/dsd/checks/test_cli_usability.py" \
	  --sox "$(abs_builddir)/src/sox"
	$(MAKE) check-dsd-loud-encode
	$(MAKE) check-dsd-release-111

# Deterministic strict-mode regression including actual high-rate runtimes.
.PHONY: check-dsd-release-111
check-dsd-release-111: all
	PYTHONDONTWRITEBYTECODE=1 python3 "$(abs_srcdir)/tests/dsd/checks/test_release_111.py" \
	  --sox "$(abs_builddir)/src/sox"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(abs_srcdir)/tests/dsd/checks/test_one_encoder_111.py" \
	  --sox "$(abs_builddir)/src/sox"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(abs_srcdir)/tests/dsd/checks/test_mastering_coefficients_111.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(abs_srcdir)/tests/dsd/checks/test_unified_decode_111.py" \
	  --sox "$(abs_builddir)/src/sox"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(abs_srcdir)/tests/dsd/checks/test_111_receipt_redaction.py"

# Standalone loud-master acceptance; no dependency on historical receipts.
.PHONY: check-dsd-loud-encode
check-dsd-loud-encode: all
	PYTHONDONTWRITEBYTECODE=1 python3 "$(abs_srcdir)/tests/dsd/checks/test_loud_encode.py" \
	  --sox "$(abs_builddir)/src/sox"

# Long-running loud guard regression, deliberately opt-in rather than part
# of the quick loud encode acceptance or unrelated legacy SoX tests.
.PHONY: check-dsd-loud-guard
check-dsd-loud-guard: all
	PYTHONDONTWRITEBYTECODE=1 python3 "$(abs_srcdir)/tests/dsd/checks/test_loud_guard.py" \
	  --sox "$(abs_builddir)/src/sox"

# P00 and subsequent DSD phases use one runner and one named make target.
# The original 'make check' target is unchanged.
.PHONY: check-dsd
DSD_PHASE ?= P18
# Phase gates write receipts. Keep new runs outside the versioned historical
# evidence directory; callers may still choose a different location with
# DSD_RESULTS=... for comparison or archival qualification.
DSD_RESULTS ?= $(abs_builddir)/.dsd-check-results/$(DSD_PHASE)
check-dsd: all
	$(MAKE) check-dsd-optimization
	$(MAKE) check-sdm-guard-policy
	@if ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ); then \
	  $(MAKE) -C test dsd_test_p14$(EXEEXT); \
	fi
	@if ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  $(MAKE) -C test dsd_test_p10$(EXEEXT) sox_p10_candidate$(EXEEXT); \
	fi
	@if test "$(DSD_PHASE)" = "P06" || test "$(DSD_PHASE)" = "P07" || test "$(DSD_PHASE)" = "P08" || test "$(DSD_PHASE)" = "P09" || ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  python3 -c 'import mpmath, numpy, scipy' || { \
	    echo "UNRUN: required P06/P07 numerical gate (mpmath/numpy/scipy not installed)" >&2; exit 2; }; \
	fi
	$(MAKE) -C test dsd_test_io$(EXEEXT)
	$(MAKE) -C test dsd_test_dff_writer$(EXEEXT)
	@if test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18"; then \
	  $(MAKE) -C test dsd_test_p16$(EXEEXT) || exit $$?; \
	fi
	@if test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18"; then \
	  $(MAKE) -C test dsd_test_p17$(EXEEXT) || exit $$?; \
	fi
	@if test "$(DSD_PHASE)" = "P18"; then \
	  $(MAKE) -C test dsd_test_p18$(EXEEXT) || exit $$?; \
	fi
	python3 $(srcdir)/tests/dsd/run.py --phase $(DSD_PHASE) --results $(DSD_RESULTS) --sox $(abs_builddir)/src/sox --probe $(abs_builddir)/test/dsd_test_io$(EXEEXT) --writer-unit $(abs_builddir)/test/dsd_test_dff_writer$(EXEEXT) --p10-unit $(abs_builddir)/test/dsd_test_p10$(EXEEXT) --p16-unit $(abs_builddir)/test/dsd_test_p16$(EXEEXT) --p17-unit $(abs_builddir)/test/dsd_test_p17$(EXEEXT) --p18-unit $(abs_builddir)/test/dsd_test_p18$(EXEEXT)
	@if test "$(DSD_PHASE)" = "P02" || test "$(DSD_PHASE)" = "P03" || test "$(DSD_PHASE)" = "P04" || test "$(DSD_PHASE)" = "P05" || test "$(DSD_PHASE)" = "P06" || test "$(DSD_PHASE)" = "P07" || test "$(DSD_PHASE)" = "P08" || test "$(DSD_PHASE)" = "P09" || ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  $(MAKE) -C test dsd_test_dop_capacity$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_dop_capacity$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/checks/test_streaming.py \
	    --probe $(abs_builddir)/test/dsd_test_io$(EXEEXT) \
	    --sox $(abs_builddir)/src/sox \
	    --results $(DSD_RESULTS)/streaming; \
	fi
	@if test "$(DSD_PHASE)" = "P03" || test "$(DSD_PHASE)" = "P04" || test "$(DSD_PHASE)" = "P05" || test "$(DSD_PHASE)" = "P06" || test "$(DSD_PHASE)" = "P07" || test "$(DSD_PHASE)" = "P08" || test "$(DSD_PHASE)" = "P09" || ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  $(MAKE) -C test dsd_test_seek_contract$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/checks/test_seek.py \
	    --probe $(abs_builddir)/test/dsd_test_seek_contract$(EXEEXT) \
	    --sox $(abs_builddir)/src/sox \
	    --results $(DSD_RESULTS)/seek; \
	fi
	@if test "$(DSD_PHASE)" = "P04" || test "$(DSD_PHASE)" = "P05" || test "$(DSD_PHASE)" = "P06" || test "$(DSD_PHASE)" = "P07" || test "$(DSD_PHASE)" = "P08" || test "$(DSD_PHASE)" = "P09" || ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  $(MAKE) -C test dsd_test_layout$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/checks/test_layout.py \
	    --unit $(abs_builddir)/test/dsd_test_layout$(EXEEXT) \
	    --sox $(abs_builddir)/src/sox \
	    --results $(DSD_RESULTS)/layout; \
	fi
	@if test "$(DSD_PHASE)" = "P05" || test "$(DSD_PHASE)" = "P06" || test "$(DSD_PHASE)" = "P07" || test "$(DSD_PHASE)" = "P08" || test "$(DSD_PHASE)" = "P09" || ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  $(MAKE) -C test dsd_test_plan$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_plan$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/checks/test_plan.py \
	    --sox $(abs_builddir)/src/sox \
	    --results $(DSD_RESULTS)/plan; \
	fi
	@if test "$(DSD_PHASE)" = "P06" || test "$(DSD_PHASE)" = "P07" || test "$(DSD_PHASE)" = "P08" || test "$(DSD_PHASE)" = "P09" || ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  $(MAKE) -C test dsd_test_decode$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_decode$(EXEEXT) && \
	  $(MAKE) -C test dsd_test_decode_faults$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_decode_faults$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/checks/test_decode.py \
	    --unit $(abs_builddir)/test/dsd_test_decode$(EXEEXT) \
	    --results $(DSD_RESULTS)/scalar; \
	fi

	@if test "$(DSD_PHASE)" = "P07" || test "$(DSD_PHASE)" = "P08" || test "$(DSD_PHASE)" = "P09" || ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  $(MAKE) -C test dsd_test_p07$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_p07$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/checks/test_p07.py \
	    --sox $(abs_builddir)/src/sox \
	    --results $(DSD_RESULTS)/integration && \
	  python3 $(srcdir)/tests/dsd/checks/test_p07_output_failures.py \
	    --sox $(abs_builddir)/src/sox \
	    --results $(DSD_RESULTS)/output-errors && \
	  $(MAKE) -C test dsd_test_p07_reference$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/checks/test_p07_reference.py \
	    --unit $(abs_builddir)/test/dsd_test_p07_reference$(EXEEXT) \
	    --results $(DSD_RESULTS)/numeric && \
	  python3 $(srcdir)/tests/dsd/checks/test_p07_composite.py \
	    --unit $(abs_builddir)/test/dsd_test_p07_reference$(EXEEXT) \
	    --results $(DSD_RESULTS)/numeric && \
	  python3 $(srcdir)/tests/dsd/checks/test_p07_impulse.py \
	    --unit $(abs_builddir)/test/dsd_test_p07_reference$(EXEEXT) \
	    --results $(DSD_RESULTS)/numeric && \
	  python3 $(srcdir)/tests/dsd/checks/test_p07_public_rate.py \
	    --sox $(abs_builddir)/src/sox; \
	fi

	@if test "$(DSD_PHASE)" = "P08" || test "$(DSD_PHASE)" = "P09" || ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  python3 $(srcdir)/tests/dsd/checks/test_p08.py \
	    --sox $(abs_builddir)/src/sox \
	    --results $(DSD_RESULTS)/integration; \
	fi

# P00 distributable design/test inputs (generated raw runs live in the continuation archive).
	@if test "$(DSD_PHASE)" = "P09" || ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  $(MAKE) -C test dsd_test_p09$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/checks/test_p09.py \
	    --unit $(abs_builddir)/test/dsd_test_p09$(EXEEXT) \
	    --results $(DSD_RESULTS)/unit && \
	  python3 $(srcdir)/tests/dsd/reference/analysis-v1/verify.py \
	    --results $(DSD_RESULTS)/numeric; \
	fi

	@if ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ); then \
	  $(MAKE) -C test dsd_test_host_isa$(EXEEXT) dsd_test_p11$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_host_isa$(EXEEXT) --self-test && \
	  $(abs_builddir)/test/dsd_test_host_isa$(EXEEXT) --tiers >/dev/null && \
	  $(abs_builddir)/test/dsd_test_p11$(EXEEXT) && \
	  if test "$(DSD_PHASE)" = "P11"; then \
	    tiers=$$($(abs_builddir)/test/dsd_test_host_isa$(EXEEXT) --tiers) || exit $$?; \
	    p11_tiers=scalar; \
	    case " $$tiers " in *" sse2 "*) p11_tiers="$$p11_tiers sse2";; esac; \
	    case " $$tiers " in *" avx1 "*) p11_tiers="$$p11_tiers avx1";; esac; \
	    python3 $(srcdir)/tests/dsd/checks/test_p11_numeric.py \
	      --phase P11 --tiers $$p11_tiers \
	      --unit $(abs_builddir)/test/dsd_test_p11$(EXEEXT) \
	      --results $(DSD_RESULTS)/numeric; \
	  fi; \
	fi

# P12: execute only host-supported tiers. Always build and audit ISA objects;
# the host probe fails when the CPU can run a tier but the build cannot.
	@if test "$(DSD_PHASE)" = "P12"; then \
	  tiers=$$($(abs_builddir)/test/dsd_test_host_isa$(EXEEXT) --tiers) || exit $$?; \
	  p12_tiers=$${tiers% avx512}; \
	  channels="scalar"; \
	  case " $$tiers " in *" avx2 "*) channels="scalar avx2";; esac; \
	  $(MAKE) -C test dsd_test_p12_bounds$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_p12_bounds$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/checks/test_p11_integration.py \
	    --phase P12 --tiers $$p12_tiers \
	    --sox $(abs_builddir)/src/sox \
	    --candidate $(abs_builddir)/test/sox_p10_candidate \
	    --results $(DSD_RESULTS)/forced-cli && \
	  python3 $(srcdir)/tests/dsd/checks/test_p12_channels.py \
	    --tiers $$channels \
	    --sox $(abs_builddir)/src/sox \
	    --candidate $(abs_builddir)/test/sox_p10_candidate \
	    --results $(DSD_RESULTS)/channels && \
	  python3 $(srcdir)/tests/dsd/checks/test_p11_numeric.py \
	    --phase P12 --tiers $$p12_tiers \
	    --unit $(abs_builddir)/test/dsd_test_p11$(EXEEXT) \
	    --results $(DSD_RESULTS)/cross-isa && \
	  if grep -q '^#define HAVE_DSD_AVX2 1' $(abs_builddir)/src/soxconfig.h; then \
	    python3 $(srcdir)/tests/dsd/qualification/check_p12_isa.py \
	      --build-root $(abs_builddir) --results $(DSD_RESULTS)/isa; \
	  elif grep -q '^#define HAVE_DSD_AVX1 1' $(abs_builddir)/src/soxconfig.h; then \
	    echo 'SKIP P12 AVX2 object ISA audit: compiler did not build tier'; \
	    python3 $(srcdir)/tests/dsd/qualification/check_p11_isa.py \
	      --build-root $(abs_builddir) --results $(DSD_RESULTS)/isa; \
	  else \
	    echo 'SKIP P12 x86 SIMD object ISA audit: compiler did not build tiers'; \
	  fi; \
	fi

# P13: retain mocked CPUID and static ISA audits even without AVX-512F.
# The P12/P13 test binaries report SKIP only for unavailable executable tiers.
# A test failure on an executable tier is never treated as a skip.
	@if ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ); then \
	  tiers=$$($(abs_builddir)/test/dsd_test_host_isa$(EXEEXT) --tiers) || exit $$?; \
	  channels="scalar"; \
	  case " $$tiers " in *" avx2 "*) channels="$$channels avx2";; esac; \
	  case " $$tiers " in *" avx512 "*) channels="$$channels avx512";; esac; \
	  $(MAKE) -C test dsd_test_p12_bounds$(EXEEXT) dsd_test_p13$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_p12_bounds$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_p13$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/checks/test_p11_integration.py \
	    --phase P13 --tiers $$tiers \
	    --sox $(abs_builddir)/src/sox \
	    --candidate $(abs_builddir)/test/sox_p10_candidate \
	    --results $(DSD_RESULTS)/forced-cli && \
	  python3 $(srcdir)/tests/dsd/checks/test_p12_channels.py \
	    --phase P13 --tiers $$channels \
	    --sox $(abs_builddir)/src/sox \
	    --candidate $(abs_builddir)/test/sox_p10_candidate \
	    --results $(DSD_RESULTS)/channels && \
	  python3 $(srcdir)/tests/dsd/checks/test_p11_numeric.py \
	    --phase P13 --tiers $$tiers \
	    --unit $(abs_builddir)/test/dsd_test_p11$(EXEEXT) \
	    --results $(DSD_RESULTS)/cross-isa && \
	  if grep -q '^#define HAVE_DSD_AVX512 1' $(abs_builddir)/src/soxconfig.h; then \
	    python3 $(srcdir)/tests/dsd/qualification/check_p13_isa.py \
	      --build-root $(abs_builddir) --results $(DSD_RESULTS)/isa; \
	  elif grep -q '^#define HAVE_DSD_AVX2 1' $(abs_builddir)/src/soxconfig.h; then \
	    echo 'SKIP P13 AVX-512F object ISA audit: compiler did not build tier'; \
	    python3 $(srcdir)/tests/dsd/qualification/check_p12_isa.py \
	      --build-root $(abs_builddir) --results $(DSD_RESULTS)/isa; \
	  elif grep -q '^#define HAVE_DSD_AVX1 1' $(abs_builddir)/src/soxconfig.h; then \
	    echo 'SKIP P13 AVX2/AVX-512F object ISA audits: compiler did not build tiers'; \
	    python3 $(srcdir)/tests/dsd/qualification/check_p11_isa.py \
	      --build-root $(abs_builddir) --results $(DSD_RESULTS)/isa; \
	  else \
	    echo 'SKIP P13 x86 SIMD object ISA audit: compiler did not build tiers'; \
	  fi; \
	fi

# P14's independent native-bit, final-report, and digital-filter tests.
	@if ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ); then \
	  $(MAKE) -C test dsd_test_p14$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/checks/test_p14.py \
	    --sox $(abs_builddir)/src/sox \
	    --unit $(abs_builddir)/test/dsd_test_p14$(EXEEXT) \
	    --results $(DSD_RESULTS)/report && \
	  python3 $(srcdir)/tests/dsd/checks/test_p14_numeric.py \
	    --sox $(abs_builddir)/src/sox \
	    --unit $(abs_builddir)/test/dsd_test_p14$(EXEEXT) \
	    --results $(DSD_RESULTS)/numeric-p14; \
	fi

# P15 is not a pass-through phase. Inherit all P00-P14 executable gates and
# add the release/default/alias compatibility smoke suite.
	@if test "$(DSD_PHASE)" = "P15"; then \
	  python3 $(srcdir)/tests/dsd/checks/test_p15.py \
	    --sox $(abs_builddir)/src/sox \
	    --results $(DSD_RESULTS)/release; \
	fi


# P16: real native packed input gate. P15 is operator-authorized and stays
# source-bound; P16 may inherit P00-P14 tests but cannot rewrite its receipts.
	@if ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ); then \
	  tiers=$$($(abs_builddir)/test/dsd_test_host_isa$(EXEEXT) --tiers) || exit $$?; \
	  p16_tiers=scalar; \
	  case " $$tiers " in *" avx2 "*) p16_tiers="scalar avx2";; esac; \
	  $(MAKE) -C test dsd_test_p16$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/checks/test_p16.py \
	    --tiers $$p16_tiers \
	    --sox $(abs_builddir)/src/sox \
	    --unit $(abs_builddir)/test/dsd_test_p16$(EXEEXT) \
	    --results $(DSD_RESULTS)/integration; \
	fi


# P17: experimental high-rate DSP only. The P16 gate above remains inherited;
# this tests strict descriptor/SDM qualification and finite packed parity.
	@if test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18"; then \
	  tiers=$$($(abs_builddir)/test/dsd_test_host_isa$(EXEEXT) --tiers) || exit $$?; \
	  $(MAKE) -C test dsd_test_p17$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/generators/generate_p17_profiles.py --check && \
	  python3 $(srcdir)/tests/dsd/checks/test_p17_numeric.py \
	    --host-tiers $$tiers \
	    --unit $(abs_builddir)/test/dsd_test_p17$(EXEEXT) \
	    --results $(DSD_RESULTS)/numeric-p17; \
	fi


EXTRA_DIST += docs/dsd/DSD_DESIGN.md docs/dsd/README.md tests/dsd/README.md \
  tests/dsd/benchmarks/bench.py tests/dsd/fixtures/block_minus_1.dsf \
  tests/dsd/fixtures/block_plus_1.dsf tests/dsd/fixtures/dop_stereo_1.pcm24le \
  tests/dsd/fixtures/dop_stereo_15.pcm24le tests/dsd/fixtures/dop_stereo_16.pcm24le \
  tests/dsd/fixtures/dop_stereo_17.pcm24le tests/dsd/fixtures/dop_stereo_32.pcm24le \
  tests/dsd/fixtures/dop_stereo_33.pcm24le tests/dsd/fixtures/empty.dsf \
  tests/dsd/fixtures/five_16.dff tests/dsd/fixtures/five_96.dsf \
  tests/dsd/fixtures/four_16.dff tests/dsd/fixtures/manifest.json \
  tests/dsd/fixtures/mono_128_manf.dff tests/dsd/fixtures/mono_16.dff \
  tests/dsd/fixtures/mono_16.wsd tests/dsd/fixtures/mono_32_dop.dsf \
  tests/dsd/fixtures/mono_9.dff tests/dsd/fixtures/mono_96.dsf \
  tests/dsd/fixtures/msb_stereo_96.dsf tests/dsd/fixtures/nine.dsf \
  tests/dsd/fixtures/one.dsf tests/dsd/fixtures/one_cluster.dff \
  tests/dsd/fixtures/pcm_sine_352800.wav tests/dsd/fixtures/pcm_sine_705600.wav \
  tests/dsd/fixtures/pcm_sine_88200.wav tests/dsd/fixtures/seven.dsf \
  tests/dsd/fixtures/six_16.dff tests/dsd/fixtures/six_96.dsf \
  tests/dsd/fixtures/stereo_128.dff tests/dsd/fixtures/stereo_32.wsd \
  tests/dsd/fixtures/stereo_96.dsf tests/dsd/fixtures/type4_quad_96.dsf \
  tests/dsd/fixtures/type5_quad_96.dsf tests/dsd/benchmarks/measure.py tests/dsd/reference/__init__.py \
  tests/dsd/reference/fixtures.py tests/dsd/reference/metrology.py \
  tests/dsd/reference/verify.py tests/dsd/run.py tests/dsd/native/test_io.c \
  tests/dsd/native/test_dff_writer.c tests/dsd/reference/writer.py \
  tests/dsd/fixtures/p01_writer_vectors.json tests/dsd/benchmarks/bench_dff.py \
  tests/dsd/BENCHMARKING.md tests/dsd/benchmarks/benchprep.sh tests/dsd/checks/test_streaming.py \
  tests/dsd/native/test_dop_capacity.c tests/dsd/benchmarks/bench_read_p02.py docs/dsd/SEEK_CONTRACT.md \
  tests/dsd/checks/test_seek.py tests/dsd/native/test_seek_contract.c

# P04 independent channel-identity evidence and documentation.
EXTRA_DIST += docs/dsd/LAYOUT_CONTRACT.md tests/dsd/checks/test_layout.py tests/dsd/native/test_layout.c \
  tests/dsd/fixtures/p04/manifest.json tests/dsd/fixtures/p04/p04_ambiguous.dff \
  tests/dsd/fixtures/p04/p04_context.dff tests/dsd/fixtures/p04/p04_five_lsco3.dff \
  tests/dsd/fixtures/p04/p04_mono_unmasked.wav \
  tests/dsd/fixtures/p04/p04_opaque_assignment.wsd \
  tests/dsd/fixtures/p04/p04_quad_unmasked.wav tests/dsd/fixtures/p04/p04_six_lsco4.dff \
  tests/dsd/fixtures/p04/p04_stereo_masked.wav tests/dsd/fixtures/p04/p04_stereo_lsco0.dff \
  tests/dsd/fixtures/p04/p04_stereo_side_masked.wav \
  tests/dsd/fixtures/p04/p04_stereo_unmasked.wav \
  tests/dsd/fixtures/p04/p04_stereo_unsupported_mask.wav \
  tests/dsd/fixtures/p04/p04_swap_lsco.dff tests/dsd/fixtures/p04/p04_type5_standard.dff

# P05 preflight fixture generators, numeric/unit tests and human handoff.
EXTRA_DIST += tests/dsd/native/test_plan.c tests/dsd/checks/test_plan.py tests/dsd/benchmarks/bench_plan.py

# Round briefs: the instructions dispatched per phase and correction.

# P02 DFF read hotfix: equivalence check, targeted bench and handoff.
EXTRA_DIST += tests/dsd/benchmarks/bench_hotfix_dff.py tests/dsd/qualification/check_hotfix_equivalence.py

# P06 private scalar reconstruction certification, fixtures and benchmarks.
EXTRA_DIST += src/dsd_packed.h src/dsd_packed.c
EXTRA_DIST += src/dsd_coeffs.h src/dsd_decode.h src/dsd_kernels.h \
  tests/dsd/generators/generate_coeffs.py tests/dsd/qualification/certify_filters.py tests/dsd/native/test_decode.c \
  tests/dsd/checks/test_decode.py tests/dsd/benchmarks/bench_decode.py tests/dsd/native/test_decode_faults.c \
  tests/dsd/reference/p06_coefficients.json

# P07 public decoder and explicit conversion integration evidence.
EXTRA_DIST += src/rate_internal.h src/dsd_public.c src/dsdpcm.c tests/dsd/native/test_p07.c \
  tests/dsd/checks/test_p07.py tests/dsd/checks/test_p07_output_failures.py tests/dsd/benchmarks/bench_p06_hotfix.py \
  tests/dsd/native/test_p07_reference.c tests/dsd/checks/test_p07_reference.py \
  tests/dsd/checks/test_p07_composite.py tests/dsd/checks/test_p07_impulse.py \
  tests/dsd/checks/test_p07_public_rate.py tests/dsd/reference/p07_public_rate_goldens.json \
  tests/dsd/benchmarks/bench_p07.py

# P08 automatic graph and pre-combiner domain boundaries.
EXTRA_DIST += tests/dsd/checks/test_p08.py tests/dsd/benchmarks/bench_p08_adapter.py

# P09 exact-rate registry, immutable analysis reference, tests and handoff.
EXTRA_DIST += tests/dsd/native/test_p09.c tests/dsd/checks/test_p09.py \
  tests/dsd/reference/p09_original_coefficients.json \
  tests/dsd/reference/analysis-v1/README.md tests/dsd/reference/analysis-v1/generate.py \
  tests/dsd/reference/analysis-v1/analyze.py tests/dsd/reference/analysis-v1/verify.py \
  tests/dsd/reference/analysis-v1/measure_candidates.py \
  tests/dsd/reference/analysis-v1/manifest.json \
  tests/dsd/reference/analysis-v1/SHA256SUMS.txt \
  tests/dsd/reference/analysis-v1/fir-2822400.f64le \
  tests/dsd/reference/analysis-v1/fir-5644800.f64le \
  tests/dsd/reference/analysis-v1/fir-11289600.f64le
EXTRA_DIST += tests/dsd/benchmarks/bench_p09.py
EXTRA_DIST += tests/dsd/qualification/sanitize_p09_results.py

# P10 fail-closed composite candidate and executable qualification evidence.
EXTRA_DIST += tests/dsd/native/test_p10.c tests/dsd/checks/test_p10.py tests/dsd/native/p10_candidate_cli.c \
  tests/dsd/generators/generate_p10_coeffs.py tests/dsd/phases/p10_corpus.py tests/dsd/qualification/qualify_p10.py \
  tests/dsd/reference/p10_prefilters.json tests/dsd/reference/p10_guards.json

EXTRA_DIST += tests/dsd/qualification/soak_p10.py tests/dsd/benchmarks/bench_p10.py \
  tests/dsd/support/corroborate_p10.py

EXTRA_DIST += tests/dsd/checks/test_p10_qualification.py

EXTRA_DIST += tests/dsd/generators/generate_p10_profiles.py \
  tests/dsd/reference/p10_profiles.json \
  tests/dsd/reference/p10_certificate_input.json \
  tests/dsd/reference/p10_qualification_snapshot.json

EXTRA_DIST += tests/dsd/benchmarks/bench_p10_kernel_control.py

# P10 corrective: evidence classification, independent stage measurements and
# a versioned *negative* profile record. These are not release activation gates.
EXTRA_DIST += tests/dsd/reference/p10_soak_nominal_v2.json \
  tests/dsd/reference/p10_profiles_corrective.json tests/dsd/qualification/verify_p10_corrective.py \
  tests/dsd/qualification/replay_p10_numeric_bits.py tests/dsd/qualification/sanitize_p10_corrective.py \
  tests/dsd/qualification/qualify_p10_corrective.py tests/dsd/checks/test_p10_corrective_qualification.py \
  tests/dsd/generators/generate_p10_corrective_profiles.py

# P10 revalidation: executable receipt coverage and source-quantization audit.
EXTRA_DIST += tests/dsd/checks/test_p10_soak_receipts.py tests/dsd/native/test_p10_fixture_rounding.c

# P10 release-gate measurement on material this project did not generate. The
# corpus audio itself is not distributed; only the driver and its analyser.
EXTRA_DIST += tests/dsd/support/corpus_realworld.py \
  tests/dsd/support/dsd_windows.py tests/dsd/support/corpus_pcm.py \
  tests/dsd/checks/test_p10_pcm.py

# P10 independent release gate ratification (versioned; historical corrective
# receipts/certificates remain frozen). No source audio is distributed.
# P10_RATIFICATION.md, P10_HOTFIX.md and P15_CLOSEOUT_ADJUDICATION_2026-10-14.md
# name private recordings and stay in the repository only.
EXTRA_DIST += tests/dsd/reference/p10_ratification_criteria.json \
  tests/dsd/qualification/ratify_p10_gates.py tests/dsd/qualification/qualify_p10_ratification.py \
  tests/dsd/checks/test_p10_ratification.py

# P10 explicit reviewer closeout; positive certification and verifier are
# separate from historical negative receipts and P15 default activation.
EXTRA_DIST += tests/dsd/qualification/check_p10_certification.py

# P11 per-context dispatch, frozen cross-ISA qualifications, runnable ISA
# isolation and host-specific throughput characterization.
EXTRA_DIST += tests/dsd/native/test_sdm_auto.c tests/dsd/native/test_p11.c tests/dsd/checks/test_p11_numeric.py \
  tests/dsd/checks/test_p11_integration.py tests/dsd/checks/test_p11_p10_regression.py \
  tests/dsd/qualification/check_p11_isa.py tests/dsd/checks/test_check_p11_isa.py tests/dsd/benchmarks/bench_p11.py \
  tests/dsd/benchmarks/bench_p11_e2e.py
EXTRA_DIST += tests/dsd/qualification/sanitize_p11_results.py
EXTRA_DIST += tests/dsd/qualification/qualify_p11_avx1_emulator.py

# P12 independently forceable AVX2, numerical tests and ISA evidence.
EXTRA_DIST += src/dsd_kernels_avx2.c tests/dsd/qualification/check_p12_isa.py tests/dsd/native/test_p12_bounds.c \
  tests/dsd/checks/test_p12_channels.py tests/dsd/benchmarks/bench_p12_matrix.py \
  tests/dsd/qualification/sanitize_p12_results.py

# P13 AVX-512F baseline, numeric/guard/ISA tests and host-bound matrix.
EXTRA_DIST += src/dsd_kernels_avx512.c tests/dsd/native/test_p13.c tests/dsd/qualification/check_p13_isa.py \
  tests/dsd/benchmarks/bench_p13_matrix.py

# P14 observational native statistics and versioned report contract.
EXTRA_DIST += tests/dsd/native/test_p14.c tests/dsd/checks/test_p14.py tests/dsd/checks/test_p14_numeric.py \
  tests/dsd/benchmarks/bench_p14.py tests/dsd/reference/p14_report_schema_v1.json \
  tests/dsd/reference/p14_report_golden.json


# Legacy SDM policy: no external research fixtures or nonstandard Python modules.
.PHONY: check-sdm-guard-policy
check-sdm-guard-policy: all
	python3 $(srcdir)/tests/dsd/checks/test_legacy_sdm_guard_policy.py --sox $(abs_builddir)/src/sox$(EXEEXT)
	python3 $(srcdir)/tests/dsd/checks/test_legacy_sdm_f32_input.py --sox $(abs_builddir)/src/sox$(EXEEXT)
EXTRA_DIST += tests/dsd/checks/test_legacy_sdm_guard_policy.py \
  tests/dsd/checks/test_legacy_sdm_f32_input.py \
  tests/dsd/benchmarks/bench_legacy_sdm_avx.py \
  docs/dsd/LEGACY_SDM_GUARD_POLICY.md

# Non-phase performance investigation; no production policy or DSP changes.
EXTRA_DIST += tests/dsd/benchmarks/profile_decode.py tests/dsd/checks/test_perf_measurements.py

.PHONY: check-dsd-optimization
check-dsd-optimization: all
	$(MAKE) -C test dsd_test_decode_optimization$(EXEEXT)
	$(abs_builddir)/test/dsd_test_decode_optimization$(EXEEXT) scalar

# Decoder optimization measurements; production policy remains unchanged.
EXTRA_DIST += tests/dsd/benchmarks/bench_decode_optimization.py

# P15 release qualification and migration (source-only continuation).
EXTRA_DIST += docs/dsd/QUALIFICATION.md docs/dsd/MIGRATION_P15.md tests/dsd/checks/test_p15.py \
  tests/dsd/phases/p15_release_manifest.py

# P15 closeout is an adjudication of retained source-bound receipts, not a
# qualification bit or automatic-default migration.
EXTRA_DIST += tests/dsd/phases/p15_closeout_review.py tests/dsd/checks/test_p15_closeout_review.py

# Retired P15-R3 decoder-v2 execution tests are removed from the release
# tree. The historical generators and certificates are kept as a record, not
# as live targets: the generators read src/dsd_coeffs_v2.h, removed in 1.1.1,
# so rerunning them needs a 1.1.0 checkout.
EXTRA_DIST += tests/dsd/generators/generate_p15_r3_coeffs.py tests/dsd/qualification/certify_p15_r3_filters.py \
  tests/dsd/benchmarks/bench_p15_r3_local.py tests/dsd/reference/p15_r3_coefficients.json

# P16 additive native-packed contract, probes and paired end-to-end benchmark.
EXTRA_DIST += src/dsd_packed.h src/dsd_packed.c tests/dsd/native/test_p16.c tests/dsd/checks/test_p16.py \
  tests/dsd/benchmarks/bench_p16.py

# P17 private research candidates and source-bound qualification records.
EXTRA_DIST += src/sdm_p17_candidates.h tests/dsd/native/test_p17.c \
  tests/dsd/generators/generate_p17_profiles.py tests/dsd/reference/p17_profiles.json \
  tests/dsd/checks/test_p17_numeric.py tests/dsd/benchmarks/bench_p17.py

# P18 closed capability release machinery and synthetic reference fixtures.
EXTRA_DIST += tests/dsd/native/test_p18.c tests/dsd/checks/test_p18.py \
  tests/dsd/reference/p18_fixture_matrix.json tests/dsd/qualification/seal_p18_manifest.py \
  tests/dsd/fixtures/p18/p18-22579200-dff-8-1-1.dff \
  tests/dsd/fixtures/p18/p18-22579200-dff-8-1-17.dff \
  tests/dsd/fixtures/p18/p18-22579200-dff-8-1-32769.dff \
  tests/dsd/fixtures/p18/p18-22579200-dff-8-2-1.dff \
  tests/dsd/fixtures/p18/p18-22579200-dff-8-2-17.dff \
  tests/dsd/fixtures/p18/p18-22579200-dff-8-2-32769.dff \
  tests/dsd/fixtures/p18/p18-22579200-dff-8-6-1.dff \
  tests/dsd/fixtures/p18/p18-22579200-dff-8-6-17.dff \
  tests/dsd/fixtures/p18/p18-22579200-dff-8-6-32769.dff \
  tests/dsd/fixtures/p18/p18-22579200-dsf-1-1-1.dsf \
  tests/dsd/fixtures/p18/p18-22579200-dsf-1-1-17.dsf \
  tests/dsd/fixtures/p18/p18-22579200-dsf-1-1-32769.dsf \
  tests/dsd/fixtures/p18/p18-22579200-dsf-1-2-1.dsf \
  tests/dsd/fixtures/p18/p18-22579200-dsf-1-2-17.dsf \
  tests/dsd/fixtures/p18/p18-22579200-dsf-1-2-32769.dsf \
  tests/dsd/fixtures/p18/p18-22579200-dsf-1-6-1.dsf \
  tests/dsd/fixtures/p18/p18-22579200-dsf-1-6-17.dsf \
  tests/dsd/fixtures/p18/p18-22579200-dsf-1-6-32769.dsf \
  tests/dsd/fixtures/p18/p18-45158400-dff-8-1-1.dff \
  tests/dsd/fixtures/p18/p18-45158400-dff-8-1-17.dff \
  tests/dsd/fixtures/p18/p18-45158400-dff-8-1-32769.dff \
  tests/dsd/fixtures/p18/p18-45158400-dff-8-2-1.dff \
  tests/dsd/fixtures/p18/p18-45158400-dff-8-2-17.dff \
  tests/dsd/fixtures/p18/p18-45158400-dff-8-2-32769.dff \
  tests/dsd/fixtures/p18/p18-45158400-dff-8-6-1.dff \
  tests/dsd/fixtures/p18/p18-45158400-dff-8-6-17.dff \
  tests/dsd/fixtures/p18/p18-45158400-dff-8-6-32769.dff \
  tests/dsd/fixtures/p18/p18-45158400-dsf-1-1-1.dsf \
  tests/dsd/fixtures/p18/p18-45158400-dsf-1-1-17.dsf \
  tests/dsd/fixtures/p18/p18-45158400-dsf-1-1-32769.dsf \
  tests/dsd/fixtures/p18/p18-45158400-dsf-1-2-1.dsf \
  tests/dsd/fixtures/p18/p18-45158400-dsf-1-2-17.dsf \
  tests/dsd/fixtures/p18/p18-45158400-dsf-1-2-32769.dsf \
  tests/dsd/fixtures/p18/p18-45158400-dsf-1-6-1.dsf \
  tests/dsd/fixtures/p18/p18-45158400-dsf-1-6-17.dsf \
  tests/dsd/fixtures/p18/p18-45158400-dsf-1-6-32769.dsf \
  tests/dsd/fixtures/p18/p18-dop-22579200-2-17.pcm24le \
  tests/dsd/fixtures/p18/p18-dop-22579200-2-33.pcm24le \
  tests/dsd/fixtures/p18/p18-dop-45158400-2-17.pcm24le \
  tests/dsd/fixtures/p18/p18-dop-45158400-2-33.pcm24le

# Scoped upstream-sync lifecycle regressions; no external network or fixtures.
.PHONY: check-sync-url check-sync-p10 check-sync
check-sync-url: all
	python3 $(srcdir)/tests/sync/test_url_process.py --sox $(abs_builddir)/src/sox$(EXEEXT)

check-sync-p10: all
	$(MAKE) -C test dsd_test_p10$(EXEEXT) dsd_test_io$(EXEEXT)
	python3 $(srcdir)/tests/sync/test_p10_path.py --source $(abs_srcdir) --build $(abs_builddir)

check-sync-p16-p18: all
	$(MAKE) -C test dsd_test_io$(EXEEXT) dsd_test_p16$(EXEEXT) dsd_test_p17$(EXEEXT) dsd_test_p18$(EXEEXT)
	python3 $(srcdir)/tests/sync/test_p16_p18_path.py --source $(abs_srcdir) --build $(abs_builddir)

check-sync-waveaudio:
	python3 $(srcdir)/tests/sync/test_waveaudio_teardown.py --source $(abs_srcdir)

check-sync: check-sync-url check-sync-p10 check-sync-p16-p18 check-sync-waveaudio

# Register-resident SDM qualification and independent original scalar oracle.
EXTRA_DIST += docs/dsd/SDM_REGISTER_PROOF.md \
  tests/dsd/SDM_REGISTER_QUALIFICATION.md \
  tests/dsd/native/test_sdm_register.c tests/dsd/qualification/run_sdm_register.py \
  tests/dsd/qualification/run_sdm_existing.py \
  tests/dsd/support/build_sdm_native.py tests/dsd/qualification/check_sdm_register_isa.py \
  tests/dsd/qualification/prepare_sdm_canonical.py \
  tests/dsd/native/bench_sdm_register.c tests/dsd/benchmarks/paired_sdm_bench.py \
  tests/dsd/benchmarks/paired_sdm_e2e.py \
  tests/dsd/reference/sdm_register_oracle/README.md \
  tests/dsd/reference/sdm_register_oracle/provenance.json \
  tests/dsd/reference/sdm_register_oracle/sdm.c \
  tests/dsd/reference/sdm_register_oracle/dsd_kernels_scalar.c \
  tests/dsd/reference/sdm_register_oracle/sdm_normal_commit_i.h \
  tests/dsd/reference/sdm_register_oracle/sdm_x86.h \
  tests/dsd/reference/sdm_register_oracle/sdm_p17_candidates.h \
  tests/dsd/reference/sdm_register_oracle/sdm_p19_candidates.h \
  tests/dsd/reference/sdm_register_oracle/sdm_p20_candidates.h

# CLI-target dependencies must ship even when referenced elsewhere in recipes.
EXTRA_DIST += tests/dsd/checks/test_loud_guard.py

# All moved test sources and support files ship with source distributions.
EXTRA_DIST += tests/dsd/benchmarks/bench_dsd256_2x.py \
  tests/dsd/benchmarks/bench_p15_dsd256_ps_matched.py \
  tests/dsd/benchmarks/bench_src_optimization.py \
  tests/dsd/benchmarks/profile_src_optimization.py \
  tests/dsd/checks/test_adjudicate_p10_p15_corpus.py \
  tests/dsd/checks/test_operator_rebind_recovery.py \
  tests/dsd/checks/test_p15_adjudication_corrective.py \
  tests/dsd/checks/test_p15_campaign_corrective_synthetic.py \
  tests/dsd/checks/test_p15_campaign_dispatch_corrective.py \
  tests/dsd/checks/test_p15_current_closeout.py \
  tests/dsd/checks/test_p15_final_obligations.py \
  tests/dsd/checks/test_p15_final_prover_audit.py \
  tests/dsd/checks/test_p15_high_rate_census.py \
  tests/dsd/checks/test_p15_high_rate_coverage_report.py \
  tests/dsd/checks/test_p15_high_rate_experiment.py \
  tests/dsd/checks/test_p15_high_rate_independent.py \
  tests/dsd/checks/test_p15_high_rate_population.py \
  tests/dsd/checks/test_p15_high_rate_terminal_saturation.py \
  tests/dsd/checks/test_p15_instrument.py \
  tests/dsd/checks/test_p15_normative_limit_rounding.py \
  tests/dsd/checks/test_p15_opt_source_rebind.py \
  tests/dsd/checks/test_p15_prover_fixed_interval.py \
  tests/dsd/checks/test_p15_prover_second_pass.py \
  tests/dsd/checks/test_p15_prover_third_pass.py \
  tests/dsd/checks/test_p15_question_resolution.py \
  tests/dsd/checks/test_p15_r52_physical_benchmark_review.py \
  tests/dsd/checks/test_p15_r6_exact_composite.py \
  tests/dsd/checks/test_p15_r7_fast_fir.py \
  tests/dsd/checks/test_p15_r7_fast_math.py \
  tests/dsd/checks/test_p15_r8_dyadic.py \
  tests/dsd/checks/test_p15_r9_strong.py \
  tests/dsd/checks/test_p15_r9_uniform_math.py \
  tests/dsd/checks/test_p15_readjudication.py \
  tests/dsd/checks/test_p15_remaining_math.py \
  tests/dsd/checks/test_p15_sixteenth_readmission.py \
  tests/dsd/checks/test_p15_src_bound_operator.py \
  tests/dsd/checks/test_p15_src_complete_aliases.py \
  tests/dsd/checks/test_p15_src_continuum_bounds.py \
  tests/dsd/checks/test_p15_src_envelope_review.py \
  tests/dsd/checks/test_p15_src_operator_observations.py \
  tests/dsd/checks/test_p17_dsf_probe.py \
  tests/dsd/checks/test_p17_long_dsf_stream.py \
  tests/dsd/checks/test_p17_qualification_registry.py \
  tests/dsd/checks/test_residual_asymmetry.py \
  tests/dsd/generators/generate_p17_qualification_certificates.py \
  tests/dsd/generators/generate_p19_candidate_certificate.py \
  tests/dsd/generators/generate_p20_candidate_certificate.py \
  tests/dsd/native/p17_dsf_probe.c \
  tests/dsd/native/probe_p15_fir_roundoff.c \
  tests/dsd/native/test_decode_optimization.c \
  tests/dsd/native/test_host_isa.c \
  tests/dsd/native/test_p15_instrument.c \
  tests/dsd/native/test_p15_src_stage_export.c \
  tests/dsd/native/test_src_optimization.c \
  tests/dsd/phases/p15_boundary_schedule_replay.py \
  tests/dsd/phases/p15_compare_cross_host.py \
  tests/dsd/phases/p15_current_closeout.py \
  tests/dsd/phases/p15_dsd256_comparator_2026.py \
  tests/dsd/phases/p15_fft_bin_matrix_interval.py \
  tests/dsd/phases/p15_fft_coefficient_interval.py \
  tests/dsd/phases/p15_final_receipt_adjudicator.py \
  tests/dsd/phases/p15_full_band_campaign.py \
  tests/dsd/phases/p15_graph_integration.py \
  tests/dsd/phases/p15_high_rate_bound_diagnostic.py \
  tests/dsd/phases/p15_high_rate_census.py \
  tests/dsd/phases/p15_high_rate_coverage_report.py \
  tests/dsd/phases/p15_high_rate_experiment.py \
  tests/dsd/phases/p15_historical_campaign_binding.py \
  tests/dsd/phases/p15_intel_receipt_review.py \
  tests/dsd/phases/p15_matrix_contract.py \
  tests/dsd/phases/p15_matrix_instrument.py \
  tests/dsd/phases/p15_matrix_receipt_review.py \
  tests/dsd/phases/p15_native_coefficient_interval.py \
  tests/dsd/phases/p15_numerical_reference.py \
  tests/dsd/phases/p15_physical_archive_review.py \
  tests/dsd/phases/p15_prover_benchmark.py \
  tests/dsd/phases/p15_prover_build_corpus.py \
  tests/dsd/phases/p15_prover_cost_profile.py \
  tests/dsd/phases/p15_prover_evidence_integrity.py \
  tests/dsd/phases/p15_prover_fir_microbenchmark.py \
  tests/dsd/phases/p15_prover_stage_parity_audit.py \
  tests/dsd/phases/p15_prover_summarize.py \
  tests/dsd/phases/p15_r52_physical_benchmark_review.py \
  tests/dsd/phases/p15_r52_run_physical_benchmark.sh \
  tests/dsd/phases/p15_r5_exact_trig.py \
  tests/dsd/phases/p15_r5_integer_spectral.py \
  tests/dsd/phases/p15_r6_adversarial_replay.py \
  tests/dsd/phases/p15_r6_exact_composite.py \
  tests/dsd/phases/p15_r6_exact_policy.py \
  tests/dsd/phases/p15_r6_seal_evidence.py \
  tests/dsd/phases/p15_r6_witness.py \
  tests/dsd/phases/p15_r7_campaign.py \
  tests/dsd/phases/p15_r7_corrupt_real_proof.py \
  tests/dsd/phases/p15_r7_engine.py \
  tests/dsd/phases/p15_r7_fast_fir.py \
  tests/dsd/phases/p15_r7_regenerate_hints.py \
  tests/dsd/phases/p15_r7_seal_evidence.py \
  tests/dsd/phases/p15_r7_witness.py \
  tests/dsd/phases/p15_r8_dyadic_engine.py \
  tests/dsd/phases/p15_r8_highrate_witness.py \
  tests/dsd/phases/p15_r9_src_global_family.py \
  tests/dsd/phases/p15_r9_src_strong.py \
  tests/dsd/phases/p15_r9_uniform_stop.py \
  tests/dsd/phases/p15_readjudication.py \
  tests/dsd/phases/p15_second_pass_benchmark.py \
  tests/dsd/phases/p15_second_pass_fir_benchmark.py \
  tests/dsd/phases/p15_src_bound_operator.py \
  tests/dsd/phases/p15_src_branch_bound.py \
  tests/dsd/phases/p15_src_capture_matrix.py \
  tests/dsd/phases/p15_src_complete_aliases.py \
  tests/dsd/phases/p15_src_continuum_bounds.py \
  tests/dsd/phases/p15_src_difference_upper.py \
  tests/dsd/phases/p15_src_envelope_review.py \
  tests/dsd/phases/p15_src_fixed_interval.py \
  tests/dsd/phases/p15_src_full_chain.py \
  tests/dsd/phases/p15_src_halfband_majorant.py \
  tests/dsd/phases/p15_src_interval_recurrence.py \
  tests/dsd/phases/p15_src_operator_observations.py \
  tests/dsd/phases/p15_src_opt_build_contract.py \
  tests/dsd/phases/p15_src_spectral.py \
  tests/dsd/phases/p15_src_stagewise_alias_proof.py \
  tests/dsd/phases/p15_src_stagewise_continuum.py \
  tests/dsd/phases/p15_src_symmetric_interval.py \
  tests/dsd/phases/p15_third_pass_benchmark.py \
  tests/dsd/phases/p15_third_pass_fir_benchmark.py \
  tests/dsd/phases/p17_qualify_guards.py \
  tests/dsd/phases/p17_soak_assess.py \
  tests/dsd/phases/p17_soak_run.py \
  tests/dsd/phases/p19_audio_compare.py \
  tests/dsd/phases/p19_qualify_dsd1024.py \
  tests/dsd/phases/p19_soak_assess.py \
  tests/dsd/phases/p19_soak_run.py \
  tests/dsd/phases/p20_audio_compare.py \
  tests/dsd/phases/p20_qualify_dsd512.py \
  tests/dsd/phases/p20_soak_assess.py \
  tests/dsd/phases/p20_soak_run.py \
  tests/dsd/qualification/adjudicate_p10_p15_corpus.py \
  tests/dsd/qualification/certify_p21_highrate_decode.py \
  tests/dsd/qualification/check_avx1_physical.sh \
  tests/dsd/qualification/check_intel_avx512.sh \
  tests/dsd/qualification/check_intel_avx512_perf.sh \
  tests/dsd/qualification/check_p15_avx1_receipt.py \
  tests/dsd/qualification/p16_dev_input_drift.py \
  tests/dsd/qualification/p16_verify_inputs.py \
  tests/dsd/qualification/rebind_p15_src_operator.py \
  tests/dsd/qualification/recover_p15_src_operator_rebind.py \
  tests/dsd/qualification/verify_dsd256_control_match.py \
  tests/dsd/qualification/verify_p11_replay_receipts.py \
  tests/dsd/qualification/verify_p15_sixteenth_readmission.py \
  tests/dsd/support/compare_src_optimization_operators.py \
  tests/dsd/support/diagnose_residual_asymmetry.py \
  tests/dsd/support/summarize_src_optimization.py \
  tests/dsd/benchmarks/README.md \
  tests/dsd/checks/README.md \
  tests/dsd/generators/README.md \
  tests/dsd/native/README.md \
  tests/dsd/phases/README.md \
  tests/dsd/qualification/README.md \
  tests/dsd/support/README.md
