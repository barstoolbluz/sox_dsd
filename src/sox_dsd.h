/* Additive DSD layout API.  Public sox_ng.h structures are unchanged.
 * Layouts are owned snapshots: no getter returns a pointer into a format. */
#ifndef SOX_DSD_H
#define SOX_DSD_H
#include "sox_ng.h"
#if defined(__cplusplus)
extern "C" {
#endif
/* Match the host libSoX calling convention on targets where it is not the
 * native C default.  x86-64 GCC ignores its legacy cdecl attribute. */
#if defined(_MSC_VER) || (defined(__GNUC__) && defined(__i386__))
#define SOX_DSD_CALL LSX_API
#else
#define SOX_DSD_CALL
#endif

typedef struct sox_dsd_layout sox_dsd_layout_t;
typedef enum {
  SOX_DSD_OK = 0, SOX_DSD_NEED_INPUT, SOX_DSD_NEED_OUTPUT,
  SOX_DSD_DONE, SOX_DSD_BAD_ARGUMENT, SOX_DSD_UNSUPPORTED,
  SOX_DSD_IO_ERROR, SOX_DSD_NUMERIC_ERROR
} sox_dsd_status_t;

typedef enum {
  SOX_DSD_ROLE_UNKNOWN = 0, SOX_DSD_ROLE_MONO, SOX_DSD_ROLE_FL,
  SOX_DSD_ROLE_FR, SOX_DSD_ROLE_FC, SOX_DSD_ROLE_LFE,
  SOX_DSD_ROLE_BL, SOX_DSD_ROLE_BR, SOX_DSD_ROLE_SL, SOX_DSD_ROLE_SR
} sox_dsd_role_t;

typedef enum {
  SOX_DSD_CONTAINER_UNKNOWN = 0, SOX_DSD_CONTAINER_DSF,
  SOX_DSD_CONTAINER_DFF, SOX_DSD_CONTAINER_WSD,
  SOX_DSD_CONTAINER_WAV
} sox_dsd_container_t;

/* A channel copy.  ID bytes are the original DFF four-byte, non-terminated ID.
 * The first two fields permit future compatible extensions. */
typedef struct {
  size_t size;
  unsigned version; /* 1 */
  sox_dsd_role_t role;
  sox_bool dff_id_valid;
  unsigned char dff_id[4];
} sox_dsd_channel_info_t;

typedef struct {
  size_t size;
  unsigned version; /* 1 */
  sox_dsd_container_t container;
  uint64_t native_hz;
  uint64_t frames;
  unsigned channels;
  unsigned physical_bit_order; /* 1 LSB, 8 MSB, 0 not applicable */
  sox_bool length_known;
  unsigned original_dsf_type; /* 0 when absent */
  sox_bool dff_lsco_present;
  unsigned dff_lsco;
  sox_bool wsd_assignment_present;
  uint32_t wsd_assignment; /* uninterpreted original field */
} sox_dsd_stream_info_t;

sox_dsd_layout_t *SOX_DSD_CALL sox_dsd_layout_new(unsigned channels);
sox_dsd_layout_t *SOX_DSD_CALL sox_dsd_layout_copy(const sox_dsd_layout_t *src);
void SOX_DSD_CALL sox_dsd_layout_free(sox_dsd_layout_t *layout);
unsigned SOX_DSD_CALL sox_dsd_layout_channels(const sox_dsd_layout_t *layout);
sox_dsd_status_t SOX_DSD_CALL sox_dsd_layout_channel(
    const sox_dsd_layout_t *layout, unsigned index, sox_dsd_channel_info_t *out);
sox_dsd_status_t SOX_DSD_CALL sox_dsd_layout_set_role(
    sox_dsd_layout_t *layout, unsigned index, sox_dsd_role_t role);
sox_dsd_status_t SOX_DSD_CALL sox_dsd_layout_set_dff_id(
    sox_dsd_layout_t *layout, unsigned index, const unsigned char id[4]);
sox_dsd_status_t SOX_DSD_CALL sox_dsd_layout_set_dsf_type(sox_dsd_layout_t *layout, unsigned type);
unsigned SOX_DSD_CALL sox_dsd_layout_dsf_type(const sox_dsd_layout_t *layout);
sox_dsd_status_t SOX_DSD_CALL sox_dsd_layout_set_dff_lsco(sox_dsd_layout_t *layout, unsigned value);
sox_bool SOX_DSD_CALL sox_dsd_layout_dff_lsco(const sox_dsd_layout_t *layout, unsigned *value);
sox_bool SOX_DSD_CALL sox_dsd_layout_wsd_assignment(const sox_dsd_layout_t *layout, uint32_t *value);
/* Output indexes refer to source channels.  Reject duplicates; unlike a mix,
 * an index-only subset/permutation retains corresponding channel identity. */
sox_dsd_layout_t *SOX_DSD_CALL sox_dsd_layout_map(
    const sox_dsd_layout_t *src, const unsigned *source_indexes, unsigned count);
void SOX_DSD_CALL sox_dsd_layout_invalidate(sox_dsd_layout_t *layout);
/* Copy-out WAV bit-mask and ascending-mask-order permutation; unsupported if
 * an exact named speaker assignment is not representable. */
sox_dsd_status_t SOX_DSD_CALL sox_dsd_layout_wav_mask(
    const sox_dsd_layout_t *layout, uint32_t *mask, unsigned *source_indexes, size_t capacity);
sox_dsd_status_t SOX_DSD_CALL sox_dsd_get_layout(const sox_format_t *ft, sox_dsd_layout_t **owned_copy);
sox_dsd_status_t SOX_DSD_CALL sox_dsd_get_stream_info(const sox_format_t *ft, sox_dsd_stream_info_t *out);
/* Clones layout and installs it in format-private state before startwrite. */
sox_format_t *SOX_DSD_CALL sox_open_write_dsd(
    const char *path, const sox_signalinfo_t *signal,
    const sox_encodinginfo_t *encoding, const char *filetype,
    const sox_oob_t *oob, sox_bool (*overwrite_permitted)(const char *),
    const sox_dsd_layout_t *layout);

/* P07: additive binary64 reconstruction ABI.  API samples retain values
 * beyond +/-1.0; only the SoX graph adapter clips to signed int32. */
typedef struct sox_dsd_decoder sox_dsd_decoder_t;
typedef enum {
  SOX_DSD_DECODE_MASTERING = 0, SOX_DSD_DECODE_WIDEBAND = 1,
  /* Value 2 is reserved for the private legacy profile (not a public mode).
   * Explicit unqualified v2 candidate; previous ABI/enum values unchanged. */
  SOX_DSD_DECODE_MASTERING_V2 = 3
} sox_dsd_decode_profile_t;
typedef enum {
  SOX_DSD_LEVEL_PRESERVE = 0, SOX_DSD_LEVEL_SACD = 1
} sox_dsd_decode_level_t;
typedef enum {
  SOX_DSD_BANDWIDTH_ADAPT = 0, SOX_DSD_BANDWIDTH_STRICT = 1
} sox_dsd_decode_bandwidth_t;
typedef struct sox_dsd_decode_options {
  size_t size;
  unsigned version;                   /* 1 */
  uint32_t native_hz, output_hz;
  unsigned channels;
  sox_dsd_decode_profile_t profile;
  sox_dsd_decode_level_t level;
  sox_dsd_decode_bandwidth_t bandwidth;
  /* Optional P11 extension, NULL=family environment/default policy. A
   * non-NULL override has precedence over environment variables. Call
   * sox_dsd_decode_options_init_extended() to initialize and activate it;
   * the original initializer deliberately uses the shorter P07 record size
   * to preserve ABI safety for already compiled callers. */
  const char *kernel_fir;
} sox_dsd_decode_options_t;
typedef struct sox_dsd_report {
  size_t size;
  unsigned version;                   /* 1 */
  uint64_t native_frames, intermediate_frames, output_frames;
  uint32_t native_hz, intermediate_hz, output_hz;
  unsigned channels;
  double applied_gain, effective_passband_hz;
  sox_dsd_status_t status;
} sox_dsd_report_t;
void SOX_DSD_CALL sox_dsd_decode_options_init(sox_dsd_decode_options_t *);
/* Initialize the full P11-sized record, including the optional FIR override. */
void SOX_DSD_CALL sox_dsd_decode_options_init_extended(sox_dsd_decode_options_t *);
sox_dsd_status_t SOX_DSD_CALL sox_dsd_decoder_create(
    const sox_dsd_decode_options_t *, sox_dsd_decoder_t **);
sox_dsd_status_t SOX_DSD_CALL sox_dsd_decoder_process(
    sox_dsd_decoder_t *, const sox_sample_t *, size_t *, double *, size_t *);
/* P16 optional borrowed native input. Byte order describes the returned
 * bytes (DSF MSB input is normalized in its owned read cache). `data` remains
 * borrowed only until the next packed read or successful seek/close. The
 * bit offset starts at 0..7 in the first addressed byte; `last_valid_bits`
 * is the count 1..8 of chronological bits through the final frame in that
 * byte, including the starting offset for a sub-byte block. Frame 0/channel
 * 0 is data[0]; byte_stride advances a channel's next packed byte and
 * channel_stride advances to the next channel's first packed byte.
 * `bytes` is the physical readable extent from data[0], not a count of
 * audio bytes; callers must never decode frames beyond `frames`.
 * The storage must not be modified by a caller. A handle cannot alternate
 * packed and expanded reads until a successful seek (including seek(0)). */
typedef enum {
  SOX_DSD_PACKED_LSB = 1, SOX_DSD_PACKED_MSB = 8
} sox_dsd_packed_order_t;
typedef struct sox_dsd_packed_block {
  size_t size;
  unsigned version;                    /* 1 */
  const uint8_t *data;                  /* borrowed, never writable */
  size_t bytes;                         /* available buffer extent */
  size_t frames;                        /* valid native DSD frames */
  unsigned channels;
  unsigned bit_offset, last_valid_bits; /* 0..7, 1..8 */
  size_t channel_stride, byte_stride;   /* bytes, not frames */
  sox_dsd_packed_order_t bit_order;
} sox_dsd_packed_block_t;
void SOX_DSD_CALL sox_dsd_packed_block_init(sox_dsd_packed_block_t *);
sox_bool SOX_DSD_CALL sox_dsd_packed_supported(const sox_format_t *);
/* Returns OK with frames>0, DONE at EOF, or a named error. `max_frames`
 * bounds the returned block. Exactly one update of ft->olength occurs on OK. */
sox_dsd_status_t SOX_DSD_CALL sox_dsd_read_packed(
    sox_format_t *, size_t max_frames, sox_dsd_packed_block_t *);
/* Consume a descriptor slice, starting at `start_frame`, through the normal
 * first-stage FIR and downstream SRC, without an interleaved int32 buffer.
 * input_frames is input capacity on entry/consumed count on return. */
sox_dsd_status_t SOX_DSD_CALL sox_dsd_decoder_process_packed(
    sox_dsd_decoder_t *, const sox_dsd_packed_block_t *, size_t start_frame,
    size_t *input_frames, double *interleaved_pcm, size_t *output_frames);

sox_dsd_status_t SOX_DSD_CALL sox_dsd_decoder_finish(
    sox_dsd_decoder_t *, double *, size_t *);
sox_dsd_status_t SOX_DSD_CALL sox_dsd_decoder_report(
    const sox_dsd_decoder_t *, sox_dsd_report_t *);
void SOX_DSD_CALL sox_dsd_decoder_destroy(sox_dsd_decoder_t *);

#if defined(__cplusplus)
}
#endif
#endif
