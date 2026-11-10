/* Differential qualification for register-resident normal SDM kernels.
 * The oracle is the separately compiled, immutable original scalar source.
 * No production implementation or acceptor is copied into this harness. */
#include "sox_i.h"
#include "dsd_kernels.h"
#include <fenv.h>
#include <float.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if defined(__SSE2__)
#include <emmintrin.h>
#endif

extern const lsx_dsd_kernel original_lsx_dsd_kernel_scalar;
extern const sdm_profile_t *original_sdm_profile_find(const char *, unsigned);
extern int original_sdm_profile_coefficients(const sdm_profile_t *,
    const double **, const double **, unsigned *);
extern int original_sdm_normal_init(sdm_normal_t *, const sdm_profile_t *);
extern void original_sdm_normal_monitor_init(sdm_normal_monitor_t *);
extern void original_sdm_normal_attach_monitor(sdm_normal_t *, sdm_normal_monitor_t *);

enum { CAPACITY=521 };
typedef struct {
  sdm_normal_t s;
  sdm_normal_monitor_t m;
  double input[CAPACITY], bounds[8], peak;
  sox_sample_t output[CAPACITY];
  size_t n, committed;
  unsigned coordinate;
  double envelope;
  int input_alias, bounds_alias, peak_alias, no_monitor, no_bounds;
  int committed_alias, coordinate_alias;
} fixture;

static const struct { const char *id; unsigned rate; } profiles[]={
  {"encode.mastering.v1.dsd64",2822400u},
  {"encode.mastering.v1.dsd128",5644800u},
  {"encode.mastering.v1.dsd256",11289600u},
  {"encode.mastering.v2.dsd512",22579200u},
  {"encode.mastering.v2.dsd1024",45158400u},
  {"encode.mastering.v1.dsd512",22579200u},
  {"encode.mastering.v1.dsd1024",45158400u},
  {"encode.legacy.v1.dsd64",2822400u},
  {"encode.legacy.v1.dsd128",5644800u},
  {"encode.legacy.v1.dsd256",11289600u},
  {"encode.diagnostic.sdm6.v1.dsd64",2822400u},
  {"encode.diagnostic.sdm6.v1.dsd128",5644800u},
  {"encode.diagnostic.sdm6.v1.dsd256",11289600u},
  {"encode.diagnostic.clans8.v1.dsd64",2822400u},
  {"encode.diagnostic.clans8.v1.dsd128",5644800u},
  {"encode.diagnostic.clans8.v1.dsd256",11289600u}
};
static const uint64_t patterns[]={
  UINT64_C(0), UINT64_C(0x8000000000000000),
  UINT64_C(1), UINT64_C(0x8000000000000001),
  UINT64_C(0x000fffffffffffff), UINT64_C(0x800fffffffffffff),
  UINT64_C(0x0010000000000000), UINT64_C(0x8010000000000000),
  UINT64_C(0x3fd0000000000000), UINT64_C(0xbfd0000000000000),
  UINT64_C(0x7fefffffffffffff), UINT64_C(0xffefffffffffffff),
  UINT64_C(0x7ff0000000000000), UINT64_C(0xfff0000000000000),
  UINT64_C(0x7ff8000000000042), UINT64_C(0xfff8000000000053),
  UINT64_C(0x7ff0000000000064), UINT64_C(0xfff0000000000075)
};

static const char *current_tier="unset", *current_profile="unset";
static unsigned current_case, current_variant, current_round, current_flush;
static uint64_t comparisons, frames_compared;
static int compare_exceptions;
static int selected_case=-1;

static void fail(const char *what, int line)
{
  fprintf(stderr,"FAIL line=%d tier=%s profile=%s case=%u variant=%u "
      "round=%u flush=%u: %s\n",line,current_tier,current_profile,
      current_case,current_variant,current_round,current_flush,what);
  exit(1);
}
#define CHECK(x) do { if (!(x)) fail(#x,__LINE__); } while (0)

static void clear_exceptions(void)
{
  CHECK(!feclearexcept(FE_ALL_EXCEPT));
#if defined(__SSE2__)
  /* C's FE_ALL_EXCEPT does not include x86's denormal-operand status bit. */
  _mm_setcsr(_mm_getcsr() & ~0x3fu);
#endif
}

