/* P04 public C ABI/lifetime/metadata unit probe.  No writer under test is
 * used to establish the expected roles or mask.  All sample oracles in
 * test_layout.py are constructed independently. */
#include "sox_dsd.h"
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned passed;
#define CHECK(ok) do {if (!(ok)) {fprintf(stderr,"layout-test:%d: %s\n",__LINE__,#ok);return 1;} ++passed;}while(0)

static int channel(sox_dsd_layout_t const *p,unsigned index,
    sox_dsd_role_t role,char const *id)
{
  sox_dsd_channel_info_t c={0};
  c.size=sizeof(c);c.version=1;
  CHECK(sox_dsd_layout_channel(p,index,&c)==SOX_DSD_OK);
  CHECK(c.role==role);
  CHECK(c.dff_id_valid==(id!=NULL));
  if(id) CHECK(!memcmp(c.dff_id,id,4));
  return 0;
}

static int unit(void)
{
  static unsigned const flip[]={1,0,2,3},dup[]={0,0,1,2},identity[]={0,1,2,3};
  uint32_t mask;
  unsigned order[4]={100,100,100,100},v;
  sox_dsd_channel_info_t info={0};
  sox_dsd_layout_t *quad,*t5,*clone,*mapped,*dff;
  CHECK(!sox_dsd_layout_new(0));
  CHECK(!sox_dsd_layout_new(65536));
  CHECK((quad=sox_dsd_layout_new(4))!=NULL);
  CHECK(sox_dsd_layout_set_dsf_type(quad,4)==SOX_DSD_OK);
  CHECK(sox_dsd_layout_dsf_type(quad)==4);
  CHECK(!channel(quad,2,SOX_DSD_ROLE_BL,NULL));
  CHECK((t5=sox_dsd_layout_new(4))!=NULL);
  CHECK(sox_dsd_layout_set_dsf_type(t5,5)==SOX_DSD_OK);
  CHECK(sox_dsd_layout_dsf_type(t5)==5);
  CHECK(!channel(t5,2,SOX_DSD_ROLE_FC,NULL));
  { /* Version 1 accepts and writes only the caller-provided known prefix. */
    struct {sox_dsd_channel_info_t value; unsigned char guard[8];} prefix;
    const size_t writable=offsetof(sox_dsd_channel_info_t,role)+sizeof(info.role);
    memset(&prefix,0xa5,sizeof(prefix));
    prefix.value.size=writable;prefix.value.version=1;
    CHECK(sox_dsd_layout_channel(t5,2,&prefix.value)==SOX_DSD_OK);
    CHECK(prefix.value.size==writable && prefix.value.role==SOX_DSD_ROLE_FC);
    CHECK(((unsigned char *)&prefix.value)[writable]==0xa5);
  }
  CHECK(sox_dsd_layout_wav_mask(quad,&mask,order,4)==SOX_DSD_OK && mask==0x33);
  CHECK(sox_dsd_layout_wav_mask(t5,&mask,order,4)==SOX_DSD_OK && mask==0xf);
  CHECK(sox_dsd_layout_set_dsf_type(quad,5)==SOX_DSD_OK);
  CHECK((clone=sox_dsd_layout_copy(t5))!=NULL);
  sox_dsd_layout_free(t5);
  CHECK(sox_dsd_layout_dsf_type(clone)==5);
  CHECK(!channel(clone,3,SOX_DSD_ROLE_LFE,NULL));
  info.size=offsetof(sox_dsd_channel_info_t,role);info.version=1;
  CHECK(sox_dsd_layout_channel(clone,0,&info)==SOX_DSD_BAD_ARGUMENT);
  info.size=sizeof(info);info.version=99;
  CHECK(sox_dsd_layout_channel(clone,0,&info)==SOX_DSD_BAD_ARGUMENT);
  CHECK(sox_dsd_layout_channel(clone,5,&info)==SOX_DSD_BAD_ARGUMENT);
  CHECK(!sox_dsd_layout_map(clone,dup,4));
  CHECK((mapped=sox_dsd_layout_map(clone,flip,4))!=NULL);
  CHECK(!channel(mapped,0,SOX_DSD_ROLE_FR,NULL));
  CHECK(sox_dsd_layout_dsf_type(mapped)==0);
  CHECK(sox_dsd_layout_wav_mask(mapped,&mask,order,4)==SOX_DSD_OK && mask==0xf);
  CHECK(order[0]==1 && order[1]==0 && order[2]==2 && order[3]==3);
  sox_dsd_layout_free(mapped);
  CHECK((mapped=sox_dsd_layout_map(clone,identity,4))!=NULL);
  CHECK(sox_dsd_layout_dsf_type(mapped)==5);
  sox_dsd_layout_free(mapped);
  CHECK(sox_dsd_layout_set_role(clone,0,SOX_DSD_ROLE_UNKNOWN)==SOX_DSD_OK);
  CHECK(sox_dsd_layout_wav_mask(clone,&mask,order,4)==SOX_DSD_UNSUPPORTED);
  CHECK(sox_dsd_layout_set_role(clone,0,(sox_dsd_role_t)123)==SOX_DSD_BAD_ARGUMENT);
  sox_dsd_layout_invalidate(clone);
  CHECK(!channel(clone,2,SOX_DSD_ROLE_UNKNOWN,NULL));
  sox_dsd_layout_free(clone);
  sox_dsd_layout_free(quad);

  CHECK((dff=sox_dsd_layout_new(4))!=NULL);
  CHECK(sox_dsd_layout_set_dff_id(dff,0,(unsigned char const *)"X001")==SOX_DSD_OK);
  CHECK(sox_dsd_layout_set_dff_id(dff,1,(unsigned char const *)"X002")==SOX_DSD_OK);
  CHECK(sox_dsd_layout_set_dff_id(dff,2,(unsigned char const *)"X003")==SOX_DSD_OK);
  CHECK(sox_dsd_layout_set_dff_id(dff,3,(unsigned char const *)"X004")==SOX_DSD_OK);
  CHECK(sox_dsd_layout_set_dff_lsco(dff,65535)==SOX_DSD_OK);
  CHECK(sox_dsd_layout_dff_lsco(dff,&v) && v==65535);
  CHECK((mapped=sox_dsd_layout_copy(dff))!=NULL);
  sox_dsd_layout_free(dff);
  CHECK(!channel(mapped,2,SOX_DSD_ROLE_UNKNOWN,"X003"));
  CHECK(sox_dsd_layout_dff_lsco(mapped,&v) && v==65535);
  CHECK(sox_dsd_layout_set_role(mapped,2,SOX_DSD_ROLE_FL)==SOX_DSD_OK);
  CHECK(!channel(mapped,2,SOX_DSD_ROLE_FL,NULL));
  CHECK(!sox_dsd_layout_dff_lsco(mapped,&v));
  CHECK(sox_dsd_layout_set_dff_lsco(mapped,65536)==SOX_DSD_BAD_ARGUMENT);
  sox_dsd_layout_invalidate(mapped);
  CHECK(!channel(mapped,1,SOX_DSD_ROLE_UNKNOWN,NULL));
  sox_dsd_layout_free(mapped);
  printf("{\"result\":\"pass\",\"checks\":%u}\n",passed);
  return 0;
}

