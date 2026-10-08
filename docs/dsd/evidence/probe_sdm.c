/* Include the reviewed source to observe its otherwise private normal-path state. */
#ifndef SOX_SOURCE
#error Compile with SOX_SOURCE naming the reviewed src/sdm.c file.
#endif
#include SOX_SOURCE
#include <math.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
static uint32_t rng=0x1729abcd;
static double noise(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return ((double)rng/4294967296.0)*2-1;}
int main(int argc,char **argv){
 if(argc<6)return 2;
 const char *name=argv[1],*kind=argv[3];unsigned fs=(unsigned)strtoul(argv[2],NULL,10);
 double amp=strtod(argv[4],NULL),dur=strtod(argv[5],NULL);uint64_t n=(uint64_t)(dur*fs+.5);
 sdm_t *p=sdm_init(name,fs,0,0,0);if(!p)return 3;
 uint32_t hist=0;unsigned ones=0,minones=28,maxones=0;uint64_t violations=0;double maxstate=0;int nonfinite=0;
 FILE *f=argc>6?fopen(argv[6],"wb"):NULL;unsigned byte=0,nb=0;
 for(uint64_t i=0;i<n;i++){
   double t=(double)i/fs,x=0;
   if(!strcmp(kind,"sine"))x=amp*sin(2*M_PI*1000*t);
   else if(!strcmp(kind,"edge"))x=amp*sin(2*M_PI*19000*t);
   else if(!strcmp(kind,"wide"))x=amp*(sin(2*M_PI*30000*t)+sin(2*M_PI*60000*t)+sin(2*M_PI*80000*t))/3;
   else if(!strcmp(kind,"dc"))x=amp;
   else if(!strcmp(kind,"step"))x=(i<n/3?0:i<2*n/3?amp:-amp);
   else if(!strcmp(kind,"square"))x=sin(2*M_PI*100*t)>=0?amp:-amp;
   else if(!strcmp(kind,"noise"))x=amp*noise();
   else if(!strcmp(kind,"multi"))x=amp*(sin(2*M_PI*61*t)+sin(2*M_PI*997*t)+sin(2*M_PI*17011*t))/3;
   else if(!strcmp(kind,"impulse"))x=(i==n/2)?amp:0;
   else if(strcmp(kind,"silence"))return 4;
   unsigned bit=sdm_sample(p,x)>0;ones+=bit;ones-=(hist>>27)&1;hist=((hist<<1)|bit)&0xfffffffU;
   if(i>=27){if(ones<minones)minones=ones;if(ones>maxones)maxones=ones;if(ones<4||ones>24)violations++;}
   double *s=p->trellis[0].sdm[p->idx].state;
   for(int k=0;k<p->filter->order;k++){double v=fabs(s[k]);if(!isfinite(v))nonfinite=1;if(v>maxstate)maxstate=v;}
   if(f){byte=(byte<<1)|bit;if(++nb==8){fputc(byte,f);byte=nb=0;}}
 }
 if(f){if(nb)fputc(byte<<(8-nb),f);fclose(f);}
 printf("{\"filter\":\"%s\",\"rate\":%u,\"stimulus\":\"%s\",\"amplitude_dsd\":%.8g,\"frames\":%llu,\"min_ones28\":%u,\"max_ones28\":%u,\"excursions28\":%llu,\"max_abs_state\":%.9g,\"nonfinite\":%s}\n",name,fs,kind,amp,(unsigned long long)n,minones,maxones,(unsigned long long)violations,maxstate,nonfinite?"true":"false");
 sdm_close(p);return 0;
}