static int exception_status(void)
{
  int status=fetestexcept(FE_ALL_EXCEPT);
#if defined(__SSE2__)
  status|=(int)(_mm_getcsr()&0x3fu)<<16;
#endif
  return status;
}

static double bits(uint64_t u)
{ double x; memcpy(&x,&u,sizeof(x)); return x; }

static uint32_t random32(uint32_t *seed)
{
  *seed^=*seed<<13; *seed^=*seed>>17; *seed^=*seed<<5;
  return *seed;
}

static void initialize(fixture *f,const sdm_profile_t *p,int original,
    uint32_t seed,unsigned bank)
{
  unsigned i;
  memset(f,0,sizeof(*f));
  if (original) {
    CHECK(!original_sdm_normal_init(&f->s,p));
    original_sdm_normal_monitor_init(&f->m);
    original_sdm_normal_attach_monitor(&f->s,&f->m);
  } else {
    CHECK(!sdm_normal_init(&f->s,p));
    sdm_normal_monitor_init(&f->m);
    sdm_normal_attach_monitor(&f->s,&f->m);
  }
  f->s.bank=bank;
  for (i=0;i<8;++i) {
    f->s.state[bank^1][i]=(double)(i+1)*0x1.23456789p-12;
    f->bounds[i]=0x1p100;
  }
  for (i=0;i<CAPACITY;++i) {
    f->input[i]=(int32_t)random32(&seed)*0x1p-35;
    f->output[i]=(sox_sample_t)0x395726a4;
  }
  f->n=512;
  f->peak=-0.;
  f->envelope=.5;
  f->coordinate=0xace02468u;
  f->committed=(size_t)-1;
  f->peak_alias=-1;
}

/* All alias cases use existing double objects. No test relies on type-punning,
 * out-of-bounds pointer arithmetic or undefined overlapping objects. */
static double *peak_pointer(fixture *f)
{
  if (f->peak_alias<0) return &f->peak;
  if (f->peak_alias<16)
    return &f->s.state[f->peak_alias/8][f->peak_alias%8];
  if (f->peak_alias==16) return &f->s.previous_decision;
  if (f->peak_alias<25) return &f->m.max_abs_state[f->peak_alias-17];
  if (f->peak_alias<33) return &f->bounds[f->peak_alias-25];
  if (f->peak_alias<66) return &f->input[f->peak_alias-33];
  return NULL;
}

static const double *input_pointer(fixture *f)
{
  switch (f->input_alias) {
    case 1: return f->s.state[0];
    case 2: return f->s.state[1];
    case 3: return f->m.max_abs_state;
    case 4: return f->bounds;
    default: return f->n ? f->input : NULL;
  }
}

static const double *bounds_pointer(fixture *f)
{
  if (f->no_bounds) return NULL;
  switch (f->bounds_alias) {
    case 1: return f->s.state[0];
    case 2: return f->s.state[1];
    case 3: return f->m.max_abs_state;
    case 4: return f->input;
    default: return f->bounds;
  }
}

static size_t *committed_pointer(fixture *f)
{
  if (f->committed_alias==1) return (size_t *)&f->s.frames;
  if (f->committed_alias==2) return (size_t *)&f->m.frames;
  return &f->committed;
}

static unsigned *coordinate_pointer(fixture *f)
{
  if (f->coordinate_alias==1) return &f->s.bank;
  if (f->coordinate_alias==2) return &f->m.history_bits;
  if (f->coordinate_alias==3) return &f->m.last_bit;
  if (f->coordinate_alias==4) return &f->m.min_ones28;
  return &f->coordinate;
}

