/* Audit the unchanged hash-pinned fixture generator. Scaling already-quantized
 * PCM adds another quantization step; matching target level is not bit equality.
 * Keep this separate from test_p10.c so its preserved evidence identity holds. */
#define main p10_test_driver_main
#include "test_p10.c"
#undef main
int main(void) {
 uint32_t rates[]={88200,176400}; unsigned j;
 for (j=0;j<2;j++) {
  uint32_t hz=rates[j];uint64_t i,count=(uint64_t)30*hz, different=0,first=UINT64_MAX;double peak=0;
  long long max_steps=0;
  for(i=0;i<count;i++) {
   double original=soak_source_version((uint64_t)240*hz+i,hz,0);
   double nominal=soak_source_version((uint64_t)240*hz+i,hz,1);
   double attenuated=nearbyint((original*(.45/.7))*SOX_SAMPLE_MAX)/SOX_SAMPLE_MAX;
   double difference=fabs(nominal-attenuated);
   long long steps=llabs(llround(nominal*SOX_SAMPLE_MAX)-llround(attenuated*SOX_SAMPLE_MAX));
   if(steps>max_steps)max_steps=steps;
   if(difference){++different;if(first==UINT64_MAX)first=i;}
   if(difference>peak)peak=difference;
  }
  if(!different || max_steps!=1)return 1;
  printf("{\"source_hz\":%u,\"frames\":%" PRIu64 ",\"different_samples\":%" PRIu64 ",\"first_difference\":%" PRIu64 ",\"max_abs_difference\":%.17g,\"lsb\":%.17g,\"max_int32_steps\":%lld}\n",hz,count,different,first,peak,1./SOX_SAMPLE_MAX,max_steps);
 }
 return 0;
}
