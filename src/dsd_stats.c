/* P14: native-bit statistics and strictly observational SOS measurement.
 * No routines here write to the graph, decode samples, or modulate bits.
 * SOS design: bilinear transform of the analog Butterworth N=5 prototype,
 * prewarped at each digital cutoff. Q for pole pairs = 1/(2 sin(pi/10))
 * and 1/(2 sin(3*pi/10)), plus one real pole. TDF-II binary64 sections.
 * SACD-style measurement is NOT certified physical SACD metrology. */
#include "sox_i.h"
#include "dsd_stats.h"
#include "dsd_decode.h"
#include "pcmdsd_guards.h"
#include <inttypes.h>
#include <float.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#define BANDS 4
#define SACD_ALPHA (1.0/524288.0) /* Scarlet Book/Saracon Annex D.4, 2^-19 */
#define PI_DSD 3.14159265358979323846264338327950288

typedef struct {
  uint64_t ones, windows, excursions, first_excursion, max_run, frames;
  uint64_t run; uint32_t window; unsigned filled, window_ones;
  unsigned min_ones, max_ones, last;
  unsigned overflow;
  lsx_dsd_sos level[3], ultrasonic[6], bands[BANDS][6];
  unsigned band_count[BANDS];
  double squared[BANDS], level_squared, ultrasonic_squared;
  double sacd_exp_power, sacd_exp_max_power, level_peak;
} channel_stat;
struct lsx_dsd_stats {
  uint32_t hz;
  unsigned channels, analysis, failure;
  uint64_t frames, excluded, integrated;
  channel_stat *c;
};
typedef struct {sox_dsd_report_t base; lsx_dsd_decode profile;
  lsx_dsd_level level; char kernel[24]; uint64_t clips;double peak;} decode_record;
typedef struct {lsx_pcmdsd_report base; char kernel[24];
  uint32_t native_hz; double reference_scale;
  char profile[64], certificate[68];} encode_record;
struct lsx_dsd_report_context {
  decode_record *dec; size_t ndecs;
  encode_record *enc; size_t nencs;
  lsx_dsd_stats *effect_stat; /* most recent dsdstat; channels ordered */
  unsigned out_of_memory;
};
static lsx_dsd_report_context *current_report;

static int increment(uint64_t *value)
{
  if (*value==UINT64_MAX) return 0;
  ++*value; return 1;
}

int lsx_dsd_butterworth5(uint32_t hz, double cutoff, int hp,
    lsx_dsd_sos s[3])
{
  double k, k2, q, d;unsigned i;
  if (!s || !hz || !isfinite(cutoff) || cutoff<=0 || cutoff>=hz*.5)
    return 0;
  memset(s,0,3*sizeof(*s));
  k=tan(PI_DSD*cutoff/hz);k2=k*k;
  if (!isfinite(k)) return 0;
  d=1/(1+k);
  s[0].order=1;s[0].b[0]=hp?d:k*d;
  s[0].b[1]=hp?-d:k*d;
  s[0].a[0]=1;s[0].a[1]=(k-1)*d;
  for (i=1;i<3;++i) {
    q=1/(2*sin((i==1?1:3)*PI_DSD/10));
    d=1/(1+k/q+k2);
    s[i].order=2;s[i].a[0]=1;
    s[i].a[1]=2*(k2-1)*d;
    s[i].a[2]=(1-k/q+k2)*d;
    s[i].b[0]=(hp?1:k2)*d;
    s[i].b[1]=hp?-2*s[i].b[0]:2*s[i].b[0];
    s[i].b[2]=s[i].b[0];
  }
  return 1;
}
double lsx_dsd_sos_tick(lsx_dsd_sos s[3], double x)
{
  unsigned j;
  for (j=0;j<3;j++) {
    lsx_dsd_sos *p=&s[j];
    double y=p->b[0]*x+p->z[0];
    p->z[0]=p->b[1]*x-p->a[1]*y+p->z[1];
    p->z[1]=p->order==2?p->b[2]*x-p->a[2]*y:0;
    x=y;
  }
  return x;
}