static int clone_file(char const *src,char const *dst)
{
  sox_format_t *in=NULL,*out=NULL;
  sox_dsd_layout_t *layout=NULL;
  sox_sample_t samples[4096];
  sox_dsd_stream_info_t stream={0};
  size_t count;
  int rc=1;
  in=sox_open_read(src,NULL,NULL,NULL);
  CHECK(in!=NULL);
  CHECK(sox_dsd_get_layout(in,&layout)==SOX_DSD_OK);
  stream.size=sizeof(stream);stream.version=1;
  CHECK(sox_dsd_get_stream_info(in,&stream)==SOX_DSD_OK);
  CHECK(stream.channels==in->signal.channels);
  {
    struct {sox_dsd_stream_info_t value;unsigned char guard[8];} prefix;
    const size_t writable=offsetof(sox_dsd_stream_info_t,channels)+sizeof(stream.channels);
    memset(&prefix,0xa5,sizeof(prefix));
    prefix.value.size=writable;prefix.value.version=1;
    CHECK(sox_dsd_get_stream_info(in,&prefix.value)==SOX_DSD_OK);
    CHECK(prefix.value.size==writable && prefix.value.channels==stream.channels);
    CHECK(((unsigned char *)&prefix.value)[writable]==0xa5);
  }
  if (stream.container==SOX_DSD_CONTAINER_DSF)
    CHECK(stream.physical_bit_order==1 || stream.physical_bit_order==8);
  out=sox_open_write_dsd(dst,&in->signal,&in->encoding,NULL,NULL,NULL,layout);
  CHECK(out!=NULL);
  sox_dsd_layout_free(layout);layout=NULL;
  while ((count=sox_read(in,samples,sizeof(samples)/sizeof(samples[0]))))
    CHECK(sox_write(out,samples,count)==count);
  CHECK(sox_close(out)==SOX_SUCCESS);out=NULL;
  CHECK(sox_close(in)==SOX_SUCCESS);in=NULL;
  rc=0;
  printf("{\"result\":\"pass\",\"checks\":%u,\"source_container\":%d,\"channels\":%u}\n",
    passed,stream.container,stream.channels);
  if (in)sox_close(in);
  if (out)sox_close(out);
  return rc;
}

