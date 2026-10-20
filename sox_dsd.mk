# This file is part of MXE. See LICENSE.md for licensing information.

PKG             := sox_dsd
$(PKG)_WEBSITE  := https://github.com/barstoolbluz/sox_dsd
$(PKG)_DESCR    := SoX DSD
$(PKG)_IGNORE   :=
$(PKG)_VERSION  := 14.8.0+git
$(PKG)_CHECKSUM := 0000000000000000000000000000000000000000000000000000000000000000
$(PKG)_SUBDIR   := $(PKG)-$($(PKG)_VERSION)
$(PKG)_FILE     := $(PKG)-$($(PKG)_VERSION).tar.gz
$(PKG)_URL      := https://github.com/barstoolbluz/sox_dsd/releases/download/$($(PKG)_SUBDIR)/$($(PKG)_FILE)
$(PKG)_DEPS     := cc fftw file flac lame libid3tag libltdl libmad libpng \
                   libsndfile opencore-amr opusfile libopusenc speex speexdsp \
                   twolame vorbis wavpack

define $(PKG)_UPDATE
     echo 'TODO: write update script for $(PKG).' >&2
     echo $($(PKG)_VERSION)
endef

define $(PKG)_BUILD
    # Enable cross-target OpenMP for static link metadata. The fork retains
    # the public SoX-NG library and pkg-config interface.
    $(SED) -i 's,^\(Cflags:.*\),\1 -fopenmp,' '$(1)/sox_ng.pc.in'

    cd '$(1)' && ./configure \
        --host='$(TARGET)' \
        --prefix='$(PREFIX)/$(TARGET)' \
        --build="`config.guess`" \
        --disable-shared \
        --enable-static \
        --disable-debug \
        --with-libltdl \
	CFLAGS='-fno-pie -O2' \
	LDFLAGS='-fno-pie' \
        LIBS='-lshlwapi -lgnurx'

    $(MAKE) -C '$(1)' -j '$(JOBS)' bin_PROGRAMS= EXTRA_PROGRAMS=
    $(MAKE) -C '$(1)' -j 1 install
endef

$(PKG)_BUILD_SHARED =