static void filters_init(channel_stat *c,uint32_t hz)
{
  static const double lows[BANDS]={20000,40000,100000,200000};
  static const double highs[BANDS]={40000,100000,200000,0};
  unsigned i;
  lsx_dsd_butterworth5(hz,50000,0,c->level);
  lsx_dsd_butterworth5(hz,40000,1,c->ultrasonic);
  lsx_dsd_butterworth5(hz,100000,0,c->ultrasonic+3);
  for (i=0;i<BANDS;i++) {
    if (!lsx_dsd_butterworth5(hz,lows[i],1,c->bands[i])) continue;
    c->band_count[i]=3;
    if (highs[i] && lsx_dsd_butterworth5(hz,highs[i],0,c->bands[i]+3))
      c->band_count[i]=6;
  }
}
lsx_dsd_stats *lsx_dsd_stats_create(unsigned channels, uint32_t hz, int analysis)
{
  lsx_dsd_stats *s;
  unsigned i;
  if (!channels || channels>64 || !hz || (analysis && hz<=400000)) return NULL;
  s=calloc(1,sizeof(*s));
  if (!s) return NULL;
  s->c=calloc(channels,sizeof(*s->c));
  if (!s->c) {free(s);return NULL;}
  s->channels=channels;s->hz=hz;s->analysis=!!analysis;
  s->excluded=analysis?hz/50:0; /* fixed 20 ms warm-up; no energy counted */
  for (i=0;i<channels;i++) {
    s->c[i].min_ones=29;
    s->c[i].first_excursion=UINT64_MAX;
    if (analysis) filters_init(&s->c[i],hz);
  }
  return s;
}
uint64_t lsx_dsd_stats_frames(const lsx_dsd_stats *s) {return s?s->frames:0;}
void lsx_dsd_stats_destroy(lsx_dsd_stats *s)
{if (s) {free(s->c);free(s);}}

int lsx_dsd_stats_feed(lsx_dsd_stats *s,const sox_sample_t *bits,size_t frames)
{
  size_t j;unsigned ch;
  if (!s || (!bits && frames) || s->failure || frames>UINT64_MAX-s->frames ||
      frames>SIZE_MAX/s->channels)
    return 0;
  for (j=0;j<frames;j++) {
    for (ch=0;ch<s->channels;ch++) {
      channel_stat *c=&s->c[ch];
      sox_sample_t sample=bits[j*s->channels+ch];
      unsigned bit;double x;
      if (sample!=SOX_SAMPLE_MAX && sample!=(-SOX_SAMPLE_MAX))
        return s->failure=1,0;
      bit=sample>0;
      if (bit && !increment(&c->ones)) return s->failure=1,0;
      if (c->frames && bit==c->last) {
        if (!increment(&c->run)) return s->failure=1,0;
      } else c->run=1;
      if (c->run>c->max_run) c->max_run=c->run;
      c->last=bit;
      c->window=((c->window<<1)|bit)&0x0FFFFFFFu;
      if (c->filled<28) ++c->filled;
      if (c->filled==28) {
        unsigned v=c->window;
        /* Small exact popcount, no dependence on SIMD or architecture. */
        v=v-((v>>1)&0x55555555u);
        v=(v&0x33333333u)+((v>>2)&0x33333333u);
        v=(v+(v>>4))&0x0F0F0F0Fu;
        v=(v*0x01010101u)>>24;
        if (!increment(&c->windows)) return s->failure=1,0;
        if (v<c->min_ones) c->min_ones=v;
        if (v>c->max_ones) c->max_ones=v;
        if (v<4 || v>24) {
          if (!c->excursions) c->first_excursion=c->frames-27;
          if (!increment(&c->excursions)) return s->failure=1,0;
        }
      }
      if (s->analysis) {
        unsigned band;
        double lv,uh;
        x=bit?1.:-1.;
        lv=lsx_dsd_sos_tick(c->level,x);
        uh=lsx_dsd_sos_tick(c->ultrasonic,x);
        uh=lsx_dsd_sos_tick(c->ultrasonic+3,uh);
        /* Scarlet Book Annex D.4 exponential smoothing is over power and
         * runs from the first frame (not the integrated-RMS warm-up). */
        c->sacd_exp_power+=(uh*uh-c->sacd_exp_power)*SACD_ALPHA;
        if (c->sacd_exp_power>c->sacd_exp_max_power)
          c->sacd_exp_max_power=c->sacd_exp_power;
        if (fabs(lv)>c->level_peak) c->level_peak=fabs(lv);
        if (j+s->frames>=s->excluded) {
          c->level_squared+=lv*lv;
          c->ultrasonic_squared+=uh*uh;
          for (band=0;band<BANDS;band++) if (c->band_count[band]) {
            double y=lsx_dsd_sos_tick(c->bands[band],x);
            if (c->band_count[band]==6)
              y=lsx_dsd_sos_tick(c->bands[band]+3,y);
            c->squared[band]+=y*y;
          }
        } else {
          for (band=0;band<BANDS;band++) if (c->band_count[band]) {
            double y=lsx_dsd_sos_tick(c->bands[band],x);
            if (c->band_count[band]==6)
              (void)lsx_dsd_sos_tick(c->bands[band]+3,y);
          }
        }
        if (!isfinite(lv) || !isfinite(uh) || !isfinite(c->sacd_exp_power))
          return s->failure=1,0;
      }
      if (!increment(&c->frames)) return s->failure=1,0;
    }
  }
  s->frames+=(uint64_t)frames;
  s->integrated=s->frames>s->excluded?s->frames-s->excluded:0;
  return 1;
}

