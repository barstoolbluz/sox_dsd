#!/usr/bin/env python3
"""Source-independent R7 exact-dyadic Fourier/Taylor FIR enclosures.

Unlike one-trigonometric-call-per-tap evaluation, this method constructs
z=exp(2*pi*i*m) once with the R5 outward-grid sine/cosine kernel, and
certifiably builds z**k for every signed tap index using outward-rounded
complex BALL multiplication. A proven radial error propagation prevents the
exponential overestimation from naïve rectangular interval iteration.

The existing R5 Taylor derivative/remainder theorem and grid are unchanged.
No mpmath, libm, floating complex ops, or numerical tolerance is used to PASS.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as F
from math import factorial,isqrt
import math

from p15_r5_exact_trig import GRID,GRID_BITS,sincos
from p15_r5_integer_spectral import (FIRCertificate,IntervalRefusal,add,
    neg,ratio,mul,pi2,maxabs,minabs,magnitude_lower,magnitude_upper,ceil_f)

I_ZERO=((0,0),(0,0))


def ceil_sqrt(n:int)->int:
    """Smallest integer >= sqrt(n), no floating point."""
    root=isqrt(n)
    return root if root*root==n else root+1


def ball_from_rect(rect):
    """Contain a complex rectangular interval in an integer-grid disk.

    Rectangles use the R5 dyadic GRID for both axes. The integer radius
    encloses the Euclidean distance to the chosen exact-grid center, via
    integer sqrt and a ceil. No float distance calculation is involved.
    """
    (rl,rh),(il,ih)=rect
    cr=(rl+rh)//2;ci=(il+ih)//2
    dx=max(cr-rl,rh-cr);dy=max(ci-il,ih-ci)
    return cr,ci,ceil_sqrt(dx*dx+dy*dy)


def ball_conj(a):
    return a[0],-a[1],a[2]


def ball_mul(a,b):
    """Rigorous complex ball product, exact dyadic midpoint, outward radius.

    If a=(A,ra),b=(B,rb), then |ab-AB| <= |A|rb+|B|ra+ra*rb
    in real units. The new exact-grid midpoint rounds each Cartesian
    component down, with <=1 grid unit error per component; add 2 to the
    integer radial bound (more than sqrt(2)). Every quotient rounds UP.
    """
    ar,ai,ra=a;br,bi,rb=b
    if min(ra,rb)<0:raise IntervalRefusal('negative interval radius')
    cen_re=(ar*br-ai*bi)//GRID
    cen_im=(ar*bi+ai*br)//GRID
    amag=ceil_sqrt(ar*ar+ai*ai)
    bmag=ceil_sqrt(br*br+bi*bi)
    numerator=amag*rb+bmag*ra+ra*rb
    radius=ceil_f(F(numerator,GRID))+2
    return cen_re,cen_im,radius


def ball_power(a,n:int):
    if type(n) is not int or n<0 or n>10**8:
        raise IntervalRefusal('invalid complex ball recurrence exponent')
    base=a;result=(GRID,0,0)
    while n:
        if n&1:result=ball_mul(result,base)
        n>>=1
        if n:base=ball_mul(base,base)
    return result


def ball_rectangle(a):
    cr,ci,r=a
    if r<0:raise IntervalRefusal('negative interval radius')
    return (cr-r,cr+r),(ci-r,ci+r)


def certify_fir_fast(taps:tuple[tuple[int,float],...], lo:F,hi:F,
                     *,center:F=F(0),order:int=8)->FIRCertificate:
    """Enclose the |H| of every real f in [lo,hi], using signed-index phase powers.

    z's exact-grid disk contains exp(2*pi*i*m). The complex ball product
    lemma proves inductively that each phase disk includes exp(2*pi*i*k*m).
    Conjugation retains the radius for negative exponents. For general
    rational phase center, multiply by a certified exp(-2*pi*i*center*m).
    Then apply the R5 exact-grid Taylor midpoint/derivative and rational
    magnitude/remainder bounds, with identical admitted domains.
    """
    if (type(lo) is not F or type(hi) is not F or type(center) is not F or
        not F(0)<=lo<=hi<=F(1,2) or not 1<=order<=14 or
        not 1<=len(taps)<=10000):
        raise IntervalRefusal('unsupported range / Taylor order / input')
    if (len({k for k,_ in taps})!=len(taps) or
        any(type(k) is not int or abs(k)>10**8 or type(h) is not float or
            not math.isfinite(h) for k,h in taps)):
        raise IntervalRefusal('malformed FIR taps')
    # A lone finite exponential has constant modulus |h| throughout its
    # domain, independently of signed index, phase center or frequency.
    if len(taps)==1:
        q=abs(F.from_float(taps[0][1]))
        low=(q.numerator*GRID)//q.denominator
        high=ceil_f(q*GRID)
        return FIRCertificate(low,high,GRID_BITS,1,order,str(lo),str(hi),
                              (low,high),0,0)
    midpoint=(lo+hi)/2; radius=(hi-lo)/2
    derivatives=[I_ZERO for _ in range(order+1)]
    pi=pi2(); degree=order+1; moment=F(0)
    sin0,cos0=sincos(midpoint)
    z=ball_from_rect((cos0,sin0))
    phase=(GRID,0,0)
    if center:
        sin_shift,cos_shift=sincos(-center*midpoint)
        phase=ball_from_rect((cos_shift,sin_shift))
    taps_sorted=sorted(taps)
    last_index=0
    for k,h in taps_sorted:
        step=k-last_index
        if step<0:
            shift=ball_power(ball_conj(z),-step)
        else:
            shift=ball_power(z,step)
        phase=ball_mul(phase,shift)
        rectangular_phase=ball_rectangle(phase)
        last_index=k
        u=F(k)-center
        coeff=F.from_float(h)
        moment+=abs(coeff)*abs(u)**degree
        re=ratio(rectangular_phase[0],coeff)
        im=ratio(rectangular_phase[1],coeff)
        freq=ratio(pi,u)
        for j in range(order+1):
            re0,im0=derivatives[j]
            derivatives[j]=(add(re0,re),add(im0,im))
            if j<order:
                re,im=neg(mul(im,freq)),mul(re,freq)
    central_lo=magnitude_lower(derivatives[0][0],derivatives[0][1])
    central_hi=magnitude_upper(derivatives[0][0],derivatives[0][1])
    delta=0
    for j in range(1,order+1):
        re,im=derivatives[j]
        delta+=ceil_f(F(magnitude_upper(re,im))*radius**j/factorial(j))
    remainder=ceil_f(moment*(F(pi[1],GRID)*radius)**degree/factorial(degree)*GRID)
    variation=delta+remainder
    return FIRCertificate(max(0,central_lo-variation),central_hi+variation,
        GRID_BITS,len(taps),order,str(lo),str(hi),
        (central_lo,central_hi),delta,remainder)


def certify_linear_phase_fir(taps:tuple[tuple[int,float],...],lo:F,hi:F,
                             *,order:int=8)->FIRCertificate:
    """Rigorous real Taylor bound for an EXACTLY palindromic FIR.

    The coefficient identity h[c+j]=h[c-j] is tested by exact binary64
    equality, with c integral or half-integral. The transform has the form
      exp(2*pi*i*c*f) * (h[c] + sum_{k>c} 2*h[k]*cos(2*pi*(k-c)*f)).
    Its modulus is the absolute value of the *real* parenthesis. We bound
    only the real derivatives, reducing phase work by about fourfold. No
    approximate symmetry or tolerance-based cancellation is admitted.
    """
    if (type(lo) is not F or type(hi) is not F or
        not F(0)<=lo<=hi<=F(1,2) or
        type(order) is not int or not 1<=order<=14 or
        not 1<=len(taps)<=10000):
        raise IntervalRefusal('invalid real-FIR domain')
    if (len({k for k,_ in taps})!=len(taps) or
        any(type(k) is not int or abs(k)>10**8 or type(h) is not float or
            not math.isfinite(h) for k,h in taps)):
        raise IntervalRefusal('invalid real-FIR tap')
    ordered=sorted(taps)
    center=F(ordered[0][0]+ordered[-1][0],2)
    if any(k1+k2!=2*center or h1!=h2 for (k1,h1),(k2,h2)
           in zip(ordered,reversed(ordered))):
        raise IntervalRefusal('real-FIR symmetry not exact')
    mid=(lo+hi)/2;radius=(hi-lo)/2
    sin0,cos0=sincos(mid)
    z=ball_from_rect((cos0,sin0))
    sinshift,cosshift=sincos(-center*mid)
    current=ball_from_rect((cosshift,sinshift))
    last_k=0
    moments=F(0)
    degree=order+1
    derivs=[(0,0) for _ in range(order+1)]
    pi=pi2()
    for k,h in ordered:
        if F(k)<center:continue
        if F(k)==center:
            # A centered tap is constant in the real, phase-normalized FIR.
            derivs[0]=add(derivs[0],ratio((GRID,GRID),F.from_float(h)))
            continue
        step=k-last_k
        if step<0:
            current=ball_mul(current,ball_power(ball_conj(z),-step))
        else:
            current=ball_mul(current,ball_power(z,step))
        last_k=k
        re,im=ball_rectangle(current)
        u=F(k)-center
        coeff=2*F.from_float(h)
        moments+=abs(coeff)*u**degree
        c=ratio(re,coeff)
        s=ratio(im,coeff)
        freq=ratio(pi,u)
        for j in range(order+1):
            v=(c,neg(s),neg(c),s)[j%4]
            derivs[j]=add(derivs[j],v)
            if j<order:
                c=mul(c,freq)
                s=mul(s,freq)
    central_lo=minabs(derivs[0])
    central_hi=maxabs(derivs[0])
    delta=sum(ceil_f(F(maxabs(derivs[j]))*radius**j/factorial(j))
              for j in range(1,order+1))
    remainder=ceil_f(moments*(F(pi[1],GRID)*radius)**degree/
                     factorial(degree)*GRID)
    variation=delta+remainder
    return FIRCertificate(max(0,central_lo-variation),central_hi+variation,
         GRID_BITS,len(taps),order,str(lo),str(hi),
         (central_lo,central_hi),delta,remainder)


def certify_fir_auto(taps:tuple[tuple[int,float],...],lo:F,hi:F,
                     *,order:int=8)->FIRCertificate:
    """Use exact linear-phase symmetry only when all tap pairs match."""
    if taps:
        ordered=sorted(taps)
        mirror=ordered[0][0]+ordered[-1][0]
        if all(k1+k2==mirror and h1==h2
               for (k1,h1),(k2,h2) in zip(ordered,reversed(ordered))):
            return certify_linear_phase_fir(taps,lo,hi,order=order)
    return certify_fir_fast(taps,lo,hi,order=order)


def certify_paired_fir(taps:tuple[tuple[int,float],...],lo:F,hi:F,
                       *,order:int=8)->FIRCertificate:
    """Fourier enclosure for a mirror-supported, not necessarily symmetric FIR.

    For center c=(k_min+k_max)/2 and each reflected pair k_+>c,
       e^(-2*pi*i*c*f) [h_+e^(2*pi*i*k_+*f) + h_-e^(2*pi*i*k_-*f)]
       = (h_+ + h_-)*cos(2*pi*(k_+-c)*f)
         + i*(h_+ - h_-)*sin(2*pi*(k_+-c)*f).
    Bounds both real components and their real derivatives on a 256-bit
    dyadic grid, retaining all cancellation and signed coefficients. The
    support pairing is established *exactly*, never approximately.
    """
    if (type(lo) is not F or type(hi) is not F or
        not F(0)<=lo<=hi<=F(1,2) or
        type(order) is not int or not 1<=order<=14 or
        not 1<=len(taps)<=10000):
        raise IntervalRefusal('invalid paired-FIR domain')
    if (len({k for k,_ in taps})!=len(taps) or
        any(type(k) is not int or abs(k)>10**8 or type(h) is not float or
            not math.isfinite(h) for k,h in taps)):
        raise IntervalRefusal('invalid paired-FIR tap')
    ordered=sorted(taps)
    twicecenter=ordered[0][0]+ordered[-1][0]
    if any(a[0]+b[0]!=twicecenter for a,b in zip(ordered,reversed(ordered))):
        raise IntervalRefusal('FIR support is not exactly reflected')
    center=F(twicecenter,2)
    mid=(lo+hi)/2;r=(hi-lo)/2;degree=order+1
    sin0,cos0=sincos(mid)
    z=ball_from_rect((cos0,sin0))
    sinshift,cosshift=sincos(-center*mid)
    phase=ball_from_rect((cosshift,sinshift))
    last_k=0;moment=F(0)
    derivatives=[(I_ZERO[0],I_ZERO[1]) for _ in range(order+1)]
    pi=pi2();n=len(ordered)
    for j in range((n+1)//2):
        left=ordered[j];right=ordered[n-1-j]
        kl,hl=left;kr,hr=right
        if kl==kr:
            derivatives[0]=(add(derivatives[0][0],
                ratio((GRID,GRID),F.from_float(hr))),derivatives[0][1])
            continue
        step=kr-last_k
        if step<0:
            phase=ball_mul(phase,ball_power(ball_conj(z),-step))
        else:
            phase=ball_mul(phase,ball_power(z,step))
        last_k=kr
        u=F(kr)-center
        hp,hm=F.from_float(hr),F.from_float(hl)
        moment+=(abs(hp)+abs(hm))*u**degree
        re,im=ball_rectangle(phase)
        re_a=ratio(re,hp+hm);im_a=ratio(im,hp+hm)
        re_b=ratio(re,hp-hm);im_b=ratio(im,hp-hm)
        freq=ratio(pi,u)
        for d in range(order+1):
            a=(re_a,neg(im_a),neg(re_a),im_a)[d%4]
            b=(im_b,re_b,neg(im_b),neg(re_b))[d%4]
            prior_re,prior_im=derivatives[d]
            derivatives[d]=add(prior_re,a),add(prior_im,b)
            if d<order:
                re_a,im_a=mul(re_a,freq),mul(im_a,freq)
                re_b,im_b=mul(re_b,freq),mul(im_b,freq)
    central_lo=magnitude_lower(*derivatives[0]);central_hi=magnitude_upper(*derivatives[0])
    delta=sum(ceil_f(F(magnitude_upper(*derivatives[d]))*r**d/factorial(d))
              for d in range(1,order+1))
    remainder=ceil_f(moment*(F(pi[1],GRID)*r)**degree/factorial(degree)*GRID)
    variation=delta+remainder
    return FIRCertificate(max(0,central_lo-variation),central_hi+variation,
        GRID_BITS,len(taps),order,str(lo),str(hi),
        (central_lo,central_hi),delta,remainder)


def certify_fir_auto(taps:tuple[tuple[int,float],...],lo:F,hi:F,
                     *,order:int=8)->FIRCertificate:
    """Exact coefficient symmetry, then exact support pairing, else generic."""
    if taps:
        ordered=sorted(taps)
        mirror=ordered[0][0]+ordered[-1][0]
        if all(k1+k2==mirror for (k1,_),(k2,_) in zip(ordered,reversed(ordered))):
            if all(h1==h2 for (_,h1),(_,h2) in zip(ordered,reversed(ordered))):
                return certify_linear_phase_fir(taps,lo,hi,order=order)
            return certify_paired_fir(taps,lo,hi,order=order)
    return certify_fir_fast(taps,lo,hi,order=order)
