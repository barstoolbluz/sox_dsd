/* Effect: change sample rate  Copyright (c) 2008,12 robs@users.sourceforge.net
 *
 * This library is free software; you can redistribute it and/or modify it
 * under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or (at
 * your option) any later version.
 *
 * This library is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser
 * General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this library; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
 */

#include <float.h>

/* Resample using a non-interpolated poly-phase FIR with length LEN.*/
/* Input must be followed by LEN-1 samples. */

#define _ sum += (coef(p->shared->poly_fir_coefs, 0, FIR_LENGTH, divided.rem, 0, j)) *at[j], ++j;

static void FUNCTION(stage_t * p, fifo_t * output_fifo)
{
  sample_t const * input = stage_read_p(p);
  int i, num_in = stage_occupancy(p), max_num_out = 1 + num_in*p->out_in_ratio;
  sample_t * output = lsx_fifo_reserve(output_fifo, max_num_out);
#if defined(LSX_RATE_ORDERED_OPT) && LSX_RATE_ORDERED_OPT && \
    !defined(__FAST_MATH__) && FLT_EVAL_METHOD == 0
  /* Candidate path: the opt-in build must also disable FP contraction.
   * Each accumulator visits j in the original order.  Pairing independent
   * output samples exposes instruction/SIMD parallelism without splitting
   * either dot product into partial sums.  Coefficients are unchanged.
   *
   * If A = q*L+r and step = u*L+v, advancing A is exactly
   * q += u+carry, r += v-carry*L, carry = (r >= L-v).
   * This avoids per-output division and an overflowing intermediate r+v.
   * L and step are positive for every rational stage made by rate_init. */
  div_t divided = div(p->at.parts.integer, p->L);
  div_t const step = div(p->step.parts.integer, p->L);

  i = 0;
  while (divided.quot < num_in) {
    div_t next = divided;
    {
      int carry = next.rem >= p->L - step.rem;
      next.quot += step.quot + carry;
      next.rem += step.rem - carry * p->L;
    }
    if (next.quot >= num_in) break;
    {
      sample_t const * at0 = input + divided.quot;
      sample_t const * at1 = input + next.quot;
      sample_t const * c0 = p->shared->poly_fir_coefs + FIR_LENGTH * divided.rem;
      sample_t const * c1 = p->shared->poly_fir_coefs + FIR_LENGTH * next.rem;
      sample_t sum0 = 0, sum1 = 0;
      int j = 0;
#undef _
#define _ sum0 += c0[j] * at0[j], sum1 += c1[j] * at1[j], ++j;
      CONVOLVE
      output[i++] = sum0;
      output[i++] = sum1;
#undef _
#define _ sum += (coef(p->shared->poly_fir_coefs, 0, FIR_LENGTH, divided.rem, 0, j)) *at[j], ++j;
    }
    divided = next;
    {
      int carry = divided.rem >= p->L - step.rem;
      divided.quot += step.quot + carry;
      divided.rem += step.rem - carry * p->L;
    }
  }
  for (; divided.quot < num_in; ++i) {
    sample_t const * at = input + divided.quot;
    sample_t sum = 0;
    int j = 0;
    CONVOLVE
    output[i] = sum;
    {
      int carry = divided.rem >= p->L - step.rem;
      divided.quot += step.quot + carry;
      divided.rem += step.rem - carry * p->L;
    }
  }
  if (!(max_num_out - i >= 0)) lsx_warn("Assertion `max_num_out - i >= 0' failed. Carrying on anyway...");
  lsx_fifo_trim_by(output_fifo, max_num_out - i);
  lsx_fifo_read(&p->fifo, divided.quot, NULL);
  p->at.parts.integer = divided.rem;
#else
  div_t divided2;

  for (i = 0; p->at.parts.integer < num_in * p->L; ++i, p->at.parts.integer += p->step.parts.integer) {
    div_t divided = div(p->at.parts.integer, p->L);
    sample_t const * at = input + divided.quot;
    sample_t sum = 0;
    int j = 0;
    CONVOLVE
    output[i] = sum;
  }
  if (!(max_num_out - i >= 0)) lsx_warn("Assertion `max_num_out - i >= 0' failed. Carrying on anyway...");
  lsx_fifo_trim_by(output_fifo, max_num_out - i);
  divided2 = div(p->at.parts.integer, p->L);
  lsx_fifo_read(&p->fifo, divided2.quot, NULL);
  p->at.parts.integer = divided2.rem;
#endif
}

#undef _
#undef CONVOLVE
#undef FIR_LENGTH
#undef FUNCTION
