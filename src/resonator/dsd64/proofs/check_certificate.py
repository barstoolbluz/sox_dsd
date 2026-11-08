#!/usr/bin/env python3
"""Exact rational certificate checker; uses no numerical linear algebra."""
import argparse, hashlib, json, math
from fractions import Fraction as Q
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def tr(a): return [list(r) for r in zip(*a)]
def mm(a,b): return [[sum((x*y for x,y in zip(r,c)),Q(0)) for c in tr(b)] for r in a]
def inverse(a):
    n=len(a); t=[list(r)+[Q(int(i==j)) for j in range(n)] for i,r in enumerate(a)]
    for i in range(n):
        k=next((k for k in range(i,n) if t[k][i]),None)
        if k is None: raise ValueError('Singular matrix')
        t[i],t[k]=t[k],t[i]; v=t[i][i]; t[i]=[x/v for x in t[i]]
        for j in range(n):
            if j!=i:
                v=t[j][i]; t[j]=[x-v*y for x,y in zip(t[j],t[i])]
    return [r[n:] for r in t]
def require(v,msg):
    if not v: raise ValueError(msg)
def ldlt(a):
    n=len(a); L=[[Q(int(i==j)) for j in range(n)] for i in range(n)]; d=[]
    require(a==tr(a),'matrix must be exactly symmetric')
    for j in range(n):
        p=a[j][j]-sum((L[j][k]**2*d[k] for k in range(j)),Q(0)); require(p>0,'nonpositive exact LDL pivot'); d.append(p)
        for i in range(j+1,n): L[i][j]=(a[i][j]-sum((L[i][k]*L[j][k]*d[k] for k in range(j)),Q(0)))/p
    return d
