# SoX DSD

SoX DSD is a fork of [SoX-NG](https://codeberg.org/sox_ng/sox_ng),
with better DSD support as its first priority. It remains a general-purpose
SoX: the existing formats, effects, command-line tools and build system
are part of the project, not something we plan to replace.

SoX-NG maintains and improves SoX by bringing together fixes and new work
from distributions and other forks. SoX DSD builds on that work, but is
putting more effort into DSD and into the numerical quality of audio
processing more generally.

## What is different?

### DSD

The current work extends DSD64, DSD128 and DSD256 processing, including
native DSF and DSDIFF I/O, DSD-to-PCM reconstruction, and DSD encoding.
It adds DSD-aware planning and versioned reconstruction filters rather
than treating all DSD-to-PCM conversions as interchangeable.

**DSD512 and DSD1024 are next on the roadmap.** We plan to support them
as native DSD formats, with the decoding, encoding, filtering, performance
work and tests that go with that. They are not shipped features yet. P18 has added explicit per-format and per-transport refusal gates; see
[the compatibility ledger](docs/dsd/P18_COMPATIBILITY_LEDGER.md).

The source-aware v2 mastering reconstruction is the default for DSD64,
DSD128 and DSD256. The earlier v1 filters are preserved and remain
selectable. To ask for v1 explicitly:

    sox --dsd-mode auto --dsd-decode decode.mastering.v1.dsd64 \
      input.dsf -r 176400 -b 24 output.wav

For profile selection, supported conversions and current qualification
status, see [the DSD CLI guide](docs/dsd/MIGRATION_P15.md) and
[the DSD documentation](docs/dsd/README.md).

### Numerical accuracy

DSD is where we're starting, not where we intend to stop. We also want to
improve the rest of SoX's DSP where better algorithms or more careful
arithmetic can make a real difference: resampling, filtering, gain
processing and other effects.

We care about errors small enough to measure, even when they are too small
to hear. But more bits and more complicated code are not automatically
better. We'll use independent numerical references, difficult test cases
and measurements to find out whether a change actually improves things.
And we'll keep performance in view. The aim is to get as close to the
mathematically intended result as practical, without claiming that a
finite-precision program can be literally perfect.

## Terminology

`sox` means the command-line executable used by SoX DSD; the original SoX project is at [sox.sf.net](http://sox.sf.net)<BR>
`SoX` means the Swiss Army Knife of command-line audio processing in any of its incarnations<BR>
`sox_ng` means the hard fork of `sox-14.4.2` aiming to sanitize `SoX`<BR>
`SoX_ng` means the project to maintain `sox_ng`<BR>
`SoX DSD` means this fork of SoX-NG

## How to get it

Use the SoX DSD source tree or a release archive from this project.
The [SoX-NG repository](https://codeberg.org/sox_ng/sox_ng) and its
[releases](https://codeberg.org/sox_ng/sox_ng/releases) are **upstream
SoX-NG**, not SoX DSD.

### Releases

For a SoX DSD source release on Unix-compatible systems, extract the
archive, change into its directory, and build it:

    ./configure
    make

Install it:

    sudo make install

The command-line executable is named `sox`. The source still retains
SoX-NG-derived library and header names, including `sox_ng.h` and
`libsox_ng.so`.
The accompanying commands use the standard names `soxi`, `play` and `rec`
(where audio-device support makes `play`/`rec` available). Existing
`soxi_ng`, `play_ng` and `rec_ng` command aliases remain available for
compatibility when symbolic links are enabled. `--disable-symlinks`
suppresses those aliases; `--enable-replace` now controls only optional
library, header, pkg-config and library-documentation compatibility aliases.
This binary-name change does **not** rename the library ABI or the headers.

### Development branches

#### main

From a checkout of this project's source tree, compile it with:

    autoreconf -i
    ./configure
    make

and install it with:

    sudo make install

To build with FFmpeg format support when FFmpeg is installed, add
`--with-ffmpeg` to `./configure`. For DSD-specific regression tests,
run `make check-dsd`.

## Runtime dependencies

If `ffmpeg` is installed on your system, `sox` will be able to read
four dozen more audio formats as well as extract soundtracks from video files.

If `wget`, `wget2` or `curl` are installed, you can fetch URLs as input
streams.

## Build dependencies

To compile a release tarball you will need `make`, and `gcc` or `clang`

To build the git repository you will also need `autoconf`, `automake`
and `libtool`.

To enable all of SoX's optional modules you can install
`ladspa-sdk`
`lame`,
`libao`,
`libfftw3`,
`libflac`,
`libid3tag`,
`libmad`
`libogg`,
`libopus`,
`libopusfile`,
`libpng`,
`libsndfile`,
`libspeex`,
`libspeexdsp`,
`libvorbis`,
`opencore-amr`,
`twolame`,
`wavpack`.

### Debian, Ubuntu, Mint etc.

    apt install gcc make libtool ladspa-sdk libao-dev libasound2-dev libfftw3-dev \
    libgsm1-dev libid3tag0-dev libltdl-dev libmad0-dev libmagic-dev \
    libmp3lame-dev libopencore-amrnb-dev libopencore-amrwb-dev \
    libopusfile-dev libpng-dev libpulse-dev \
    libsndfile1-dev libspeex-dev libspeexdsp-dev libtwolame-dev \
    libvorbis-dev libwavpack-dev

and to run `issues/getissues.sh` and the `makehtml.sh` scripts you will need

    apt-get install jq libtext-multimarkdown-perl

### Fedora, Red Hat, CentOS etc.

    yum install gcc make libtool \
    alsa-lib-devel fftw-devel file-devel flac-devel gsm-devel \
    ladspa-devel lame-devel libao-devel libid3tag-devel \
    libmad-devel libpng-devel libsndfile-devel \
    libtool-ltdl-devel libvorbis-devel opencore-amr-devel \
    opusfile-devel pulseaudio-libs-devel speex-devel speexdsp-devel \
    twolame-devel wavpack-devel

and to run `issues/getissues.sh` and the `makehtml.sh` scripts you will need

    yum install jq multimarkdown

### FreeBSD

    pkg install gcc dmake fftw3 file ladspa libid3tag png \
    flac gsm lame libmad libsndfile libvorbis opencore-amr \
    opusfile speex speexdsp twolame wavpack

but you can almost certainly omit `file` which it wants for `libmagic`
which is installed in a default FreeBSD installation in `/usr/lib`.
If you install it with `pkg`, you get a second copy under `/usr/local`.

You can also install `pulseaudio` `alsa-libs` and `libao`
if you want support for those alternative sound I/O systems.

If you are compiling its development git tree you will also need to

    pkg install autotools libtool

To run `issues/getissues.sh` and the `makehtml.sh` scripts you will need

    pkg install jq multimarkdown

## Upstream SoX-NG

The original SoX-NG code, wiki and issue tracker are at
[codeberg.org/sox_ng/sox_ng](https://codeberg.org/sox_ng/sox_ng).
The following contacts belong to **SoX-NG**, not to SoX DSD.

### Accessibility

You can edit and commit to the upstream code and wiki using Codeberg's web
interface or from the command-line. The command-line is the only way to add
images and attachments to the wiki.

The issues can be downloaded as well as uploaded replacing all remote content
but this risks overwriting changes made via the web interface so for now
it is recommended to edit them on the Codeberg web site.

## README and PDFs

To generate SoX's original README, run `./README.sh` or `make README`

To generate the PDF version of the documentation, `make pdf`
