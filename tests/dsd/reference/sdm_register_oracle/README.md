# Frozen scalar oracle

These seven files are byte-for-byte copies from the attached reconstruction,
identified in `provenance.json`. They are test data, not production sources.

`run_sdm_register.py` verifies their hashes before compilation and renames
public symbols with preprocessor definitions. The resulting scalar step and
block entry point use the original recurrence, acceptor, profile coefficients
and monitor code. They do not share candidate acceptance code.

Common type and platform headers come from the source/build under test. The
runner checks that original and candidate coefficient values, orders and rate
identities agree before differential tests. The tested changes do not alter
these common declarations.

Do not update this oracle to make a candidate pass. A new reference requires
an explicit provenance change and independent review.