static void setup(fixture *f,unsigned scenario,unsigned variant)
{
  unsigned i,coordinate=variant%8;
  unsigned active=f->s.bank;
  static const unsigned positions[]={0,1,27,28,255,511,512};
  static const unsigned histories[]={0,1,26,27,28};
  switch (scenario) {
  case 0: break; /* production-sized block */
  case 1: f->n=0; break;
  case 2: f->no_bounds=1; f->no_monitor=1; break;
  case 3:
    f->n=513;
    f->input[positions[variant%7]]=bits(patterns[(variant/7)%18]);
    break;
  case 4:
    f->n=7;
    f->s.state[(variant/8)%2][coordinate]=bits(patterns[(variant/16)%18]);
    break;
  case 5:
    f->n=7; f->s.previous_decision=bits(patterns[variant%18]); break;
  case 6:
    f->n=7; f->bounds[coordinate]=bits(patterns[(variant/8)%18]); break;
  case 7:
    f->n=7; f->peak=bits(patterns[variant%18]); break;
  case 8:
    f->n=7; f->m.max_abs_state[coordinate]=bits(patterns[(variant/8)%18]);
    /* Positive tiny input can exceed a subnormal peak even if every active
     * state coordinate later rounds or flushes to signed zero. */
    if (variant&1) for (i=0;i<7;++i) f->input[i]=bits((uint64_t)i+1);
    break;
  case 9:
    f->n=33; f->input[0]=-.25; f->peak_alias=(int)(variant%16); break;
  case 10:
    f->n=33; f->input[0]=-.25; f->peak_alias=16; break;
  case 11:
    f->n=33; f->input[0]=-.25; f->peak_alias=17+(int)coordinate; break;
  case 12:
    f->n=33; f->input[0]=-.25; f->peak_alias=33+(int)(variant%33); break;
  case 13:
    f->n=33; f->input[0]=-.25; f->peak_alias=25+(int)coordinate;
    f->bounds[coordinate]=-.01; break;
  case 14:
    f->n=8; f->input_alias=1+(int)(variant%2);
    for (i=0;i<8;++i) f->s.state[variant%2][i]=(double)(i+1)*.001;
    break;
  case 15:
    f->n=8; f->input_alias=3;
    for (i=0;i<8;++i) f->m.max_abs_state[i]=(double)(i+1)*.001;
    break;
  case 16:
    f->n=8; f->input_alias=4;
    for (i=0;i<8;++i) f->bounds[i]=(double)(i+1)*.001;
    break;
  case 17:
    f->n=33; f->bounds_alias=1+(int)(variant%2); break;
  case 18:
    f->n=33; f->bounds_alias=3;
    for (i=0;i<8;++i) f->m.max_abs_state[i]=32.;
    break;
  case 19: f->n=33; f->bounds_alias=4; break;
  case 20:
    f->n=33; f->s.frames=UINT64_MAX-(variant%4); break;
  case 21:
    f->n=33; f->envelope=1.;
    for (i=0;i<33;++i) f->input[i]=.51;
    f->m.frames=f->m.windows28=f->m.excursions28=
      f->m.overloads=f->m.nonfinite=UINT64_MAX-(variant%2);
    f->m.run_length=UINT32_MAX-(variant%2);
    f->m.last_bit=(variant/2)%2;
    f->m.history_bits=28;
    f->m.history28=(variant&4) ? 0x0fffffff : 0;
    f->m.ones28=(variant&4) ? 28 : 0;
    if (variant&8) f->input[17]=bits(UINT64_C(0x7ff8000000001234));
    break;
  case 22:
    f->n=33; f->m.history_bits=histories[variant%5];
    f->m.history28=(1u<<f->m.history_bits)-1;
    f->m.ones28=f->m.history_bits;
    f->m.last_bit=(variant/5)%2;
    f->m.run_length=UINT32_MAX;
    break;
  case 23:
    f->n=33; f->bounds[coordinate]=0.; f->bounds[7-coordinate]=0.;
    for (i=0;i<8;++i) f->s.state[active][i]=(double)(i+1)*.125;
    break;
  case 24:
    f->n=7;
    for (i=0;i<8;++i)
      f->s.state[active][i]=bits(patterns[(variant+i)%18]);
    f->s.previous_decision=bits(patterns[(variant*7+3)%18]);
    break;
  case 25:
    f->n=33; f->input[variant%33]=(variant&1) ? -.51 : .51;
    break;
  case 26:
    f->n=7; f->envelope=bits(patterns[variant%18]); break;
  case 30:
    f->n=33;
    if (_Generic((size_t *)0,uint64_t *:1,default:0))
      f->committed_alias=1+(int)(variant%2);
    if (variant&2) f->input[17]=INFINITY;
    break;
  case 31:
    f->n=33; f->bounds[coordinate]=-1.;
    f->coordinate_alias=1+(int)((variant/8)%4);
    break;
  case 32:
    f->n=513; f->peak_alias=66;
    f->no_bounds=variant&1; f->no_monitor=variant&2;
    break;
  default: CHECK(0);
  }
  if (f->no_monitor) f->s.monitor=NULL;
}

