#!/usr/bin/env python3
"""D11: source-pinned, *conditional* all-input error accounting.

This is deliberately not an FFT4G or libm certificate. The FIR/polyphase
arithmetic terms are computable for the stored coefficients under the named
IEEE environment. FFT4G terms use the predecessor's explicit 512*log2(N)
FINITE SCREEN, not an established worst-case result. Unknown premises are
always reported OPEN, including on a clean pass.

The existing high-precision tests remain the independent numeric witnesses.
This gate verifies those receipts, source snapshots and routes, composes their
arithmetic envelopes, and rejects unsupported changes or discrepant samples.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import copy
from fractions import Fraction as F
import hashlib
import json
import math
import platform
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tests/dsd'))
sys.path.insert(0, str(ROOT / 'tests/pcm64/qualification'))
from p15_src_bound_operator import load_snapshot
from fir_reference import BANKS, read_bank
from unified_reference import banks as decoder_banks

U = F(1, 2 ** 53)
ETA = F(1, 2 ** 1074)
# This is the OLD finite-screen multiplier, not a validated FFT4G theorem.
FFT_SCREEN_FACTOR = 512


class InvalidEvidence(AssertionError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidEvidence(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(path, want):
    obj = json.loads(path.read_text())
    require(obj.get('status') == want, f'{path.name}: missing/failed receipt')
    return obj


def exact_abs_sum(numbers):
    return sum((abs(F.from_float(float(v))) for v in numbers), F(0))


def gamma(k):
    require(type(k) is int and 0 < k and k * U < 1, 'non-admissible gamma operations')
    return (k * U) / (1 - k * U)


def summarize(value):
    """Readable binary64 approximation; all bounds are computed as rationals."""
    return format(float(value), '.17g')


def src_stage_norm(stage):
    """Proven ideal L_infinity operator upper bound from stored tap words.

    For FFT/overlap-save it is the maximum absolute FIR row norm over each
    interpolation residue. It does NOT bound the executed FFT arithmetic.
    Phase-wise bound is materially tighter than L*sum(abs(all taps)).
    """
    if stage.kind == 2:
        require(stage.L > 0 and stage.dft_length in (1024, 4096, 8192),
                'unrecognized FFT family or length')
        return max(F(stage.L) * exact_abs_sum(stage.coeff[r::stage.L])
                   for r in range(stage.L))
    if stage.kind == 3:
        require(stage.order == 0 and stage.phases == stage.L,
                'higher-order polyphase needs a separate error proof')
        return max(exact_abs_sum(stage.coeff[i*stage.n:(i+1)*stage.n])
                   for i in range(stage.phases))
    if stage.kind == 1:
        return F(1, 2) + 2 * exact_abs_sum(stage.coeff)
    raise InvalidEvidence('unknown source stage')


def step(ideal_peak, incoming_error, norm, k):
    """For exact stored coefficients and finite, gradual-underflow RN math.

    Standard relative-add/multiply gamma with a per-operation ETA remainder:
      |fl(sum) - sum| <= gamma(k)*sum_i|w_i*x_i| + k*eta.
    For FFT this is ONLY an unproved conditional term (k is a screen).
    """
    local = gamma(k) * norm * (ideal_peak + incoming_error) + k * ETA
    return norm * ideal_peak, norm * incoming_error + local


def stage_accounting(operator, peak, error, *, route):
    rows = []
    for index, s in enumerate(operator.stages):
        norm = src_stage_norm(s)
        if s.kind == 2:
            k = FFT_SCREEN_FACTOR * int(math.log2(s.dft_length))
            premise = 'UNPROVED_FFT4G_512_LOG2_SCREEN'
        elif s.kind == 3:
            k = 2 * s.n + 2   # n products, n accumulations; two margin ops
            premise = 'IEEE_RN_POLYPHASE_ORDER0'
        else:
            k = 3 * len(s.coeff) + 3  # generic half-band margin
            premise = 'IEEE_RN_HALF_BAND'
        peak, error = step(peak, error, norm, k)
        rows.append({'stage': index, 'family': s.kind, 'input_hz': operator.input_hz,
                     'output_hz': operator.output_hz, 'fft_length': s.dft_length,
                     'interpolation_L': s.L, 'source_taps': s.dft_taps if s.kind == 2 else s.n,
                     'coefficient_row_L1_upper': summarize(norm), 'k_model': k,
                     'roundoff_premise': premise,
                     'ideal_peak_upper': summarize(peak),
                     'absolute_error_upper_conditional': summarize(error)})
    return peak, error, rows


def frozen_snapshot(folder, metadata):
    path = folder / metadata['path']
    require(path.is_file() and sha(path) == metadata['sha256'],
            f'{path.name}: changed or absent source operator snapshot')
    return load_snapshot(path)


def verify_receipt_source_hashes(data, source):
    for rel, expected in data['source_sha256'].items():
        require(sha(source / rel) == expected, f'source changed since witness: {rel}')


def verify_witnesses(p2, p3, decoder, libm):
    require(len(decoder['cases']) == 64, '64 independently reconstructed DSD cases absent')
    for c in decoder['cases']:
        require(c['native_hz'] in (2822400, 5644800) and
                c['profile'] in ('mastering', 'wideband') and
                c['backend'] in ('scalar', 'auto'), 'unknown native decoder witness')
        for sample in c['samples']:
            require(0 <= sample['absolute_error_max'] <= sample['conditional_envelope'],
                    'native P3 sample exceeds independent finite screen')
    require(p3['case_count'] == 32 and len(p3['cases']) == 32 and
            len(p3['wrong_tail_mutants']) == 2, 'P3 final-SRC cases incomplete')
    require(len(p2['primitive_and_composed_cases']) == 8 and
            p2['native_src_witness_count'] == 8 and
            len(p2['native_src_witnesses']) == 8, 'P2 SRC/FIR witnesses incomplete')
    require(len(p2['negative_controls']) == 4 and
            all(c['status'] == 'REJECTED' for c in p2['negative_controls']) and
            all(c['status'] == 'REJECTED' for c in p3['wrong_tail_mutants']),
            'negative controls not rejected')
    require(libm['sample_count'] >= 41 and
            len(libm['samples']) == libm['sample_count'] and
            max(libm['observed_max_pow_ulps'], libm['observed_max_exp_ulps']) < 2,
            'libm operand witness corpus incomplete or above finite screen')
    for c in p3['cases']:
        require(c['profile'] in ('mastering', 'wideband') and
                c['kernel'] in ('scalar', 'auto') and
                c['native_hz'] in (2822400, 5644800), 'unexpected P3 route')
        for row in c['rows']:
            require(0 <= row['abs_error'] <= row['finite_screen'],
                    'P3 final-SRC sample breaks its original numerical screen')
    for c in p2['native_src_witnesses']:
        require(c['rate_hz'] in (2822400, 5644800), 'unrecognized P2 native rate')
        for row in c['native_src_stage_rows']:
            require(0 <= row['absolute_error'] <= row['source_fft_roundoff_screen'],
                    'P2 native SRC sample breaks its original numerical screen')



def recheck_runtime_libm_samples(data):
    """Recheck operands against *C* strtod and dynamically linked libm.

    A sample may pass without establishing a uniform worst-case guarantee.
    This catches discrepancies masked by Python's separate float parser,
    a changed libm, or a runtime CPU-specific implementation selection.
    """
    libc = ctypes.CDLL(None)
    libc.strtod.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p)]
    libc.strtod.restype = ctypes.c_double
    libm_path = ctypes.util.find_library('m')
    require(libm_path is not None, 'no linked libm for source runtime verification')
    libm = ctypes.CDLL(libm_path)
    libm.pow.argtypes = [ctypes.c_double, ctypes.c_double]
    libm.pow.restype = ctypes.c_double
    libm.exp.argtypes = [ctypes.c_double]
    libm.exp.restype = ctypes.c_double
    # The literal is pinned by gain_libm_reference.py and util.h's M_LN10.
    ln10 = float.fromhex('0x1.26bb1bbb55516p+1')
    for row in data['samples']:
        text = row['decimal_dB'].encode('ascii')
        end = ctypes.c_char_p()
        parsed = libc.strtod(text, ctypes.byref(end))
        require(parsed.hex() == row['parsed_binary64_hex'] and
                not end.value, f'C strtod disagrees with source witness: {text!r}')
        headroom = -parsed / 20.0
        gain = (parsed * ln10) * 0.05
        require(headroom.hex() == row['headroom_exponent_hex'] and
                gain.hex() == row['gain_exp_exponent_hex'],
                f'headroom/gain exponent premise changed for {text!r}')
        require(libm.pow(10., headroom).hex() == row['libm_pow_hex'] and
                libm.exp(gain).hex() == row['libm_exp_hex'],
                f'linked libm changed since finite witness: {text!r}')
    return len(data['samples'])


def compiled_binary_identity(sox):
    """Bind this witness to the libtool launcher *and* actual ELF objects.

    The hashes identify what was tested. Hash identity is not a proof that
    the compiler emitted the source-level floating-point operation graph.
    """
    entries = {'invoked_path': str(sox), 'invoked_sha256': sha(sox)}
    for key, path in (
        ('libtool_executable', sox.parent / '.libs' / sox.name),
        ('shared_sox_core', sox.parent / '.libs' / 'libsox_ng.so.5.0.0'),
    ):
        if path.is_file():
            entries[key] = {'path': str(path.resolve()), 'sha256': sha(path)}
        else:
            entries[key] = {'status': 'NOT_IDENTIFIED_ON_THIS_BUILD'}
    return entries


def named_environment():
    libm_name = ctypes.util.find_library('m')
    libm = ctypes.CDLL(libm_name) if libm_name else None
    # glibc FE_TONEAREST is zero on this Linux test target. This tests the
    # Python qualification process, not all possible production invocations.
    round_mode = None
    if libm is not None and hasattr(libm, 'fegetround'):
        libm.fegetround.restype = ctypes.c_int
        round_mode = libm.fegetround()
    require(sys.float_info.mant_dig == 53 and
            math.nextafter(0., 1.) == 2. ** -1074,
            'binary64/gradual-underflow premise not met by witness process')
    require(round_mode == 0, 'witness process not FE_TONEAREST')
    try:
        compiler = subprocess.check_output(['cc', '--version'], text=True).splitlines()[0]
    except (OSError, subprocess.CalledProcessError, IndexError):
        compiler = 'NOT_IDENTIFIED'
    try:
        libc = subprocess.check_output(['getconf', 'GNU_LIBC_VERSION'], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        libc = str(platform.libc_ver())
    return {'system': platform.platform(), 'machine': platform.machine(),
            'compiler_identity_observed': compiler, 'libc': libc,
            'libm_soname': libm_name, 'witness_process_fegetround': round_mode,
            'witness_python_mantissa_bits': sys.float_info.mant_dig,
            'source_to_production_binary_fp_semantics_proof': 'OPEN'}


def run(results, sox, source):
    results = results.resolve()
    require(sox.is_file(), 'SoX production binary absent')
    r = lambda name: results / name
    p2 = receipt(r('p2-encoder-frontend/independent-primitive-cascade.json'), 'PASS')
    p3 = receipt(r('p3-final-src/final-src-reference.json'), 'PASS_FINITE_WITNESSES_ONLY')
    dec = receipt(r('unified-decoder/unified-reference.json'), 'PASS_FINITE_WITNESSES_ONLY')
    libm = receipt(r('d6-libm/gain-libm-reference.json'), 'PASS_FINITE_WITNESSES_ONLY')
    verify_witnesses(p2, p3, dec, libm)
    verify_receipt_source_hashes(p3, source)
    verify_receipt_source_hashes(libm, source)
    operand_count = recheck_runtime_libm_samples(libm)
    require(p3['sox_sha256'] == sha(sox), 'decoder binary changed since SRC witness')
    require(p2['frozen_encoder_frontend_sha256']['src/rate.c'] == sha(source / 'src/rate.c'),
            'encoder SRC arithmetic changed from its frozen predecessor')
    coeff = decoder_banks()  # enforces pinned decoder coefficient SHA
    source_model = []
    for native in (2822400, 5644800):
        for profile in ('mastering', 'wideband'):
            taps = [coeff['halfband']] * 4 + [coeff['wideband'] if profile == 'wideband'
                    else coeff['master64_256' if native == 2822400 else 'master128']]
            peak, error = F(1), F(0)
            stages = []
            for h in taps:
                norm = exact_abs_sum(h)
                k = 2*len(h) + 4
                peak, error = step(peak, error, norm, k)
                stages.append({'taps': len(h), 'L1_upper': summarize(norm),
                               'k_source_upper': k, 'conditional_error': summarize(error)})
            assert native//32 in (88200, 176400)
            op = frozen_snapshot(r('p3-final-src'),
                     p3['source_operator_snapshots'][str(native//32)])
            require(op.input_hz == native//32 and op.output_hz == 96000,
                    'unexpected decoder rate selection')
            _peak, _error, rows = stage_accounting(op, peak, error, route='P3')
            source_model.append({'route': 'P3_decode', 'dsd_hz': native,
                'profile': profile, 'fir_stages': stages,
                'fir_out_peak_upper': summarize(peak),
                'fir_out_error_upper_ieee': summarize(error),
                'final_src_stages': rows,
                'final_src_out_error_upper_conditional': summarize(_error)})
    for native, mult in ((2822400, 2), (5644800, 4)):
        work = frozen_snapshot(r('p2-encoder-frontend'), p2['snapshots'][str(mult)])
        interpolate = frozen_snapshot(r('p2-encoder-frontend'),
                                       p2['snapshots'][f'{mult}-native'])
        require(work.input_hz == 44100 and work.output_hz == 44100*mult and
                interpolate.input_hz == 44100*mult and interpolate.output_hz == native,
                'unexpected encoder interpolation route')
        peak, error, working_rows = stage_accounting(work, F(1), F(0), route='P2')
        name, count = BANKS[64 if mult == 2 else 128]
        prefilter = read_bank(source / 'src/pcmdsd_coeffs.h', name, count)
        norm = exact_abs_sum(prefilter)
        peak, error = step(peak, error, norm, 2*count+4)
        prefilter_row = {'taps': count, 'L1_upper': summarize(norm),
                         'k_source_upper': 2*count+4,
                         'error_upper_conditional': summarize(error)}
        peak, error, native_rows = stage_accounting(interpolate, peak, error, route='P2')
        # The core applies a single multiply by .5*gain (0dB gives .5 exact).
        # B_pow MUST be added for nonzero headroom in an adopted proof.
        scale = F(1, 2)
        peak, error = step(peak, error, scale, 1)
        source_model.append({'route': 'P2_encode', 'dsd_hz': native,
            'pcm_hz': 44100, 'input_assumed_normalized_peak': '1',
            'working_src_stages': working_rows, 'prefilter': prefilter_row,
            'native_32x_src_stages': native_rows,
            'resonator_input_peak_upper': summarize(peak),
            'resonator_input_error_upper_conditional_0db': summarize(error),
            'headroom_dB_nonzero_additional_term':
                'abs(pre_scale_native_word)*B_pow + argument_roundoff + multiplication_roundoff',
            'certified_admission':
                'actual runtime input is checked against 0.5 + scale*2/SOX_SAMPLE_MAX '
                'and independently checked by unchanged certified resonator'})
    # Validate the computed candidate envelopes against the separate run's
    # samples. This is not a proof of the unproved FFT_SCREEN_FACTOR=512.
    comparisons = 0
    for c in dec['cases']:
        m = next(x for x in source_model if x['route'] == 'P3_decode' and
                 x['dsd_hz'] == c['native_hz'] and x['profile'] == c['profile'])
        budget = float(m['fir_out_error_upper_ieee'])
        for sample in c['samples']:
            require(sample['absolute_error_max'] <= budget,
                    'native decoder exceeds computed IEEE FIR gamma budget')
    for c in p2['primitive_and_composed_cases']:
        m = next(x for x in source_model if x['route'] == 'P2_encode' and
                 x['dsd_hz'] == c['rate_hz'])
        require(c['max_src_abs_error'] <=
                float(m['working_src_stages'][-1]['absolute_error_upper_conditional']),
                'P2 working SRC violates conditional stage accounting')
        require(c['max_cascade_abs_error'] <=
                float(m['prefilter']['error_upper_conditional']),
                'P2 prefilter violates conditional stage accounting')
    for c in p3['cases']:
        m = next(x for x in source_model if x['route'] == 'P3_decode' and
                 x['dsd_hz'] == c['native_hz'] and x['profile'] == c['profile'])
        budget = float(m['final_src_out_error_upper_conditional'])
        for row in c['rows']:
            require(row['abs_error'] <= budget,
                    'P3 sample exceeds composed conditional accounting envelope')
            comparisons += 1
    for c in p2['native_src_witnesses']:
        m = next(x for x in source_model if x['route'] == 'P2_encode' and
                 x['dsd_hz'] == c['rate_hz'])
        # Input is a sparse impulse (at most 0.5, -0.25, 0.125): M=1
        # model is an upper bound. Compare native stage error before scale;
        # 2x the scale=0.5 error is NOT sufficient because rescaling is also
        # rounded, so use the native stage budget itself.
        budget = float(m['native_32x_src_stages'][-1]['absolute_error_upper_conditional'])
        for row in c['native_src_stage_rows']:
            require(row['absolute_error'] <= budget,
                    'P2 native SRC sample exceeds conditional accounting envelope')
            comparisons += 1
    return {'schema': 'phase08-d11-source-accounting/1',
        'status': 'PASS_CONDITIONAL_ACCOUNTING_OWNER_OPEN',
        'release_authorized': False,
        'fft4g_worst_case_error_bound': 'OPEN',
        'glibc_pow_exp_maximum_error_bound': 'OPEN',
        'owner_adoption_of_D11': 'OPEN',
        'screen_multiplier_512_is_a_theorem': False,
        'model': 'exact stored-tap per-phase infinity norms; stagewise gamma and eta; '
                 'unproven 512*log2(N) FFT4G finite screen',
        'finite_witness_count': {'native_decoder': 64, 'final_src': 32,
             'working_src': 8, 'native_src': 8, 'libm': libm['sample_count'],
             'negative_controls_rejected': 6, 'composed_rows_checked': comparisons,
             'C_strtod_and_linked_libm_rechecked': operand_count},
        'source_sha256': {rel: sha(source/rel) for rel in
            ('src/rate.c', 'src/fft4g.c', 'src/rate_poly_fir0.h',
             'src/pcmdsd.c', 'src/pcmdsd_coeffs.h',
             'src/dsd_coeffs.h', 'src/dsd_kernels_scalar.c')},
        'sox_sha256': sha(sox),
        'compiled_binary_identity': compiled_binary_identity(sox),
        'source_to_binary_premises': named_environment(),
        'unresolved': [
            'FFT4G error including source twiddle creation (atan/cos/sin), '
            'coefficient FFT preparation and runtime roundoff, supported over all admitted inputs',
            'pow/exp maximum error including argument parsing and exponent construction',
            'general accepted source/output rates, encodings, gains, ISA and compiler path',
            'owner adoption of the proposed error model and tolerances'],
        'routes': source_model}


def self_test(results=None):
    class Stage:
        kind=2; L=2; dft_length=1024; coeff=(0.25, 0.125, 0.5, -0.25)
    assert src_stage_norm(Stage()) == F(3, 2)  # max phase: (0.25+0.5)*2
    assert gamma(1) > U
    m,e = step(F(1), F(0), F(3, 2), 4)
    assert m == F(3,2) and e > 0
    class Poly(Stage):
        kind=3; phases=2; n=2; order=1
    try:
        src_stage_norm(Poly())
    except InvalidEvidence:
        pass
    else:
        raise AssertionError('unsupported polyphase unexpectedly accepted')
    assert not (2 * float(e) < float(e))
    if results is not None:
        p2 = receipt(results/'p2-encoder-frontend/independent-primitive-cascade.json', 'PASS')
        p3 = receipt(results/'p3-final-src/final-src-reference.json',
                     'PASS_FINITE_WITNESSES_ONLY')
        dec = receipt(results/'unified-decoder/unified-reference.json',
                      'PASS_FINITE_WITNESSES_ONLY')
        libm = receipt(results/'d6-libm/gain-libm-reference.json',
                       'PASS_FINITE_WITNESSES_ONLY')
        wrong = copy.deepcopy(p3)
        wrong['cases'][0]['rows'][0]['abs_error'] = 2*wrong['cases'][0]['rows'][0]['finite_screen']
        try:
            verify_witnesses(p2, wrong, dec, libm)
        except InvalidEvidence:
            pass
        else:
            raise AssertionError('over-budget output mutant was accepted')
        wrong = copy.deepcopy(p3['source_operator_snapshots']['88200'])
        wrong['sha256'] = '0'*64
        try:
            frozen_snapshot(results/'p3-final-src', wrong)
        except InvalidEvidence:
            pass
        else:
            raise AssertionError('changed operator snapshot was accepted')
        wrong = copy.deepcopy(libm)
        wrong['samples'][0]['libm_pow_hex'] = '0x1.0000000000000p+0'
        if wrong['samples'][0]['libm_pow_hex'] == libm['samples'][0]['libm_pow_hex']:
            wrong['samples'][0]['libm_pow_hex'] = '0x1.0000000000001p+0'
        try:
            recheck_runtime_libm_samples(wrong)
        except InvalidEvidence:
            pass
        else:
            raise AssertionError('changed runtime libm output was accepted')
    print('D11 arithmetic-unit and evidence-mutation controls PASS')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--results',type=Path)
    ap.add_argument('--sox',type=Path)
    ap.add_argument('--source',default=ROOT,type=Path)
    ap.add_argument('--self-test',action='store_true')
    args=ap.parse_args()
    if args.self_test:
        self_test(args.results.resolve() if args.results else None);return 0
    if not args.results or not args.sox:
        ap.error('--results and --sox are required')
    path=args.results/'d11-accounting/d11-bound-accounting.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        result=run(args.results,args.sox.resolve(),args.source.resolve())
    except Exception as exc:
        result={'schema':'phase08-d11-source-accounting/1', 'status':'FAIL',
                'fft4g_worst_case_error_bound':'OPEN',
                'glibc_pow_exp_maximum_error_bound':'OPEN',
                'error':f'{type(exc).__name__}: {exc}'}
    path.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('D11 accounting:',result['status'],result.get('error',''))
    return 0 if result['status']=='PASS_CONDITIONAL_ACCOUNTING_OWNER_OPEN' else 1


if __name__=='__main__':
    raise SystemExit(main())
