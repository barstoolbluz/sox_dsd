"""RF64 ds64 table entries: independently constructed native-only acceptance.

These fixtures intentionally do not use the SoX RF64 writer. The one-entry
historical fixture does *not* use a sentinel JUNK length; the additional cases
below exercise table sizes that must be used to find the audio payload.
"""
import struct
import subprocess

U32 = 0xffffffff


def chunk(tag, payload, sentinel=False):
    return (tag + struct.pack('<I', U32 if sentinel else len(payload)) + payload +
            (b'\x00' if len(payload) & 1 else b''))


def make_pair(extra, *, table=None):
    """extra: sequence (FourCC, bytes, sentinel); table entries in chunk order."""
    fmt = struct.pack('<HHIIHH', 1, 2, 48000, 192000, 4, 16)
    data = struct.pack('<12h', 32767, -32768, -100, 100, -1, 1,
                       12345, -12345, 3, -3, 0, 17)
    before = chunk(b'fmt ', fmt)
    for tag, payload, sentinel in extra:
        before += chunk(tag, payload, sentinel)
    payload_chunks = before + chunk(b'data', data, True)
    entries = [(tag, len(body)) for tag, body, sentinel in extra if sentinel]
    if table is not None:
        entries = table
    table_bytes = b''.join(tag + struct.pack('<Q', size) for tag, size in entries)
    ds_body_length = 28 + len(table_bytes)
    rf64_size = 4 + 8 + ds_body_length + len(payload_chunks)
    ds = struct.pack('<QQQI', rf64_size, len(data), 6, len(entries)) + table_bytes
    rf64 = (b'RF64' + struct.pack('<I', U32) + b'WAVE' + chunk(b'ds64', ds) + payload_chunks)
    normal = chunk(b'fmt ', fmt)
    for tag, payload, _ in extra:
        normal += chunk(tag, payload)
    normal += chunk(b'data', data)
    riff = b'RIFF' + struct.pack('<I', 4+len(normal)) + b'WAVE' + normal
    return riff, rf64