static int inspect_file(char const *path)
{
  sox_format_t *in;
  sox_dsd_layout_t *layout=NULL;
  sox_dsd_stream_info_t stream={0};
  unsigned i;
  in=sox_open_read(path,NULL,NULL,NULL);
  CHECK(in!=NULL);
  CHECK(sox_dsd_get_layout(in,&layout)==SOX_DSD_OK);
  stream.size=sizeof(stream);stream.version=1;
  CHECK(sox_dsd_get_stream_info(in,&stream)==SOX_DSD_OK);
  CHECK(sox_close(in)==SOX_SUCCESS); /* snapshot remains owned and readable */
  printf("{\"container\":%u,\"bit_order\":%u,\"dsf_type\":%u,\"lsco_present\":%u,\"lsco\":%u,\"wsd_present\":%u,\"wsd_assignment\":%u,\"channels\":[",
    (unsigned)stream.container,stream.physical_bit_order,stream.original_dsf_type,
    (unsigned)stream.dff_lsco_present,stream.dff_lsco,
    (unsigned)stream.wsd_assignment_present,stream.wsd_assignment);
  for(i=0;i<stream.channels;i++) {
    sox_dsd_channel_info_t c={0};
    c.size=sizeof(c);c.version=1;
    CHECK(sox_dsd_layout_channel(layout,i,&c)==SOX_DSD_OK);
    printf("%s{\"role\":%u,\"id\":",i?",":"",(unsigned)c.role);
    if (c.dff_id_valid)printf("\"%02x%02x%02x%02x\"",c.dff_id[0],c.dff_id[1],c.dff_id[2],c.dff_id[3]);
    else printf("null");
    printf("}");
  }
  printf("]}\n");
  sox_dsd_layout_free(layout);
  return 0;
}

int main(int argc,char **argv)
{
  int result;
  if (sox_init()!=SOX_SUCCESS)return 1;
  if (argc==2 && !strcmp(argv[1],"unit"))result=unit();
  else if (argc==4 && !strcmp(argv[1],"clone"))result=clone_file(argv[2],argv[3]);
  else if (argc==3 && !strcmp(argv[1],"inspect"))result=inspect_file(argv[2]);
  else {fprintf(stderr,"usage: layout unit | clone source destination | inspect source\n");result=2;}
  if (sox_quit()!=SOX_SUCCESS)result=1;
  return result;
}