static void compare(const fixture *a,const fixture *b,int ra,int rb,int ea,int eb)
{
  CHECK(ra==rb);
  CHECK(a->committed==b->committed);
  CHECK(a->coordinate==b->coordinate);
  CHECK(a->s.bank==b->s.bank);
  CHECK(a->s.frames==b->s.frames);
  CHECK(!memcmp(a->s.state,b->s.state,sizeof(a->s.state)));
  CHECK(!memcmp(&a->s.previous_decision,&b->s.previous_decision,sizeof(double)));
  CHECK(!memcmp(&a->m,&b->m,sizeof(a->m)));
  CHECK(!memcmp(a->output,b->output,sizeof(a->output)));
  CHECK(!memcmp(a->input,b->input,sizeof(a->input)));
  CHECK(!memcmp(a->bounds,b->bounds,sizeof(a->bounds)));
  CHECK(!memcmp(&a->peak,&b->peak,sizeof(double)));
  if (compare_exceptions) CHECK(ea==eb);
  ++comparisons;
  frames_compared+=a->committed_alias==1 ? a->s.frames :
    (a->committed_alias==2 ? a->m.frames : a->committed);
}

static int invoke(fixture *f,lsx_dsd_sdm_block_fn fn,int *exceptions)
{
  int rc;
  clear_exceptions();
  rc=fn(&f->s,input_pointer(f),f->n,f->n ? f->output : NULL,
      committed_pointer(f),bounds_pointer(f),coordinate_pointer(f),
      f->envelope,peak_pointer(f));
  *exceptions=exception_status();
  return rc;
}

static void case_pair(const lsx_dsd_kernel *tier,const sdm_profile_t *pa,
    const sdm_profile_t *pb,unsigned scenario,unsigned variant)
{
  fixture a,b;
  int ra,rb,ea,eb;
  uint32_t seed=0x148fc736u+(scenario*0x10001u)+variant;
  current_case=scenario; current_variant=variant;
  initialize(&a,pa,1,seed,variant&1);
  initialize(&b,pb,0,seed,variant&1);
  setup(&a,scenario,variant); setup(&b,scenario,variant);
  ra=invoke(&a,original_lsx_dsd_kernel_scalar.sdm_block,&ea);
  rb=invoke(&b,tier->sdm_block,&eb);
  compare(&a,&b,ra,rb,ea,eb);
}

static void continuation(const lsx_dsd_kernel *tier,const sdm_profile_t *pa,
    const sdm_profile_t *pb)
{
  static const unsigned sizes[]={0,1,2,7,27,28,29,511,512,513,521};
  fixture a,b;
  uint32_t seed=0x8ca6e12du;
  unsigned round,i;
  current_case=27;
  initialize(&a,pa,1,seed,0); initialize(&b,pb,0,seed,0);
  for (round=0;round<55;++round) {
    int ra,rb,ea,eb;
    current_variant=round;
    a.n=b.n=sizes[round%11];
    a.committed=b.committed=(size_t)-1;
    a.coordinate=b.coordinate=0xace02468u;
    for (i=0;i<CAPACITY;++i) {
      a.input[i]=b.input[i]=(int32_t)random32(&seed)*0x1p-35;
      a.output[i]=b.output[i]=(sox_sample_t)0x395726a4;
    }
    /* Attach/detach without resetting either the state or saved monitor. */
    a.s.monitor=(round%4==0) ? NULL : &a.m;
    b.s.monitor=(round%4==0) ? NULL : &b.m;
    a.no_bounds=b.no_bounds=(round%7==0);
    ra=invoke(&a,original_lsx_dsd_kernel_scalar.sdm_block,&ea);
    rb=invoke(&b,tier->sdm_block,&eb);
    compare(&a,&b,ra,rb,ea,eb);
    if (ra) break;
  }
}

