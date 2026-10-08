/* P02: exercise the actual DoP effect with zero/partial output capacity.
 * Independent word constants, including the 0x69 tail, are fixed by hand.
 */
#include "../../src/dop.c"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { \
  fprintf(stderr, "DoP capacity: line %d: %s\n", __LINE__, #expr); return 1; \
} } while (0)

int main(void)
{
  dop_t state;
  sox_effect_t eff;
  sox_sample_t ones[32], next[32], tail[6];
  sox_sample_t output[4];
  size_t in, out;
  unsigned i;

  memset(&state, 0, sizeof(state));
  memset(&eff, 0, sizeof(eff));
  eff.priv = &state;
  eff.in_signal.channels = eff.out_signal.channels = 2;
  state.buf = calloc(2, sizeof(*state.buf));
  CHECK(state.buf != NULL);
  state.marker = 0x05;
  for (i = 0; i < 16; ++i) {
    ones[i * 2] = SOX_SAMPLE_MAX;
    ones[i * 2 + 1] = -SOX_SAMPLE_MAX;
    next[i * 2] = -SOX_SAMPLE_MAX;
    next[i * 2 + 1] = SOX_SAMPLE_MAX;
  }
  output[0] = 17; output[1] = 19; output[2] = 23;
  in = 30; out = 2;
  CHECK(dop_flow(&eff, ones, output, &in, &out) == SOX_SUCCESS);
  CHECK(in == 30 && out == 0 && state.pos == 15);
  CHECK(output[0] == 17 && output[1] == 19);

  in = 2; out = 0;
  CHECK(dop_flow(&eff, ones + 30, output, &in, &out) == SOX_SUCCESS);
  CHECK(in == 0 && out == 0 && state.pos == 15);
  CHECK(output[0] == 17 && output[1] == 19);

  in = 2; out = 1; /* one interleaved sample cannot hold two channels */
  CHECK(dop_flow(&eff, ones + 30, output, &in, &out) == SOX_SUCCESS);
  CHECK(in == 0 && out == 0 && state.pos == 15);
  CHECK(output[0] == 17 && output[1] == 19);

  in = 2; out = 2;
  CHECK(dop_flow(&eff, ones + 30, output, &in, &out) == SOX_SUCCESS);
  CHECK(in == 2 && out == 2 && state.pos == 0 && state.marker == 0xfa);
  CHECK((uint32_t)output[0] == UINT32_C(0x05ffff00));
  CHECK((uint32_t)output[1] == UINT32_C(0x05000000));

  in = 32; out = 2;
  CHECK(dop_flow(&eff, next, output, &in, &out) == SOX_SUCCESS);
  CHECK(in == 32 && out == 2 && state.pos == 0 && state.marker == 0x05);
  CHECK((uint32_t)output[0] == UINT32_C(0xfa000000));
  CHECK((uint32_t)output[1] == UINT32_C(0xfaffff00));

  tail[0] = SOX_SAMPLE_MAX; tail[1] = -SOX_SAMPLE_MAX;
  tail[2] = -SOX_SAMPLE_MAX; tail[3] = -SOX_SAMPLE_MAX;
  tail[4] = SOX_SAMPLE_MAX; tail[5] = -SOX_SAMPLE_MAX;
  in = 6; out = 2;
  CHECK(dop_flow(&eff, tail, output, &in, &out) == SOX_SUCCESS);
  CHECK(in == 6 && out == 0 && state.pos == 3);

  output[0] = 31; output[1] = 37;
  out = 0;
  CHECK(dop_drain(&eff, output, &out) == SOX_SUCCESS);
  CHECK(out == 0 && state.pos == 3);
  CHECK(output[0] == 31 && output[1] == 37);
  out = 1;
  CHECK(dop_drain(&eff, output, &out) == SOX_SUCCESS);
  CHECK(out == 0 && state.pos == 3);
  CHECK(output[0] == 31 && output[1] == 37);
  out = 2;
  CHECK(dop_drain(&eff, output, &out) == SOX_SUCCESS);
  CHECK(out == 2 && state.pos == 0);
  CHECK((uint32_t)output[0] == UINT32_C(0x05a96900));
  CHECK((uint32_t)output[1] == UINT32_C(0x05096900));
  out = 2;
  CHECK(dop_drain(&eff, output, &out) == SOX_SUCCESS && out == 0);
  free(state.buf);
  puts("P02 DoP capacity: 29 independent assertions PASS");
  return 0;
}
