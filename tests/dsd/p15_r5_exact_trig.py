#!/usr/bin/env python3
"""Pure-integer, outward dyadic enclosures for sin/cos(2*pi*r), r rational.

Trusted mathematical facts: Machin's arctan identity, alternating-series
remainder for atan(x), Taylor/Lagrange remainder with |sin^(n)|,|cos^(n)|<=1,
and the global 1-Lipschitz property of sin/cos. No libm/mpmath/MPFR arithmetic
participates in bound CONSTRUCTION. Exact Python integers are the primitive.

This is a proof companion, not a retrospective validation of R4 receipts.
"""
from __future__ import annotations
from fractions import Fraction as F
from functools import lru_cache
from math import factorial

GRID_BITS=256
GRID=1<<GRID_BITS
ATAN5_TERMS=78
ATAN239_TERMS=20
TAYLOR_TERMS=62


class TrigRefusal(ValueError):
    pass


def _ceil(q: F)->int:
    return -((-q.numerator)//q.denominator)


def _floor(q: F)->int:
    return q.numerator//q.denominator


def _atan_interval(inv: int, terms: int) -> tuple[F,F]:
    if type(inv) is not int or type(terms) is not int or inv<=1 or not 1<=terms<=512:
        raise TrigRefusal('invalid arctan input')
    x=F(1,inv); x2=x*x; power=x; total=F(0)
    for j in range(terms):
        total+=power*F(1 if j%2==0 else -1,2*j+1)
        power*=x2
    next_term=power*F(1 if terms%2==0 else -1,2*terms+1)
    return min(total,total+next_term),max(total,total+next_term)


@lru_cache(maxsize=1)
def pi_interval() -> tuple[F,F]:
    a,b=_atan_interval(5,ATAN5_TERMS)
    c,d=_atan_interval(239,ATAN239_TERMS)
    lo,hi=16*a-4*d,16*b-4*c
    if not (F(3)<lo<hi<F(22,7)):
        raise TrigRefusal('Machin pi enclosure invalid')
    if hi-lo>=F(1,1<<310):
        raise TrigRefusal('Machin pi enclosure too wide for 256-bit dyadic anchors')
    return lo,hi


def rational_angle(value:F) -> F:
    if type(value) is not F or max(abs(value.numerator).bit_length(),value.denominator.bit_length())>8192:
        raise TrigRefusal('angle must be a bounded exact rational')
    # Exact periodic reduction to [-1/2,+1/2]. The following interval is
    # contained in [-pi,pi], irrespective of the original coefficient index.
    return (value+F(1,2))%1-F(1,2)


# The Taylor evaluator works on a finer *integer* grid than the public
# enclosure. Each operation rounds outward; this avoids denominators growing
# exponentially with the degree while preserving an exact proof.
INTERNAL_BITS=312
INTERNAL=1<<INTERNAL_BITS


def _imul(a: tuple[int,int],b:tuple[int,int])->tuple[int,int]:
    products=(a[0]*b[0],a[0]*b[1],a[1]*b[0],a[1]*b[1])
    low=min(products);high=max(products)
    return low//INTERNAL, -((-high)//INTERNAL)


def _divide(a:tuple[int,int],den:int)->tuple[int,int]:
    if den<=0:raise TrigRefusal('nonpositive Taylor denominator')
    return a[0]//den,-((-a[1])//den)


def _neg(a:tuple[int,int])->tuple[int,int]:
    return -a[1],-a[0]


def _taylor_grid(x:int,kind:str)->tuple[int,int]:
    if kind not in ('sin','cos') or abs(x)>4*INTERNAL:
        raise TrigRefusal('Taylor domain violated')
    x2=_imul((x,x),(x,x))
    term=(x,x) if kind=='sin' else (INTERNAL,INTERNAL)
    total=term
    for j in range(1,TAYLOR_TERMS):
        den=(2*j)*(2*j+1) if kind=='sin' else (2*j-1)*(2*j)
        term=_divide(_neg(_imul(term,x2)),den)
        total=(total[0]+term[0],total[1]+term[1])
    degree=2*TAYLOR_TERMS if kind=='sin' else 2*TAYLOR_TERMS-1
    remainder=F(22,7)**degree/factorial(degree)
    if remainder>=F(1,1<<300):
        raise TrigRefusal('Taylor remainder is too wide for certificate')
    slack=_ceil(remainder*INTERNAL)
    return total[0]-slack,total[1]+slack


def enclosure(value:F,kind:str)->tuple[int,int]:
    """Return integers (lo,hi) with f(2*pi*value) in [lo/2^256,hi/2^256]."""
    r=rational_angle(value)
    a,b=pi_interval()
    arg_lo=min(2*r*a,2*r*b);arg_hi=max(2*r*a,2*r*b)
    a_grid=_floor(arg_lo*INTERNAL); b_grid=_ceil(arg_hi*INTERNAL)
    midpoint=(a_grid+b_grid)//2
    radius=max(midpoint-a_grid,b_grid-midpoint)
    if radius>=INTERNAL>>290:
        raise TrigRefusal('pi uncertainty defeats required enclosure')
    lo,hi=_taylor_grid(midpoint,kind)
    # Mean-value theorem: sin/cos are globally 1-Lipschitz in their argument.
    # Rounding from 312-bit grid to public 256-bit grid is OUTWARD again.
    return (lo-radius)//(INTERNAL//GRID), -((-(hi+radius))//(INTERNAL//GRID))


def sincos(value:F)->tuple[tuple[int,int],tuple[int,int]]:
    return enclosure(value,'sin'),enclosure(value,'cos')


def cert_word(value:F,kind:str)->tuple[str,str]:
    lo,hi=enclosure(value,kind)
    return f'{lo}/{GRID}',f'{hi}/{GRID}'