static void jstr(FILE *f,const char *s)
{
  const unsigned char *p=(const unsigned char *)(s?s:"");
  fputc('"',f);
  while (*p) {
    if (*p=='"' || *p=='\\') {fputc('\\',f);fputc(*p,f);}
    else if (*p<32) fprintf(f,"\\u%04x",*p);
    else fputc(*p,f);
    ++p;
  }
  fputc('"',f);
}
void lsx_dsd_stats_uint64_json(FILE *f,uint64_t v)
{fprintf(f,"\"%" PRIu64 "\"",v);}
static void jint(FILE *f,uint64_t v) {lsx_dsd_stats_uint64_json(f,v);}
static void jnumber(FILE *f,double v) {if (isfinite(v))fprintf(f,"%.17g",v);else fputs("null",f);}
static void jdb(FILE *f,double power,double norm)
{
  if (isfinite(power) && power>0 && norm>0) jnumber(f,10*log10(power/norm));
  else fputs("null",f);
}
static const char *role_name(sox_dsd_role_t role)
{
  switch (role) {
    case SOX_DSD_ROLE_MONO:return "MONO";
    case SOX_DSD_ROLE_FL:return "FL";
    case SOX_DSD_ROLE_FR:return "FR";
    case SOX_DSD_ROLE_FC:return "FC";
    case SOX_DSD_ROLE_LFE:return "LFE";
    case SOX_DSD_ROLE_BL:return "BL";
    case SOX_DSD_ROLE_BR:return "BR";
    case SOX_DSD_ROLE_SL:return "SL";
    case SOX_DSD_ROLE_SR:return "SR";
    default:return "unknown";
  }
}
static void json_chan(FILE *f,const channel_stat *c,const lsx_dsd_stats *s)
{
  unsigned i;
  fputs("{\"frames\":",f);jint(f,c->frames);
  fputs(",\"one_bits\":",f);jint(f,c->ones);
  fputs(",\"zero_bits\":",f);jint(f,c->frames-c->ones);
  fputs(",\"complete_28_bit_windows\":",f);jint(f,c->windows);
  fputs(",\"28_bit_excursions\":",f);jint(f,c->excursions);
  fputs(",\"first_excursion_start_frame\":",f);
  if (!c->excursions) fputs("null",f);else jint(f,c->first_excursion);
  fputs(",\"min_ones_28\":",f);
  if (!c->windows)fputs("null",f);else fprintf(f,"%u",c->min_ones);
  fputs(",\"max_ones_28\":",f);
  if (!c->windows)fputs("null",f);else fprintf(f,"%u",c->max_ones);
  fputs(",\"longest_identical_bit_run\":",f);jint(f,c->max_run);
  if (s->analysis) {
    fputs(",\"measurement\":{\"method\":\"native_f64_butterworth5_sos_bilinear_prewarp\",\"formal_sacd_certification\":false,\"input_domain\":\"original_native_bits\",\"warmup_excluded_frames\":",f);
    jint(f,s->excluded);
    fputs(",\"integrated_frames\":",f);jint(f,s->integrated);
    fputs(",\"sacd_style\":{\"lowpass_hz\":50000,\"highpass_hz\":40000,\"band_lowpass_hz\":100000,\"power_average_alpha\":0.0000019073486328125,\"lowpass_peak_db_sacd\":",f);
    if (c->frames && c->level_peak>0)jnumber(f,20*log10(c->level_peak/.5));else fputs("null",f);
    fputs(",\"band_exp_rms_max_db_sacd\":",f);
    jdb(f,c->sacd_exp_max_power,.125);
    fputs("},\"integrated_bands\":[",f);
    for (i=0;i<BANDS;i++) {
      static const unsigned limits[4][2]={{20000,40000},{40000,100000},{100000,200000},{200000,0}};
      if (i) fputc(',',f);
      fprintf(f,"{\"low_hz\":%u,\"high_hz\":",limits[i][0]);
      if (limits[i][1])fprintf(f,"%u",limits[i][1]);else fprintf(f,"%.1f",s->hz*.5);
      fputs(",\"power_dbfs_sine_reference\":",f);
      if (s->integrated && c->band_count[i])
        jdb(f,c->squared[i]/s->integrated,.5);
      else fputs("null",f);
      fputc('}',f);
    }
    fputs("]}",f);
  }
  fputc('}',f);
}
void lsx_dsd_stats_json(FILE *f,const lsx_dsd_stats *s)
{
  unsigned i;
  if (!s) {fputs("null",f);return;}
  fprintf(f,"{\"native_hz\":%u,\"channel_count\":%u,\"frames\":",
      s->hz,s->channels);
  jint(f,s->frames);
  fputs(",\"count_semantics\":\"overlapping_28_bit_windows_chronological\",\"analysis_enabled\":",f);
  fputs(s->analysis?"true":"false",f);
  fputs(",\"status\":",f);jstr(f,s->failure?"failed":"observed");
  fputs(",\"channels\":[",f);
  for (i=0;i<s->channels;i++) {if(i)fputc(',',f);json_chan(f,&s->c[i],s);}
  fputs("]}",f);
}


