/* Bounded, owned metadata for DSD channel identity.  No global registry.
 * No work from this module runs in the sample conversion loops. */
#include "sox_i.h"
#include "dsd_layout_i.h"
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LAYOUT_CHANNELS 65535U /* DFF CHNL stores a 16-bit count */
#define DFF_ID(a,b,c,d) ((uint32_t)(a)<<24 | (uint32_t)(b)<<16 | (uint32_t)(c)<<8 | (uint32_t)(d))

static const sox_dsd_role_t dsf_roles[7][6] = {
  {SOX_DSD_ROLE_MONO},
  {SOX_DSD_ROLE_FL, SOX_DSD_ROLE_FR},
  {SOX_DSD_ROLE_FL, SOX_DSD_ROLE_FR, SOX_DSD_ROLE_FC},
  {SOX_DSD_ROLE_FL, SOX_DSD_ROLE_FR, SOX_DSD_ROLE_BL, SOX_DSD_ROLE_BR},
  {SOX_DSD_ROLE_FL, SOX_DSD_ROLE_FR, SOX_DSD_ROLE_FC, SOX_DSD_ROLE_LFE},
  {SOX_DSD_ROLE_FL, SOX_DSD_ROLE_FR, SOX_DSD_ROLE_FC, SOX_DSD_ROLE_BL, SOX_DSD_ROLE_BR},
  {SOX_DSD_ROLE_FL, SOX_DSD_ROLE_FR, SOX_DSD_ROLE_FC, SOX_DSD_ROLE_LFE, SOX_DSD_ROLE_BL, SOX_DSD_ROLE_BR},
};
static const unsigned dsf_counts[] = {1,2,3,4,4,5,6};

sox_dsd_layout_t *sox_dsd_layout_new(unsigned count)
{
  sox_dsd_layout_t *p;
  unsigned i;
  if (!count || count > MAX_LAYOUT_CHANNELS)
    return NULL;
  p = calloc(1, sizeof(*p) + (size_t)count * sizeof(p->channel[0]));
  if (!p) return NULL;
  p->channels = count;
  for (i=0; i<count; ++i) {
    p->channel[i].size = sizeof(p->channel[i]);
    p->channel[i].version = 1;
  }
  return p;
}

sox_dsd_layout_t *sox_dsd_layout_copy(const sox_dsd_layout_t *src)
{
  sox_dsd_layout_t *p;
  if (!src || !(p = sox_dsd_layout_new(src->channels))) return NULL;
  memcpy(p,src,sizeof(*p) + (size_t)src->channels * sizeof(src->channel[0]));
  return p;
}
void sox_dsd_layout_free(sox_dsd_layout_t *p) { free(p); }
unsigned sox_dsd_layout_channels(const sox_dsd_layout_t *p) { return p ? p->channels : 0; }