def check(path):
    cdata=json.loads(path.read_text()); require(cdata.get('schema')=='dsd64-iq-certificate/3','certificate schema'); hx=lambda v:Q(float.fromhex(v))
    T=[[hx(x) for x in r] for r in cdata['T_hex']]; g=[hx(v) for v in cdata['g_hex']]; n=8
    require(len(T)==n and all(len(r)==n for r in T) and len(g)==n,'dimensions')
    require(all(T[i][i]>0 for i in range(n)) and all(T[i][j]==0 for i in range(n) for j in range(i)),'upper triangular positive T')
    require(max(abs(v) for v in g)<=1 and max(abs(v) for row in T for v in row)<=1,'denormal-loss multiplier bounds')
    rho=hx(cdata['rho_hex']); require(rho==Q(1,2)+Q(1,2**28),'input contract')
    c=Q(cdata['c_upper']); k=Q(cdata['k']); require(0<c<1 and k>0,'positive ellipsoid parameters')
    A=[[Q(int(i==j)+int(i==j+1)) for j in range(n)] for i in range(n)]
    for i in range(n-1): A[i][i+1]=-g[i]
    Ti=inverse(T); F=mm(mm(T,A),Ti); f=[r[0] for r in T]; FF=mm(F,tr(F))
    H=[[c*int(i==j)+k*f[i]*f[j]-FF[i][j] for j in range(n)] for i in range(n)]
    piv=ldlt(H); B2=sum((v*v for v in f),Q(0)); M2=c+k*B2
    require(0<B2<M2,'0 < B < M'); K0=c+(1+rho)**2*B2; require(K0<1,'transverse endpoint')
    d=M2-1-(1-rho)**2*B2; require(d<0 or d*d<4*(1-rho)**2*B2,'longitudinal endpoint')
    Mu=Q(cdata['M_upper']); Bu=Q(cdata['B_upper']); Bl=Q(cdata['B_lower'])
    require(0<Bl and Bl*Bl<=B2<=Bu*Bu and M2<=Mu*Mu,'rational square-root brackets')
    require(Mu>(1-rho)*Bl,'endpoint sign'); K=max(K0,(Mu-(1-rho)*Bl)**2)
    u=Q(1,2**53); tiny=Q(1,2**1022)
    S=[math.ceil(sum(abs(v) for v in r)) for r in Ti]
    E=[]; U=[]
    for j in range(n):
        cap=Q(S[j])+(S[j-1] if j else 0)+(abs(g[j])*S[j+1] if j<7 else 0)
        err=16*u*(cap+rho+1)+16*tiny; E.append(err)
        U.append(cap+(rho+1 if j==0 else 0)+err)
    dn=sum((abs(T[i][j])*E[j] for i in range(n) for j in range(n)),Q(0))
    L=[sum((abs(T[i][j])*U[j] for j in range(n)),Q(0)) for i in range(n)]
    DE=[64*u*l+64*tiny for l in L]
    ee=sum((2*l*e+e*e for l,e in zip(L,DE)),Q(0))+64*u*sum(((l+e)**2 for l,e in zip(L,DE)),Q(0))+64*tiny
    db=Q(cdata['update_norm_error_bound']); eb=Q(cdata['energy_error_bound']); limit=Q(cdata['energy_limit'])
    require(dn<=db,'rounded update bound'); require(ee<=eb,'energy evaluation bound'); require(limit+eb<1,'membership acceptance soundness')
    require(K+2*db+db*db+eb<limit,'at least one rounded candidate passes')
    legacy=[hx(v) for v in cdata['legacy_a_hex']]; pref=[hx(v) for v in cdata['preferred_a_hex']]
    require(all(pref[i]==Q(float(legacy[i]*Q(26,25)**(i+1))) for i in range(n)),'preferred coefficient recipe')
    require(max(S)<2**1000 and max(U)<2**1000 and sum(abs(pref[i])*S[i] for i in range(n))+rho<2**1000,'no arithmetic overflow in recurrence/comparator')
    # V3 unrestricted one-bit comparator with conditional dissipation.
    # Because the squared norm is convex in alpha and the same constructive bit
    # is valid at alpha=0 and alpha=1, it remains valid for every 0<=alpha<=1.
    # Alpha=1/4 is exact exponent scaling except at the subnormal boundary,
    # whose absolute error is included in the previously conservative E_j.
    rec=cdata['recovery']; alpha=hx(rec['contraction_hex'])
    require(alpha==Q(1,4),'frozen exact power-of-two contraction')
    entry=hx(rec['entry_energy_hex']); ex=hx(rec['exit_energy_hex'])
    require(0<ex<entry<limit,'recovery hysteresis energy bounds')
    caps_in=[hx(x) for x in rec['entry_caps_hex']]; caps_out=[hx(x) for x in rec['exit_caps_hex']]
    require(len(caps_in)==n and len(caps_out)==n,'recovery cap dimensions')
    require(all(0<b<=a for a,b in zip(caps_in,caps_out)),'recovery hysteresis coordinate caps')
    # Coordinate-only entry avoids a full energy evaluation on every sample.
    # The whole entry box is contained in an energy ball strictly inside the
    # stated threshold, so a high-energy state cannot evade entry.
    box_energy=sum((sum((abs(T[i][j])*caps_in[j] for j in range(n)),Q(0))**2 for i in range(n)),Q(0))
    require(box_energy<entry,'entry box can contain high-energy states')
    # A freshly discharged state cannot immediately re-enter next sample even
    # with hostile input: bound each undamped next-state coordinate, q arbitrary.
    next_exit=[caps_out[j]+(caps_out[j-1] if j else 0)+
               (abs(g[j])*caps_out[j+1] if j<7 else 0)+
               ((1+rho) if j==0 else 0)+E[j] for j in range(n)]
    require(all(v<cap for v,cap in zip(next_exit,caps_in)),'recovery release can immediately re-enter')

    steps=rec['certified_max_active_steps']; require(type(steps) is int and 1<=steps<=256,'recovery step count')
    # Non-damped roundoff envelope E_j also covers the damped branch:
    # exact binary scaling adds at most subnormal loss, already reserved.
    # Constructively bound every coordinate for arbitrary q and arbitrary
    # admitted x, starting at the full certified state-coordinate caps.
    p=[Q(v) for v in S]; radial=Q(1)
    for _ in range(steps):
        p=[alpha*(p[j]+(p[j-1] if j else 0)+(abs(g[j])*p[j+1] if j<7 else 0))+
           ((1+rho) if j==0 else 0)+E[j] for j in range(n)]
        radial=alpha*Mu*radial+(1+rho)*Bu+db
    require(radial*radial+eb<ex,'contracted energy does not reach release threshold')
    require(all(v<cap for v,cap in zip(p,caps_out)),'contracted state cannot enter release box in time')
    # Finite exit in <= steps follows by contradiction: if mode has not exited
    # earlier, all these damped transitions were performed and must satisfy
    # both release tests after this step. This is NOT a bound on re-entry.
    recovery_result={'alpha':str(alpha),'max_active_steps':steps,'post_step_norm_upper':str(radial),
        'post_step_energy_upper':str(radial*radial+eb),
        'coordinate_caps_upper':[str(v) for v in p], 'entry_energy':str(entry), 'exit_energy':str(ex), 'entry_box_energy_upper':str(box_energy), 'post_release_next_state_coordinate_bound':[str(x) for x in next_exit]}
    # Both possible one-bit decisions are safe.  For any |x|<=rho and q=+-1,
    # ||alpha*F*z + f*(x-q)|| <= alpha*M_upper*||z||+(1+rho)*B_upper.
    # Normal mode occurs only inside the certified entry box.  During
    # dissipative mode, the preceding state may be anywhere in E.
    normal_radius_upper=Q(17,100)
    require(normal_radius_upper**2>=box_energy,'normal radius underbound')
    normal_bound=Mu*normal_radius_upper+(1+rho)*Bu+db
    dissipative_bound=alpha*Mu+(1+rho)*Bu+db
    require(normal_bound**2+eb<limit,'ordinary one-bit successor not universally safe')
    require(dissipative_bound**2+eb<limit,'dissipative one-bit successor not universally safe')
    return {'status':'PASS','certificate_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'exact_positive_LDL_pivots':len(piv),'rho':str(rho),'ideal_worst_energy_upper':str(K),'update_norm_error_computed':str(dn),'update_norm_error_reserved':str(db),'energy_error_computed':str(ee),'energy_error_reserved':str(eb),'energy_limit':str(limit),'coordinate_caps':S,'recovery_certificate':recovery_result,'unrestricted_quantizer_safety':{'normal_energy_upper':str(normal_bound**2+eb),'dissipative_energy_upper':str(dissipative_bound**2+eb)},'display':{'B':math.sqrt(float(B2)),'M_bound':float(Mu),'ideal_worst_energy_upper':float(K),'update_norm_error_computed':float(dn),'energy_error_computed':float(ee),'normal_anybit_energy_upper':float(normal_bound**2+eb),'dissipative_anybit_energy_upper':float(dissipative_bound**2+eb)},'proof_scope':'bounded state for all admitted inputs; not a universal audio-fidelity theorem'}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--write',action='store_true'); ap.add_argument('--certificate',type=Path,default=ROOT/'proofs/certificate.json'); ns=ap.parse_args(); result=check(ns.certificate)
    if ns.write: (ROOT/'results/proof.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k in ('status','certificate_sha256','exact_positive_LDL_pivots','display')},indent=2))
if __name__=='__main__': main()
