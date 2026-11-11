# Tracking sox_ng

SoX DSD is a fork of [sox_ng](https://codeberg.org/sox_ng/sox_ng), which is
itself a continuation of SoX. We keep pulling from it.

## Why our version number is independent

SoX DSD versions itself from `1.0.0`, not from sox_ng's number. The sox_ng
release a tree is synchronised with is recorded separately, in
`SOX_DSD_UPSTREAM_BASE` in `configure.ac`, and printed by `sox --version`:

    sox:      SoX DSD v1.1.1 (based on sox_ng 14.8.1)

The alternative, versioning as `14.8.0.1+dsd.N`, was rejected deliberately.
Under that scheme a sync to sox_ng 14.9 would move our version for reasons
that have nothing to do with our work, reset our own counter, and leave
nobody able to tell from a version whether SoX DSD changed or merely
rebased. Taking sox_ng's next unused number, 15.0, would have been worse:
it claims a position in a sequence we do not control, so a future sox_ng
15.0 would collide with ours.

Merging upstream and owning a version line are independent choices. Keep
pulling; bump our number when *we* ship something.

## Remotes

    upstream   https://codeberg.org/sox_ng/sox_ng   (fetch only; push is disabled)
    sox_dsd    github.com:barstoolbluz/sox_dsd      (our releases, branch main)
    origin, gh  personal sox_ng forks, predating SoX DSD

`upstream` has its push URL set to a non-resolving placeholder on purpose.
Nothing of ours belongs there.

## Syncing

    git fetch upstream --tags
    git log --oneline sox_ng-<ourbase>..sox_ng-<new>      # read what is coming
    git merge sox_ng-<new>

Then, in one commit:

1. Resolve conflicts. They concentrate in the inherited files we have
   changed most: `src/sox_ng.c`, `src/formats.c`, `src/dsf.c` and
   `src/dsdiff.c`, where DSD hooks meet inherited code, and the legacy SDM
   modulator (`src/sdm.c`, `src/sdm.h`, `src/sdm_x86.h`), which carries our
   register kernels and guard. Smaller changes in `src/rate.c`,
   `src/util.c` and the build files (`Makefile.am`, `configure.ac`,
   `cmake-buildsetup/`) can conflict too. The 41 DSD-specific files in
   `src/` cannot conflict, which is why keeping the hooks small and clearly
   delimited is worth the effort at review time.
2. Update `SOX_DSD_UPSTREAM_BASE` in `configure.ac` and
   `cmake-buildsetup/CMakeLists.txt` to the new sox_ng release. Leave
   SoX DSD's own release version unchanged.
3. Re-run `autoreconf -fi && ./configure && make clean && make`. The clean
   is not optional after `autoreconf`: stale objects from the previous
   configuration produce link errors that look like missing symbols in
   `libgsm` and have nothing to do with the merge.
4. Run `make check-dsd`, `make check` and `make check-rename`. `check-dsd`
   writes its results under `.dsd-check-results/`, which is not tracked.

A sync is not a release. Bump the SoX DSD version only when shipping.

## Tags

Our releases are tagged `sox_dsd-<version>`. The inherited `sox_ng-*` tags
are upstream history and the fetch above adds more of them; do not create
new tags in that namespace.

## Divergence, as of 1.1.1

41 of 286 files in `src/` are DSD-specific; the other 245 come from sox_ng
14.8.1. Our modifications to inherited code are concentrated in the files
listed above. The whole DSD engine, its tests under `tests/dsd/` and its
documentation under `docs/dsd/` are ours and have no upstream counterpart.
The phase evidence that used to live in `tests/dsd/results/` is published
as an asset of the 1.1.1 GitHub release.