static void invalid_arguments(const lsx_dsd_kernel *tier,
    const sdm_profile_t *pa,const sdm_profile_t *pb)
{
  unsigned c;
  current_case=28;
  for (c=0;c<6;++c) {
    fixture a,b;
    int ra,rb,ea,eb;
    sdm_normal_t *sa,*sb;
    const double *ia,*ib;
    sox_sample_t *oa,*ob;
    size_t *ca,*cb;
    current_variant=c;
    initialize(&a,pa,1,1,0); initialize(&b,pb,0,1,0);
    sa=&a.s; sb=&b.s; ia=a.input; ib=b.input;
    oa=a.output; ob=b.output; ca=&a.committed; cb=&b.committed;
    if (c==0) { sa=sb=NULL; }
    if (c==1) { a.s.profile=b.s.profile=NULL; }
    if (c==2) { ia=ib=NULL; }
    if (c==3) { oa=ob=NULL; }
    if (c==4) { ca=cb=NULL; a.committed=b.committed=0; }
    if (c==5) { a.n=b.n=0; ia=ib=NULL; oa=ob=NULL; }
    clear_exceptions();
    ra=original_lsx_dsd_kernel_scalar.sdm_block(sa,ia,a.n,oa,ca,
        a.bounds,&a.coordinate,a.envelope,&a.peak);
    ea=exception_status();
    clear_exceptions();
    rb=tier->sdm_block(sb,ib,b.n,ob,cb,b.bounds,&b.coordinate,b.envelope,&b.peak);
    eb=exception_status();
    compare(&a,&b,ra,rb,ea,eb);
  }
}

static void random_bits(const lsx_dsd_kernel *tier,const sdm_profile_t *pa,
    const sdm_profile_t *pb)
{
  uint32_t seed=0x93bc2167u;
  unsigned v,i;
  current_case=29;
  for (v=0;v<128;++v) {
    fixture a,b;
    int ra,rb,ea,eb;
    current_variant=v;
    initialize(&a,pa,1,seed,v&1); initialize(&b,pb,0,seed,v&1);
    a.n=b.n=7;
    a.no_bounds=b.no_bounds=(v%3==0);
    for (i=0;i<8;++i) {
      uint64_t u=((uint64_t)random32(&seed)<<32)|random32(&seed);
      if (v%4==0) u=patterns[(v+i)%18];
      a.s.state[a.s.bank][i]=b.s.state[b.s.bank][i]=bits(u);
    }
    ra=invoke(&a,original_lsx_dsd_kernel_scalar.sdm_block,&ea);
    rb=invoke(&b,tier->sdm_block,&eb);
    compare(&a,&b,ra,rb,ea,eb);
  }
}

static void suite(const lsx_dsd_kernel *tier)
{
  static const unsigned variants[]={
    1,1,1,126,288,18,144,18,144,16,1,8,33,8,2,1,1,2,1,1,4,16,10,8,36,33,18
  };
  unsigned p,c,v;
  current_tier=tier->name;
  for (p=0;p<sizeof(profiles)/sizeof(profiles[0]);++p) {
    const sdm_profile_t *pa=original_sdm_profile_find(profiles[p].id,profiles[p].rate);
    const sdm_profile_t *pb=sdm_profile_find(profiles[p].id,profiles[p].rate);
    const double *aa,*ga,*ab,*gb;
    unsigned oa,ob;
    current_profile=profiles[p].id;
    CHECK(pa && pb);
    CHECK(!original_sdm_profile_coefficients(pa,&aa,&ga,&oa));
    CHECK(!sdm_profile_coefficients(pb,&ab,&gb,&ob));
    CHECK(oa==ob);
    CHECK(!memcmp(aa,ab,oa*sizeof(double)));
    CHECK(!memcmp(ga,gb,oa*sizeof(double)));
    for (c=0;c<sizeof(variants)/sizeof(variants[0]);++c)
      if (selected_case<0 || (unsigned)selected_case==c)
        for (v=0;v<variants[c];++v) case_pair(tier,pa,pb,c,v);
    if (selected_case<0 || selected_case==27) continuation(tier,pa,pb);
    if (selected_case<0 || selected_case==28) invalid_arguments(tier,pa,pb);
    if (selected_case<0 || selected_case==29) random_bits(tier,pa,pb);
    for (c=30;c<=32;++c)
      if (selected_case<0 || (unsigned)selected_case==c)
        for (v=0;v<(c==31 ? 32u : 4u);++v) case_pair(tier,pa,pb,c,v);
  }
}

