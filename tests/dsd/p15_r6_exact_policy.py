#!/usr/bin/env python3
"""Pure-rational inclusion for the original +/-0.0001 dB policy.

ln(10) = 3 ln(2) + ln(5/4); ln(x)=2 atanh((x-1)/(x+1)).
The geometric tail of positive atanh terms is bounded exactly. Exponential
Taylor remainder uses exp(|x|) <= 1/(1-|x|) for |x| < 1; no libm is used.
"""
from fractions import Fraction as F
from functools import lru_cache
from math import factorial

class PolicyRefusal(ValueError): pass


def _atanh_positive_inverse(den: int, n: int):
    if den <= 1 or n < 1:
        raise PolicyRefusal('bad atanh argument')
    z=F(1,den)
    result=sum((z**(2*j+1)/F(2*j+1) for j in range(n)),F(0))
    # For j>=n, 1/(2j+1) <= 1/(2n+1); geometric upper tail.
    tail=z**(2*n+1)/(F(2*n+1)*(1-z*z))
    return result,result+tail


@lru_cache(maxsize=1)
def ln10_bounds():
    l2,u2=_atanh_positive_inverse(3,115)
    l5,u5=_atanh_positive_inverse(9,58)
    lo=6*l2+2*l5
    hi=6*u2+2*u5
    if not F(2)<lo<hi<F(3) or hi-lo >= F(1,2**320):
        raise PolicyRefusal('ln10 bound too wide')
    return lo,hi


def _exp_bounds_at(x:F, terms=28):
    if not -F(1,2) <= x <= F(1,2):
        raise PolicyRefusal('unsupported exponential argument')
    term=F(1);s=term
    for j in range(1,terms+1):
        term=term*x/j
        s+=term
    absx=abs(x)
    # |R_n| <= exp(|x|) |x|^(n+1)/(n+1)!, exp(|x|)<=1/(1-|x|).
    r=absx**(terms+1)/(factorial(terms+1)*(1-absx))
    return s-r,s+r


@lru_cache(maxsize=1)
def db_pass_bounds():
    """Return (low guarantee, high guarantee) for exact 10^(+/-0.0001/20).

    Values are INTERVALS; PASS needs |H| >= lower[1] and <= upper[0].
    """
    a,b=ln10_bounds()
    t=F(1,200000)
    minus_lo,minus_hi=_exp_bounds_at(-b*t)[0],_exp_bounds_at(-a*t)[1]
    plus_lo,plus_hi=_exp_bounds_at(a*t)[0],_exp_bounds_at(b*t)[1]
    if not 0<minus_lo<minus_hi<1<plus_lo<plus_hi:
        raise PolicyRefusal('exponential enclosure invalid')
    return ((minus_lo,minus_hi),(plus_lo,plus_hi))


def policy_data():
    """Short inward dyadic *reporting* of exact rational policy endpoints.

    Acceptance compares original exact rational endpoints from db_pass_bounds;
    this display metadata is not used in proof decisions. Avoid serializing
    huge denominator products from exact exponential Taylor arithmetic.
    """
    a,b=ln10_bounds(); low,high=db_pass_bounds()
    scale=1<<256
    lower_up=-((-low[1].numerator*scale)//low[1].denominator)
    upper_down=(high[0].numerator*scale)//high[0].denominator
    if not (low[1]<=F(lower_up,scale)<1<F(upper_down,scale)<=high[0]):
        raise PolicyRefusal('policy reporting approximation not inward')
    return dict(method='exact-rational atanh geometric tail + exp Taylor remainder',
                ln10_width_strictly_lt_2pow_minus_320=b-a<F(1,2**320),
                inward_report_grid_bits=256,
                pass_min_inward_dyadic=f'{lower_up}/{scale}',
                pass_max_inward_dyadic=f'{upper_down}/{scale}',
                coherent_alias_limit='1/100000000',
                band_db='0.0001',stop_db='-160')
