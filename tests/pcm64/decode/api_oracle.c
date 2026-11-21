/* Phase 05B independent executable: opens the selected native format reader
 * and feeds the public DSD64/128 binary64 API directly.  It does not call
 * src/dsd_f64_decode.c, the PCM coordinator, CLI planning, or WAV writer.
 * Output is native-endian IEEE754 double words, with a compact count receipt. */
#include "sox_ng.h"
#include "sox_dsd.h"
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHUNK 4096
#define MAX_CH 64
static const size_t read_partitions[] = {1,7,256,511,4096,13,1023};
static const size_t output_partitions[] = {1,7,256,511,4096,3,31};

static int error(const char *what)
{
  fprintf(stderr,"oracle: %s\n",what);
  return 2;
}

int main(int argc,char **argv)
{
  sox_format_t *source=NULL;
  sox_dsd_decoder_t *decoder=NULL;
  sox_dsd_decode_options_t opts;
  sox_dsd_report_t report={0};
  sox_sample_t *native=NULL;
  double *pcm=NULL;
  FILE *output=NULL;
  uint64_t read_total=0,produced_total=0;
  size_t iteration=0,cursor=0,pending=0;
  unsigned channels;
  int eof=0,finished=0,rc=2;
  char *end;
  unsigned long rate;
  if (argc!=8) return error("usage: api_oracle IN.rawDSD OUT.rawF64 RATE PROFILE LEVEL BANDWIDTH KERNEL");
  errno=0;
  rate=strtoul(argv[3],&end,10);
  if (errno || *end || rate>UINT32_MAX || !rate) return error("invalid output rate");
  if (sox_init()!=SOX_SUCCESS) return error("sox_init");
  source=sox_open_read(argv[1],NULL,NULL,NULL);
  if (!source || source->encoding.encoding!=SOX_ENCODING_DSD ||
      source->signal.channels<1 || source->signal.channels>MAX_CH ||
      (source->signal.rate!=2822400. && source->signal.rate!=5644800.)) {
    error("native DSD reader metadata");goto done;
  }
  channels=source->signal.channels;
  sox_dsd_decode_options_init_extended(&opts);
  opts.native_hz=(uint32_t)source->signal.rate;
  opts.output_hz=(uint32_t)rate;
  opts.channels=channels;
  if (!strcmp(argv[4],"mastering")) opts.profile=SOX_DSD_DECODE_MASTERING;
  else if (!strcmp(argv[4],"wideband")) opts.profile=SOX_DSD_DECODE_WIDEBAND;
  else {error("unrecognized profile");goto done;}
  if (!strcmp(argv[5],"sacd")) opts.level=SOX_DSD_LEVEL_SACD;
  else if (!strcmp(argv[5],"preserve")) opts.level=SOX_DSD_LEVEL_PRESERVE;
  else {error("unrecognized level");goto done;}
  if (!strcmp(argv[6],"strict"))opts.bandwidth=SOX_DSD_BANDWIDTH_STRICT;
  else if (!strcmp(argv[6],"adapt"))opts.bandwidth=SOX_DSD_BANDWIDTH_ADAPT;
  else {error("unrecognized bandwidth");goto done;}
  opts.kernel_fir=!strcmp(argv[7],"auto")?NULL:argv[7];
  if (sox_dsd_decoder_create(&opts,&decoder)!=SOX_DSD_OK) {
    error("public decoder create failed");goto done;
  }
  native=malloc(CHUNK*channels*sizeof(*native));
  pcm=malloc(CHUNK*channels*sizeof(*pcm));
  output=fopen(argv[2],"wb");
  if (!native || !pcm || !output) {error("bounded allocation/open");goto done;}
  for (;;) {
    size_t n,made=output_partitions[iteration %
        (sizeof(output_partitions)/sizeof(output_partitions[0]))],used=0;
    sox_dsd_status_t st;
    if (!eof && cursor==pending) {
      n=read_partitions[iteration %
          (sizeof(read_partitions)/sizeof(read_partitions[0]))];
      pending=sox_read(source,native,n*channels);
      if (pending%channels || (!pending && source->sox_errno)) {
        error("native reader short/bad channel frame");goto done;
      }
      pending/=channels;cursor=0;
      if (pending>UINT64_MAX-read_total) {error("native frame count overflow");goto done;}
      read_total+=pending;
      if (!pending) eof=1;
    }
    if (eof) st=sox_dsd_decoder_finish(decoder,pcm,&made);
    else {
      used=pending-cursor;
      st=sox_dsd_decoder_process(decoder,native+cursor*channels,
          &used,pcm,&made);
      cursor+=used;
    }
    if (st!=SOX_DSD_NEED_INPUT && st!=SOX_DSD_NEED_OUTPUT &&
        st!=SOX_DSD_DONE) {error("public decoder process/finish failed");goto done;}
    if (!used && !made && !eof) {error("public decoder stalled");goto done;}
    if (made) {
      if (fwrite(pcm,sizeof(*pcm)*channels,made,output)!=made ||
          made>UINT64_MAX-produced_total) {
        error("oracle output write/count failed");goto done;
      }
      produced_total+=made;
    }
    iteration++;
    if (eof && st==SOX_DSD_DONE) {finished=1;break;}
  }
  report.size=sizeof(report);report.version=1;
  if (!finished || sox_dsd_decoder_report(decoder,&report)!=SOX_DSD_OK ||
      report.native_frames!=read_total || report.output_frames!=produced_total) {
    error("oracle final decoder count mismatch");goto done;
  }
  if (source->signal.length!=SOX_UNKNOWN_LEN &&
      source->signal.length!=SOX_UNSPEC &&
      source->signal.length/channels!=read_total) {
    error("source declared frame count mismatch");goto done;
  }
  if (fclose(output)) {output=NULL;error("oracle close failed");goto done;}
  output=NULL;
  printf("native=%" PRIu64 " intermediate=%" PRIu64
      " pcm=%" PRIu64 " channels=%u profile=%s level=%s rate=%u finish=done\n",
      report.native_frames,report.intermediate_frames,report.output_frames,
      channels,argv[4],argv[5],report.output_hz);
  rc=0;
done:
  if (output) fclose(output);
  free(native);free(pcm);
  sox_dsd_decoder_destroy(decoder);
  if (source) sox_close(source);
  sox_quit();
  return rc;
}