#if defined(__SSE2__) && (defined(__GNUC__) || defined(__clang__))
static unsigned supported_mxcsr(void)
{
  struct __attribute__((aligned(16))) { unsigned char bytes[512]; } save;
  unsigned mask;
  memset(&save,0,sizeof(save));
  __asm__ volatile("fxsave %0" : "=m"(save));
  memcpy(&mask,save.bytes+28,sizeof(mask));
  /* Intel/AMD's architectural fallback mask excludes optional DAZ. */
  return mask ? mask : 0x0000ffbfu;
}
#endif

int main(int argc,char **argv)
{
  const char *names[]={"scalar","sse2","avx1","avx2","avx512"};
  const int rounds[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
  const lsx_dsd_kernel *tiers[5];
  unsigned n=0,i,r,f,flush_count=1;
  unsigned flush_modes[4]={0,1u<<15,1u<<6,(1u<<15)|(1u<<6)};
  unsigned features=lsx_dsd_features_host();
  int saved_round=fegetround();
  const char *selected_tier=NULL;
  int quick=0,arg;
#if defined(__SSE2__)
  unsigned saved_mxcsr=_mm_getcsr();
#endif
  for (arg=1;arg<argc;++arg) {
    if (!strcmp(argv[arg],"--exceptions")) compare_exceptions=1;
    else if (!strcmp(argv[arg],"--quick")) quick=1;
    else if (!strcmp(argv[arg],"--tier") && arg+1<argc) selected_tier=argv[++arg];
    else if (!strcmp(argv[arg],"--case") && arg+1<argc) {
      char *end;
      long value=strtol(argv[++arg],&end,10);
      if (*end || value<0 || value>32) { fputs("invalid case number\n",stderr); return 2; }
      selected_case=(int)value;
    }
    else {
      fprintf(stderr,"usage: %s [--exceptions] [--quick] [--tier NAME] [--case N]\n",argv[0]);
      return 2;
    }
  }
  for (i=0;i<5;++i) {
    const lsx_dsd_kernel *tier=NULL;
    if (selected_tier && strcmp(selected_tier,names[i])) continue;
    if (!lsx_dsd_kernel_select_features(LSX_DSD_SDM,names[i],features,&tier))
      tiers[n++]=tier;
  }
  CHECK(n>0);
#if defined(__SSE2__) && (defined(__GNUC__) || defined(__clang__))
  flush_count=(supported_mxcsr()&(1u<<6)) ? 4 : 2;
#endif
  if (quick) flush_count=1;
  printf("original scalar differential: tiers=%u profiles=16 rounds=%u "
      "flush_modes=%u exceptions=%d\n",n,quick ? 1u : 4u,flush_count,compare_exceptions);
  fflush(stdout);
  for (r=0;r<(quick ? 1u : 4u);++r) {
    CHECK(!fesetround(rounds[r]));
    current_round=r;
    for (f=0;f<flush_count;++f) {
      current_flush=f;
#if defined(__SSE2__)
      _mm_setcsr((_mm_getcsr()&~((1u<<15)|(1u<<6)))|flush_modes[f]);
#else
      (void)flush_modes;
#endif
      for (i=0;i<n;++i) suite(tiers[i]);
      printf("PASS round=%u flush=%u cumulative_cases=%llu committed_frames=%llu\n",
          r,f,(unsigned long long)comparisons,(unsigned long long)frames_compared);
      fflush(stdout);
    }
  }
  CHECK(!fesetround(saved_round));
#if defined(__SSE2__)
  _mm_setcsr(saved_mxcsr);
#endif
  puts("PASS original scalar: outputs, both banks, all monitor bytes, peaks, "
       "aliases, rejected samples, prefixes, counter saturation and block boundaries");
  return 0;
}