/* Standalone dsdstat is useful even without --dsd-report. Match SoX stat's
 * stderr sink; never mix observational text into an audio or JSON stdout.
 * The structured JSON keeps complete, lossless values for automation. */
void lsx_dsd_stats_text(FILE *f,const lsx_dsd_stats *s)
{
  unsigned ch,i;
  if(!s)return;
  fprintf(f,"Native DSD: %u Hz, %u channel(s), %" PRIu64 " frames/channel\n",
      s->hz,s->channels,s->frames);
  for (ch=0;ch<s->channels;ch++) {
    const channel_stat *c=&s->c[ch];
    fprintf(f,"  Channel %u: one bits=%" PRIu64 ", zero bits=%" PRIu64
        ", complete overlapping 28-bit windows=%" PRIu64
        ", excursions (<4 or >24 one bits)=%" PRIu64
        ", longest identical-bit run=%" PRIu64 "\n",
        ch+1,c->ones,c->frames-c->ones,c->windows,c->excursions,c->max_run);
    if(c->windows) fprintf(f,"    28-bit one-count min=%u max=%u",c->min_ones,c->max_ones);
    else fputs("    28-bit one-count min/max=unknown (no complete window)",f);
    if(c->excursions)fprintf(f,", first excursion starts at frame %" PRIu64,c->first_excursion);
    fputc('\n',f);
    if(s->analysis) {
      static const unsigned endpoints[4][2]={{20000,40000},{40000,100000},{100000,200000},{200000,0}};
      fprintf(f,"    Native SACD-style digital fifth-order Butterworth SOS (uncertified), 50 kHz LP, 40-100 kHz HP/LP, alpha=2^-19\n");
      if(c->frames && c->level_peak>0)
        fprintf(f,"    50 kHz LP digital peak: %.4f dB SACD\n",20*log10(c->level_peak/.5));
      if(c->sacd_exp_max_power>0)
        fprintf(f,"    40-100 kHz band exponential max power: %.4f dB SACD\n",10*log10(c->sacd_exp_max_power/.125));
      fprintf(f,"    Integrated band power: %" PRIu64 " frames after %" PRIu64 " warm-up frames, dBFS sine-reference\n",
          s->integrated,s->excluded);
      for(i=0;i<BANDS;i++) {
        fprintf(f,"      %u-%u Hz: ",endpoints[i][0],endpoints[i][1]?endpoints[i][1]:s->hz/2);
        if(s->integrated && c->band_count[i] && c->squared[i]>0)
          fprintf(f,"%.4f dBFS\n",10*log10(c->squared[i]/s->integrated/.5));
        else fputs("unknown (zero or too short)\n",f);
      }
    }
  }
}

lsx_dsd_report_context *lsx_dsd_report_create(void)
{return calloc(1,sizeof(lsx_dsd_report_context));}
void lsx_dsd_report_enable(lsx_dsd_report_context *s) {current_report=s;}
void lsx_dsd_report_disable(void) {current_report=NULL;}
void lsx_dsd_report_destroy(lsx_dsd_report_context *s)
{if(s){if(current_report==s)current_report=NULL;free(s->dec);free(s->enc);
    lsx_dsd_stats_destroy(s->effect_stat);free(s);}}
