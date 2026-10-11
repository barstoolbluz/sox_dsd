# P10 independent positive certification (2026-10-11)

`certification.json` is the explicit reviewer decision for the three original
P10 guarded scalar mastering profiles. It is a **receipt-level** decision:
commercial audio and physical host executions are operator-reported, not
replayed here. It closes P10 and permits P11; it does not activate mastering
profiles or change release defaults, which are reserved for P15.

Validation from the repository root:

    python3 tests/dsd/check_p10_certification.py
    python3 tests/dsd/qualify_p10_ratification.py --output <new-output.json>
    python3 tests/dsd/test_p10_ratification.py

The ratification collector intentionally says `qualified: false`, even when
its ten measured gates pass. It measures gates but cannot itself issue this
positive certificate. Historical negative/partial certificates remain intact.
See `docs/dsd/handoffs/P10_ADJUDICATION.md` for scope and limitations.