sox_dsd_status_t sox_dsd_layout_channel(const sox_dsd_layout_t *p,
    unsigned index, sox_dsd_channel_info_t *out)
{
  size_t capacity;
  sox_dsd_channel_info_t result;
  if (!p || index >= p->channels || !out ||
      out->size < offsetof(sox_dsd_channel_info_t, role) + sizeof(out->role) ||
      out->version != 1)
    return SOX_DSD_BAD_ARGUMENT;
  capacity = out->size;
  result = p->channel[index];
  result.size = capacity; /* Keep the caller's actual writable capacity. */
  memcpy(out, &result, capacity < sizeof(result) ? capacity : sizeof(result));
  return SOX_DSD_OK;
}
sox_dsd_status_t sox_dsd_layout_set_role(sox_dsd_layout_t *p,
    unsigned index, sox_dsd_role_t role)
{
  if (!p || index >= p->channels || role > SOX_DSD_ROLE_SR)
    return SOX_DSD_BAD_ARGUMENT;
  if (p->channel[index].role != role) {
    p->dsf_type = 0;
    p->lsco_present = sox_false;
    p->channel[index].role = role;
    p->channel[index].dff_id_valid = sox_false;
    memset(p->channel[index].dff_id, 0, 4);
  }
  return SOX_DSD_OK;
}
sox_dsd_status_t sox_dsd_layout_set_dff_id(sox_dsd_layout_t *p,
    unsigned index, const unsigned char id[4])
{
  if (!p || index >= p->channels || !id) return SOX_DSD_BAD_ARGUMENT;
  memcpy(p->channel[index].dff_id,id,4);
  p->channel[index].dff_id_valid = sox_true;
  p->dsf_type = 0;
  p->lsco_present = sox_false;
  return SOX_DSD_OK;
}
sox_dsd_status_t sox_dsd_layout_set_dsf_type(sox_dsd_layout_t *p, unsigned type)
{
  unsigned i;
  if (!p || !type || type > 7 || p->channels != dsf_counts[type-1])
    return SOX_DSD_BAD_ARGUMENT;
  for (i=0;i<p->channels;i++) {
    p->channel[i].role = dsf_roles[type-1][i];
    p->channel[i].dff_id_valid = sox_false;
  }
  p->dsf_type = type;
  p->origin = SOX_DSD_CONTAINER_DSF;
  p->lsco_present = sox_false;
  return SOX_DSD_OK;
}
sox_dsd_layout_t *lsx_dsd_layout_from_dsf(unsigned type, unsigned count)
{
  sox_dsd_layout_t *p = sox_dsd_layout_new(count);
  if (!p) return NULL;
  p->origin = SOX_DSD_CONTAINER_DSF;
  if (type >= 1 && type <= 7 && count == dsf_counts[type-1])
    sox_dsd_layout_set_dsf_type(p,type);
  return p;  /* unknown type is retained by the stream-info raw field */
}
unsigned sox_dsd_layout_dsf_type(const sox_dsd_layout_t *p) {return p ? p->dsf_type : 0;}
sox_dsd_status_t sox_dsd_layout_set_dff_lsco(sox_dsd_layout_t *p,unsigned v)
{
  if (!p || v > UINT16_MAX) return SOX_DSD_BAD_ARGUMENT;
  p->lsco = v;
  p->lsco_present = sox_true;
  return SOX_DSD_OK;
}
sox_bool sox_dsd_layout_dff_lsco(const sox_dsd_layout_t *p,unsigned *v)
{
  if (!p || !p->lsco_present) return sox_false;
  if (v) *v = p->lsco;
  return sox_true;
}
sox_bool sox_dsd_layout_wsd_assignment(const sox_dsd_layout_t *p,uint32_t *v)
{
  if (!p || !p->wsd_present) return sox_false;
  if (v) *v = p->wsd_assignment;
  return sox_true;
}
sox_dsd_layout_t *sox_dsd_layout_map(const sox_dsd_layout_t *src,
    const unsigned *map, unsigned count)
{
  sox_dsd_layout_t *out;
  unsigned i,j;
  sox_bool identity;
  if (!src || !map || !count || count > src->channels) return NULL;
  for (i=0;i<count;i++) {
    if (map[i] >= src->channels) return NULL;
    for (j=0;j<i;j++) if (map[i]==map[j]) return NULL;
  }
  out = sox_dsd_layout_new(count);
  if (!out) return NULL;
  identity = count == src->channels;
  for (i=0;i<count;i++) {
    out->channel[i] = src->channel[map[i]];
    if (map[i]!=i) identity = sox_false;
  }
  if (identity) {
    out->dsf_type = src->dsf_type;
    out->lsco_present = src->lsco_present;
    out->lsco = src->lsco;
    out->wsd_present = src->wsd_present;
    out->wsd_assignment = src->wsd_assignment;
    out->origin = src->origin;
  } else
    out->origin = SOX_DSD_CONTAINER_UNKNOWN;
  return out;
}
void sox_dsd_layout_invalidate(sox_dsd_layout_t *p)
{
  unsigned i;
  if (!p) return;
  p->origin = SOX_DSD_CONTAINER_UNKNOWN;
  p->dsf_type = 0;
  p->lsco_present = sox_false;
  p->wsd_present = sox_false;
  for (i=0;i<p->channels;i++) {
    p->channel[i].role = SOX_DSD_ROLE_UNKNOWN;
    p->channel[i].dff_id_valid = sox_false;
    memset(p->channel[i].dff_id,0,4);
  }
}
static unsigned role_mask(sox_dsd_role_t role)
{
  static const unsigned bits[] = {0,0x4,0x1,0x2,0x4,0x8,0x10,0x20,0x200,0x400};
  return role < (sizeof(bits)/sizeof(bits[0])) ? bits[role] : 0;
}
sox_dsd_status_t sox_dsd_layout_wav_mask(const sox_dsd_layout_t *p,
    uint32_t *mask, unsigned *indices, size_t capacity)
{
  unsigned i,j,m=0;
  if (!p || !mask || (indices && capacity < p->channels)) return SOX_DSD_BAD_ARGUMENT;
  for (i=0;i<p->channels;i++) {
    unsigned b=role_mask(p->channel[i].role);
    if (!b || (m & b)) return SOX_DSD_UNSUPPORTED;
    m |= b;
  }
  *mask = m;
  if (indices) {
    for (i=0;i<p->channels;i++) {
      unsigned best=UINT_MAX, bit=UINT_MAX;
      for (j=0;j<p->channels;j++) {
        unsigned b=role_mask(p->channel[j].role);
        if (b>0 && b<bit) {
          unsigned k; sox_bool seen=sox_false;
          for(k=0;k<i;k++) if(indices[k]==j)seen=sox_true;
          if(!seen) {bit=b;best=j;}
        }
      }
      indices[i]=best;
    }
  }
  return SOX_DSD_OK;
}
sox_dsd_layout_t *lsx_dsd_layout_from_wav(unsigned count,uint32_t mask)
{
  sox_dsd_layout_t *p=sox_dsd_layout_new(count);
  unsigned i,j=0,b;
  if (!p) return NULL;
  p->origin = SOX_DSD_CONTAINER_WAV;
  p->wav_mask_nonzero = mask != 0;
  /* A partial/extended/zero mask does not define all channel positions. */
  for(i=0;i<32;i++) if(mask & (1U<<i)) j++;
  if (!mask || j!=count || (mask & ~(0x63fU)))return p;
  j=0;
  for(i=0;i<32;i++) if((b=(1U<<i)) & mask) {
    sox_dsd_role_t r;
    /* SPEAKER_FRONT_CENTER is FC in multichannel audio.  A one-channel
     * WAV carrying only that bit may instead describe mono programme audio. */
    for(r=SOX_DSD_ROLE_FL; r<=SOX_DSD_ROLE_SR;r++)
      if (role_mask(r)==b)break;
    if (r>SOX_DSD_ROLE_SR) {sox_dsd_layout_invalidate(p);return p;}
    p->channel[j++].role = count==1 && r==SOX_DSD_ROLE_FC ? SOX_DSD_ROLE_MONO : r;
  }
  return p;
}
sox_bool lsx_dsd_layout_wav_without_assignment(const sox_dsd_layout_t *p)
{
  unsigned i;
  if (!p || p->origin != SOX_DSD_CONTAINER_WAV || p->wav_mask_nonzero)
    return sox_false;
  for (i=0;i<p->channels;++i)
    if (p->channel[i].role != SOX_DSD_ROLE_UNKNOWN ||
        p->channel[i].dff_id_valid)
      return sox_false;
  return sox_true;
}
unsigned lsx_dsd_layout_resolve_dsf(const sox_dsd_layout_t *p)
{
  unsigned t,i;
  if (!p) return 0;
  /* Original type must still describe the current channel order. */
  if (p->dsf_type >= 1 && p->dsf_type <= 7 && p->channels==dsf_counts[p->dsf_type-1]) {
    for(i=0;i<p->channels;i++)
      if(p->channel[i].role!=dsf_roles[p->dsf_type-1][i])break;
    if(i==p->channels)return p->dsf_type;
  }
  for (t=1;t<=7;t++) if(p->channels==dsf_counts[t-1]) {
    for (i=0;i<p->channels;i++)
      if(p->channel[i].role!=dsf_roles[t-1][i])break;
    if(i==p->channels)return t;
  }
  return 0;
}
uint32_t lsx_dsd_dff_id(const sox_dsd_layout_t *p,unsigned n)
{
  const sox_dsd_channel_info_t *c = &p->channel[n];
  if (c->dff_id_valid) {
    const unsigned char *s=c->dff_id;
    return DFF_ID(s[0],s[1],s[2],s[3]);
  }
  switch(c->role) {
    case SOX_DSD_ROLE_FL:return p->channels==2 ? DFF_ID('S','L','F','T') : DFF_ID('M','L','F','T');
    case SOX_DSD_ROLE_FR:return p->channels==2 ? DFF_ID('S','R','G','T') : DFF_ID('M','R','G','T');
    case SOX_DSD_ROLE_FC:case SOX_DSD_ROLE_MONO:return DFF_ID('C',' ',' ',' ');
    case SOX_DSD_ROLE_LFE:return DFF_ID('L','F','E',' ');
    /* DFF surround carries no side/back angle. The DSF->DFF convention
     * deliberately loses the distinction, not the channel chronology. */
    case SOX_DSD_ROLE_SL:case SOX_DSD_ROLE_BL:return DFF_ID('L','S',' ',' ');
    case SOX_DSD_ROLE_SR:case SOX_DSD_ROLE_BR:return DFF_ID('R','S',' ',' ');
    default:return DFF_ID('C','0'+(n/100)%10,'0'+(n/10)%10,'0'+n%10);
  }
}
sox_dsd_role_t lsx_dsd_role_from_dff_id(uint32_t id)
{
  switch(id) {
    case DFF_ID('S','L','F','T'):case DFF_ID('M','L','F','T'):return SOX_DSD_ROLE_FL;
    case DFF_ID('S','R','G','T'):case DFF_ID('M','R','G','T'):return SOX_DSD_ROLE_FR;
    case DFF_ID('C',' ',' ',' '):return SOX_DSD_ROLE_FC;
    case DFF_ID('L','F','E',' '):return SOX_DSD_ROLE_LFE;
    default:return SOX_DSD_ROLE_UNKNOWN; /* LS/RS is angle-ambiguous */
  }
}
sox_bool lsx_dsd_lsco_consistent(const sox_dsd_layout_t *p)
{
  unsigned i,v;
  static const uint32_t stereo[] = {DFF_ID('S','L','F','T'),DFF_ID('S','R','G','T')};
  static const uint32_t five[] = {DFF_ID('M','L','F','T'),DFF_ID('M','R','G','T'),DFF_ID('C',' ',' ',' '),DFF_ID('L','S',' ',' '),DFF_ID('R','S',' ',' ')};
  static const uint32_t six[] = {DFF_ID('M','L','F','T'),DFF_ID('M','R','G','T'),DFF_ID('C',' ',' ',' '),DFF_ID('L','F','E',' '),DFF_ID('L','S',' ',' '),DFF_ID('R','S',' ',' ')};
  const uint32_t *expected = NULL;
  if (!p || !sox_dsd_layout_dff_lsco(p,&v))return sox_true;
  if (v==0 && p->channels==2)expected=stereo;
  else if(v==3 && p->channels==5)expected=five;
  else if(v==4 && p->channels==6)expected=six;
  else if(v==0 || v==3 || v==4)return sox_false;
  else return sox_true; /* reserved/undefined: uninterpreted */
  for(i=0;i<p->channels;i++)if(lsx_dsd_dff_id(p,i)!=expected[i])return sox_false;
  return sox_true;
}
sox_bool lsx_dsd_layout_has_identity(const sox_dsd_layout_t *p)
{
  unsigned i;
  if (!p)return sox_false;
  for(i=0;i<p->channels;i++)
    if(p->channel[i].role!=SOX_DSD_ROLE_UNKNOWN || p->channel[i].dff_id_valid)
      return sox_true;
  return sox_false;
}
/* Names and private layout prefix are deliberately checked before casting. */
lsx_dsd_layout_state_t *lsx_dsd_layout_state(const sox_format_t *ft)
{
  const char *name;
  if (!ft || !ft->priv || !ft->handler.names || !(name=ft->handler.names[0]))return NULL;
  if (!strcmp(name,"dsf") || !strcmp(name,"dff") || !strcmp(name,"wsd") ||
      !strcmp(name,"wav"))
    return (lsx_dsd_layout_state_t *)ft->priv;
  return NULL;
}
sox_dsd_status_t sox_dsd_get_layout(const sox_format_t *ft,sox_dsd_layout_t **out)
{
  lsx_dsd_layout_state_t *s;
  if (!out || !ft)return SOX_DSD_BAD_ARGUMENT;
  *out = NULL;
  s = lsx_dsd_layout_state(ft);
  if (!s || !s->layout)return SOX_DSD_UNSUPPORTED;
  *out=sox_dsd_layout_copy(s->layout);
  return *out ? SOX_DSD_OK : SOX_DSD_IO_ERROR;
}
sox_dsd_status_t sox_dsd_get_stream_info(const sox_format_t *ft,sox_dsd_stream_info_t *out)
{
  lsx_dsd_layout_state_t *s;
  sox_dsd_container_t container=SOX_DSD_CONTAINER_UNKNOWN;
  const char *name;
  size_t capacity;
  sox_dsd_stream_info_t result={0};
  if (!ft || !out ||
      out->size<offsetof(sox_dsd_stream_info_t,channels)+sizeof(out->channels) ||
      out->version!=1 || !ft->handler.names ||
      !(name=ft->handler.names[0]))return SOX_DSD_BAD_ARGUMENT;
  if (!strcmp(name,"dsf"))container=SOX_DSD_CONTAINER_DSF;
  else if (!strcmp(name,"dff"))container=SOX_DSD_CONTAINER_DFF;
  else if (!strcmp(name,"wsd"))container=SOX_DSD_CONTAINER_WSD;
  else if (!strcmp(name,"wav"))container=SOX_DSD_CONTAINER_WAV;
  else return SOX_DSD_UNSUPPORTED;
  s=lsx_dsd_layout_state(ft);
  if (!s || !s->layout)return SOX_DSD_UNSUPPORTED;
  capacity=out->size;
  result.size=capacity;
  result.version=1;
  result.container=container;
  result.native_hz=(uint64_t)ft->signal.rate;
  result.channels=ft->signal.channels;
  result.length_known=ft->signal.length!=SOX_UNKNOWN_LEN;
  result.frames=result.length_known && ft->signal.channels ? ft->signal.length / ft->signal.channels : 0;
  result.physical_bit_order=container==SOX_DSD_CONTAINER_DFF ? 8 : container==SOX_DSD_CONTAINER_DSF ?
      s->layout->physical_bit_order : 0;
  result.original_dsf_type=s->layout->dsf_type;
  result.dff_lsco_present=s->layout->lsco_present;
  result.dff_lsco=s->layout->lsco;
  result.wsd_assignment_present=s->layout->wsd_present;
  result.wsd_assignment=s->layout->wsd_assignment;
  memcpy(out,&result,capacity<sizeof(result) ? capacity : sizeof(result));
  return SOX_DSD_OK;
}
