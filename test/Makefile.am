EXTRA_DIST = samples.c \
  BUG-libsndfile-float-level/README \
  BUG-libsndfile-float-level/run \
  BUG-libsndfile-float-level/sox-f32-minus20.caf \
  BUG-libsndfile-float-level/sox-f32-minus20.w64 \
  BUG-libsndfile-float-level/sox-f64-minus20.caf \
  BUG-libsndfile-float-level/sox-f64-minus20.w64

CLEANFILES = samples$(EXEEXT) samples.o

samples$(EXEEXT): samples.c
	$(CC) -o samples$(EXEEXT) samples.c

check-am: samples$(EXEEXT)
	sox=../../src/sox_ng sh $(srcdir)/check.sh -n

dist-hook:
	rm -f $(distdir)/samples$(EXEEXT) $(distdir)/samples.o
	rm -rf $(distdir)/.deps