static lsx_dsd_stats *stats_copy(const lsx_dsd_stats *s)
{
  lsx_dsd_stats *c;
  if (!s) return NULL;
  c=malloc(sizeof(*c));if (!c) return NULL;
  *c=*s;c->c=malloc(s->channels*sizeof(*c->c));
  if (!c->c) {free(c);return NULL;}
  memcpy(c->c,s->c,s->channels*sizeof(*c->c));return c;
}
void lsx_dsd_report_note_stat(const lsx_dsd_stats *s)
{
  lsx_dsd_stats *copy;
  if (!current_report) return;
  copy=stats_copy(s);
  if (!copy){current_report->out_of_memory=1;return;}
  lsx_dsd_stats_destroy(current_report->effect_stat);
  current_report->effect_stat=copy;
}
void lsx_dsd_report_note_decode(const sox_dsd_decoder_t *decoder,
    lsx_dsd_decode profile, lsx_dsd_level level, uint64_t clips, double peak)
{
  decode_record *array, *r;sox_dsd_report_t report={0};
  const char *name;
  if (!current_report || !decoder) return;
  report.size=sizeof(report);report.version=1;
  if (sox_dsd_decoder_report(decoder,&report)!=SOX_DSD_OK) {
    current_report->out_of_memory=1;return;
  }
  if (current_report->ndecs==SIZE_MAX/sizeof(*r)) {
    current_report->out_of_memory=1;return;
  }
  array=realloc(current_report->dec,(current_report->ndecs+1)*sizeof(*r));
  if (!array) {current_report->out_of_memory=1;return;}
  current_report->dec=array;r=&array[current_report->ndecs++];
  memset(r,0,sizeof(*r));r->base=report;r->profile=profile;r->level=level;
  r->clips=clips;r->peak=peak;
  name=lsx_dsd_decoder_kernel_name(decoder);
  snprintf(r->kernel,sizeof(r->kernel),"%s",name?name:"unknown");
}
void lsx_dsd_report_note_encode(const lsx_pcmdsd *encoder)
{
  encode_record *array, *r;lsx_pcmdsd_report report={0};
  const lsx_pcmdsd_profile *profile;const char *name;
  if (!current_report || !encoder) return;
  if (lsx_pcmdsd_report_get(encoder,&report)!=SOX_DSD_OK) {
    current_report->out_of_memory=1;return;
  }
  if (current_report->nencs==SIZE_MAX/sizeof(*r)) {
    current_report->out_of_memory=1;return;
  }
  array=realloc(current_report->enc,(current_report->nencs+1)*sizeof(*r));
  if (!array) {current_report->out_of_memory=1;return;}
  current_report->enc=array;r=&array[current_report->nencs++];
  memset(r,0,sizeof(*r));r->base=report;
  r->reference_scale=lsx_pcmdsd_reference_scale(encoder);
  /* Composite P10's actual native rate can be derived from the certified
   * constant ratio only through profile lookup, not a requested CLI alias. */
  profile=NULL;
  if (report.committed_frames || report.input_frames) {
    /* A private context getter supplies its actual immutable profile. */
    profile=lsx_pcmdsd_profile_of(encoder);
  } else profile=lsx_pcmdsd_profile_of(encoder);
  if (profile) {
    r->native_hz=profile->native_hz;
    snprintf(r->profile,sizeof(r->profile),"%s",profile->id);
    snprintf(r->certificate,sizeof(r->certificate),"%s",profile->certificate_sha256);
  }
  name=lsx_pcmdsd_kernel_name(encoder);
  snprintf(r->kernel,sizeof(r->kernel),"%s",name?name:"unknown");
}

/* The frontend banks are immutable and certified by the P06 manifest.
 * P14 reports the actual selected last-stage bank together with the
 * unchanged halfband bank identity; the P06 reference file is the authority. */
static const char *bank_hash(lsx_dsd_last_bank bank)
{
  switch (bank) {
    case LSX_DSD_BANK_MASTER64_256:return "76749b06a43bb529207e68abc8d71631d21013f547de74ecd7837638d6506139";
    case LSX_DSD_BANK_MASTER128:return "306a836d730b97b8f8f8e82d01ea2fc87eeec7efc70939c76558ab8e8fc44673";
    case LSX_DSD_BANK_WIDEBAND:return "658f940a7fbc529a6f927e05c36b9d3c4b5858f001d2b21759e7a6e36ed658d0";
    case LSX_DSD_BANK_MASTER64_V2:return "1cf7807a6be4651bfd264873dd09075f7f532b22ab3b9638223857f4af09107b";
    case LSX_DSD_BANK_MASTER128_V2:return "8f84430b2f0113d4b2055073833b8ab9acba2cd145b300f0f75b7cccc0faaf1b";
    case LSX_DSD_BANK_MASTER256_V2:return "2b908ebaa0cacc23965d63e46b3838d7eff4149dee5dd01e2d8f12996ee20231";
    default:return NULL;
  }
}