def verify(runner):
    def insist(ok, message):
        if not ok:
            raise AssertionError(message)
    # The supplied one-entry file already passes native admission in the
    # parent revision; keep it as a permanent regression for that fact.
    from pathlib import Path
    supplied = Path(__file__).resolve().parent / 'fixtures' / 'phase04'
    rf = supplied / 'rf64-pcm-ds64-table-entry.wav'
    ri = supplied / 'riff-pcm-table-case-same-audio.wav'
    expected = []
    for path in (rf, ri):
        runner.query(path, frames=300, channels=2, bits=16, rate=48000)
        if runner.native_dsp:
            b, _ = runner.invoke(['dump', path, 23], label='rf64-supplied-dump-'+path.name)
            expected.append(b)
    if runner.native_dsp:
        insist(expected[0] == expected[1], 'supplied RF64 vs RIFF PCM differs')
        runner.tick('rf64_table_supplied_pcm_comparisons')
    # Legacy read behavior for the supplied pair must be unaffected.
    legacy = []
    for path in (rf, ri):
        cmd = [str(runner.sox), '-R', '-D', str(path), '-t', 'raw',
               '-e', 'signed-integer', '-b', '16', '-']
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        insist(cp.returncode == 0, 'ordinary SoX refused supplied RF64/RIFF pair')
        legacy.append(cp.stdout)
        runner.commands.append({'label':'rf64-table-ordinary-sox', 'argv':cmd,
                                'exit':cp.returncode, 'stdout_bytes':len(cp.stdout)})
    insist(legacy[0] == legacy[1], 'ordinary SoX changed supplied RF64 audio')
    runner.tick('rf64_table_legacy_pair_checks')

    variants = (
        ('zero', [], None),
        ('one-normal', [(b'JUNK', b'abcde', False)], None),
        ('one-sentinel', [(b'JUNK', b'abcde', True)], None),
        ('two-sentinel', [(b'JUNK', b'abcde', True), (b'LIST', b'xyz1234', True)], None),
        ('repeated-id', [(b'JUNK', b'abcde', True), (b'JUNK', b'abcdef', True)], None),
        ('three-mixed', [(b'JUNK', b'abcde', True), (b'LIST', b'\x01', False),
                         (b'NOTE', b'01234567', True)], None),
        # The table orders entries by FourCC, not necessarily by file chunk
        # order. Occurrences of the SAME FourCC still retain their order.
        ('reversed-distinct', [(b'JUNK', b'abcde', True),
                               (b'LIST', b'xyz1234', True)],
         [(b'LIST', 7), (b'JUNK', 5)]),
        ('grouped-repeated', [(b'JUNK', b'abcde', True),
                              (b'LIST', b'one', True),
                              (b'JUNK', b'012345678', True),
                              (b'LIST', b'xyz1234', True)],
         [(b'JUNK', 5), (b'JUNK', 9), (b'LIST', 3), (b'LIST', 7)]),
        ('interleaved-table', [(b'JUNK', b'abcde', True),
                               (b'LIST', b'one', True),
                               (b'JUNK', b'012345678', True),
                               (b'LIST', b'xyz1234', True)],
         [(b'LIST', 3), (b'JUNK', 5), (b'LIST', 7), (b'JUNK', 9)]),
    )
    for name, extra, table in variants:
        riff, rf64 = make_pair(extra, table=table)
        rp = runner.file('rf64-table-'+name+'-riff.wav', riff)
        fp = runner.file('rf64-table-'+name+'-rf64.wav', rf64)
        for f in (rp, fp):
            runner.query(f, frames=6, channels=2, bits=16, rate=48000)
        runner.tick('rf64_table_valid_variants')
        if runner.native_dsp:
            r, _ = runner.invoke(['dump', rp, 7], label='rf64-table-'+name+'-riff-dump')
            f, _ = runner.invoke(['dump', fp, 7], label='rf64-table-'+name+'-rf64-dump')
            insist(r == f and len(f) == 12*8,
                   'RF64 ds64 table changed native decoded PCM: '+name)
            runner.tick('rf64_table_exact_pcm_comparisons')

    _, valid = make_pair([(b'JUNK', b'abcde', True), (b'LIST', b'xyz1234', True)])
    def change(index, value):
        data = bytearray(valid)
        data[index:index+len(value)] = value
        return bytes(data)
    # ds64 begins at offset 12; count at 44; first entry at 48.
    rejects = {
        'count-over': change(44, struct.pack('<I', 3)),
        'count-under': change(44, struct.pack('<I', 1)),
        'wrong-tag': change(48, b'NONE'),
        'wrong-size': change(52, struct.pack('<Q', 400)),
        'wrong-second-size': change(64, struct.pack('<Q', 1)),
        'ds64-length-short': change(16, struct.pack('<I', 40)),
        'ds64-length-long': change(16, struct.pack('<I', 64)),
        'table-truncated': valid[:55],
        'data-truncated': valid[:-1],
        'out-of-range-size': change(52, struct.pack('<Q', 1<<63)),
    }
    # Sentinel chunk without a table entry must also refuse.
    _, no_entry = make_pair([(b'JUNK', b'abcde', True)], table=[])
    rejects['sentinel-entry-missing'] = no_entry
    for name, blob in rejects.items():
        fp = runner.file('rf64-table-invalid-'+name+'.wav', blob)
        runner.reject(['query', fp], label='rf64-table-invalid-'+name)
        runner.tick('rf64_table_malformed_refusals')
    runner.gates['rf64_ds64_table_native_metadata'] = 'PASS'
    runner.gates['rf64_ds64_table_native_decode'] = (
        'PASS' if runner.native_dsp else runner.native_unavailable())
    runner.gates['rf64_ds64_table_ordinary_reader_unchanged'] = 'PASS'
