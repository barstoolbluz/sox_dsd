{
  description = "SoX DSD - a SoX-NG fork prioritising DSD support and numerical accuracy";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        # Shared by every variant. autoreconf is needed because the tree
        # ships no configure script.
        nativeDeps = with pkgs; [ autoconf automake libtool pkg-config file ];

        # Enough to build, run the DSD work and pass `make check-dsd`.
        # Deliberately small: this is the prototyping and CI target.
        bareDeps = with pkgs; [ libtool ];

        # Everything configure knows how to probe for. ffmpeg is in here
        # because --with-ffmpeg unlocks four dozen more input formats.
        fullDeps = with pkgs; [
          alsa-lib
          ffmpeg
          fftwFloat
          fftw
          flac
          glib
          gsm
          lame
          ladspaH
          libao
          libid3tag
          libmad
          libogg
          libopus
          libpng
          libpulseaudio
          libsndfile
          libvorbis
          opencore-amr
          opusfile
          speex
          speexdsp
          twolame
          wavpack
          curl
          libtool
        ];

        # src/ffmpeg.c execs `ffmpeg` and src/formats.c execs curl/wget to
        # fetch URLs. They are PATH lookups at runtime, not link-time deps, so
        # a full build has to carry them or it silently loses those formats.
        runtimeHelpers = with pkgs; [ ffmpeg curl wget ];

        # The DSD regression suite drives python harnesses.
        checkDeps = with pkgs; [
          (python3.withPackages (ps: with ps; [ numpy scipy mpmath jsonschema ]))
        ];

        mkSox = { variant, extraDeps ? [], configureFlags ? [], doCheck ? false,
                  wrapWith ? [] }:
          pkgs.stdenv.mkDerivation {
            pname = "sox-dsd-${variant}";
            version = "14.8.0+git";
            src = self;

            nativeBuildInputs = nativeDeps
              ++ pkgs.lib.optional (wrapWith != []) pkgs.makeWrapper
              ++ pkgs.lib.optionals doCheck checkDeps;
            buildInputs = extraDeps;

            preConfigure = "autoreconf -fi";
            inherit configureFlags;

            enableParallelBuilding = true;

            inherit doCheck;
            checkTarget = "check-dsd";

            postInstall = pkgs.lib.optionalString (wrapWith != []) ''
              wrapProgram $out/bin/sox \
                --prefix PATH : ${pkgs.lib.makeBinPath wrapWith}
            '';

            meta = with pkgs.lib; {
              description = "SoX DSD (${variant} build): SoX-NG fork prioritising DSD";
              homepage = "https://github.com/barstoolbluz/sox_dsd";
              license = licenses.gpl2Plus;
              mainProgram = "sox";
              platforms = platforms.unix;
            };
          };
      in {
        packages = rec {
          # Small, fast, no optional codecs. For prototyping and CI.
          bare = mkSox {
            variant = "bare";
            extraDeps = bareDeps;
            configureFlags = [ "--without-ffmpeg" "--disable-shared" ];
          };

          # Everything SoX can link against, including ffmpeg.
          full = mkSox {
            variant = "full";
            extraDeps = fullDeps;
            configureFlags = [ "--with-ffmpeg" ];
            wrapWith = runtimeHelpers;
          };

          # Same as bare, but runs make check-dsd during the build.
          checked = mkSox {
            variant = "checked";
            extraDeps = bareDeps;
            configureFlags = [ "--without-ffmpeg" "--disable-shared" ];
            doCheck = true;
          };

          default = full;
        };

        apps.default = {
          type = "app";
          program = "${self.packages.${system}.full}/bin/sox";
        };

        devShells.default = pkgs.mkShell {
          packages = nativeDeps ++ fullDeps ++ checkDeps;
          shellHook = ''
            echo "SoX DSD dev shell. autoreconf -fi && ./configure && make"
          '';
        };
      });
}