static void json_dec(FILE *f,const decode_record *r)
{
  const lsx_dsd_frontend_profile *p=lsx_dsd_frontend_profile_find(r->base.native_hz,r->profile);
  const char *id=p?p->canonical_id:NULL;
  fputs("{\"profile_id\":",f);if(id)jstr(f,id);else fputs("null",f);
  fputs(",\"fir_kernel_actual\":",f);jstr(f,r->kernel);
  fputs(",\"coefficients\":{\"bank_halfband_sha256\":\"140a07d78b4d31f55680554298b8f1a2d4e444643123af570e3f2f552361f125\",\"bank_last_sha256\":",f);
  if(p && bank_hash(p->last_bank))jstr(f,bank_hash(p->last_bank));else fputs("null",f);
  fputs("},\"source_native_hz\":",f);fprintf(f,"%u",r->base.native_hz);
  fputs(",\"output_pcm_hz\":",f);fprintf(f,"%u",r->base.output_hz);
  fputs(",\"intermediate_pcm_hz\":",f);fprintf(f,"%u",r->base.intermediate_hz);
  fputs(",\"guaranteed_passband_hz\":",f);if(p)jnumber(f,p->pass_hz);else fputs("null",f);
  fputs(",\"guaranteed_stopband_hz\":",f);if(p)jnumber(f,p->stop_hz);else fputs("null",f);
  fputs(",\"candidate_unqualified\":",f);
  fputs(r->profile==LSX_DSD_PROFILE_MASTERING_V2?"true":"false",f);
  fputs(",\"frames_consumed\":",f);jint(f,r->base.native_frames);
  fputs(",\"frames_produced\":",f);jint(f,r->base.output_frames);
  fputs(",\"intermediate_frames\":",f);jint(f,r->base.intermediate_frames);
  fputs(",\"filter_delay_native_frames\":",f);
  if(p)jint(f,p->delay_native_frames);else fputs("null",f);
  fputs(",\"filter_phase_native_frames\":",f);
  if(p)jint(f,p->delay_native_frames%(p->native_hz/p->intermediate_hz));else fputs("null",f);
  fputs(",\"filter_discard_intermediate_frames\":",f);
  if(p)jint(f,p->delay_native_frames/(p->native_hz/p->intermediate_hz));else fputs("null",f);
  /* Decoder timestamps are compensated, but compensation is not zero
   * streaming lookahead. Keep frontend support separate from the private
   * SRC's unexposed multistage delay and from scheduling-dependent FIFOs.
   * A queue capacity is not a measured buffering latency. */
  fputs(",\"latency\":{\"front_end_lookahead_native_frames\":",f);
  if(p)jint(f,p->delay_native_frames);else fputs("null",f);
  fputs(",\"front_end_lookahead_seconds\":",f);
  if(p && r->base.native_hz)jnumber(f,(double)p->delay_native_frames/r->base.native_hz);
  else fputs("null",f);
  fputs(",\"final_src_active\":",f);
  fputs(r->base.output_hz!=r->base.intermediate_hz?"true":"false",f);
  fputs(",\"final_src_lookahead_intermediate_frames\":",f);
  if(r->base.output_hz==r->base.intermediate_hz)jint(f,0);
  else fputs("null",f);
  fputs(",\"final_src_lookahead_seconds\":",f);
  if(r->base.output_hz==r->base.intermediate_hz)jnumber(f,0.);
  else fputs("null",f);
  fputs(",\"final_src_lookahead_note\":",f);
  if(r->base.output_hz==r->base.intermediate_hz)fputs("null",f);
  else jstr(f,"multistage private rate backend does not expose an exact lookahead; no delay inferred from tap count or block size");
  fputs(",\"buffering_latency_seconds\":null,\"buffering_latency_note\":",f);
  jstr(f,"processing-schedule-dependent decoder FIFO occupancy is not a fixed latency; FIFO capacity is not elapsed time");
  fputs(",\"total_latency_seconds\":null,\"total_latency_note\":",f);
  jstr(f,"not calculable without a fixed buffering latency; nonidentity SRC lookahead is also unavailable");
  fputc('}',f);
  fputs(",\"effective_passband_hz\":",f);jnumber(f,r->base.effective_passband_hz);
  fputs(",\"gain_mapping\":{\"input\":\"theoretical_dsd_amplitude\",\"output\":\"pcm_dbfs\",\"mode\":",f);
  jstr(f,r->level==LSX_DSD_LEVEL_SACD?"sacd_reference":"preserve");
  fputs(",\"applied_linear_gain\":",f);jnumber(f,r->base.applied_gain);
  fputs("},\"graph_clips\":",f);jint(f,r->clips);
  fputs(",\"max_graph_preclip_amplitude\":",f);
  if(r->base.output_frames)jnumber(f,r->peak);else fputs("null",f);
  fputs(",\"context_status\":",f);jstr(f,r->base.status==SOX_DSD_DONE?"done":r->base.status==SOX_DSD_NUMERIC_ERROR?"failed":"incomplete");
  fputc('}',f);
}
static void json_enc(FILE *f,const encode_record *r)
{
  unsigned i;const sdm_normal_monitor_t *m=&r->base.monitor;
  fputs("{\"profile_id\":",f);jstr(f,r->profile);
  fputs(",\"coefficient_certificate_sha256\":",f);jstr(f,r->certificate);
  fputs(",\"sdm_kernel_actual\":",f);jstr(f,r->kernel);
  fprintf(f,",\"native_hz\":%u,\"source_frames\":",r->native_hz);jint(f,r->base.input_frames);
  fputs(",\"committed_native_frames\":",f);jint(f,r->base.committed_frames);
  fputs(",\"effective_passband_hz\":",f);jnumber(f,r->base.effective_pass_hz);
  fputs(",\"modulator_input_scale_actual\":",f);jnumber(f,r->reference_scale);
  fputs(",\"first_error_frame\":",f);
  if(r->base.failure==LSX_PCMDSD_NO_ERROR)fputs("null",f);else jint(f,r->base.first_bad_frame);
  fprintf(f,",\"failure_code\":%u,\"channel_index\":%u,\"peak_modulator_input\":",
      r->base.failure,r->base.channel);
  jnumber(f,r->base.peak);
  fputs(",\"monitor\":{\"frames\":",f);jint(f,m->frames);
  fputs(",\"windows_28\":",f);jint(f,m->windows28);
  fputs(",\"excursions_28\":",f);jint(f,m->excursions28);
  fputs(",\"minimum_one_bits_28\":",f);
  if(m->windows28)fprintf(f,"%u",m->min_ones28);else fputs("null",f);
  fputs(",\"maximum_one_bits_28\":",f);
  if(m->windows28)fprintf(f,"%u",m->max_ones28);else fputs("null",f);
  fputs(",\"longest_identical_bit_run\":",f);jint(f,m->longest_run);
  fputs(",\"first_overload_frame\":",f);
  if(m->overloads)jint(f,m->first_overload_frame);else fputs("null",f);
  fputs(",\"overloads\":",f);jint(f,m->overloads);
  fputs(",\"counter_saturated\":",f);fputs(m->counter_saturated?"true":"false",f);
  fputs(",\"nonfinite\":",f);jint(f,m->nonfinite);
  fputs(",\"state_extrema_absolute\":[",f);
  for (i=0;i<8;i++) {if(i)fputc(',',f);jnumber(f,m->max_abs_state[i]);}
  fputs("]}}",f);
}

