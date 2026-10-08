/* Design-time probe: intentionally observes unmodified repository behavior. */
#include "sox_ng.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
int main(int argc, char **argv) {
  sox_format_t *f; sox_sample_t b[4096]; size_t n, total=0, first=0;
  if (sox_init()!=SOX_SUCCESS || argc<3) return 2;
  if (!strcmp(argv[1], "write")) {
    unsigned c=(unsigned)strtoul(argv[3],NULL,10), frames=(unsigned)strtoul(argv[4],NULL,10);
    sox_signalinfo_t s={2822400,c,1,(sox_uint64_t)c*frames,NULL}; sox_encodinginfo_t e;
    sox_init_encodinginfo(&e); e.encoding=SOX_ENCODING_DSD; e.bits_per_sample=1;
    f=sox_open_write(argv[2],&s,&e,"dff",NULL,NULL); if(!f)return 3;
    for(unsigned j=0;j<4096;j++)b[j]=-SOX_SAMPLE_MAX;
    size_t left=(size_t)c*frames;
    while(left){n=left<4096?left:4096; n-=n%c; if(!n)return 5;
      n=sox_write(f,b,n); if(!n)return 6;left-=n;}
    int rc=sox_close(f); sox_quit(); return rc==SOX_SUCCESS?0:7;
  }
  f=sox_open_read(argv[2],NULL,NULL,NULL); if(!f){puts("{\"open\":false}");return 0;}
  unsigned initial=argc>3?(unsigned)strtoul(argv[3],NULL,10):0;
  uint64_t offset=argc>4?strtoull(argv[4],NULL,10):0;
  unsigned cap=argc>5?(unsigned)strtoul(argv[5],NULL,10):4096;
  int seek=argc>6?atoi(argv[6]):0, fix=argc>7?atoi(argv[7]):0;
  if(cap>4096||initial>4096)return 4;
  if(initial)first=sox_read(f,b,initial);
  int rc=seek?sox_seek(f,offset,SOX_SEEK_SET):0;
  uint64_t pos_before=f->olength;
  if(fix&&rc==0)f->olength=offset;
  unsigned head=0, hn=0;
  while((n=sox_read(f,b,cap))){for(size_t i=0;i<n&&hn<16;i++,hn++) head=(head<<1)|(b[i]>0);total+=n;}
  printf("{\"open\":true,\"length\":%llu,\"channels\":%u,\"first_read\":%zu,\"seek_rc\":%d,\"olength_after_seek\":%llu,\"remaining_returned\":%zu,\"head16\":%u}\n",(unsigned long long)f->signal.length,f->signal.channels,first,rc,(unsigned long long)pos_before,total,head);
  sox_close(f);sox_quit();return 0;
}
