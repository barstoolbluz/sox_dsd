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

#if defined(__cplusplus)
}
#endif
#endif
