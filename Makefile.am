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
EXTRA_DIST = sox.txt soxi.txt soxeffect_ng.txt soxformat_ng.txt \
             libsox_ng.txt libsoxeffect_ng.txt libsoxformat_ng.txt \
             sox.pdf soxi.pdf soxeffect_ng.pdf soxformat_ng.pdf \
             libsox_ng.pdf libsoxeffect_ng.pdf libsoxformat_ng.pdf \
             ltmain.sh compile missing install-sh config.guess config.sub \
	     sox_ng.pc.in sox_dsd.mk COPYING AUTHORS INSTALL \
	     README.win32 scripts/batch-example.bat \
	     README.md RULES.md RULES-issues.md RULES-wiki.md \
	     docs/UPSTREAM.md \
	     tests/sync/test_url_process.py tests/sync/test_p10_path.py \
             tests/sync/test_p16_p18_path.py tests/sync/test_waveaudio_teardown.py \
	     README.sh FEATURES.in test/* issues wiki/* \
             tests/rename_smoke.sh

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

# P00 and subsequent DSD phases use one runner and one named make target.
# The original 'make check' target is unchanged.
.PHONY: check-dsd
DSD_PHASE ?= P18
DSD_RESULTS ?= $(abs_builddir)/tests/dsd/results/$(DSD_PHASE)
check-dsd: all
	$(MAKE) check-dsd-optimization
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
	  python3 $(srcdir)/tests/dsd/test_streaming.py \
	    --probe $(abs_builddir)/test/dsd_test_io$(EXEEXT) \
	    --sox $(abs_builddir)/src/sox \
	    --results $(DSD_RESULTS)/streaming; \
	fi
	@if test "$(DSD_PHASE)" = "P03" || test "$(DSD_PHASE)" = "P04" || test "$(DSD_PHASE)" = "P05" || test "$(DSD_PHASE)" = "P06" || test "$(DSD_PHASE)" = "P07" || test "$(DSD_PHASE)" = "P08" || test "$(DSD_PHASE)" = "P09" || ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  $(MAKE) -C test dsd_test_seek_contract$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/test_seek.py \
	    --probe $(abs_builddir)/test/dsd_test_seek_contract$(EXEEXT) \
	    --sox $(abs_builddir)/src/sox \
	    --results $(DSD_RESULTS)/seek; \
	fi
	@if test "$(DSD_PHASE)" = "P04" || test "$(DSD_PHASE)" = "P05" || test "$(DSD_PHASE)" = "P06" || test "$(DSD_PHASE)" = "P07" || test "$(DSD_PHASE)" = "P08" || test "$(DSD_PHASE)" = "P09" || ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  $(MAKE) -C test dsd_test_layout$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/test_layout.py \
	    --unit $(abs_builddir)/test/dsd_test_layout$(EXEEXT) \
	    --sox $(abs_builddir)/src/sox \
	    --results $(DSD_RESULTS)/layout; \
	fi
	@if test "$(DSD_PHASE)" = "P05" || test "$(DSD_PHASE)" = "P06" || test "$(DSD_PHASE)" = "P07" || test "$(DSD_PHASE)" = "P08" || test "$(DSD_PHASE)" = "P09" || ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  $(MAKE) -C test dsd_test_plan$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_plan$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/test_plan.py \
	    --sox $(abs_builddir)/src/sox \
	    --results $(DSD_RESULTS)/plan; \
	fi
	@if test "$(DSD_PHASE)" = "P06" || test "$(DSD_PHASE)" = "P07" || test "$(DSD_PHASE)" = "P08" || test "$(DSD_PHASE)" = "P09" || ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  $(MAKE) -C test dsd_test_decode$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_decode$(EXEEXT) && \
	  $(MAKE) -C test dsd_test_decode_faults$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_decode_faults$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/test_decode.py \
	    --unit $(abs_builddir)/test/dsd_test_decode$(EXEEXT) \
	    --results $(DSD_RESULTS)/scalar; \
	fi

	@if test "$(DSD_PHASE)" = "P07" || test "$(DSD_PHASE)" = "P08" || test "$(DSD_PHASE)" = "P09" || ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  $(MAKE) -C test dsd_test_p07$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_p07$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/test_p07.py \
	    --sox $(abs_builddir)/src/sox \
	    --results $(DSD_RESULTS)/integration && \
	  python3 $(srcdir)/tests/dsd/test_p07_output_failures.py \
	    --sox $(abs_builddir)/src/sox \
	    --results $(DSD_RESULTS)/output-errors && \
	  $(MAKE) -C test dsd_test_p07_reference$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/test_p07_reference.py \
	    --unit $(abs_builddir)/test/dsd_test_p07_reference$(EXEEXT) \
	    --results $(DSD_RESULTS)/numeric && \
	  python3 $(srcdir)/tests/dsd/test_p07_composite.py \
	    --unit $(abs_builddir)/test/dsd_test_p07_reference$(EXEEXT) \
	    --results $(DSD_RESULTS)/numeric && \
	  python3 $(srcdir)/tests/dsd/test_p07_impulse.py \
	    --unit $(abs_builddir)/test/dsd_test_p07_reference$(EXEEXT) \
	    --results $(DSD_RESULTS)/numeric && \
	  python3 $(srcdir)/tests/dsd/test_p07_public_rate.py \
	    --sox $(abs_builddir)/src/sox; \
	fi

	@if test "$(DSD_PHASE)" = "P08" || test "$(DSD_PHASE)" = "P09" || ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  python3 $(srcdir)/tests/dsd/test_p08.py \
	    --sox $(abs_builddir)/src/sox \
	    --results $(DSD_RESULTS)/integration; \
	fi

# P00 distributable design/test inputs (generated raw runs live in the continuation archive).
	@if test "$(DSD_PHASE)" = "P09" || ( test "$(DSD_PHASE)" = "P10" || ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ) ); then \
	  $(MAKE) -C test dsd_test_p09$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/test_p09.py \
	    --unit $(abs_builddir)/test/dsd_test_p09$(EXEEXT) \
	    --results $(DSD_RESULTS)/unit && \
	  python3 $(srcdir)/tests/dsd/reference/analysis-v1/verify.py \
	    --results $(DSD_RESULTS)/numeric; \
	fi

	@if ( test "$(DSD_PHASE)" = "P11" || test "$(DSD_PHASE)" = "P12" || ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ) ); then \
	  $(MAKE) -C test dsd_test_p11$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_p11$(EXEEXT) && \
	  if test "$(DSD_PHASE)" = "P11"; then \
	    python3 $(srcdir)/tests/dsd/test_p11_numeric.py \
	      --unit $(abs_builddir)/test/dsd_test_p11$(EXEEXT) \
	      --results $(DSD_RESULTS)/numeric; \
	  fi; \
	fi

# P12: verify actual AVX2 execution and all four tiers on the actual CLI.
	@if test "$(DSD_PHASE)" = "P12"; then \
	  $(MAKE) -C test dsd_test_p12_bounds$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_p12_bounds$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/test_p11_integration.py \
	    --phase P12 --tiers scalar sse2 avx1 avx2 \
	    --sox $(abs_builddir)/src/sox \
	    --candidate $(abs_builddir)/test/sox_p10_candidate \
	    --results $(DSD_RESULTS)/forced-cli && \
	  python3 $(srcdir)/tests/dsd/test_p12_channels.py \
	    --sox $(abs_builddir)/src/sox \
	    --candidate $(abs_builddir)/test/sox_p10_candidate \
	    --results $(DSD_RESULTS)/channels && \
	  python3 $(srcdir)/tests/dsd/test_p11_numeric.py \
	    --phase P12 --tiers scalar sse2 avx1 avx2 \
	    --unit $(abs_builddir)/test/dsd_test_p11$(EXEEXT) \
	    --results $(DSD_RESULTS)/cross-isa && \
	  python3 $(srcdir)/tests/dsd/check_p12_isa.py \
	    --build-root $(abs_builddir) --results $(DSD_RESULTS)/isa; \
	fi


# P13: independent AVX-512F execution plus the retained four-tier coverage.
# The static ISA audit is additional evidence, never a substitute for the
# executable CPUID/XCR0, guard-page and production CLI tests.
	@if ( test "$(DSD_PHASE)" = "P13" || ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ) ); then \
	  $(MAKE) -C test dsd_test_p12_bounds$(EXEEXT) dsd_test_p13$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_p12_bounds$(EXEEXT) && \
	  $(abs_builddir)/test/dsd_test_p13$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/test_p11_integration.py \
	    --phase P13 --tiers scalar sse2 avx1 avx2 avx512 \
	    --sox $(abs_builddir)/src/sox \
	    --candidate $(abs_builddir)/test/sox_p10_candidate \
	    --results $(DSD_RESULTS)/forced-cli && \
	  python3 $(srcdir)/tests/dsd/test_p12_channels.py \
	    --phase P13 --tiers scalar avx2 avx512 \
	    --sox $(abs_builddir)/src/sox \
	    --candidate $(abs_builddir)/test/sox_p10_candidate \
	    --results $(DSD_RESULTS)/channels && \
	  python3 $(srcdir)/tests/dsd/test_p11_numeric.py \
	    --phase P13 --tiers scalar sse2 avx1 avx2 avx512 \
	    --unit $(abs_builddir)/test/dsd_test_p11$(EXEEXT) \
	    --results $(DSD_RESULTS)/cross-isa && \
	  python3 $(srcdir)/tests/dsd/check_p13_isa.py \
	    --build-root $(abs_builddir) --results $(DSD_RESULTS)/isa; \
	fi

# P14's independent native-bit, final-report, and digital-filter tests.
	@if ( test "$(DSD_PHASE)" = "P14" || ( test "$(DSD_PHASE)" = "P15" || ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ) ) ); then \
	  $(MAKE) -C test dsd_test_p14$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/test_p14.py \
	    --sox $(abs_builddir)/src/sox \
	    --unit $(abs_builddir)/test/dsd_test_p14$(EXEEXT) \
	    --results $(DSD_RESULTS)/report && \
	  python3 $(srcdir)/tests/dsd/test_p14_numeric.py \
	    --sox $(abs_builddir)/src/sox \
	    --unit $(abs_builddir)/test/dsd_test_p14$(EXEEXT) \
	    --results $(DSD_RESULTS)/numeric-p14; \
	fi

# P15 is not a pass-through phase. Inherit all P00-P14 executable gates and
# add the release/default/alias compatibility smoke suite.
	@if test "$(DSD_PHASE)" = "P15"; then \
	  python3 $(srcdir)/tests/dsd/test_p15.py \
	    --sox $(abs_builddir)/src/sox \
	    --results $(DSD_RESULTS)/release; \
	fi


# P16: real native packed input gate. P15 is operator-authorized and stays
# source-bound; P16 may inherit P00-P14 tests but cannot rewrite its receipts.
	@if ( test "$(DSD_PHASE)" = "P16" || test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18" ); then \
	  $(MAKE) -C test dsd_test_p16$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/test_p16.py \
	    --sox $(abs_builddir)/src/sox \
	    --unit $(abs_builddir)/test/dsd_test_p16$(EXEEXT) \
	    --results $(DSD_RESULTS)/integration; \
	fi


# P17: experimental high-rate DSP only. The P16 gate above remains inherited;
# this tests strict descriptor/SDM qualification and finite packed parity.
	@if test "$(DSD_PHASE)" = "P17" || test "$(DSD_PHASE)" = "P18"; then \
	  $(MAKE) -C test dsd_test_p17$(EXEEXT) && \
	  python3 $(srcdir)/tests/dsd/generate_p17_profiles.py --check && \
	  python3 $(srcdir)/tests/dsd/test_p17_numeric.py --unit $(abs_builddir)/test/dsd_test_p17$(EXEEXT) --results $(DSD_RESULTS)/numeric-p17; \
	fi


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
  docs/dsd/handoffs/P02_CHECKPOINT.md \
  docs/dsd/SEEK_CONTRACT.md docs/dsd/handoffs/P03.md \
  docs/dsd/handoffs/P03_CHECKPOINT.md \
  tests/dsd/test_seek.py tests/dsd/test_seek_contract.c

# P04 independent channel-identity evidence and documentation.
EXTRA_DIST += \
  docs/dsd/LAYOUT_CONTRACT.md docs/dsd/handoffs/P04.md \
  docs/dsd/handoffs/P04_CHECKPOINT.md \
  tests/dsd/test_layout.py tests/dsd/test_layout.c \
  tests/dsd/fixtures/p04/manifest.json \
  tests/dsd/fixtures/p04/p04_ambiguous.dff \
  tests/dsd/fixtures/p04/p04_context.dff \
  tests/dsd/fixtures/p04/p04_five_lsco3.dff \
  tests/dsd/fixtures/p04/p04_mono_unmasked.wav \
  tests/dsd/fixtures/p04/p04_opaque_assignment.wsd \
  tests/dsd/fixtures/p04/p04_quad_unmasked.wav \
  tests/dsd/fixtures/p04/p04_six_lsco4.dff \
  tests/dsd/fixtures/p04/p04_stereo_masked.wav \
  tests/dsd/fixtures/p04/p04_stereo_lsco0.dff \
  tests/dsd/fixtures/p04/p04_stereo_side_masked.wav \
  tests/dsd/fixtures/p04/p04_stereo_unmasked.wav \
  tests/dsd/fixtures/p04/p04_stereo_unsupported_mask.wav \
  tests/dsd/fixtures/p04/p04_swap_lsco.dff \
  tests/dsd/fixtures/p04/p04_type5_standard.dff

# P05 preflight fixture generators, numeric/unit tests and human handoff.
EXTRA_DIST += docs/dsd/sows/P05.md docs/dsd/handoffs/P05.md \
  tests/dsd/test_plan.c tests/dsd/test_plan.py tests/dsd/bench_plan.py

# Round briefs: the instructions dispatched per phase and correction.
EXTRA_DIST += docs/dsd/briefs/P00a-corrective.md \
  docs/dsd/briefs/P01.md \
  docs/dsd/briefs/P02.md \
  docs/dsd/briefs/P03.md \
  docs/dsd/briefs/P04.md \
  docs/dsd/briefs/P05.md \
  docs/dsd/briefs/hotfix-p02-dff-read.md

# P02 DFF read hotfix: equivalence check, targeted bench and handoff.
EXTRA_DIST += tests/dsd/bench_hotfix_dff.py \
  tests/dsd/check_hotfix_equivalence.py \
  docs/dsd/handoffs/P02_DFF_READ_HOTFIX.md

# P06 private scalar reconstruction certification, fixtures and benchmarks.
EXTRA_DIST += src/dsd_packed.h src/dsd_packed.c
EXTRA_DIST += src/dsd_coeffs.h src/dsd_decode.h src/dsd_kernels.h \
  tests/dsd/generate_coeffs.py tests/dsd/certify_filters.py \
  tests/dsd/test_decode.c tests/dsd/test_decode.py \
  tests/dsd/bench_decode.py tests/dsd/test_decode_faults.c tests/dsd/reference/p06_coefficients.json \
  docs/dsd/handoffs/P06.md
EXTRA_DIST += docs/dsd/briefs/P07.md

# P07 public decoder and explicit conversion integration evidence.
EXTRA_DIST += src/rate_internal.h src/dsd_public.c src/dsdpcm.c \
  tests/dsd/test_p07.c tests/dsd/test_p07.py tests/dsd/test_p07_output_failures.py tests/dsd/bench_p06_hotfix.py \
  tests/dsd/test_p07_reference.c tests/dsd/test_p07_reference.py \
  tests/dsd/test_p07_composite.py tests/dsd/test_p07_impulse.py tests/dsd/test_p07_public_rate.py tests/dsd/bench_p07.py \
  docs/dsd/handoffs/P06_READ_HOTFIX_CHECKPOINT.md \
  docs/dsd/handoffs/P07.md \
  docs/dsd/handoffs/P06_READ_HOTFIX.md

# P08 automatic graph and pre-combiner domain boundaries.
EXTRA_DIST += tests/dsd/test_p08.py tests/dsd/bench_p08_adapter.py docs/dsd/handoffs/P08.md

# P09 exact-rate registry, immutable analysis reference, tests and handoff.
EXTRA_DIST += tests/dsd/test_p09.c tests/dsd/test_p09.py \
  tests/dsd/reference/p09_original_coefficients.json \
  tests/dsd/reference/analysis-v1/README.md tests/dsd/reference/analysis-v1/generate.py \
  tests/dsd/reference/analysis-v1/analyze.py tests/dsd/reference/analysis-v1/verify.py \
  tests/dsd/reference/analysis-v1/measure_candidates.py \
  tests/dsd/reference/analysis-v1/manifest.json tests/dsd/reference/analysis-v1/SHA256SUMS.txt \
  tests/dsd/reference/analysis-v1/fir-2822400.f64le \
  tests/dsd/reference/analysis-v1/fir-5644800.f64le \
  tests/dsd/reference/analysis-v1/fir-11289600.f64le \
  docs/dsd/handoffs/P09.md docs/dsd/handoffs/P09_CHECKPOINT.md
EXTRA_DIST += tests/dsd/bench_p09.py
EXTRA_DIST += docs/dsd/briefs/P09_brief.md tests/dsd/sanitize_p09_results.py

# P10 fail-closed composite candidate and executable qualification evidence.
EXTRA_DIST += tests/dsd/test_p10.c tests/dsd/test_p10.py \
  tests/dsd/p10_candidate_cli.c tests/dsd/generate_p10_coeffs.py \
  tests/dsd/p10_corpus.py tests/dsd/qualify_p10.py \
  tests/dsd/reference/p10_prefilters.json tests/dsd/reference/p10_guards.json \
  docs/dsd/handoffs/P10.md docs/dsd/briefs/P10_brief.md

EXTRA_DIST += tests/dsd/soak_p10.py tests/dsd/bench_p10.py \
  tests/dsd/corroborate_p10.py

EXTRA_DIST += tests/dsd/test_p10_qualification.py

EXTRA_DIST += tests/dsd/generate_p10_profiles.py tests/dsd/reference/p10_profiles.json \
  tests/dsd/results/P10/certificate-input.json

EXTRA_DIST += tests/dsd/bench_p10_kernel_control.py

# P10 corrective: evidence classification, independent stage measurements and
# a versioned *negative* profile record. These are not release activation gates.
EXTRA_DIST += docs/dsd/handoffs/P10_CORRECTIVE.md \
  docs/dsd/handoffs/P10_CORRECTIVE_CHECKPOINT.md \
  tests/dsd/reference/p10_soak_nominal_v2.json \
  tests/dsd/reference/p10_profiles_corrective.json \
  tests/dsd/verify_p10_corrective.py \
  tests/dsd/replay_p10_numeric_bits.py \
  tests/dsd/sanitize_p10_corrective.py \
  tests/dsd/qualify_p10_corrective.py \
  tests/dsd/test_p10_corrective_qualification.py \
  tests/dsd/generate_p10_corrective_profiles.py

# P10 revalidation: executable receipt coverage and source-quantization audit.
EXTRA_DIST += tests/dsd/test_p10_soak_receipts.py \
  tests/dsd/test_p10_fixture_rounding.c \
  docs/dsd/handoffs/P10_REVALIDATION.md \
  docs/dsd/handoffs/P10_REVALIDATION_CHECKPOINT.md

# P10 release-gate measurement on material this project did not generate. The
# corpus audio itself is not distributed; only the driver and its analyser.
EXTRA_DIST += tests/dsd/corpus_realworld.py \
  tests/dsd/dsd_windows.py tests/dsd/corpus_pcm.py \
  tests/dsd/test_p10_pcm.py

# P10 independent release gate ratification (versioned; historical corrective
# receipts/certificates remain frozen). No source audio is distributed.
EXTRA_DIST += docs/dsd/handoffs/P10_RATIFICATION.md \
  docs/dsd/handoffs/P10_RATIFICATION_WORKLOG.md \
  tests/dsd/reference/p10_ratification_criteria.json \
  tests/dsd/ratify_p10_gates.py \
  tests/dsd/qualify_p10_ratification.py \
  tests/dsd/test_p10_ratification.py \
  docs/dsd/handoffs/P10_HOTFIX.md \
  docs/dsd/handoffs/P10_HOTFIX_CHECKPOINT.md

# P10 explicit reviewer closeout; positive certification and verifier are
# separate from historical negative receipts and P15 default activation.
EXTRA_DIST += docs/dsd/handoffs/P10_ADJUDICATION.md \
  docs/dsd/handoffs/P10_ADJUDICATION_WORKLOG.md \
  tests/dsd/check_p10_certification.py \
  tests/dsd/results/P10_certification_2026-10-11/certification.json \
  tests/dsd/results/P10_certification_2026-10-11/README.md \
  docs/dsd/handoffs/P10_ADJUDICATION_SHA256SUMS.txt

# P11 per-context dispatch, frozen cross-ISA qualifications, runnable ISA
# isolation and host-specific throughput characterization.
EXTRA_DIST += \
  docs/dsd/handoffs/P11.md docs/dsd/handoffs/P11_CHECKPOINT.md \
  tests/dsd/test_p11.c tests/dsd/test_p11_numeric.py \
  tests/dsd/test_p11_integration.py tests/dsd/test_p11_p10_regression.py \
  tests/dsd/check_p11_isa.py tests/dsd/bench_p11.py \
  tests/dsd/bench_p11_e2e.py
EXTRA_DIST += tests/dsd/sanitize_p11_results.py
EXTRA_DIST += tests/dsd/qualify_p11_avx1_emulator.py

# P12 independently forceable AVX2, numerical tests and ISA evidence.
EXTRA_DIST += docs/dsd/handoffs/P12.md docs/dsd/handoffs/P12_CHECKPOINT.md \
  src/dsd_kernels_avx2.c tests/dsd/check_p12_isa.py \
  tests/dsd/test_p12_bounds.c tests/dsd/test_p12_channels.py \
  tests/dsd/bench_p12_matrix.py tests/dsd/sanitize_p12_results.py

# P13 AVX-512F baseline, numeric/guard/ISA tests and host-bound matrix.
EXTRA_DIST += docs/dsd/handoffs/P13.md docs/dsd/handoffs/P13_CHECKPOINT.md \
  src/dsd_kernels_avx512.c tests/dsd/test_p13.c \
  tests/dsd/check_p13_isa.py tests/dsd/bench_p13_matrix.py

# P14 observational native statistics and versioned report contract.
EXTRA_DIST += docs/dsd/handoffs/P14.md docs/dsd/handoffs/P14_CHECKPOINT.md \
  docs/dsd/handoffs/P14_CORRECTIVE.md \
  docs/dsd/handoffs/P14_CORRECTIVE_CHECKPOINT.md \
  tests/dsd/test_p14.c \
  tests/dsd/test_p14.py tests/dsd/test_p14_numeric.py \
  tests/dsd/bench_p14.py tests/dsd/reference/p14_report_schema_v1.json \
  tests/dsd/reference/p14_report_golden.json


# Non-phase performance investigation; no production policy or DSP changes.
EXTRA_DIST += tests/dsd/profile_decode.py tests/dsd/test_perf_measurements.py \
  docs/dsd/PERFORMANCE_INVESTIGATION_2026-10-12.md

.PHONY: check-dsd-optimization
check-dsd-optimization: all
	$(MAKE) -C test dsd_test_decode_optimization$(EXEEXT)
	$(abs_builddir)/test/dsd_test_decode_optimization$(EXEEXT) scalar

# Decoder optimization measurements; production policy remains unchanged.
EXTRA_DIST += tests/dsd/bench_decode_optimization.py

# P15 release qualification and migration (source-only continuation).
EXTRA_DIST += docs/dsd/handoffs/P15.md docs/dsd/handoffs/P15_CHECKPOINT.md \
  docs/dsd/QUALIFICATION.md docs/dsd/MIGRATION_P15.md \
  docs/dsd/P15_RELEASE_NOTES.md tests/dsd/test_p15.py \
  tests/dsd/p15_release_manifest.py

# P15 closeout is an adjudication of retained source-bound receipts, not a
# qualification bit or automatic-default migration.
EXTRA_DIST += docs/dsd/handoffs/P15_CLOSEOUT_ADJUDICATION_2026-10-14.md \
  docs/dsd/handoffs/P15_CLOSEOUT_CHECKPOINT_2026-10-14.md \
  tests/dsd/p15_closeout_review.py tests/dsd/test_p15_closeout_review.py \
  tests/dsd/results/P15_closeout_adjudication_2026-10-14/review.json \
  tests/dsd/results/P15_closeout_adjudication_2026-10-14/preservation.json

# P15-R3 additive candidate: explicit, opt-in qualification runner.
# Results go to the build directory; never mutate historical source receipts.
.PHONY: check-dsd-p15-r3
check-dsd-p15-r3: all
	$(MAKE) -C test dsd_test_p15_instrument dsd_test_p07_reference
	PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 python3 $(srcdir)/tests/dsd/generate_coeffs.py --check
	PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 python3 $(srcdir)/tests/dsd/generate_p15_r3_coeffs.py --check
	PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 python3 $(srcdir)/tests/dsd/certify_p15_r3_filters.py --grid 8192 --results $(abs_builddir)/p15-r3-check/numeric
	PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 python3 $(srcdir)/tests/dsd/test_p15_r3_numeric.py --probe $(abs_builddir)/test/dsd_test_p15_instrument --results $(abs_builddir)/p15-r3-check/numeric
	PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 python3 $(srcdir)/tests/dsd/test_p15_r3.py --sox $(abs_builddir)/src/sox --results $(abs_builddir)/p15-r3-check/integration
	PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 python3 $(srcdir)/tests/dsd/test_p15_r3_src_spot.py --probe $(abs_builddir)/test/dsd_test_p07_reference --results $(abs_builddir)/p15-r3-check/numeric

EXTRA_DIST += docs/dsd/handoffs/P15_R3_RECONSTRUCTION_POLICY_HANDOFF.md \
  docs/dsd/handoffs/P15_R3_RECONSTRUCTION_POLICY_CHECKPOINT.md \
  tests/dsd/generate_p15_r3_coeffs.py tests/dsd/certify_p15_r3_filters.py \
  tests/dsd/test_p15_r3_numeric.py tests/dsd/test_p15_r3.py \
  tests/dsd/test_p15_r3_src_spot.py tests/dsd/bench_p15_r3_local.py \
  tests/dsd/reference/p15_r3_coefficients.json \
  tests/dsd/results/P15_R3/numeric/fir-certificate.json \
  tests/dsd/results/P15_R3/numeric/finite-and-isa.json \
  tests/dsd/results/P15_R3/numeric/src-sampled-holdouts.json \
  tests/dsd/results/P15_R3/integration/selection-and-audio.json \
  tests/dsd/results/P15_R3/regression/cli-qualification.json \
  tests/dsd/results/P15_R3/performance/local-unmatched-development-benchmark.json \
  tests/dsd/results/P15_R3/preservation.json

# P16 additive native-packed contract, probes and paired end-to-end benchmark.
EXTRA_DIST += src/dsd_packed.h src/dsd_packed.c tests/dsd/test_p16.c \
  tests/dsd/test_p16.py tests/dsd/bench_p16.py docs/dsd/handoffs/P16.md

# P17 private research candidates and source-bound qualification records.
EXTRA_DIST += src/sdm_p17_candidates.h tests/dsd/test_p17.c \
  tests/dsd/generate_p17_profiles.py tests/dsd/reference/p17_profiles.json \
  tests/dsd/test_p17_numeric.py tests/dsd/bench_p17.py \
  docs/dsd/handoffs/P17.md

# P18 closed capability release machinery and synthetic reference fixtures.
EXTRA_DIST += tests/dsd/test_p18.c tests/dsd/test_p18.py \
  docs/dsd/handoffs/P18.md docs/dsd/handoffs/P18_CHECKPOINT.md \
  docs/dsd/P18_COMPATIBILITY_LEDGER.md docs/dsd/P18_RELEASE_NOTES.md \
  docs/dsd/P18_RELEASE_MANIFEST.json docs/dsd/P18_RELEASE_MANIFEST.schema.json \
  tests/dsd/reference/p18_fixture_matrix.json tests/dsd/seal_p18_manifest.py \
  tests/dsd/fixtures/p18/p18-22579200-dff-8-1-1.dff tests/dsd/fixtures/p18/p18-22579200-dff-8-1-17.dff tests/dsd/fixtures/p18/p18-22579200-dff-8-1-32769.dff \
  tests/dsd/fixtures/p18/p18-22579200-dff-8-2-1.dff tests/dsd/fixtures/p18/p18-22579200-dff-8-2-17.dff tests/dsd/fixtures/p18/p18-22579200-dff-8-2-32769.dff \
  tests/dsd/fixtures/p18/p18-22579200-dff-8-6-1.dff tests/dsd/fixtures/p18/p18-22579200-dff-8-6-17.dff tests/dsd/fixtures/p18/p18-22579200-dff-8-6-32769.dff \
  tests/dsd/fixtures/p18/p18-22579200-dsf-1-1-1.dsf tests/dsd/fixtures/p18/p18-22579200-dsf-1-1-17.dsf tests/dsd/fixtures/p18/p18-22579200-dsf-1-1-32769.dsf \
  tests/dsd/fixtures/p18/p18-22579200-dsf-1-2-1.dsf tests/dsd/fixtures/p18/p18-22579200-dsf-1-2-17.dsf tests/dsd/fixtures/p18/p18-22579200-dsf-1-2-32769.dsf \
  tests/dsd/fixtures/p18/p18-22579200-dsf-1-6-1.dsf tests/dsd/fixtures/p18/p18-22579200-dsf-1-6-17.dsf tests/dsd/fixtures/p18/p18-22579200-dsf-1-6-32769.dsf \
  tests/dsd/fixtures/p18/p18-45158400-dff-8-1-1.dff tests/dsd/fixtures/p18/p18-45158400-dff-8-1-17.dff tests/dsd/fixtures/p18/p18-45158400-dff-8-1-32769.dff \
  tests/dsd/fixtures/p18/p18-45158400-dff-8-2-1.dff tests/dsd/fixtures/p18/p18-45158400-dff-8-2-17.dff tests/dsd/fixtures/p18/p18-45158400-dff-8-2-32769.dff \
  tests/dsd/fixtures/p18/p18-45158400-dff-8-6-1.dff tests/dsd/fixtures/p18/p18-45158400-dff-8-6-17.dff tests/dsd/fixtures/p18/p18-45158400-dff-8-6-32769.dff \
  tests/dsd/fixtures/p18/p18-45158400-dsf-1-1-1.dsf tests/dsd/fixtures/p18/p18-45158400-dsf-1-1-17.dsf tests/dsd/fixtures/p18/p18-45158400-dsf-1-1-32769.dsf \
  tests/dsd/fixtures/p18/p18-45158400-dsf-1-2-1.dsf tests/dsd/fixtures/p18/p18-45158400-dsf-1-2-17.dsf tests/dsd/fixtures/p18/p18-45158400-dsf-1-2-32769.dsf \
  tests/dsd/fixtures/p18/p18-45158400-dsf-1-6-1.dsf tests/dsd/fixtures/p18/p18-45158400-dsf-1-6-17.dsf tests/dsd/fixtures/p18/p18-45158400-dsf-1-6-32769.dsf \
  tests/dsd/fixtures/p18/p18-dop-22579200-2-17.pcm24le tests/dsd/fixtures/p18/p18-dop-22579200-2-33.pcm24le tests/dsd/fixtures/p18/p18-dop-45158400-2-17.pcm24le \
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
