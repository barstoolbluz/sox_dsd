/* DSD64 invariant-constrained nonlinear resonator, v2 research reference.
 * See PROOF.md.  The quarter-strength contraction is part of this one
 * modulator's state transition, not a substitute filter or a state reset.
 */
#include "dsd64_iq.h"
#include <fenv.h>
#include <float.h>
#include <limits.h>
#include <math.h>
#include <string.h>
#if defined(__SSE2__)
#  include <xmmintrin.h>
#endif
#if defined(__FAST_MATH__)
#  error fast-math invalidates the finite-arithmetic proof
#endif
#if FLT_RADIX!=2 || DBL_MANT_DIG!=53 || DBL_MAX_EXP!=1024 || FLT_EVAL_METHOD!=0 || CHAR_BIT!=8
#  error Direct IEEE binary64 and eight-bit bytes are required
#endif
_Static_assert(sizeof(double)==8,"IEEE binary64 storage is required");
#include "constants.h"
#define MAGIC UINT64_C(0x4453443634495132)

static int environment(void) {
    if(fegetround()!=FE_TONEAREST) return 0;
#if defined(__SSE2__)
    /* The SSE control word may have been changed independently of fenv. */
    const unsigned csr=_mm_getcsr();
    if((csr & 0x6000u)!=0 || (csr & 0x1f80u)!=0x1f80u) return 0;
#endif
    return 1;
}

static double energy(const double s[8]) {
    double e=0.;
    for(unsigned i=0;i<8;i++) {
        double z=0.;
        for(unsigned j=i;j<8;j++) z=z+transform[i][j]*s[j];
        e=e+z*z;
    }
    return e;
}

static int in_box(const double s[8],const double caps[8]) {
    for(unsigned j=0;j<8;j++) if(!(fabs(s[j])<=caps[j])) return 0;
    return 1;
}

static int valid(const dsd64_iq *c) {
    if(!c || c->magic!=MAGIC || c->mode>1 ||
       c->interventions>c->samples || c->recovery_steps>c->samples ||
       c->recovery_entries>c->recovery_steps ||
       !in_box(c->state,state_cap)) return 0;
    return energy(c->state)<=IQ_ENERGY_LIMIT;
}

static int overlaps(const void *a,size_t na,const void *b,size_t nb) {
    const uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    if(!na || !nb) return 0;
    if(na>UINTPTR_MAX-x || nb>UINTPTR_MAX-y) return 1;
    return x<y+nb && y<x+na;
}

static void inc_check(dsd64_iq *c) {
    if(c->checks!=UINT64_MAX) c->checks++;
}

int dsd64_iq_init(dsd64_iq *c) {
    if(!c) return DSD64_IQ_ARGUMENT;
    if(!environment()) return DSD64_IQ_ENVIRONMENT;
    memset(c,0,sizeof(*c)); c->magic=MAGIC;
    return DSD64_IQ_OK;
}

static int process(dsd64_iq *c,const double *x,int8_t *y,size_t n,int checked) {
    if(!c || (n && (!x || !y))) return DSD64_IQ_ARGUMENT;
    if(!environment()) return DSD64_IQ_ENVIRONMENT;
    if(!valid(c)) return DSD64_IQ_STATE;
    if(n>SIZE_MAX/sizeof(*x) || n>UINT64_MAX-c->samples) return DSD64_IQ_OVERFLOW;
    if(overlaps(c,sizeof(*c),x,n*sizeof(*x)) ||
       overlaps(c,sizeof(*c),y,n) ||
       overlaps(x,n*sizeof(*x),y,n)) return DSD64_IQ_ARGUMENT;
    /* A corrupt final sample cannot cause publication of an earlier prefix. */
    for(size_t i=0;i<n;i++)
        if(!isfinite(x[i]) || fabs(x[i])>DSD64_IQ_INPUT_BOUND)
            return DSD64_IQ_INPUT;

    for(size_t i=0;i<n;i++) {
        double v=x[i],t[8],base,e=0.;
        int q,recovery=(int)c->mode;
        if(!recovery && !in_box(c->state,recovery_entry_cap)) {
            recovery=1;
            c->recovery_entries++;
        }
        for(unsigned j=0;j<8;j++) v=v+feedback[j]*c->state[j];
        q=signbit(v)?-1:1;

        base=c->state[0]-resonator[0]*c->state[1];
        if(recovery) base=base*IQ_RECOVERY_ALPHA;
        base=base+x[i];
        t[0]=base-(double)q;
        for(unsigned j=1;j<7;j++) {
            double z=c->state[j]+c->state[j-1];
            z=z-resonator[j]*c->state[j+1];
            if(recovery) z=z*IQ_RECOVERY_ALPHA;
            t[j]=z;
        }
        t[7]=c->state[7]+c->state[6];
        if(recovery) t[7]=t[7]*IQ_RECOVERY_ALPHA;

        /* The exact certificate proves that *either* quantizer bit has a
         * safe successor in both modes.  There is no corrective bit flip,
         * fallback modulator, or per-sample energy check on the normal path.
         * Always-checked processing verifies this invariant empirically. */
        if(recovery || checked) {
            e=energy(t); inc_check(c);
            if(!(e<=IQ_ENERGY_LIMIT)) return DSD64_IQ_PROOF_BREACH;
        }
        if(recovery) {
            c->recovery_steps++;
            if(e<=IQ_RECOVERY_EXIT_ENERGY && in_box(t,recovery_exit_cap))
                recovery=0;
        }
        memcpy(c->state,t,sizeof(t));
        c->samples++;
        c->mode=(uint64_t)recovery;
        y[i]=(int8_t)q;
    }
    return DSD64_IQ_OK;
}