void lsx_dsd_report_json(FILE *f,const lsx_dsd_report_context *r,
    const lsx_dsd_plan *plan,const lsx_dsd_stats *const *sources,size_t nsrc,
    const sox_dsd_stream_info_t *infos,const sox_dsd_layout_t *const *layouts,
    const sox_format_t *const *source_formats,
    uint64_t output_frames,uint64_t output_clips,
    uint64_t adapter_clips,uint64_t mixing_clips,const char *status,
    const char *version)
{
  size_t i,j;
  fprintf(f,"{\n  \"schema\":\"sox.dsd.conversion.v1\",\n  \"schema_version\":1,\n  \"build\":{\"version\":");
  jstr(f,version);
  fputs(",\"source_baseline\":\"d940cc93\",\"build_source_digest\":null,\"build_digest_note\":\"unavailable from source-only archive without git\"},\n  \"status\":",f);
  jstr(f,status);
  fputs(",\"executable\":true,\n  \"source\":[",f);
  for(i=0;i<nsrc;i++) {
    const sox_dsd_stream_info_t *si=infos?infos+i:NULL;
    const sox_dsd_layout_t *layout=layouts?layouts[i]:NULL;
    const sox_format_t *ft=source_formats?source_formats[i]:NULL;
    int native=(ft && ft->encoding.encoding==SOX_ENCODING_DSD) ||
        sources[i] || (si && (si->container==SOX_DSD_CONTAINER_DSF ||
        si->container==SOX_DSD_CONTAINER_DFF || si->container==SOX_DSD_CONTAINER_WSD));
    if(i) fputc(',',f);
    fputs("{\"domain\":",f);
    jstr(f,native?"DSD_NATIVE":"PCM_AUDIO");
    fputs(",\"container\":",f);
    if(native) jstr(f,si?si->container==SOX_DSD_CONTAINER_DSF?"dsf":
        si->container==SOX_DSD_CONTAINER_DFF?"dff":
        si->container==SOX_DSD_CONTAINER_WSD?"wsd":"unknown":"unknown");
    else jstr(f,ft&&ft->filetype?ft->filetype:"unknown");
    /* Use the *opened reader* rather than inferred output settings: P14's
     * native DSD stream info is intentionally empty for ordinary PCM. */
    fputs(",\"sample_rate_hz\":",f);
    if(!native && ft && ft->signal.rate>0)jnumber(f,ft->signal.rate);
    else fputs("null",f); /* DSD has its distinct native bit clock below. */
    fputs(",\"encoding\":",f);
    if(ft && ft->encoding.encoding>SOX_ENCODING_UNKNOWN &&
        ft->encoding.encoding<SOX_ENCODINGS)
      jstr(f,sox_encodings_info[ft->encoding.encoding].desc);
    else fputs("null",f);
    fputs(",\"bits_per_sample\":",f);
    if(ft && ft->encoding.bits_per_sample)fprintf(f,"%u",ft->encoding.bits_per_sample);
    else fputs("null",f);
    /* The generic stream-info bridge can describe WAV's sample clock in
     * native_hz. Do not publish that clock as a native DSD bit rate. */
    fputs(",\"native_hz\":",f);
    if(native && si && si->native_hz)jint(f,si->native_hz);
    else fputs("null",f);
    fputs(",\"declared_logical_frames\":",f);if(si && si->length_known)jint(f,si->frames);else fputs("null",f);
    fputs(",\"source_nyquist_hz\":",f);
    if (native && si && si->native_hz && si->container!=SOX_DSD_CONTAINER_WAV)
      jnumber(f,si->native_hz*.5);
    else if (!native && ft && ft->signal.rate>0)
      jnumber(f,ft->signal.rate*.5);
    else fputs("null",f);
    fputs(",\"known_program_bandwidth_hz\":null,\"physical_bit_order\":",f);
    if(si && si->physical_bit_order)fprintf(f,"%u",si->physical_bit_order);
    else fputs("null",f);
    fputs(",\"channel_roles\":[",f);
    if(layout)for(j=0;j<sox_dsd_layout_channels(layout);j++) {
      sox_dsd_channel_info_t ci={0};
      ci.size=sizeof(ci);ci.version=1;
      if(j)fputc(',',f);
      if(sox_dsd_layout_channel(layout,(unsigned)j,&ci)==SOX_DSD_OK)
        jstr(f,role_name(ci.role));
      else fputs("null",f);
    }
    fputs("],\"native_statistics\":",f);lsx_dsd_stats_json(f,sources[i]);
    fputc('}',f);
  }
  fputs("],\n  \"output\":{\"domain\":",f);
  jstr(f,plan?lsx_dsd_domain_name(plan->output_domain):"unknown");
  fputs(",\"actual_rate_hz\":",f);if(plan)jnumber(f,plan->output_rate);else fputs("null",f);
  fputs(",\"channels\":",f);if(plan)fprintf(f,"%u",plan->output_channels);else fputs("null",f);
  fputs(",\"frames_written\":",f);jint(f,output_frames);
  fputs(",\"native_completed_frames\":",f);
  if(plan && plan->output_domain==LSX_DSD_NATIVE)jint(f,output_frames);else fputs("null",f);
  fputs(",\"transport_frames\":",f);
  if(plan && plan->output_domain==LSX_DOP_TRANSPORT)jint(f,output_frames);else fputs("null",f);
  fputs("},\n  \"processing\":{\"requested_passband_hz\":",f);
  if(plan && plan->decoder_pass_hz)jnumber(f,plan->decoder_pass_hz);else fputs("null",f);
  fputs(",\"effective_passband_hz\":",f);
  if(plan && plan->effective_bandwidth_hz)jnumber(f,plan->effective_bandwidth_hz);else fputs("null",f);
  fputs(",\"decoder\":[",f);
  for(i=0;r && i<r->ndecs;i++){if(i)fputc(',',f);json_dec(f,&r->dec[i]);}
  fputs("],\"encoder\":[",f);
  for(i=0;r && i<r->nencs;i++){if(i)fputc(',',f);json_enc(f,&r->enc[i]);}
  fputs("]},\n  \"dsdstat\":",f);lsx_dsd_stats_json(f,r?r->effect_stat:NULL);
  fputs(",\n  \"clipping\":{\"output_writer\":",f);jint(f,output_clips);
  fputs(",\"input_adapter\":",f);jint(f,adapter_clips);
  fputs(",\"combiner\":",f);jint(f,mixing_clips);
  fputs("},\n  \"warnings\":[",f);
  if(r && r->out_of_memory)jstr(f,"report evidence incomplete: allocation failure");
  fputs("]\n}\n",f);
}