int dsd64_iq_process(dsd64_iq *c,const double *x,int8_t *y,size_t n) {
    return process(c,x,y,n,0);
}
int dsd64_iq_process_checked(dsd64_iq *c,const double *x,int8_t *y,size_t n) {
    return process(c,x,y,n,1);
}
double dsd64_iq_energy(const dsd64_iq *c) {
    return environment() && valid(c) ? energy(c->state) : NAN;
}
const char *dsd64_iq_identity(void) { return IQ_IDENTITY; }

static void put64(unsigned char *p,uint64_t x) {
    for(unsigned j=0;j<8;j++) p[j]=(unsigned char)(x>>(8*j));
}
static uint64_t get64(const unsigned char *p) {
    uint64_t x=0;
    for(unsigned j=0;j<8;j++) x|=(uint64_t)p[j]<<(8*j);
    return x;
}
static uint32_t crc32(const unsigned char *p,size_t n) {
    uint32_t c=UINT32_MAX;
    for(size_t i=0;i<n;i++) {
        c^=p[i];
        for(unsigned j=0;j<8;j++)
            c=(c>>1)^(UINT32_C(0xedb88320)&(uint32_t)-(int32_t)(c&1));
    }
    return ~c;
}

int dsd64_iq_export(const dsd64_iq *c,unsigned char output[DSD64_IQ_SNAPSHOT_SIZE]) {
    unsigned char tmp[DSD64_IQ_SNAPSHOT_SIZE]={0};
    if(!c || !output || overlaps(c,sizeof(*c),output,DSD64_IQ_SNAPSHOT_SIZE))
        return DSD64_IQ_ARGUMENT;
    if(!environment()) return DSD64_IQ_ENVIRONMENT;
    if(!valid(c)) return DSD64_IQ_STATE;
    memcpy(tmp,"DSD64IQ2",8);
    memcpy(tmp+8,identity_bytes,32);
    put64(tmp+40,c->samples);
    put64(tmp+48,c->interventions);
    put64(tmp+56,c->checks);
    put64(tmp+64,c->recovery_steps);
    put64(tmp+72,c->recovery_entries);
    put64(tmp+80,c->mode);
    for(unsigned j=0;j<8;j++) {
        uint64_t w;
        memcpy(&w,&c->state[j],8);
        put64(tmp+88+8*j,w);
    }
    const uint32_t crc=crc32(tmp,160);
    for(unsigned j=0;j<4;j++) tmp[160+j]=(unsigned char)(crc>>(8*j));
    memcpy(output,tmp,sizeof(tmp));
    return DSD64_IQ_OK;
}

int dsd64_iq_import(dsd64_iq *c,const unsigned char input[DSD64_IQ_SNAPSHOT_SIZE]) {
    dsd64_iq tmp;
    uint32_t got=0;
    if(!c || !input || overlaps(c,sizeof(*c),input,DSD64_IQ_SNAPSHOT_SIZE))
        return DSD64_IQ_ARGUMENT;
    if(!environment()) return DSD64_IQ_ENVIRONMENT;
    if(memcmp(input,"DSD64IQ2",8) || memcmp(input+8,identity_bytes,32))
        return DSD64_IQ_SNAPSHOT;
    for(unsigned j=152;j<160;j++) if(input[j]) return DSD64_IQ_SNAPSHOT;
    for(unsigned j=0;j<4;j++) got|=(uint32_t)input[160+j]<<(8*j);
    if(got!=crc32(input,160)) return DSD64_IQ_SNAPSHOT;
    memset(&tmp,0,sizeof(tmp));
    tmp.magic=MAGIC;
    tmp.samples=get64(input+40);
    tmp.interventions=get64(input+48);
    tmp.checks=get64(input+56);
    tmp.recovery_steps=get64(input+64);
    tmp.recovery_entries=get64(input+72);
    tmp.mode=get64(input+80);
    for(unsigned j=0;j<8;j++) {
        const uint64_t w=get64(input+88+8*j);
        memcpy(&tmp.state[j],&w,8);
    }
    if(!valid(&tmp)) return DSD64_IQ_STATE;
    memcpy(c,&tmp,sizeof(tmp));
    return DSD64_IQ_OK;
}
