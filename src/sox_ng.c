/* SoX - The Swiss Army Knife of Audio Manipulation.
 *
 * This is the main function for the SoX command line programs:
 *   sox, play, rec, soxi (also legacy _ng aliases).
 *
 * Copyright 1998-2009 Chris Bagwell and SoX contributors
 * Copyright 1991 Lance Norskog And Sundry Contributors
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation; either version 2 of the License, or (at your
 * option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
 * Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */

#include "soxconfig.h"
#include "sox_ng.h"
#include "sox_dsd.h"
#include "dsd.h"
#include "pcmdsd.h"
#include "dsd_stats.h"
#include "dsd_layout_query.h"
#include "util.h"
#include "softvol.h"
#include "win32-unicode.h"

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <time.h>

#ifdef HAVE_FCNTL_H
#include <fcntl.h>
#endif

#ifdef HAVE_SYS_STAT_H
#include <sys/stat.h>
#endif

/* The Linux FD_ISSET() manual says that newer POSIX systems need sys/select.h
 * but older systems did not. */
#ifdef HAVE_SYS_SELECT_H
#include <sys/select.h>
#endif

#if defined(HAVE_WIN32_GLOB_H)
  #include "win32-glob.h"
  #define HAVE_GLOB_H 1
#elif defined(HAVE_GLOB_H)
  #include <glob.h>
#endif

#ifdef HAVE_STROPTS_H
#  include <stropts.h>
#endif

#ifdef HAVE_IO_H
  #include <io.h>
#endif

#if HAVE_SUN_AUDIO
#ifdef HAVE_SUN_AUDIOIO_H
  #include <sun/audioio.h>
  #define HAVE_AUDIOIO_H 1
#else
#ifdef HAVE_SYS_AUDIOIO_H
  typedef unsigned int u_int;
  typedef unsigned char u_char;
  #include <sys/audioio.h>
  #define HAVE_AUDIOIO_H 1
#endif
#endif
#endif

#ifdef HAVE_SYS_SOUNDCARD_H
  #include <sys/soundcard.h>
  #define HAVE_SOUNDCARD_H 1
#else
#ifdef HAVE_MACHINE_SOUNDCARD_H
  #include <machine/soundcard.h>
  #define HAVE_SOUNDCARD_H 1
#endif
#endif

#ifdef HAVE_SYS_TIME_H
  #include <sys/time.h>
#endif

#ifdef HAVE_SYS_UTSNAME_H
  #include <sys/utsname.h>
#endif

#ifdef HAVE_UNISTD_H
  #include <unistd.h>
#endif

#ifdef HAVE_SYS_IOCTL_H
  #include <sys/ioctl.h>
#endif

#ifdef HAVE_GETTIMEOFDAY
  #define TIME_FRAC 1e6
#else
  #ifdef HAVE_SYS_TIMEB_H
    #include <sys/timeb.h>
  #endif
  #define timeval timeb
  #define gettimeofday(a,b) ftime(a)
  #define tv_sec time
  #define tv_usec millitm
  #define TIME_FRAC 1e3
#endif

#if !defined(HAVE_CONIO_H) && !defined(HAVE_TERMIOS_H) && (defined(_MSC_VER) || defined(__MINGW32__))
#define HAVE_CONIO_H 1
#endif

#ifdef HAVE_CONIO_H
/* _kbhit and _getch */
#include <conio.h>
#undef HAVE_TERMIOS_H
#endif

#ifdef _MSC_VER
#define IS_REGULAR_FILE(f)   ((f.st_mode & S_IFMT) == S_IFREG)
#else
#define IS_REGULAR_FILE(f)   (S_ISREG(f.st_mode))
#endif

#define SOX_OPTS "SOX_OPTS"
static lsx_getopt_t optstate;

/* argv[0] options */
static enum {sox_sox, sox_play, sox_rec, sox_soxi} sox_mode;


/* gopts */

static enum {
  sox_sequence, sox_concatenate, sox_mix, sox_mix_power,
  sox_merge, sox_multiply, sox_default
} combine_method = sox_default;
static enum { sox_single, sox_multiple } output_method = sox_single;
#define is_serial(m) ((m) <= sox_concatenate)
#define is_parallel(m) (!is_serial(m))
static sox_bool no_clobber = sox_false, interactive = sox_false;
static sox_bool uservolume = sox_false;
typedef enum {RG_off, RG_track, RG_album, RG_default} rg_mode;
static lsx_enum_item const rg_modes[] = {
  LSX_ENUM_ITEM(RG_,off)
  LSX_ENUM_ITEM(RG_,track)
  LSX_ENUM_ITEM(RG_,album)
  {0, 0}};
static rg_mode replay_gain_mode = RG_default;
static sox_option_t show_progress = sox_option_default;

/* Input & output files */

/* P08: a decoder is owned by one physical input, not by the combiner or
 * a graph effect.  Reader metadata remains native throughout its lifetime. */
typedef struct {
  sox_dsd_decoder_t *decoder;
  sox_sample_t *native;
  sox_dsd_packed_block_t packed;
  sox_bool use_packed;
  double *pcm;
  size_t pending, cursor;
  unsigned channels;
  uint64_t native_seen, native_expected;
  sox_bool native_length_known;
  uint64_t clips;
  double peak;
  sox_bool eof, done, failed;
} dsd_input_adapter_t;

typedef struct {
  char * filename;

  /* fopts */
  char const * filetype;
  sox_signalinfo_t signal;
  sox_encodinginfo_t encoding;
  double volume;
  double replay_gain;
  sox_oob_t oob;
  sox_bool no_glob;

  sox_format_t * ft;  /* libSoX file descriptor */
  uint64_t volume_clips;
  rg_mode replay_gain_mode;
  dsd_input_adapter_t *dsd_adapter;
  lsx_dsd_stats *dsd_source_stats;
  uint32_t dsd_target_hz;
  lsx_dsd_decode dsd_profile;
  lsx_dsd_level dsd_level;
  lsx_dsd_bandwidth dsd_bandwidth;
  lsx_dsd_clip dsd_clip;
} file_t;

static file_t * * files = NULL; /* Array tracking input and output files */
#define ofile files[file_count - 1]
static size_t file_count = 0;
static size_t input_count = 0;
static size_t output_count = 0;

/* Effects */

/* We parse effects into a temporary effects table and then place into
 * the real effects chain.  This allows scanning all effects to give
 * hints to what input effect options should be as well as determining
 * when mixer or resample effects need to be auto-inserted as well.
 */
static sox_effect_t **user_efftab = NULL;
static size_t user_efftab_size = 0;
static sox_effects_chain_t *effects_chain = NULL;
static sox_effect_t *save_output_eff = NULL;

static struct { char *name; int argc; char **argv; size_t argv_size; } **user_effargs = NULL;
static size_t *user_effargs_size = NULL;  /* array: size of user_effargs for each chain */
/* Size of memory structures related to effects arguments (user_effargs[i],
 * user_effargs[i][j].argv) to be extended in steps of EFFARGS_STEP */
#define EFFARGS_STEP 8
static size_t *nuser_effects = NULL;  /* array: number of effects in each chain */
static size_t current_eff_chain = 0;
static size_t eff_chain_count = 0;
static sox_bool very_first_effchain = sox_true;
  /* Indicates that not only the first effects chain is in effect (hrm), but
     also that it has never been restarted. Only then we may use the
     optimize_trim() hack. */
static char *effects_filename = NULL;
static char * play_rate_arg = NULL;
static char *norm_level = NULL;
static char *dsd_layout_assignment = NULL;
static sox_bool dsd_layout_loss_warn = sox_false;
static lsx_dsd_policy dsd_policy = {
  .mode=LSX_DSD_MODE_LEGACY,
  /* P15 release default: implicit reconstruction matches unpinned dsdpcm. */
  .decode=LSX_DSD_PROFILE_MASTERING_V2,
  .encode=LSX_DSD_ENCODE_MASTERING,
  .level=LSX_DSD_LEVEL_PRESERVE,
  .clip=LSX_DSD_CLIP_WARN,
  .bandwidth=LSX_DSD_BANDWIDTH_ADAPT
};
static sox_bool dsd_mode_explicit = sox_false, dsd_plan_only = sox_false;
static sox_bool dsd_new_policy_explicit = sox_false;
static char *dsd_report_path = NULL;
/* CLI-owned, opt-in evidence collection. A report is never an audio sink. */
static lsx_dsd_report_context *dsd_report_ctx;
static lsx_dsd_plan dsd_report_plan; /* NATIVE-mode plan, not active routing. */
static sox_bool dsd_report_active, dsd_report_published;
static uint64_t dsd_adapter_clips_total, dsd_output_clip_total;
static int dsd_report_publish(char const *status);
static void dsd_report_validate_destination(void);
static void dsd_report_preflight_destination(void);
static void dsd_report_check_open_output_alias(void);
static int dsd_observe_input(file_t *f,const sox_sample_t *samples,size_t n);

/* Planning is opt-in in P05.  The prior implicit effects graph is untouched. */
static sox_bool dsd_preflight_enabled(void)
{
  return dsd_plan_only || dsd_mode_explicit || dsd_new_policy_explicit ||
      dsd_report_path != NULL;
}

/* The only inserted routing is an explicitly planned mask-order permutation;
 * the matching layout is installed before the writer serializes its header. */
static unsigned *dsd_output_permutation = NULL;
static unsigned dsd_output_permutation_count = 0;
/* One authoritative resolved plan lives until the next effects-chain build.
 * The planner owns no effect instances and its names are static handlers. */
static lsx_dsd_plan dsd_runtime_plan;
static sox_bool dsd_runtime_active = sox_false;
static size_t *dsd_decode_before;
static size_t *dsd_encode_before; /* planned step index + 1, not a guessed encoder */
static sox_bool dsd_consume_leading;


/* Flowing */

static sox_signalinfo_t combiner_signal, ofile_signal_options;
static sox_encodinginfo_t combiner_encoding, ofile_encoding_options;
static uint64_t mixing_clips = 0;
static size_t current_input = 0;
static uint64_t input_wide_samples = 0;
static uint64_t read_wide_samples = 0;
static uint64_t output_samples = 0;
static sox_bool input_eof = sox_false;
static sox_bool output_eof = sox_false;
static sox_bool user_abort = sox_false;
static sox_bool user_skip = sox_false;
static sox_bool user_restart_eff = sox_false;
static int success = 0;
static int cleanup_called = 0;
static sox_sample_t omax[2], omin[2];

/* A failed finalization can no longer inspect ft after sox_close frees it.
 * Use the same regular-file-only policy as cleanup(), before closing. */
static void dsd_adapter_destroy(file_t *f);
static int close_output_checked(void)
{
  sox_format_t *ft = ofile->ft;
  struct stat st;
  char *regular_path = ft->io_type == lsx_io_file &&
      !lsx_stat(ft->filename, &st) && IS_REGULAR_FILE(st) ?
      lsx_strdup(ft->filename) : NULL;
  dsd_output_clip_total=ft->clips;
  int result = sox_close(ft);
  ofile->ft = NULL; /* sox_close frees the handle, even on failure. */
  if (result != SOX_SUCCESS) {
    lsx_fail("P07: output finalization failed");
    if (regular_path) lsx_unlink(regular_path);
  }
  free(regular_path);
  return result;
}

#ifdef HAVE_TERMIOS_H
#include <termios.h>
static struct termios original_termios;
static sox_bool original_termios_saved = sox_false;
#endif

static sox_bool stdin_is_a_tty, is_player, is_guarded, do_guarded_norm, no_dither, reported_sox_opts;

struct timeval load_timeofday;

static void cleanup(void)
{
  size_t i;

  if (!success && !reported_sox_opts) {
    char const * env_opts = getenv(SOX_OPTS);
    if (env_opts && *env_opts)
      lsx_report("used "SOX_OPTS"=%s", env_opts);
  }
  /* Effect stop has already captured graph conversion identities. Input
   * adapters are retired first, while native stream metadata is still live. */
  for (i=0;i<input_count;i++) dsd_adapter_destroy(files[i]);
  if (dsd_report_publish(user_abort?"cancelled":success?"complete":"failed")!=SOX_SUCCESS)
    lsx_fail("--dsd-report publication failed");
  lsx_dsd_report_disable();
  lsx_dsd_report_destroy(dsd_report_ctx);dsd_report_ctx=NULL;
  lsx_dsd_plan_free(&dsd_runtime_plan);
  lsx_dsd_plan_free(&dsd_report_plan);
  free(dsd_decode_before);
  dsd_decode_before=NULL;
  free(dsd_encode_before);
  dsd_encode_before=NULL;
  /* Close the input and output files before exiting. */
  for (i = 0; i < input_count; i++) {
    lsx_dsd_stats_destroy(files[i]->dsd_source_stats);
    files[i]->dsd_source_stats=NULL;
    if (files[i]->ft) {
      sox_close(files[i]->ft);
    }
    free(files[i]->filename);
    free(files[i]);
  }

  if (file_count) {
    if (ofile->ft) {
      if (!success && ofile->ft->io_type == lsx_io_file) {   /* If we failed part way through */
        struct stat st;                  /* writing a normal file, remove it. */
        if (!lsx_stat(ofile->ft->filename, &st) && IS_REGULAR_FILE(st)) {
          /* Don't assume we can unlink a file before closing it
           * 'cos that's not true on Windows. */
          /* sox_close frees the filename and ft, so take a copy */
          char *filename = lsx_strdup(ofile->ft->filename);
          sox_close(ofile->ft);
          lsx_unlink(filename);
          free(filename);
          goto already_closed;
        }
      }
      sox_close(ofile->ft);
    }
already_closed:
    free(ofile->filename);
    free(ofile);
  }

  free(files);

#ifdef HAVE_TERMIOS_H
  if (original_termios_saved)
    tcsetattr(fileno(stdin), TCSANOW, &original_termios);
#endif

  free(user_efftab);

  free(sox_globals.tmp_path);
  sox_globals.tmp_path = NULL;

  free(play_rate_arg);
  free(effects_filename);
  free(norm_level);

  sox_quit();

  cleanup_called = 1;
}

/* Cleanup atexit() function, hence always called. */
static void atexit_cleanup(void)
{
  /* Do not call cleanup using atexit() if possible.  pthread's can
   * act unpredictable if called outside of main().
   */
  if (!cleanup_called)
    cleanup();
}

static char const * str_time(double seconds)
{
  static char string[16][50];
  static int i;
  int hours, mins = seconds / 60;
  seconds -= mins * 60;
  hours = mins / 60;
  mins -= hours * 60;
  i = (i+1) & 15;
  sprintf(string[i], "%02i:%02i:%05.2f", hours, mins, seconds);
  return string[i];
}

static char const * size_and_bitrate(sox_format_t * ft, char const * * text)
{
  off_t size = lsx_filelength(ft);
  if (ft->signal.length && ft->signal.channels && ft->signal.rate && text) {
    double secs = ft->signal.length / ft->signal.channels / ft->signal.rate;
    *text = lsx_sigfigs3(8. * (size - ft->data_start) / secs);
  }
  return lsx_sigfigs3((double)size);
}

static void play_file_info(sox_format_t * ft, file_t * f, sox_bool full)
{
  FILE * const output = sox_mode == sox_soxi? stdout : stderr;
  char const * text, * text2 = NULL;
  char buffer[30];
  uint64_t ws = ft->signal.length / ft->signal.channels;
  (void)full;

  fprintf(output, "\n");
  if (ft->filename[0]) {
    fprintf(output, "%s:", ft->filename);
    if (strcmp(ft->filename, "-") == 0 || (ft->handler.flags & SOX_FILE_DEVICE))
      fprintf(output, " (%s)", ft->handler.names[0]);
    fprintf(output, "\n\n");
  }

  if ((text = size_and_bitrate(ft, &text2))) {
    fprintf(output, " File Size: %-10s", text);
    if (text2)
      fprintf(output, "Bit Rate: %s", text2);
    fprintf(output, "\n");
  }

  fprintf(output, "  Encoding: %-14s", sox_encodings_info[ft->encoding.encoding].name);
  text = sox_find_comment(f->ft->oob.comments, "Comment");
  if (!text)
    text = sox_find_comment(f->ft->oob.comments, "Description");
  if (!text)
    text = sox_find_comment(f->ft->oob.comments, "Year");
  if (text)
    fprintf(output, "Info: %s", text);
  fprintf(output, "\n");

  sprintf(buffer, "  Channels: %u @ %u-bit", ft->signal.channels, ft->signal.precision);
  fprintf(output, "%-25s", buffer);
  text = sox_find_comment(f->ft->oob.comments, "Tracknumber");
  if (text) {
    fprintf(output, "Track: %s", text);
    text = sox_find_comment(f->ft->oob.comments, "Tracktotal");
    if (text)
      fprintf(output, " of %s", text);
  }
  fprintf(output, "\n");

  sprintf(buffer, "Samplerate: %gHz", ft->signal.rate);
  fprintf(output, "%-25s", buffer);
  text = sox_find_comment(f->ft->oob.comments, "Album");
  if (text)
    fprintf(output, "Album: %s", text);
  fprintf(output, "\n");

  if (f && f->replay_gain != HUGE_VAL){
    sprintf(buffer, "%s gain: %+.1fdB", lsx_find_enum_value(f->replay_gain_mode, rg_modes)->text, f->replay_gain);
    buffer[0] += 'A' - 'a';
    fprintf(output, "%-24s", buffer);
  } else
    fprintf(output, "%-24s", "Replaygain: off");
  text = sox_find_comment(f->ft->oob.comments, "Artist");
  if (text)
    fprintf(output, "Artist: %s", text);
  fprintf(output, "\n");

  fprintf(output, "  Duration: %-13s", ft->signal.length? str_time((double)ws / ft->signal.rate) : "unknown");
  text = sox_find_comment(f->ft->oob.comments, "Title");
  if (text)
    fprintf(output, "Title: %s", text);
  fprintf(output, "\n\n");
}

static void display_file_info(sox_format_t * ft, file_t * f, sox_bool full)
{
  static char const * const no_yes[] = {"no", "yes"};
  FILE * const output = sox_mode == sox_soxi? stdout : stderr;
  char const * filetype = lsx_find_file_extension(ft->filename);
  sox_bool show_type = sox_true;
  size_t i;

  if (is_player && sox_globals.verbosity < 3) {
    play_file_info(ft, f, full);
    return;
  }

  fprintf(output, "\n%s: '%s'",
    ft->mode == 'r'? "Input File     " : "Output File    ", ft->filename);
  if (filetype) for (i = 0; ft->handler.names[i] && show_type; ++i)
    if (!strcasecmp(filetype, ft->handler.names[i]))
      show_type = sox_false;
  if (show_type)
    fprintf(output, " (%s)", ft->handler.names[0]);
  fprintf(output, "\n");

  fprintf(output,
    "Channels       : %u\n"
    "Sample Rate    : %g\n"
    "Precision      : %u-bit\n",
    ft->signal.channels,
    ft->signal.rate,
    ft->signal.precision);

  if (ft->signal.length && ft->signal.channels && ft->signal.rate) {
    uint64_t ws = ft->signal.length / ft->signal.channels;
    char const * text, * text2 = NULL;
    fprintf(output,
        "Duration       : %s = %" PRIu64 " samples %c %g CDDA sectors\n",
        str_time((double)ws / ft->signal.rate),
        ws, "~="[ft->signal.rate == 44100],
        (double)ws / ft->signal.rate * 44100 / 588);
    if (ft->mode == 'r' && (text = size_and_bitrate(ft, &text2))) {
      fprintf(output, "File Size      : %s\n", text);
      if (text2)
        fprintf(output, "Bit Rate       : %s\n", text2);
    }
  }

  if (ft->encoding.encoding) {
    char buffer[20] = {'\0'};
    if (ft->encoding.bits_per_sample)
      sprintf(buffer, "%u-bit ", ft->encoding.bits_per_sample);

    fprintf(output, "Sample Encoding: %s%s\n", buffer,
        sox_encodings_info[ft->encoding.encoding].desc);
  }

  if (full) {
    if (ft->encoding.bits_per_sample > 8 || (ft->handler.flags & SOX_FILE_ENDIAN))
      fprintf(output, "Endian Type    : %s\n",
          ft->encoding.reverse_bytes != MACHINE_IS_BIGENDIAN ? "big" : "little");
    if (ft->encoding.bits_per_sample)
      fprintf(output,
        "Reverse Nibbles: %s\n"
        "Reverse Bits   : %s\n",
        no_yes[ft->encoding.reverse_nibbles],
        no_yes[ft->encoding.reverse_bits]);
  }

  if (f && f->replay_gain != HUGE_VAL)
    fprintf(output, "Replay gain    : %+g dB (%s)\n" , f->replay_gain,
        lsx_find_enum_value(f->replay_gain_mode, rg_modes)->text);
  if (f && f->volume != HUGE_VAL)
    fprintf(output, "Level adjust   : %g (linear gain)\n" , f->volume);

  if (!(ft->handler.flags & SOX_FILE_DEVICE) && ft->oob.comments) {
    if (sox_num_comments(ft->oob.comments) > 1) {
      sox_comments_t p = ft->oob.comments;
      fprintf(output, "Comments       : \n");
      do fprintf(output, "%s\n", *p);
      while (*++p);
    }
    else fprintf(output, "Comment        : '%s'\n", ft->oob.comments[0]);
  }
  fprintf(output, "\n");
}

static void report_file_info(file_t * f)
{
  if (sox_globals.verbosity > 2)
    display_file_info(f->ft, f, sox_true);
}

/* A bounded native-frame queue prevents read-ahead from changing the finite
 * decoder's EOF contract.  One interleaved double-to-int32 quantization is
 * performed after the file-specific gain, never on native pulse values. */
#define DSD_ADAPTER_NATIVE_FRAMES 512
#define DSD_ADAPTER_PCM_FRAMES 256

static void dsd_adapter_destroy(file_t *f)
{
  dsd_input_adapter_t *a=f->dsd_adapter;
  if (!a) return;
  if (a->decoder)
    lsx_dsd_report_note_decode(a->decoder,f->dsd_profile,f->dsd_level,
        a->clips,a->peak);
  if (UINT64_MAX-dsd_adapter_clips_total>=a->clips)
    dsd_adapter_clips_total+=a->clips;
  if (a->clips)
    lsx_warn("P08: '%s' adapter clipped %" PRIu64
        " graph samples (max magnitude %.9g)",f->filename,a->clips,a->peak);
  sox_dsd_decoder_destroy(a->decoder);
  free(a->native);
  free(a->pcm);
  free(a);
  f->dsd_adapter=NULL;
}

static void dsd_adapter_start(file_t *f)
{
  dsd_input_adapter_t *a;
  sox_dsd_decode_options_t opt;
  sox_dsd_status_t rc;
  uint32_t native_hz;
  if (!f->dsd_target_hz) return;
  dsd_adapter_destroy(f);
  if (!lsx_dsd_integer_rate(f->ft->signal.rate,&native_hz)) {
    lsx_fail("P08: noninteger native rate in input adapter");exit(2);
  }
  a=lsx_calloc(1,sizeof(*a));
  a->channels=f->ft->signal.channels;
  /* Format readers use zero for an unknown length.  Only a declared,
   * positive native length can diagnose an unexpected physical EOF. */
  a->native_length_known=f->ft->signal.length!=SOX_UNSPEC &&
      f->ft->signal.length!=SOX_UNKNOWN_LEN;
  if (a->native_length_known) {
    a->native_expected=f->ft->signal.length/a->channels;
    if (a->native_expected*a->channels!=f->ft->signal.length) {
      lsx_fail("P08: incomplete channel frame count in '%s'",f->filename);
      free(a);exit(2);
    }
  }
  /* Explicitly opt-in. Keep the P14 native observation/report path on its
   * original expanded representation until its own packed oracle is added. */
  a->use_packed = getenv("SOX_DSD_PACKED_INPUT") &&
      !strcmp(getenv("SOX_DSD_PACKED_INPUT"),"1") &&
      sox_dsd_packed_supported(f->ft) && !dsd_report_active;
  sox_dsd_packed_block_init(&a->packed);
  if (a->use_packed)
    lsx_debug("P16: native packed input enabled for '%s'",f->filename);
  else
    a->native=lsx_malloc(DSD_ADAPTER_NATIVE_FRAMES*a->channels*sizeof(*a->native));
  a->pcm=lsx_malloc(DSD_ADAPTER_PCM_FRAMES*a->channels*sizeof(*a->pcm));
  sox_dsd_decode_options_init(&opt);
  opt.native_hz=native_hz;
  opt.output_hz=f->dsd_target_hz;
  opt.channels=a->channels;
  opt.profile=(sox_dsd_decode_profile_t)f->dsd_profile;
  opt.level=(sox_dsd_decode_level_t)f->dsd_level;
  opt.bandwidth=(sox_dsd_decode_bandwidth_t)f->dsd_bandwidth;
  rc=sox_dsd_decoder_create(&opt,&a->decoder);
  if (rc!=SOX_DSD_OK) {
    lsx_fail("P08: unable to create input decoder for '%s' (%d)",f->filename,(int)rc);
    free(a->native);free(a->pcm);free(a);exit(2);
  }
  f->dsd_adapter=a;
}

static size_t dsd_adapter_read(file_t *f,sox_sample_t *out,size_t frames)
{
  dsd_input_adapter_t *a=f->dsd_adapter;
  size_t total=0;
  SOX_SAMPLE_LOCALS;
  while (total<frames && !a->done && !a->failed) {
    size_t made=DSD_ADAPTER_PCM_FRAMES, used=0, j;
    sox_dsd_status_t rc;
    if (made>frames-total) made=frames-total;
    if (!a->eof && a->cursor==a->pending) {
      size_t samples=0;
      sox_dsd_status_t read_status=SOX_DSD_OK;
      if (a->use_packed) {
        read_status=sox_dsd_read_packed(f->ft,DSD_ADAPTER_NATIVE_FRAMES,&a->packed);
        if (read_status==SOX_DSD_OK)
          samples=a->packed.frames*a->channels;
        else if (read_status==SOX_DSD_DONE)
          samples=0;
        else {
          lsx_fail("P16: packed input read failed for '%s' (%d)",
              f->filename,(int)read_status);
          a->failed=sox_true;break;
        }
      } else
        samples=sox_read(f->ft,a->native,DSD_ADAPTER_NATIVE_FRAMES*a->channels);
      if (samples%a->channels || (!samples && f->ft->sox_errno)) {
        lsx_fail("P08: input read failed for '%s': %s",f->filename,
            f->ft->sox_errno?sox_strerror(f->ft->sox_errno):"incomplete channel frame");
        a->failed=sox_true;break;
      }
      if (!a->use_packed && !dsd_observe_input(f,a->native,samples)) {
        lsx_fail("P14: native source observation counter failed");
        a->failed=sox_true;break;
      }
      a->cursor=0;
      a->pending=samples/a->channels;
      if (a->native_length_known &&
          (a->native_seen>a->native_expected ||
           a->pending>a->native_expected-a->native_seen)) {
        lsx_fail("P08: native input exceeded its declared length in '%s'",f->filename);
        a->failed=sox_true;break;
      }
      a->native_seen+=a->pending;
      if (!samples) {
        if (a->native_length_known && a->native_seen!=a->native_expected) {
          lsx_fail("P08: premature native EOF in '%s' (read %" PRIu64
              " of %" PRIu64 " frames)",f->filename,a->native_seen,a->native_expected);
          a->failed=sox_true;break;
        }
        a->eof=sox_true;
      }
    }
    if (a->eof && a->cursor==a->pending) {
      rc=sox_dsd_decoder_finish(a->decoder,a->pcm,&made);
      if (rc!=SOX_DSD_NEED_OUTPUT && rc!=SOX_DSD_DONE) {
        lsx_fail("P08: input decoder finalization failed for '%s' (%d)",
            f->filename,(int)rc);
        a->failed=sox_true;break;
      }
      if (rc==SOX_DSD_DONE) a->done=sox_true;
    } else {
      used=a->pending-a->cursor;
      rc=a->use_packed ? sox_dsd_decoder_process_packed(a->decoder,
          &a->packed,a->cursor,&used,a->pcm,&made) :
          sox_dsd_decoder_process(a->decoder,
              a->native+a->cursor*a->channels,&used,a->pcm,&made);
      if ((rc!=SOX_DSD_NEED_INPUT && rc!=SOX_DSD_NEED_OUTPUT) ||
          (!made && !used)) {
        lsx_fail("P08: input decoder stalled for '%s' (%d)",f->filename,(int)rc);
        a->failed=sox_true;break;
      }
      a->cursor+=used;
    }
    for (j=0;j<made*a->channels;j++) {
      double sample=a->pcm[j]*f->volume;
      double magnitude=fabs(sample);
      if (!isfinite(sample)) {
        lsx_fail("P08: nonfinite sample in input adapter for '%s'",f->filename);
        a->failed=sox_true;break;
      }
      if (magnitude>a->peak) a->peak=magnitude;
      if (sample>=1. || sample< -1.) {
        ++a->clips;
        if (f->dsd_clip==LSX_DSD_CLIP_ERROR) {
          lsx_fail("P08: --dsd-clip error in input adapter '%s' (magnitude %.9g)",
              f->filename,magnitude);
          a->failed=sox_true;break;
        }
      }
      out[total*a->channels+j]=SOX_FLOAT_64BIT_TO_SAMPLE(sample,f->volume_clips);
    }
    if (a->failed) break;
    total+=made;
  }
  return total;
}

static void progress_to_next_input_file(file_t * f, sox_effect_t * effp)
{
  uint64_t native_frames;
  read_wide_samples = 0;
  native_frames = f->ft->signal.length / f->ft->signal.channels;
  input_wide_samples = native_frames;
  if (f->dsd_target_hz && f->ft->signal.length != SOX_UNKNOWN_LEN &&
      !lsx_dsd_count_convert(native_frames,(uint32_t)f->ft->signal.rate,
          f->dsd_target_hz,&input_wide_samples)) {
    lsx_fail("P08: effective input length overflow");exit(2);
  }
  if (show_progress && (sox_globals.verbosity < 3 ||
                        (is_serial(combine_method) && input_count > 1)))
    display_file_info(f->ft, f, sox_false);
  if (f->volume == HUGE_VAL)
    f->volume = 1;
  if (f->replay_gain != HUGE_VAL)
    f->volume *= pow(10.0, f->replay_gain / 20);
  if (effp && f->volume != floor(f->volume))
    effp->out_signal.precision = SOX_SAMPLE_PRECISION;
  f->ft->sox_errno = errno = 0;
  dsd_adapter_start(f);
}

/* Lengths and return values here are *effective* wide frames, while native
 * reader metadata and its sample counter retain the original clock. */
static size_t sox_read_wide(file_t *f, sox_sample_t *buf, size_t max)
{
  sox_format_t *ft=f->ft;
  size_t len=max/combiner_signal.channels;
  if (f->dsd_adapter) return dsd_adapter_read(f,buf,len);
  len=sox_read(ft,buf,len*ft->signal.channels)/ft->signal.channels;
  if (!dsd_observe_input(f,buf,len*ft->signal.channels)) {
    lsx_fail("P14: native source observation counter failed");
    ft->sox_errno=SOX_EOF;
    return 0;
  }
  if (!len && ft->sox_errno)
    lsx_fail("`%s' %s: %s",ft->filename,ft->sox_errstr,sox_strerror(ft->sox_errno));
  return len;
}

static void balance_input(sox_sample_t *buf,size_t ws,file_t *f)
{
  size_t s=ws*f->ft->signal.channels;
  if (f->dsd_adapter) return; /* binary64 decoder already consumed file gain */
  if (f->volume!=1) while (s--) {
    double d=f->volume**buf;
    *buf++=SOX_ROUND_CLIP_COUNT(d,f->volume_clips);
  }
}

/* The input combiner: contains one sample buffer per input file, but only
 * needed if is_parallel(combine_method) */
typedef struct {
  sox_sample_t * * ibuf;
  size_t *         ilen;
} input_combiner_t;

static int combiner_start(sox_effect_t *effp)
{
  input_combiner_t * z = (input_combiner_t *) effp->priv;
  uint64_t ws;
  size_t i;

  if (is_serial(combine_method))
    progress_to_next_input_file(files[current_input], effp);
  else {
    ws = 0;
    lsx_valloc(z->ibuf, input_count);
    for (i = 0; i < input_count; i++) {
      lsx_valloc(z->ibuf[i], sox_globals.bufsiz);
      progress_to_next_input_file(files[i], effp);
      ws = max(ws, input_wide_samples);
    }
    input_wide_samples = ws; /* Output length is that of longest input file. */
  }
  lsx_valloc(z->ilen, input_count);
  return SOX_SUCCESS;
}

static sox_bool can_segue(size_t i)
{
  /* A sequence reconstructs each native input with a fresh finite-file
   * filter.  Graph decoding needs the same restart even when the adjacent
   * native signals happen to have equal rates and channel counts. */
  return
    !(dsd_runtime_active && dsd_runtime_plan.graph_decode_count) &&
    !files[i]->dsd_target_hz && !files[i-1]->dsd_target_hz &&
    files[i]->ft->signal.channels == files[i - 1]->ft->signal.channels &&
    files[i]->ft->signal.rate     == files[i - 1]->ft->signal.rate;
}

static int combiner_drain(sox_effect_t *effp, sox_sample_t * obuf, size_t * osamp)
{
  input_combiner_t * z = (input_combiner_t *) effp->priv;
  size_t ws, s, i;
  size_t olen = 0;

  if (is_serial(combine_method)) {
    while (sox_true) {
      if (!user_skip)
        olen = sox_read_wide(files[current_input], obuf, *osamp);
      if (files[current_input]->dsd_adapter &&
          files[current_input]->dsd_adapter->failed) return LSX_EFF_FATAL;
      if (olen == 0) {   /* If EOF, go to the next input file. */
        if (++current_input < input_count) {
          if (combine_method == sox_sequence && !can_segue(current_input))
            break;
          progress_to_next_input_file(files[current_input], NULL);
          continue;
        }
      }
      if (files[current_input]->dsd_adapter &&
          files[current_input]->dsd_adapter->failed) return LSX_EFF_FATAL;
      balance_input(obuf, olen, files[current_input]);
      break;
    } /* while */
  } /* is_serial */ else { /* else is_parallel() */
    sox_sample_t * p = obuf;
    for (i = 0; i < input_count; ++i) {
      z->ilen[i] = sox_read_wide(files[i], z->ibuf[i], *osamp);
      if (files[i]->dsd_adapter && files[i]->dsd_adapter->failed)
        return LSX_EFF_FATAL;
      balance_input(z->ibuf[i], z->ilen[i], files[i]);
      olen = max(olen, z->ilen[i]);
    }
    for (ws = 0; ws < olen; ++ws) { /* wide samples */
      if (combine_method == sox_mix || combine_method == sox_mix_power) {
        for (s = 0; s < effp->in_signal.channels; ++s, ++p) { /* sum samples */
          *p = 0;
          for (i = 0; i < input_count; ++i)
            if (ws < z->ilen[i] && s < files[i]->ft->signal.channels) {
              /* Cast to double prevents integer overflow */
              double sample = *p + (double)z->ibuf[i][ws * files[i]->ft->signal.channels + s];
              *p = SOX_ROUND_CLIP_COUNT(sample, mixing_clips);
            }
        }
      } /* sox_mix */ else if (combine_method == sox_multiply)  {
        for (s = 0; s < effp->in_signal.channels; ++s, ++p) { /* multiply samples */
          i = 0;
          *p = ws < z->ilen[i] && s < files[i]->ft->signal.channels?
            z->ibuf[i][ws * files[i]->ft->signal.channels + s] : 0;
          for (++i; i < input_count; ++i) {
            double sample = *p * (-1. / SOX_SAMPLE_MIN) * (ws < z->ilen[i] && s < files[i]->ft->signal.channels? z->ibuf[i][ws * files[i]->ft->signal.channels + s] : 0);
            *p = SOX_ROUND_CLIP_COUNT(sample, mixing_clips);
          }
        }
      } /* sox_multiply */ else { /* sox_merge: like a multi-track recorder */
        for (i = 0; i < input_count; ++i)
          for (s = 0; s < files[i]->ft->signal.channels; ++s)
            *p++ = (ws < z->ilen[i]) * z->ibuf[i][ws * files[i]->ft->signal.channels + s];
      } /* sox_merge */
    } /* wide samples */
  } /* is_parallel */
  read_wide_samples += olen;
  olen *= effp->in_signal.channels;
  *osamp = olen;

  input_eof = olen ? sox_false : sox_true;

  if (input_eof && is_parallel(combine_method))
    current_input += input_count;

  return olen? SOX_SUCCESS : SOX_EOF;
}

static int combiner_stop(sox_effect_t *effp)
{
  input_combiner_t * z = (input_combiner_t *) effp->priv;
  size_t i;

  if (is_parallel(combine_method)) {
    /* Free input buffers now that they are not used */
    for (i = 0; i < input_count; i++)
      free(z->ibuf[i]);
    free(z->ibuf);
  }
  free(z->ilen);
  for (i=0;i<input_count;i++) dsd_adapter_destroy(files[i]);

  return SOX_SUCCESS;
}

static sox_effect_handler_t const * input_combiner_effect_fn(void)
{
  static sox_effect_handler_t handler = {
    "input", NULL, SOX_EFF_MCHAN |
    SOX_EFF_MODIFY, 0, combiner_start, 0, combiner_drain,
    combiner_stop, 0,
    sizeof(input_combiner_t),
    NULL, NULL, NULL,
  };
  return &handler;
}

static int ostart(sox_effect_t *effp)
{
  unsigned prec = effp->out_signal.precision;
  if (effp->in_signal.mult && effp->in_signal.precision > prec)
    *effp->in_signal.mult *= 1 - (1 << (31 - prec)) * (1. / SOX_SAMPLE_MAX);
  return SOX_SUCCESS;
}

static int output_flow(sox_effect_t UNUSED *effp, sox_sample_t const * ibuf,
    sox_sample_t UNUSED * obuf, size_t * isamp, size_t * osamp)
{
  size_t len;

  if (show_progress) for (len = 0; len < *isamp; len += effp->in_signal.channels) {
    omax[0] = max(omax[0], ibuf[len]);
    omin[0] = min(omin[0], ibuf[len]);
    if (effp->in_signal.channels > 1) {
      omax[1] = max(omax[1], ibuf[len + 1]);
      omin[1] = min(omin[1], ibuf[len + 1]);
    }
    else {
      omax[1] = omax[0];
      omin[1] = omin[0];
    }
  }
  *osamp = 0;
  len = *isamp? sox_write(ofile->ft, ibuf, *isamp) : 0;
  output_samples += len / ofile->ft->signal.channels;
  output_eof = (len != *isamp) ? sox_true: sox_false;
  if (len != *isamp) {
    /* A short write proves failure even if the format cleared sox_errno.
     * Ordinary EOF, trim and intentional effect termination still use EOF. */
    if (ofile->ft->sox_errno)
      lsx_fail("`%s' output write failed (%zu of %zu samples): %s: %s",
          ofile->ft->filename, len, *isamp, ofile->ft->sox_errstr,
          sox_strerror(ofile->ft->sox_errno));
    else
      lsx_fail("`%s' output write failed (%zu of %zu samples)",
          ofile->ft->filename, len, *isamp);
    return LSX_EFF_FATAL;
  }
  return SOX_SUCCESS;
}

static sox_effect_handler_t const * output_effect_fn(void)
{
  static sox_effect_handler_t handler = {"output", NULL,
    SOX_EFF_MCHAN | SOX_EFF_MODIFY | SOX_EFF_PREC,
    NULL, ostart, output_flow, NULL, NULL, NULL,
    0,
    NULL, NULL, NULL,
  };
  return &handler;
}

static void auto_effect(sox_effects_chain_t *, char const *, int, char **,
    sox_signalinfo_t *, int *);

static int add_effect(sox_effects_chain_t * chain, sox_effect_t * effp,
    sox_signalinfo_t * in, sox_signalinfo_t const * out, int * guard) {
  int no_guard = -1;
  switch (*guard) {
    case 0: if (!(effp->handler.flags & SOX_EFF_GAIN)) {
      char * arg = "-h";
      auto_effect(chain, "gain", 1, &arg, in, &no_guard);
      ++*guard;
    }
    break;
    case 1: if (effp->handler.flags & SOX_EFF_GAIN) {
      char * arg = "-r";
      auto_effect(chain, "gain", 1, &arg, in, &no_guard);
      --*guard;
    }
    break;
    case 2: if (!(effp->handler.flags & SOX_EFF_MODIFY)) {
      lsx_warn("%s: effects that modify audio should not follow dither",
        effp->handler.name);
    }
    break;
  }
  return sox_add_effect(chain, effp, in, out);
}

static void auto_effect(sox_effects_chain_t *chain, char const *name, int argc,
    char *argv[], sox_signalinfo_t *signal, int * guard)
{
  sox_effect_t * effp;

  effp = sox_create_effect(sox_find_effect(name)); /* Should always succeed. */

  if (sox_effect_options(effp, argc, argv) == SOX_EOF)
    exit(1); /* The failing effect should have displayed an error message */

  if (add_effect(chain, effp, signal, &ofile->ft->signal, guard) != SOX_SUCCESS)
    exit(2); /* The effects chain should have displayed an error message */
  free(effp);
}

/* add_eff_chain() - NOTE: this only adds memory for one
 * additional effects chain beyond value of eff_chain_count.  It
 * does not unconditionally increase size of effects chain.
 */
static void add_eff_chain(void)
{
  lsx_revalloc(user_effargs, eff_chain_count+1);
  user_effargs[eff_chain_count] = lsx_malloc(sizeof(**user_effargs));

  lsx_revalloc(user_effargs_size, eff_chain_count+1);
  user_effargs_size[eff_chain_count] = 0;
  lsx_revalloc(nuser_effects, eff_chain_count+1);
  nuser_effects[eff_chain_count] = 0;
} /* add_eff_chain */

/* free_eff_chain() - the inverse of add_eff_chain().  Frees
 * one effects chain (with index eff_chain_count) such that
 * there are eff_chain_count left, the last having index
 * eff_chain_count-1.
 */
static void free_eff_chain(void)
{
  size_t j;
  int k;
  for (j = 0; j < nuser_effects[eff_chain_count]; j++)
  {
    free(user_effargs[eff_chain_count][j].name);
    user_effargs[eff_chain_count][j].name = NULL;
    for (k = 0; k < user_effargs[eff_chain_count][j].argc; k++)
    {
      free(user_effargs[eff_chain_count][j].argv[k]);
      user_effargs[eff_chain_count][j].argv[k] = NULL;
    }
    user_effargs[eff_chain_count][j].argc = 0;
    free(user_effargs[eff_chain_count][j].argv);
    user_effargs[eff_chain_count][j].argv = NULL;
    user_effargs[eff_chain_count][j].argv_size = 0;
  }
  nuser_effects[eff_chain_count] = 0;
  free(user_effargs[eff_chain_count]);
} /* free_eff_chain */

static void delete_eff_chains(void)
{
  while (eff_chain_count > 0) {
    eff_chain_count--;
    free_eff_chain();
  }
  free(user_effargs);
  free(user_effargs_size);
  free(nuser_effects);
  user_effargs = NULL;
  user_effargs_size = NULL;
  nuser_effects = NULL;
} /* delete_eff_chains */

static sox_bool is_pseudo_effect(const char *s)
{
  if (s)
  if (strcmp("newfile", s) == 0 ||
      strcmp("restart", s) == 0 ||
      strcmp(":", s) == 0)
    return sox_true;
  return sox_false;
} /* is_pseudo_effect */

static void parse_effects(int argc, char ** argv)
{
  while (optstate.ind < argc) {
    size_t eff_offset, j;
    int newline_mode = 0;

    eff_offset = nuser_effects[eff_chain_count];
    if (eff_offset == user_effargs_size[eff_chain_count]) {
      size_t i = user_effargs_size[eff_chain_count];
      user_effargs_size[eff_chain_count] += EFFARGS_STEP;
      lsx_revalloc(user_effargs[eff_chain_count], user_effargs_size[eff_chain_count]);
      for (; i < user_effargs_size[eff_chain_count]; i++) {
        user_effargs[eff_chain_count][i].argv = NULL;
        user_effargs[eff_chain_count][i].argv_size = 0;
      }
    }

    /* pseudo-effect ":" is used to create a new effects chain */
    if (strcmp(argv[optstate.ind], ":") == 0)
    {
      /* Only create a new chain if current one has effects.
       * Error checking will be done when loop is restarted.
       */
      if (nuser_effects[eff_chain_count] != 0)
      {
        eff_chain_count++;
        add_eff_chain();
      }
      optstate.ind++;
      continue;
    }

    if (strcmp(argv[optstate.ind], "newfile") == 0)
    {
      /* Start a new effect chain for newfile if user doesn't
       * manually do it.  Restart loop without advancing
       * optstate.ind to do error checking.
       */
      if (nuser_effects[eff_chain_count] != 0)
      {
        eff_chain_count++;
        add_eff_chain();
        continue;
      }
      newline_mode = 1;
      output_method = sox_multiple;
    }
    else if (strcmp(argv[optstate.ind], "restart") == 0)
    {
      /* Start a new effect chain for restart if user doesn't
       * manually do it.  Restart loop without advancing
       * optstate.ind to do error checking.
       */
      if (nuser_effects[eff_chain_count] != 0)
      {
        eff_chain_count++;
        add_eff_chain();
        continue;
      }
      newline_mode = 1;
    }

    /* Name should always be correct! */
    user_effargs[eff_chain_count][eff_offset].name = lsx_strdup(argv[optstate.ind]);
    optstate.ind++;
    for (j = 0; j < (size_t)(argc - optstate.ind) && !sox_find_effect(argv[optstate.ind + j]) &&
         !is_pseudo_effect(argv[optstate.ind + j]); ++j) {
      if (j >= user_effargs[eff_chain_count][eff_offset].argv_size) {
        user_effargs[eff_chain_count][eff_offset].argv_size += EFFARGS_STEP;
        lsx_revalloc(user_effargs[eff_chain_count][eff_offset].argv,
            user_effargs[eff_chain_count][eff_offset].argv_size);
      }
      user_effargs[eff_chain_count][eff_offset].argv[j] = lsx_strdup(argv[optstate.ind + j]);
    }
    user_effargs[eff_chain_count][eff_offset].argc = j;

    optstate.ind += j; /* Skip past the effect arguments */
    nuser_effects[eff_chain_count]++;
    if (newline_mode)
    {
      eff_chain_count++;
      add_eff_chain();
    }
  }
} /* parse_effects */

static char * * strtoargv(char * s, int * argc)
{
  sox_bool squote = sox_false;   /* Single quote mode (') is in effect. */
  sox_bool dquote = sox_false;   /* Double quote mode (") is in effect. */
  sox_bool esc    = sox_false;   /* Escape mode (\) is in effect. */
  char * t, * * argv = NULL;

  for (*argc = 0; *s;) {
    for (; isspace((int)*s); ++s);    /* Skip past any (more) white space. */
    if (*s) {                    /* Found an arg. */
      lsx_revalloc(argv, *argc + 1);
      argv[(*argc)++] = s;       /* Store pointer to start of arg. */
                                 /* Find the end of the arg: */
      for (t = s; *s && (esc || squote || dquote || !isspace((int)*s)); ++s)
        if (!esc && !squote && *s == '"')
          dquote = !dquote;      /* Toggle double quote mode. */
        else if (!esc && !dquote && *s == '\'')
          squote = !squote;      /* Toggle single quote mode. */
        else if (!(esc = !esc && *s == '\\' && s[1] &&
              (!squote && (s[1] == '"' || !dquote))))
          *t++ = *s;             /* Only copy if not an active ', ", or \ */
      s = *s ? s + 1 : s;        /* Skip the 1st white space char. */
      *t = '\0';                 /* Terminate the arg. */
    }
  }
  return argv;
}                                /* strtoargv */

static void read_user_effects(char const *filename)
{
    FILE *file = lsx_fopen(filename, "r");
    const size_t buffer_size_step = 1024;
    size_t buffer_size = buffer_size_step;
    char *s = lsx_malloc(buffer_size); /* buffer for one input line */
    int pos = 0;
    int argc;
    char * * argv;
    sox_bool last_was_colon = sox_false; /* last line read consisted of ":" only */

    /* Free any command line options and then re-initialize to
     * starter user_effargs.
     */
    delete_eff_chains();
    current_eff_chain = 0;
    add_eff_chain();

    if (!file) {
        lsx_fail("cannot open effects file `%s': %s", filename, strerror(errno));
        exit(1);
    }

    lsx_report("reading effects from file `%s'", filename);

    while(fgets(s + pos, (int) (buffer_size - pos), file)) {
      int len = strlen(s + pos);
      if (len && s[pos+len-1] == '\n')
        s[pos+len-1] = '\0', pos = 0; /* we've read a complete line */
      else if (len == (int)(buffer_size - pos - 1)) {
        /* line was longer than buffer size */
        buffer_size += buffer_size_step;
        s = lsx_realloc(s, buffer_size);
        pos += len;
        continue; /* read next part */
      } else {
        /* something strange happened; the file might have ended
           without a '\n', might contain '\0', or a read error
           occurred */
        if (ferror(file))
          break; /* use error reporting after loop */
        lsx_fail("error reading effects file `%s' (not a text file?)", filename);
        exit(1);
      }

      last_was_colon = sox_false;

      argv = strtoargv(s, &argc);

      if (argv && argc == 1 && strcmp(argv[0], ":") == 0)
        last_was_colon = sox_true;

      if (argv) {
        /* Make sure first option is an effect name. */
        if (!sox_find_effect(argv[0]) && !is_pseudo_effect(argv[0]))
        {
          lsx_fail("cannot find an effect called `%s'.", argv[0]);
          exit(1);
        }

        /* parse_effects normally parses options from command line.
         * Reset opt index so it thinks its back at beginning of
         * main()'s argv[].
         */
        optstate.ind = 0;
        parse_effects(argc, argv);

        /* Advance to next effect but only if current chain has been
         * filled in.  This recovers from side affects of pseudo-effects.
         */
        if (nuser_effects[eff_chain_count] > 0) {
          eff_chain_count++;
          add_eff_chain();
        }

        free(argv);
      }
    }
    if (ferror(file)) {
      lsx_fail("error reading effects file `%s': %s", filename, strerror(errno));
      exit(1);
    }
    fclose(file);
    free(s);

    if (last_was_colon || eff_chain_count == 0) {
      /* user explicitly wanted an empty last effects chain,
         or didn't specify any chains at all */
      eff_chain_count++;
    } else {
      /* there's one unneeded effects chain */
      free_eff_chain();
    }
} /* read_user_effects */

/* Creates users effects and passes in user specified options.
 * This is done without putting anything into the effects chain
 * because an effect may set the effp->in_format and we may want
 * to copy that back into the input/combiner before opening and
 * inserting it.
 * Similarly, we may want to use effp->out_format to override the
 * default values of output file before we open it.
 * To keep things simple, we create all user effects.  Later, when
 * we add them, some may already be in the chain and we will need to free
 * them.
 */
static void create_user_effects(void)
{
  size_t i;
  sox_effect_t *effp;
  size_t num_effects = nuser_effects[current_eff_chain];

  /* extend user_efftab, if needed */
  if (user_efftab_size < num_effects) {
    user_efftab_size = num_effects;
    lsx_revalloc(user_efftab, num_effects);
  }

  for (i = 0; i < num_effects; i++) {
    sox_effect_handler_t const *handler =
        sox_find_effect(user_effargs[current_eff_chain][i].name);
    if (!handler) {
      lsx_fail("can't find an effect called `%s'",
               user_effargs[current_eff_chain][i].name);
      exit(1);
    }
    effp = sox_create_effect(handler);

    if (effp->handler.flags & SOX_EFF_INTERNAL) {
      lsx_fail("`%s' is a libSoX-only effect", effp->handler.name);
      exit(1);
    }

    /* The failing effect should have displayed an error message */
    if (sox_effect_options(effp, user_effargs[current_eff_chain][i].argc,
          user_effargs[current_eff_chain][i].argv) == SOX_EOF)
      exit(1);

    user_efftab[i] = effp;
  }
}

/* Add all user effects to the chain.  If the output effect's rate or
 * channel count do not match the end of the effects chain then
 * insert effects to correct this.
 *
 * This can be called with the input effect already in the effects
 * chain from a previous run.  Also, it use a pre-existing
 * output effect if its been saved into save_output_eff.
 */
/* Build each implicit graph boundary from the resolved step's rate and
 * global decoder policy.  This is only used for actual implicit_dsdpcm nodes. */
static void dsd_insert_boundary(sox_effects_chain_t *chain,
    sox_signalinfo_t *signal,int *guard,size_t index)
{
  size_t n, count;
  if (!dsd_runtime_active || !dsd_decode_before) return;
  /* An effect split by the automatic dither/rate section is visited twice.
   * Consume each boundary exactly once, before the earliest such operation. */
  count=dsd_decode_before[index];
  dsd_decode_before[index]=0;
  for (n=0;n<count;n++) {
    sox_effect_t *e=sox_create_effect(sox_find_effect("dsdpcm"));
    char rate[32];
    char *argv[5];
    double destination=0;
    size_t k;
    for (k=0;k<dsd_runtime_plan.step_count;k++)
      if (!strcmp(dsd_runtime_plan.steps[k].name,"implicit_dsdpcm") &&
          dsd_runtime_plan.steps[k].rate_before==signal->rate) {
        destination=dsd_runtime_plan.steps[k].rate_after;
        break;
      }
    if (!destination) {
      lsx_fail("P08: missing planned implicit reconstruction at %.0f Hz",signal->rate);
      exit(2);
    }
    snprintf(rate,sizeof(rate),"%.0f",destination);
    argv[0]="-p";
    if (dsd_policy.decode==LSX_DSD_PROFILE_MASTERING_V2) {
      uint32_t native;
      const lsx_dsd_frontend_profile *profile;
      if (!lsx_dsd_integer_rate(signal->rate,&native) ||
          !(profile=lsx_dsd_frontend_profile_find(native,dsd_policy.decode))) {
        lsx_fail("P15-R3: missing v2 candidate for implicit decoder clock");exit(2);
      }
      argv[1]=(char *)profile->canonical_id;
    } else argv[1]=dsd_policy.decode==LSX_DSD_PROFILE_WIDEBAND?"wideband":"mastering";
    argv[2]="-l";
    argv[3]=dsd_policy.level==LSX_DSD_LEVEL_SACD?"sacd":"preserve";
    argv[4]=rate;
    if (sox_effect_options(e,5,argv)!=SOX_SUCCESS) exit(2);
    lsx_dsd_effect_apply_policy(e,&dsd_policy);
    if (add_effect(chain,e,signal,&ofile->ft->signal,guard)!=SOX_SUCCESS) exit(2);
    free(e);
  }
  /* Guard headroom belongs to PCM, not to the native input of dsdpcm.
   * Restore the ordinary -G insertion policy only after reconstruction. */
  if (count && is_guarded && *guard < 0 &&
      dsd_runtime_plan.combiner_domain==LSX_DSD_NATIVE)
    *guard=0;
}

/* Finalize PCM gain before a composite boundary, never after its pulses.
 * The plan still decides whether normalization belongs before this boundary. */
static int dsd_normalize_before_step(size_t step)
{
  size_t j;
  for (j=0;j<step;j++)
    if (!strcmp(dsd_runtime_plan.steps[j].name,"auto_normalize")) return 1;
  return 0;
}
static void dsd_finalize_encode_gain(sox_effects_chain_t *chain,
    sox_signalinfo_t *signal,int *guard,int normalize,int *normalized)
{
  if (is_guarded && *guard>=0 &&
      ((do_guarded_norm && normalize && !*normalized) ||
       !(signal->mult && *signal->mult==1))) {
    char *args[2];int no_guard=-1;
    args[0]=do_guarded_norm && normalize && !*normalized?"-nh":*guard?"-rh":"-h";
    args[1]=norm_level;
    auto_effect(chain,"gain",norm_level?2:1,args,signal,&no_guard);
    if (do_guarded_norm && normalize) *normalized=1;
  }
}
static void dsd_insert_encoder(sox_effects_chain_t *chain,
    sox_signalinfo_t *signal,int *guard,size_t index,int *normalized)
{
  size_t step;
  lsx_dsd_plan_step const *plan;
  sox_effect_t *e;
  char rate[32],*args[1];
  int no_guard=-1;
  if (!dsd_runtime_active || !dsd_encode_before || !dsd_encode_before[index]) return;
  step=dsd_encode_before[index]-1;
  plan=&dsd_runtime_plan.steps[step];
  if (signal->rate!=plan->rate_before || signal->channels!=plan->channels_before) {
    lsx_fail("P10: composite encoder input disagrees with its resolved plan");exit(2);
  }
  dsd_finalize_encode_gain(chain,signal,guard,dsd_normalize_before_step(step),normalized);
  e=sox_create_effect(sox_find_effect("pcmdsd"));
  snprintf(rate,sizeof(rate),"%.0f",plan->rate_after);args[0]=rate;
  if (sox_effect_options(e,1,args)!=SOX_SUCCESS) exit(2);
  lsx_pcmdsd_set_reference(e,plan->reference);
  if (add_effect(chain,e,signal,&ofile->ft->signal,&no_guard)!=SOX_SUCCESS) exit(2);
  free(e);dsd_encode_before[index]=0;*guard=-1;
}
static int dsd_composite_pending(size_t index)
{
  size_t i;
  if (!dsd_runtime_active) return 0;
  for (i=index;i<=nuser_effects[current_eff_chain];i++) {
    if (dsd_encode_before && dsd_encode_before[i]) return 1;
    if (i<nuser_effects[current_eff_chain] &&
        !strcmp(user_efftab[i]->handler.name,"pcmdsd")) return 1;
  }
  return 0;
}
static void dsd_prepare_explicit_encoder(sox_effects_chain_t *chain,
    sox_signalinfo_t *signal,int *guard,size_t index,int *normalized)
{
  size_t i,k=0;
  if (!dsd_runtime_active || strcmp(user_efftab[index]->handler.name,"pcmdsd")) return;
  for (i=0;i<dsd_runtime_plan.step_count;i++) {
    const lsx_dsd_plan_step *p=&dsd_runtime_plan.steps[i];
    if (!p->implicit && p->input_index<0) {
      if (k++==index) {
        dsd_finalize_encode_gain(chain,signal,guard,dsd_normalize_before_step(i),normalized);
        break;
      }
    }
  }
  *guard=-1;
}

static void add_effects(sox_effects_chain_t *chain)
{
  sox_signalinfo_t signal = combiner_signal;
  int guard = is_guarded - 1;
  int p10_normalized=0;
  size_t i;
  sox_effect_t * effp;
  char * rate_arg = is_player ? (play_rate_arg ? play_rate_arg : "-l") : NULL;

  /* The resolved combiner is still native DSD.  Do not insert a generic
   * guarded gain until a planned decoder has switched it to PCM.  Pure
   * native repacking and terminal DoP never reach that point. */
  if (dsd_runtime_active &&
      dsd_runtime_plan.combiner_domain==LSX_DSD_NATIVE)
    guard=-1;

  /* 1st `effect' in the chain is the input combiner_signal.
   * add it only if its not there from a previous run.  */
  if (chain->length == 0) {
    effp = sox_create_effect(input_combiner_effect_fn());
    sox_add_effect(chain, effp, &signal, &ofile->ft->signal);
    free(effp);
  }

  /* Add user specified effects; stop before `dither' */
  for (i = 0; i < nuser_effects[current_eff_chain] &&
      strcmp(user_efftab[i]->handler.name, "dither"); i++) {
    dsd_insert_boundary(chain,&signal,&guard,i);
    dsd_insert_encoder(chain,&signal,&guard,i,&p10_normalized);
    dsd_prepare_explicit_encoder(chain,&signal,&guard,i,&p10_normalized);
    if (i==0 && dsd_consume_leading) {
      free(user_efftab[i]);
      continue;
    }
    if (add_effect(chain, user_efftab[i], &signal, &ofile->ft->signal,
          &guard) != SOX_SUCCESS)
      exit(2); /* Effects chain should have displayed an error message */
    /* An explicitly requested dsdpcm is also a domain boundary.  It must
     * execute before automatic gain, just like an implicit decoder. */
    if (dsd_runtime_active && is_guarded && guard < 0 &&
        !strcmp(user_efftab[i]->handler.name,"dsdpcm"))
      guard=0;
    free(user_efftab[i]);
  }

  /* A pending decoder precedes every automatic operation, even when the
   * first explicit effect is dither (which splits the two user loops). */
  dsd_insert_boundary(chain,&signal,&guard,i);

  /* Add auto effects if still needed at this point */
  if (!dsd_composite_pending(i) &&
      signal.channels < ofile->ft->signal.channels &&
      signal.rate != ofile->ft->signal.rate)
    auto_effect(chain, "rate", rate_arg != NULL, &rate_arg, &signal, &guard);
  if (signal.channels != ofile->ft->signal.channels)
    auto_effect(chain, "channels", 0, NULL, &signal, &guard);
  if (!dsd_composite_pending(i) && signal.rate != ofile->ft->signal.rate)
    auto_effect(chain, "rate", rate_arg != NULL, &rate_arg, &signal, &guard);

  if (is_guarded && guard >= 0 &&
      ((do_guarded_norm && !p10_normalized) || !(signal.mult && *signal.mult == 1))) {
    char *args[2];
    int no_guard = -1;
    args[0] = do_guarded_norm? "-nh" : guard? "-rh" : "-h";
    args[1] = norm_level;
    auto_effect(chain, "gain", norm_level ? 2 : 1, args, &signal, &no_guard);
    guard = 1;
    if (do_guarded_norm) p10_normalized=1;
  }
  if (i==nuser_effects[current_eff_chain])
    dsd_insert_encoder(chain,&signal,&guard,i,&p10_normalized);

  /* A null sink has no output precision.  Its fabricated one-bit default
   * cannot request low-level sigma-delta modulation of decoded PCM. */
  if (i == nuser_effects[current_eff_chain] && !no_dither &&
      !dsd_composite_pending(i) &&
      !(dsd_runtime_active &&
        !strcmp(ofile->ft->handler.names[0],"null")) &&
      signal.precision > ofile->ft->signal.precision &&
      ofile->ft->signal.precision < 24)
    auto_effect(chain, "dither", 0, NULL, &signal, &guard);

  /* Add user specified effects from `dither' onwards */
  for (; i < nuser_effects[current_eff_chain]; i++, guard = 2) {
    dsd_insert_boundary(chain,&signal,&guard,i);
    dsd_insert_encoder(chain,&signal,&guard,i,&p10_normalized);
    dsd_prepare_explicit_encoder(chain,&signal,&guard,i,&p10_normalized);
    if (add_effect(chain, user_efftab[i], &signal, &ofile->ft->signal,
          &guard) != SOX_SUCCESS)
      exit(2); /* Effects chain should have displayed an error message */
    free(user_efftab[i]);
  }

  dsd_insert_encoder(chain,&signal,&guard,nuser_effects[current_eff_chain],&p10_normalized);

  /* An output WAV mask describes the wire-order samples, not just labels.
   * Insert the matching pure remix before the output effect.  All role
   * work happened before the output header was opened. */
  if (dsd_output_permutation_count) {
    unsigned j, count=dsd_output_permutation_count;
    char **args=lsx_calloc(count+1,sizeof(*args));
    args[0]="-m";
    for (j=0;j<count;++j) {
      args[j+1]=lsx_malloc(24);
      snprintf(args[j+1],24,"%u",dsd_output_permutation[j]+1);
    }
    auto_effect(chain,"remix",(int)count+1,args,&signal,&guard);
    for (j=0;j<count;++j)free(args[j+1]);
    free(args);
    free(dsd_output_permutation);
    dsd_output_permutation=NULL;
    dsd_output_permutation_count=0;
  }

  if (!save_output_eff)
  {
    /* Last `effect' in the chain is the output file */
    effp = sox_create_effect(output_effect_fn());
    if (sox_add_effect(chain, effp, &signal, &ofile->ft->signal) != SOX_SUCCESS)
      exit(2);
    free(effp);
  }
  else
  {
    sox_push_effect_last(chain, save_output_eff);
    save_output_eff = NULL;
  }

  for (i = 0; i < chain->length; ++i) {
    char const * format = sox_globals.verbosity > 3?
      "effects chain: %-10s %7gHz %2u channels %7s %2u bits %s" :
      "effects chain: %-10s %7gHz %2u channels";
    sox_effect_t const * effp = &chain->effects[i][0];
    lsx_report(format, effp->handler.name, effp->out_signal.rate,
        effp->out_signal.channels,
        (effp->handler.flags & SOX_EFF_MCHAN)? "(multi)" : "",
        effp->out_signal.precision,
        effp->out_signal.length != SOX_UNKNOWN_LEN ?
          str_time(effp->out_signal.length/effp->out_signal.channels/effp->out_signal.rate) :
          "unknown length"
        );
  }
}

static int advance_eff_chain(void)
{
  sox_bool reuse_output = sox_true;

  very_first_effchain = sox_false;

  /* If input file reached EOF then delete all effects in current
   * chain and restart the current chain.
   *
   * This is only used with sox_sequence combine mode even though
   * we do not specifically check for that method.
   */
  if (input_eof) {
    /* P08 sequence boundaries reset the reconstructed DSD filter, not the
     * already-open output stream.  Preserve the output effect and writer
     * only when each segment's preflight certified the same output header.
     * Other sequence and newfile behavior remains unchanged. */
    if (combine_method==sox_sequence && current_input<input_count &&
        output_method==sox_single && dsd_runtime_active &&
        (dsd_runtime_plan.graph_decode_count ||
         dsd_runtime_plan.input_decode_count))
      save_output_eff=sox_pop_effect_last(effects_chain);
    sox_delete_effects(effects_chain);
  } else
  {
    /* If user requested to restart this effect chain then
     * do not advance to next.  Usually, this is because
     * an option to current effect was changed.
     */
    if (user_restart_eff)
      user_restart_eff = sox_false;
    /* Effect chain stopped so advance to next effect chain but
     * quite if no more chains exist.
     */
    else if (++current_eff_chain >= eff_chain_count)
      return SOX_EOF;

    while (nuser_effects[current_eff_chain] == 1 &&
           is_pseudo_effect(user_effargs[current_eff_chain][0].name))
    {
      if (strcmp("newfile", user_effargs[current_eff_chain][0].name) == 0)
      {
        if (++current_eff_chain >= eff_chain_count)
          return SOX_EOF;
        reuse_output = sox_false;
      }
      else if (strcmp("restart", user_effargs[current_eff_chain][0].name) == 0)
        current_eff_chain = 0;
    }

    if (reuse_output)
      save_output_eff = sox_pop_effect_last(effects_chain);

    while (effects_chain->length > 1)
      sox_delete_effect_last(effects_chain);
  }
  return SOX_SUCCESS;
} /* advance_eff_chain */

static uint64_t total_clips(void)
{
  size_t i;
  uint64_t clips = 0;
  for (i = 0; i < file_count; ++i)
    clips += files[i]->ft->clips + files[i]->volume_clips;
  return clips + mixing_clips + sox_effects_clips(effects_chain);
}

static sox_bool since(struct timeval * then, double secs, sox_bool always_reset)
{
  sox_bool ret;
  struct timeval now;
  time_t d;
  gettimeofday(&now, NULL);
  d = now.tv_sec - then->tv_sec;
  ret = d > ceil(secs) || now.tv_usec - then->tv_usec + d * TIME_FRAC >= secs * TIME_FRAC;
  if (ret || always_reset)
    *then = now;
  return ret;
}

static unsigned termwidth = 80;

#ifdef TIOCGWINSZ
static void get_termwidth(int s UNUSED)
{
  struct winsize w;

  if (!ioctl(2, TIOCGWINSZ, &w))
    termwidth = w.ws_col;
  else
    /* If stderr is redirected to a file, don't leave failure in errno,
     * which will be picked up later by a file-reading routine
     */
    errno = 0;
}
#endif

#define MIN_HEADROOM 6.
static double min_headroom = MIN_HEADROOM;

static char const * vu(unsigned channel)
{
  static struct timeval then;
  static char const * const text[][2] = {
    /* White: 2dB steps */
    {"", ""}, {"-", "-"}, {"=", "="}, {"-=", "=-"},
    {"==", "=="}, {"-==", "==-"}, {"===", "==="}, {"-===", "===-"},
    {"====", "===="}, {"-====", "====-"}, {"=====", "====="},
    {"-=====", "=====-"}, {"======", "======"},
    /* Red: 1dB steps */
    {"!=====", "=====!"},
  };
  int const red = 1, white = array_length(text) - red;
  double const MAX = SOX_SAMPLE_MAX, MIN = SOX_SAMPLE_MIN;
  double linear = max(omax[channel] / MAX, omin[channel] / MIN);
  double dB = linear_to_dB(linear);
  int vu_dB = linear? floor(2 * white + red + dB) : 0;
  int index = vu_dB < 2 * white? max(vu_dB / 2, 0) : min(vu_dB - white, red + white - 1);
  omax[channel] = omin[channel] = 0;
  if (-dB < min_headroom) {
    gettimeofday(&then, NULL);
    min_headroom = -dB;
  }
  else if (since(&then, 3., sox_false))
    min_headroom = -dB;

  return text[index][channel];
}

static char * headroom(void)
{
  if (min_headroom < MIN_HEADROOM) {
    static char buff[16];
    unsigned h = (unsigned)(min_headroom * 10);
    sprintf(buff, "Hd:%u.%u", h /10, h % 10);
    return buff;
  }
  return "      ";
}

static void display_status(sox_bool all_done)
{
  static struct timeval then;
  if (!show_progress)
    return;
  if (all_done || since(&then, .1, sox_false)) {
    double read_time = (double)read_wide_samples / combiner_signal.rate;
    double left_time = 0, in_time = 0, percentage = 0;
    char buf[80]; /* actually uses 78 + '\0' */
    int nchars = min(termwidth + 2, sizeof(buf));

    if (input_wide_samples) {
      in_time = (double)input_wide_samples / combiner_signal.rate;
      left_time = max(in_time - read_time, 0);
      percentage = max(100. * read_wide_samples / input_wide_samples, 0);
    }
    sprintf(buf,
      "\rIn:%-5s %s [%s] Out:%-5s [%6s|%-6s] %s Clip:%-5s",
      lsx_sigfigs3p(percentage), str_time(read_time), str_time(left_time),
      lsx_sigfigs3((double)output_samples),
      vu(0), vu(1), headroom(), lsx_sigfigs3((double)total_clips()));
    buf[nchars - 1] = '\0';
    fputs(buf, stderr);
  }
  if (all_done)
    fputc('\n', stderr);
  fflush(stderr);
}

#ifdef HAVE_TERMIOS_H
static int kbhit(void)
{
  struct timeval time_val = {0, 0};
  fd_set fdset;

  FD_ZERO(&fdset);
  FD_SET(fileno(stdin), &fdset);
  select(fileno(stdin) + 1, &fdset, NULL, NULL, &time_val);
  return FD_ISSET(fileno(stdin), &fdset);
}
#elif !defined(HAVE_CONIO_H)
#define kbhit() 0
#endif

#ifdef HAVE_SOUNDCARD_H
static void adjust_volume(int delta)
{
  char * from_env;
  int vol1 = 0, vol2 = 0, fd;

  if (lsx_adjust_softvol(delta) == SOX_SUCCESS) return;
  from_env = getenv("MIXERDEV");
  fd = open(from_env? from_env : "/dev/mixer", O_RDWR);
  if (fd >= 0) {
    if (ioctl(fd, MIXER_READ(SOUND_MIXER_PCM), &vol1) != -1) {
      int side1 = vol1 & 0xff, side2 = (vol1 >> 8) & 0xff;
      delta = delta < 0?  max(delta, -min(side1, side2)) :
          min(delta, 100 - max(side1, side2));
      vol2 = ((side2 + delta) << 8) + side1 + delta;
      lsx_debug("%04x %04x", vol1, vol2);
      if (vol1 != vol2 && ioctl(fd, MIXER_WRITE(SOUND_MIXER_PCM), &vol2) < 0)
        vol2 = vol1;
    }
    close(fd);
  }
  if (vol1 == vol2)
    putc('\a', stderr);
}
#elif defined(HAVE_SUN_AUDIO)
static void adjust_volume(int delta)
{
  int vol1 = 0, vol2 = 0, fd;
  fd = ofile->ft->fp != NULL ? *((int *)ofile->ft->fp) : -1;
  if (lsx_adjust_softvol(delta) == SOX_SUCCESS) return;
  if (fd >= 0) {
    audio_info_t audio_info;
    if (ioctl(fd, AUDIO_GETINFO, &audio_info) >= 0) {
      vol1 = (audio_info.play.gain * 100 + (AUDIO_MAX_GAIN >> 1)) / AUDIO_MAX_GAIN;
      vol2 = range_limit(vol1 + delta, 0, 100);
      AUDIO_INITINFO(&audio_info);
      audio_info.play.gain = (vol2 * AUDIO_MAX_GAIN + 50) / 100;
#if defined(__sun)
      audio_info.output_muted = 0;
#endif
      lsx_debug("%04x %04x", vol1, vol2);
      if (vol1 != vol2 && ioctl(fd, AUDIO_SETINFO, &audio_info) < 0)
        vol2 = vol1;
    }
  }
  if (vol1 == vol2)
    putc('\a', stderr);
}
#else
static void adjust_volume(int delta)
{
  if (lsx_adjust_softvol(delta))
    putc('\a', stderr);
}
#endif

/* Convert CLI frame positions to the public interleaved-sample offset. */
static sox_bool seek_offset_for_frames(sox_format_t const *ft,
    uint64_t frames, uint64_t *samples)
{
  if (!ft->signal.channels || frames > UINT64_MAX / ft->signal.channels)
    return sox_false;
  *samples = frames * ft->signal.channels;
  return sox_true;
}

static int update_status(sox_bool all_done, void * client_data)
{
  char key[2];

  (void)client_data;
  if (interactive) while (kbhit()) {
#ifdef HAVE_CONIO_H
    int ch = _getch();
#else
    int ch = getchar();
#endif

    /* See if the key is claimed by an effect parameter-changing key */
    key[0] = ch; key[1] = '\0';
    if (sox_is_keymapped(key))
      (void) sox_keymap_apply(effects_chain, key);
    else switch (ch) {

    case '>':
    case '<':
    if (!files[current_input]->dsd_target_hz &&
        (!dsd_runtime_active || dsd_runtime_plan.trim_native_seek) &&
        files[current_input]->ft->handler.seek &&
        files[current_input]->ft->seekable) {
      sox_format_t *ft = files[current_input]->ft;
      double seconds = ft->signal.rate * 30; /* 30 seconds in frames. */
      uint64_t jump, candidate, offset;
      if (!(seconds >= 0 && seconds < (double)UINT64_MAX)) {
        lsx_warn("seeking failed: invalid sample rate");
        break;
      }
      jump = (uint64_t)seconds;
      if (ch == '>') {
        if (jump > UINT64_MAX - read_wide_samples)
          break;
        candidate = read_wide_samples + jump;
        if (input_wide_samples && candidate >= input_wide_samples)
          break;
      } else
        candidate = jump < read_wide_samples ? read_wide_samples - jump : 0;
      if (!seek_offset_for_frames(ft, candidate, &offset) ||
          sox_seek(ft, offset, SOX_SEEK_SET) != SOX_SUCCESS)
        lsx_warn("seeking failed");
      else
        read_wide_samples = ft->olength / ft->signal.channels;
    } else /* FIXME: Seek forward by discarding samples */
      lsx_warn("this file type is not seekable");
    break;

    case 'R':
      /* Not very useful, eh!  Sample though of the place you
       * could change the value to effects options
       * like vol or speed or remix.
       * Modify values in user_effargs[current_eff_chain][xxx]
       * and then chain will be drain()ed and restarted whence
       * this function is existed.
       */
      user_restart_eff = sox_true;
      break;

    case 'n':
      user_skip = sox_true;
      break;

    case 'q': case 27: /* Escape key */
      user_abort = sox_true;
      break;

    case 'V': adjust_volume(+7); break;
    case 'v': adjust_volume(-7); break;
      break;

    default:
      lsx_warn("key `%s' doesn't do anything", key);
    }
  }

  display_status(all_done || user_abort);
  return (user_abort || user_restart_eff) ? SOX_EOF : SOX_SUCCESS;
}

static void optimize_trim(void)
{
  /* Speed hack.  If the "trim" effect is the first effect then peek inside its
   * "effect descriptor" and see what the start location is.  This has to be
   * done after its start() is called to have the correct location.  Also, only
   * do this when only working with one input file.  This is because the logic
   * to do it for multiple files is complex and seldom used.  The same
   * is true for a restarted or additional effects chain (relative positioning
   * within the file and possible samples still buffered in the input effect
   * would have to be taken into account).  This hack is a huge time savings
   * when trimming gigs of audio data into managable chunks.  */
  if ((!dsd_runtime_active || dsd_runtime_plan.trim_native_seek) &&
      input_count == 1 && very_first_effchain && effects_chain->length > 1 &&
      strcmp(effects_chain->effects[1][0].handler.name, "trim") == 0) {
    if (files[0]->ft->handler.seek && files[0]->ft->seekable){
      uint64_t offset = sox_trim_get_start(&effects_chain->effects[1][0]);
      if (offset && sox_seek(files[0]->ft, offset, SOX_SEEK_SET) == SOX_SUCCESS) {
        read_wide_samples = files[0]->ft->olength / files[0]->ft->signal.channels;
        /* Assuming a failed seek stayed where it was.  If the seek worked then
         * reset the start location of trim so that it thinks user didn't
         * request a skip.  */
        sox_trim_clear_start(&effects_chain->effects[1][0]);
        lsx_debug("optimize_trim successful");
      }
    }
  }
}

static sox_bool overwrite_permitted(char const * filename)
{
  char c;

  if (!no_clobber) {
    lsx_report("overwriting `%s'", filename);
    return sox_true;
  }
  lsx_warn("output file `%s' already exists", filename);
  if (!stdin_is_a_tty)
    return sox_false;
  do fprintf(stderr, "%s: overwrite `%s' (y/n)? ", sox_globals.myname, filename);
  while (scanf(" %c%*[^\n]", &c) != 1 || !strchr("yYnN", c));
  return c == 'y' || c == 'Y';
}

static char *fndup_with_count(const char *filename, size_t count)
{
    char *expand_fn, *efn;
    const char *fn, *ext, *end;
    sox_bool found_marker = sox_false;

    fn = filename;

#ifndef FILENAME_MAX
/* Undefined on Sortix */
# define FILENAME_MAX 4096
#endif
    efn = expand_fn = lsx_malloc((size_t)FILENAME_MAX);

    /* Find extension in case user didn't specify a substitution
     * marker.
     */
    end = ext = filename + strlen(filename);
    while (ext > filename && *ext != '.')
        ext--;

    /* In case extension not found, point back to end of string to do less
     * copying later.
     */
    if (*ext != '.')
        ext = end;

    while (fn < end)
    {
        /* Look for %n. If found, replace with count.  Can specify an
         * option width of 1-9.
         */
        if (fn[0] == '%' &&
            (fn[1] == 'n' ||
             (fn[1] >= '1' && fn[1] <= '9' && fn[2] == 'n')))
        {
            char width = 0;
            char format[5];

            fn++;
            if (*fn >= '1' && *fn <= '9')
                width = *fn++;
            /* *fn == 'n' */
            found_marker = sox_true;

            if (width)
                sprintf(format, "%%0%cd", width), width -= '0';
            else
                strcpy(format, "%02d"), width = 2;

            sprintf(efn, format, count);
            efn += width;
            fn++;
        }
        else
            *efn++ = *fn++;
    }

    *efn = 0;

    /* If user didn't tell us what to do then default to putting
     * the count right before file extension.
     */
    if (!found_marker)
    {
        efn -= strlen (ext);

        sprintf(efn, "%03lu", (unsigned long)count);
        efn = efn + 3;
        strcat(efn, ext);
    }

    return expand_fn;
}

/* A role list is an output assignment, not a claim about WSD/DSDIFF IDs.
 * Reject extra, missing or unknown spellings before opening the output. */
static sox_dsd_layout_t *dsd_assign_roles(sox_dsd_layout_t *layout,
    unsigned channels, char const *csv)
{
  static struct { char const *name; sox_dsd_role_t role; } const roles[] = {
    {"unknown", SOX_DSD_ROLE_UNKNOWN}, {"MONO", SOX_DSD_ROLE_MONO},
    {"FL", SOX_DSD_ROLE_FL}, {"FR", SOX_DSD_ROLE_FR},
    {"FC", SOX_DSD_ROLE_FC}, {"LFE", SOX_DSD_ROLE_LFE},
    {"BL", SOX_DSD_ROLE_BL}, {"BR", SOX_DSD_ROLE_BR},
    {"SL", SOX_DSD_ROLE_SL}, {"SR", SOX_DSD_ROLE_SR}
  };
  size_t len;
  unsigned i, j;
  char *text, *part, *next;
  sox_dsd_layout_t *result;
  if (!csv || !(len = strlen(csv)) || len > 65535) return NULL;
  text = lsx_strdup(csv);
  result = layout && sox_dsd_layout_channels(layout) == channels ?
      sox_dsd_layout_copy(layout) : sox_dsd_layout_new(channels);
  if (!result) { free(text); return NULL; }
  part = text;
  for (i=0;i<channels;++i) {
    next = strchr(part, ',');
    if (next) *next++=0;
    for (j=0;j<sizeof(roles)/sizeof(roles[0]);++j)
      if (!strcasecmp(part,roles[j].name))break;
    if (!*part || j==sizeof(roles)/sizeof(roles[0]) ||
        sox_dsd_layout_set_role(result,i,roles[j].role)!=SOX_DSD_OK)break;
    if (i+1==channels && next)break;
    if (i+1<channels && !next)break;
    part=next;
  }
  free(text);
  if (i != channels) { sox_dsd_layout_free(result);return NULL; }
  return result;
}

static sox_dsd_layout_t *dsd_default_layout(unsigned channels)
{
  sox_dsd_layout_t *p = sox_dsd_layout_new(channels);
  if (!p)return NULL;
  if (channels == 1)sox_dsd_layout_set_dsf_type(p,1);
  else if (channels == 2)sox_dsd_layout_set_dsf_type(p,2);
  return p;
}

/* An output plan consumes a private snapshot, never borrowed handler memory.
 * Results are checked against the chosen file handler before opening it. */
static sox_dsd_layout_t *dsd_plan_output(char const *path,
    char const *type)
{
  sox_format_handler_t const *handler=sox_write_handler(path,type,NULL);
  sox_dsd_layout_t *layout=NULL, *replacement;
  char const *kind;
  sox_bool native_input, native_output, wav_output, has_identity;
  unsigned i, channels;
  if (!handler)return NULL; /* The normal open path reports unsupported type. */
  kind = handler->names[0];
  native_output = !strcmp(kind,"dsf") || !strcmp(kind,"dff");
  wav_output = !strcmp(kind,"wav") && (!type || strcmp(type,"wavpcm")) &&
      (!ofile->encoding.encoding || ofile->encoding.encoding==SOX_ENCODING_SIGN2 ||
       ofile->encoding.encoding==SOX_ENCODING_UNSIGNED ||
       ofile->encoding.encoding==SOX_ENCODING_FLOAT);
  native_input = files[0]->ft->encoding.encoding == SOX_ENCODING_DSD;
  /* P04 is a DSD provenance bridge, not a change of policy for ordinary
   * PCM-to-PCM processing, including a WAV source with an extensible mask. */
  if (!native_input && !native_output && !dsd_layout_assignment)
    return NULL;
  if (sox_dsd_get_layout(files[0]->ft,&layout) != SOX_DSD_OK)
    layout = NULL;
  if (!layout && native_output)
    layout=dsd_default_layout(combiner_signal.channels);
  /* Ordinary mono/stereo PCM WAV has no mask but its reader correctly
   * supplies an unknown-role layout.  Assign the conventional PCM roles only
   * when encoding to DSD; a nonzero, unrepresentable extensible mask is not
   * an absent assignment and must not be guessed. */
  if (native_output && !native_input && layout &&
      (combiner_signal.channels == 1 || combiner_signal.channels == 2) &&
      sox_dsd_layout_channels(layout) == combiner_signal.channels &&
      lsx_dsd_layout_wav_without_assignment(layout)) {
    replacement = dsd_default_layout(combiner_signal.channels);
    sox_dsd_layout_free(layout);
    layout = replacement;
  }
  if (!layout && !dsd_layout_assignment)return NULL;

  /* The combiner's parallel arithmetic changes identity.  Serial files
   * retain identity only when all ordered input role/ID vectors agree. */
  if (layout && input_count > 1) {
    sox_bool consistent = is_serial(combine_method);
    for (i=1;consistent && i<input_count;++i) {
      sox_dsd_layout_t *other=NULL;
      unsigned j;
      if (sox_dsd_get_layout(files[i]->ft,&other)!=SOX_DSD_OK ||
          sox_dsd_layout_channels(other)!=sox_dsd_layout_channels(layout))
        consistent=sox_false;
      else for (j=0;j<sox_dsd_layout_channels(layout);++j) {
        sox_dsd_channel_info_t a={0}, b={0};
        a.size=b.size=sizeof(a);
        a.version=b.version=1;
        sox_dsd_layout_channel(layout,j,&a);
        sox_dsd_layout_channel(other,j,&b);
        if (a.role!=b.role || a.dff_id_valid!=b.dff_id_valid ||
            (a.dff_id_valid && memcmp(a.dff_id,b.dff_id,4))) {
          consistent=sox_false;break;
        }
      }
      sox_dsd_layout_free(other);
    }
    if (!consistent) sox_dsd_layout_invalidate(layout);
  }

  channels=sox_dsd_layout_channels(layout);
  for (i=0;layout && i<nuser_effects[current_eff_chain];++i) {
    sox_effect_t *effect=user_efftab[i];
    if (effect->handler.flags & SOX_EFF_CHAN) {
      /* channels N returns SOX_EFF_NULL for input N: there is no map or mix.
       * The effect has not started yet, so the planned channel count is its
       * input count; getopts already records the requested output count. */
      if (!strcmp(effect->handler.name,"channels") &&
          effect->out_signal.channels == channels)
        continue;
      unsigned *map = lsx_malloc((size_t)channels*sizeof(*map));
      if (lsx_remix_pure_map(effect,channels,map,channels)) {
        unsigned count=effect->out_signal.channels;
        replacement=sox_dsd_layout_map(layout,map,count);
        sox_dsd_layout_free(layout);
        layout=replacement;
        if (layout) channels=sox_dsd_layout_channels(layout);
      } else {
        /* Unknown channel transformation: all derived identities are stale. */
        sox_dsd_layout_invalidate(layout);
      }
      free(map);
    }
  }

  if (layout && sox_dsd_layout_channels(layout)!=ofile->signal.channels) {
    /* Implicit "channels" effect has no known one-to-one map. */
    sox_dsd_layout_free(layout);
    layout=sox_dsd_layout_new(ofile->signal.channels);
  }
  if (dsd_layout_assignment) {
    replacement=dsd_assign_roles(layout,ofile->signal.channels,
        dsd_layout_assignment);
    if (!replacement) {
      lsx_fail("--dsd-layout requires exactly %u comma-separated known roles",
          ofile->signal.channels);
      sox_dsd_layout_free(layout);
      exit(2);
    }
    sox_dsd_layout_free(layout);
    layout=replacement;
  }
  if (!layout)return NULL;
  channels=sox_dsd_layout_channels(layout);
  has_identity=sox_false;
  for (i=0;i<channels;++i) {
    sox_dsd_channel_info_t info={0};
    info.size=sizeof(info);info.version=1;
    if (sox_dsd_layout_channel(layout,i,&info)==SOX_DSD_OK &&
        (info.role!=SOX_DSD_ROLE_UNKNOWN || info.dff_id_valid))
      has_identity=sox_true;
  }
  if (!native_output && !wav_output) {
    if (has_identity && !dsd_layout_loss_warn) {
      lsx_fail("destination `%s' cannot carry named channel identity; use --dsd-layout-loss warn to allow loss",kind);
      sox_dsd_layout_free(layout);
      exit(2);
    }
    if (has_identity)
      lsx_warn("discarding DSD channel layout for `%s' (--dsd-layout-loss warn)",kind);
    sox_dsd_layout_free(layout);
    return NULL;
  }
  if (!native_output && !native_input && !has_identity) {
    /* Do not rewrite ordinary PCM files simply for an unknown layout. */
    sox_dsd_layout_free(layout);
    return NULL;
  }
  if (wav_output) {
    uint32_t mask;
    unsigned *order=lsx_malloc(channels*sizeof(*order));
    sox_dsd_status_t status=sox_dsd_layout_wav_mask(layout,&mask,order,channels);
    if (status!=SOX_DSD_OK) {
      if (has_identity && !dsd_layout_loss_warn) {
        lsx_fail("WAV cannot represent this speaker assignment without losing identity");
        free(order);
        sox_dsd_layout_free(layout);
        exit(2);
      }
      if (has_identity)
        lsx_warn("writing WAV with unspecified channel mask (--dsd-layout-loss warn)");
    } else {
      for (i=0;i<channels;++i)if(order[i]!=i)break;
      if (i<channels) {
        replacement=sox_dsd_layout_map(layout,order,channels);
        if (!replacement) {
          free(order);sox_dsd_layout_free(layout);exit(2);
        }
        sox_dsd_layout_free(layout);
        layout=replacement;
        dsd_output_permutation=order;
        dsd_output_permutation_count=channels;
        order=NULL;
      }
    }
    free(order);
  }
  return layout;
}

static void open_output_file(void)
{
  double factor;
  int i;
  sox_comments_t p = ofile->oob.comments;
  sox_oob_t oob = files[0]->ft->oob;
  char *expand_fn;

  /* Skip opening file if we are not recreating output effect */
  if (save_output_eff)
    return;

  oob.comments = sox_copy_comments(files[0]->ft->oob.comments);

  if (!oob.comments && !p)
    sox_append_comment(&oob.comments, "Processed by SoX");
  else if (p) {
    if (!(*p)[0]) {
      sox_delete_comments(&oob.comments);
      ++p;
    }
    while (*p)
      sox_append_comment(&oob.comments, *p++);
  }

  /* Copy loop info, resizing appropriately it's in samples, so # channels
   * don't matter FIXME: This doesn't work for multi-file processing or effects
   * that change file length.  */
  factor = (double) ofile->signal.rate / combiner_signal.rate;
  for (i = 0; i < SOX_MAX_NLOOPS; i++) {
    oob.loops[i].start = oob.loops[i].start * factor;
    oob.loops[i].length = oob.loops[i].length * factor;
  }

  if (output_method == sox_multiple)
    expand_fn = fndup_with_count(ofile->filename, ++output_count);
  else
    expand_fn = lsx_strdup(ofile->filename);
  {
    sox_dsd_layout_t *layout=dsd_plan_output(expand_fn,ofile->filetype);
    ofile->ft = layout ?
        sox_open_write_dsd(expand_fn, &ofile->signal, &ofile->encoding,
            ofile->filetype, &oob, overwrite_permitted, layout) :
        sox_open_write(expand_fn, &ofile->signal, &ofile->encoding,
            ofile->filetype, &oob, overwrite_permitted);
    sox_dsd_layout_free(layout);
  }
  sox_delete_comments(&oob.comments);
  free(expand_fn);

  if (!ofile->ft)
    /* sox_open_write() will call lsx_warn for most errors.
     * Rely on that printing something. */
    exit(2);

  /* If the progress display (similar to that of ogg123) has not been
   * specified by the user, auto turn on when outputting to an audio
   * device: */
  if (show_progress == sox_option_default)
    show_progress = (ofile->ft->handler.flags & SOX_FILE_DEVICE) != 0 &&
                    (ofile->ft->handler.flags & SOX_FILE_PHONY) == 0;

  report_file_info(ofile);
}

static void setsig(int sig, void (*handler)(int))
{
#ifdef HAVE_SIGACTION
  struct sigaction sa;

  sa.sa_handler = handler;
  sigemptyset(&sa.sa_mask);
  sa.sa_flags = 0;

  sigaction(sig, &sa, NULL);
#else
  signal(sig, handler);
#endif
}

static void sigint(int s)
{
  static struct timeval then;
  if (input_count > 1 && show_progress && s == SIGINT &&
      is_serial(combine_method) && since(&then, 1.0, sox_true))
  {
    setsig(SIGINT, sigint);
    user_skip = sox_true;
  }
  else user_abort = sox_true;
}

static void calculate_combiner_signal_parameters(void)
{
  size_t i;

  /* If user didn't specify # of channels then see if an effect
   * is specifying them.  This is of most use currently with the
   * synth effect were user can use null input handler and specify
   * channel counts directly in effect.  Forcing to use -c with
   * -n isn't as convenient.
   */
  for (i = 0; i < input_count; i++) {
    size_t j;
    for (j =0; j < nuser_effects[current_eff_chain] &&
               !files[i]->ft->signal.channels; ++j)
      files[i]->ft->signal.channels = user_efftab[j]->in_signal.channels;
    /* For historical reasons, default to one channel if not specified. */
    if (!files[i]->ft->signal.channels)
      files[i]->ft->signal.channels = 1;
  }

  /* Set the combiner output signal attributes to those of the 1st/next input
   * file.  If we are in sox_sequence mode then we don't need to check the
   * attributes of the other inputs, otherwise, it is mandatory that all input
   * files have the same sample rate, and for sox_concatenate, it is mandatory
   * that they have the same number of channels, otherwise, the number of
   * channels at the output of the combiner is calculated according to the
   * combiner mode. */
  combiner_signal = files[current_input]->ft->signal;
  if (combine_method == sox_sequence) {
    /* Report all input files; do this only the 1st time process() is called: */
    if (!current_input) for (i = 0; i < input_count; i++)
      report_file_info(files[i]);
    combiner_signal.length = SOX_UNKNOWN_LEN;
  } else {
    size_t total_channels = 0;
    size_t min_channels = SOX_SIZE_MAX;
    size_t max_channels = 0;
    size_t min_rate = SOX_SIZE_MAX;
    size_t max_rate = 0;
    uint64_t total_length = 0, max_length_ws = 0;

    /* Report all input files and gather info on differing rates & numbers of
     * channels, and on the resulting output audio length: */
    for (i = 0; i < input_count; i++) {
      report_file_info(files[i]);
      total_channels += files[i]->ft->signal.channels;
      min_channels = min(min_channels, files[i]->ft->signal.channels);
      max_channels = max(max_channels, files[i]->ft->signal.channels);
      min_rate     = min(min_rate    , files[i]->ft->signal.rate);
      max_rate     = max(max_rate    , files[i]->ft->signal.rate);
      max_length_ws = files[i]->ft->signal.length ?
          max(max_length_ws, files[i]->ft->signal.length / files[i]->ft->signal.channels) :
          SOX_UNKNOWN_LEN;
      if (total_length != SOX_UNKNOWN_LEN && files[i]->ft->signal.length)
        total_length += files[i]->ft->signal.length;
      else
        total_length = SOX_UNKNOWN_LEN;
    }

    /* Legacy SoX rejects differing clocks before the combiner.  Opt-in DSD
   * planning must accept this metadata long enough to place per-input
   * reconstruction at a common PCM rate; P05 blocks execution of that graph
   * until the composite decoder is implemented.  Other invocations retain
   * the original rate check. */
  if (min_rate != max_rate) {
    sox_bool has_native=sox_false;
    sox_bool opt_in=(dsd_plan_only || dsd_new_policy_explicit ||
        (dsd_mode_explicit && dsd_policy.mode==LSX_DSD_MODE_AUTO));
    for (i=0;i<input_count;i++)
      if (files[i]->ft->encoding.encoding==SOX_ENCODING_DSD) has_native=sox_true;
    if (!is_parallel(combine_method) || !has_native || !opt_in ||
        (dsd_mode_explicit && dsd_policy.mode!=LSX_DSD_MODE_AUTO))
      lsx_fail("input files must have the same sample-rate");
    else min_rate=max_rate; /* only the preflight can authorize this request */
  }
  if (min_channels != max_channels) {
    if (combine_method == sox_concatenate) {
      lsx_fail("input files must have the same number of channels");
      exit(1);
    } else if (combine_method != sox_merge)
      lsx_warn("input files don't have the same number of channels");
  }
  if (min_rate != max_rate)
    exit(1);

  /* Store the calculated # of combined channels: */
    combiner_signal.channels =
      combine_method == sox_merge? total_channels : max_channels;

    if (combine_method == sox_concatenate)
      combiner_signal.length = total_length;
    else if (is_parallel(combine_method))
      combiner_signal.length = max_length_ws != SOX_UNKNOWN_LEN ?
          max_length_ws * combiner_signal.channels : SOX_UNKNOWN_LEN;
  }
} /* calculate_combiner_signal_parameters */

static void calculate_output_signal_parameters(void)
{
  sox_bool known_length = combine_method != sox_sequence;
  size_t i;
  uint64_t olen = 0;

  /* Report all input files and gather info on differing rates & numbers of
   * channels, and on the resulting output audio length: */
  for (i = 0; i < input_count; i++) {
    known_length = known_length && files[i]->ft->signal.length != SOX_UNSPEC;
    if (combine_method == sox_concatenate)
      olen += files[i]->ft->signal.length / files[i]->ft->signal.channels;
    else
      olen = max(olen, files[i]->ft->signal.length / files[i]->ft->signal.channels);
  }

  /* Determine the output file signal attributes; set from user options
   * if given: */
  ofile->signal = ofile_signal_options;

  /* If no user option for output rate or # of channels, set from the last
   * effect that sets these, or from the input combiner if there is none such */
  for (i = 0; i < nuser_effects[current_eff_chain] && !ofile->signal.rate; ++i)
    ofile->signal.rate = user_efftab[nuser_effects[current_eff_chain] - 1 - i]->out_signal.rate;
  for (i = 0; i < nuser_effects[current_eff_chain] && !ofile->signal.channels; ++i)
    ofile->signal.channels = user_efftab[nuser_effects[current_eff_chain] - 1 - i]->out_signal.channels;
  if (!ofile->signal.rate)
    ofile->signal.rate = combiner_signal.rate;
  if (!ofile->signal.channels)
    ofile->signal.channels = combiner_signal.channels;

  /* FIXME: comment this: */
  ofile->signal.precision = combiner_signal.precision;

  /* If any given user effect modifies the audio length, then we assume that
   * we don't know what the output length will be.  FIXME: in most cases,
   * an effect that modifies length will be able to determine by how much from
   * its getopts parameters, so olen should be calculable. */
  for (i = 0; i < nuser_effects[current_eff_chain]; i++)
    known_length = known_length && !(user_efftab[i]->handler.flags & SOX_EFF_LENGTH);

  if (!known_length)
    olen = 0;
  ofile->signal.length = (uint64_t)(olen * ofile->signal.channels * ofile->signal.rate / combiner_signal.rate + .5);
}

static void set_combiner_and_output_encoding_parameters(void)
{
  /* The input encoding parameters passed to the effects chain are those of
   * the first input file (for each segued block if sox_sequence):*/
  combiner_encoding = files[current_input]->ft->encoding;

  /* Determine the output file encoding attributes; set from user options
   * if given: */
  ofile->encoding = ofile_encoding_options;

  /* Get unspecified output file encoding attributes from the input file and
   * set the output file to the resultant encoding if this is supported by the
   * output file type; if not, the output file handler should select an
   * encoding suitable for the output signal and its precision. */
  {
    sox_encodinginfo_t t = ofile->encoding;
    if (!t.encoding)
      t.encoding = combiner_encoding.encoding;
    if (!t.bits_per_sample)
      t.bits_per_sample = combiner_encoding.bits_per_sample;
    if (sox_format_supports_encoding(ofile->filename, ofile->filetype, &t))
      ofile->encoding = t;
  }
}

/* A sequence can restart the processing chain on a change of input domain,
 * rate or channel layout. Certify every segment before creating the first
 * output: a later failure must not leave an incomplete audio file. */
static void dsd_free_sequence(lsx_dsd_plan *series, size_t count)
{
  size_t i;
  for (i=0;i<count;i++) lsx_dsd_plan_free(&series[i]);
  free(series);
}

/* P05 preflight snapshots metadata before open_output_file().  Effect getopts
 * has already run, but no effect start() has run.  In native-only mode the
 * existing (unmodified) flow graph remains responsible for sample I/O.
 */
static void preflight_dsd(void)
{
  lsx_dsd_plan_spec spec;
  lsx_dsd_plan plan;
  lsx_dsd_plan *series=NULL, *active=&plan;
  size_t segments=0;
  lsx_dsd_input_spec *input;
  lsx_dsd_effect_spec *effect;
  sox_format_handler_t const *handler;
  sox_encodinginfo_t test_enc;
  char error[256];
  size_t i;
  int has_new_effect=0, has_dsd_input=0;
  char const *kind;
  FILE *report=NULL;

  lsx_dsd_plan_free(&dsd_runtime_plan);
  dsd_runtime_active=sox_false;
  free(dsd_decode_before);
  dsd_decode_before=NULL;
  free(dsd_encode_before);
  dsd_encode_before=NULL;
  dsd_consume_leading=sox_false;
  for (i=0;i<nuser_effects[current_eff_chain];i++) {
    char const *name=user_efftab[i]->handler.name;
    if (!strcmp(name,"dsdpcm") || !strcmp(name,"pcmdsd") || !strcmp(name,"dsdstat"))
      has_new_effect=1;
  }
  if (!dsd_preflight_enabled() && !has_new_effect) return;
  if (!dsd_mode_explicit && (dsd_new_policy_explicit || dsd_plan_only || has_new_effect || dsd_report_path))
    dsd_policy.mode=LSX_DSD_MODE_AUTO;
  dsd_policy.kernel_fir=getenv("SOX_DSD_KERNEL_FIR");
  dsd_policy.kernel_sdm=getenv("SOX_DSD_KERNEL_SDM");
  dsd_policy.layout_loss_warn=dsd_layout_loss_warn;
  dsd_policy.guarded=is_guarded;
  dsd_policy.normalizing=do_guarded_norm;
  dsd_policy.dither_disabled=no_dither;
  memset(&spec,0,sizeof(spec));
  memset(&plan,0,sizeof(plan));
  spec.policy=dsd_policy;
  spec.combine=(lsx_dsd_combine)combine_method;
  input=lsx_calloc(input_count,sizeof(*input));
  effect=lsx_calloc(nuser_effects[current_eff_chain]+1,sizeof(*effect));
  spec.inputs=input;spec.input_count=input_count;
  spec.effects=effect;spec.effect_count=nuser_effects[current_eff_chain];
  for (i=0;i<spec.effect_count;i++)
    lsx_dsd_effect_apply_policy(user_efftab[i],&spec.policy);
  spec.requested_output_rate=ofile_signal_options.rate;
  spec.requested_output_channels=ofile_signal_options.channels;
  spec.requested_encoding=ofile_encoding_options;
  spec.output_path=ofile->filename;
  spec.output_type=ofile->filetype;
  handler=sox_write_handler(ofile->filename,ofile->filetype,NULL);
  if (!handler) {lsx_fail("P05: cannot resolve output handler before header open");exit(2);}
  kind=handler->names[0];
  spec.output_native_capable=!strcmp(kind,"dsf") || !strcmp(kind,"dff") || !strcmp(kind,"wsd");
  spec.output_is_null=!strcmp(kind,"null");
  sox_init_encodinginfo(&test_enc);
  /* Prefer signed 24-bit.  For a PCM-only codec, select another ordinary
   * lossless PCM precision instead of treating every other output as invalid. */
  {
    static struct {sox_encoding_t e; unsigned bits;} const choices[]={
      {SOX_ENCODING_SIGN2,24},{SOX_ENCODING_SIGN2,32},
      {SOX_ENCODING_FLOAT,32},{SOX_ENCODING_SIGN2,16},
      {SOX_ENCODING_FLOAT,64},{SOX_ENCODING_UNSIGNED,16},
      {SOX_ENCODING_SIGN2,8},{SOX_ENCODING_UNSIGNED,8}
    };
    size_t k;
    for (k=0;k<sizeof(choices)/sizeof(choices[0]);k++) {
      test_enc.encoding=choices[k].e;
      test_enc.bits_per_sample=choices[k].bits;
      if (sox_format_supports_encoding(ofile->filename,ofile->filetype,&test_enc)) {
        spec.output_pcm_capable=1;
        spec.fallback_encoding=choices[k].e;
        spec.fallback_bits=choices[k].bits;
        break;
      }
    }
  }
  spec.output_dop_capable=spec.output_pcm_capable &&
      spec.fallback_encoding==SOX_ENCODING_SIGN2 &&
      spec.fallback_bits==24 && !spec.output_is_null;
  for (i=0;i<input_count;i++) {
    file_t const *f=files[i];
    sox_dsd_layout_t *layout=NULL;
    input[i].native_signal=f->ft->signal;
    input[i].encoding=f->ft->encoding.encoding;
    input[i].input_volume=f->volume==HUGE_VAL?1:f->volume;
    if (f->replay_gain!=HUGE_VAL)
      input[i].input_volume*=pow(10.,f->replay_gain/20.);
    input[i].layout_known=1;
    if (input[i].encoding==SOX_ENCODING_DSD) {
      has_dsd_input=1;
      input[i].layout_known=sox_dsd_get_layout(f->ft,&layout)==SOX_DSD_OK;
      sox_dsd_layout_free(layout);
    }
  }
  /* Compatible native concatenation must not silently relabel the next
   * file.  Compare ordered role/ID identities, not just channel counts. */
  if (spec.combine==LSX_DSD_COMBINE_CONCAT && has_dsd_input && input_count>1) {
    sox_dsd_layout_t *first=NULL;
    size_t j;
    if (sox_dsd_get_layout(files[0]->ft,&first)!=SOX_DSD_OK || !first) {
      lsx_fail("P05 native concatenation lacks the initial channel identity");exit(2);
    }
    for (i=1;i<input_count;i++) {
      sox_dsd_layout_t *other=NULL;
      sox_bool match=sox_dsd_get_layout(files[i]->ft,&other)==SOX_DSD_OK &&
          other && sox_dsd_layout_channels(other)==sox_dsd_layout_channels(first);
      for (j=0;match && j<sox_dsd_layout_channels(first);j++) {
        sox_dsd_channel_info_t a={0},b={0};
        a.version=b.version=1;a.size=b.size=sizeof(a);
        if (sox_dsd_layout_channel(first,(unsigned)j,&a)!=SOX_DSD_OK ||
            sox_dsd_layout_channel(other,(unsigned)j,&b)!=SOX_DSD_OK ||
            a.role!=b.role || a.dff_id_valid!=b.dff_id_valid ||
            (a.dff_id_valid && memcmp(a.dff_id,b.dff_id,4)))
          match=sox_false;
      }
      sox_dsd_layout_free(other);
      if (!match) {
        lsx_fail("P05 native concatenation requires identical ordered channel identities");
        sox_dsd_layout_free(first);free(input);free(effect);exit(2);
      }
    }
    sox_dsd_layout_free(first);
  }
  /* New DSD policy never changes unrelated PCM-only execution. */
  if (!has_dsd_input && !spec.output_native_capable && !has_new_effect &&
      !dsd_plan_only && !dsd_report_path) {
    free(input);free(effect);return;
  }
  for (i=0;i<spec.effect_count;i++) {
    sox_effect_t *e=user_efftab[i];
    effect[i].name=e->handler.name;
    effect[i].flags=e->handler.flags;
    effect[i].out_rate=e->out_signal.rate;
    effect[i].out_channels=e->out_signal.channels;
    effect[i].dsd=lsx_dsd_effect_get_options(e);
    effect[i].dither_precision_one=lsx_dither_explicit_one_bit(e);
    if (!strcmp(e->handler.name,"sdm"))
      effect[i].sdm_filter_name=lsx_sdm_effect_filter_name(e);
    if (!strcmp(e->handler.name,"remix") && e->out_signal.channels &&
        e->out_signal.channels <= 32) {
      unsigned count=e->out_signal.channels, *map=lsx_calloc(count,sizeof(*map));
      effect[i].native_permutation=lsx_remix_pure_map(e,
          (i?effect[i-1].out_channels:input[0].native_signal.channels),map,count);
      free(map);
    }
  }
  /* Legacy remains the default.  A legacy-only explicit request is not a
   * claim that the new reconstruction graph runs in legacy mode. */
  if (spec.policy.mode==LSX_DSD_MODE_LEGACY && !dsd_plan_only && !has_new_effect &&
      !dsd_report_path) {
    if (dsd_mode_explicit && has_dsd_input &&
        (spec.effect_count || is_parallel(combine_method)))
      lsx_warn("P05: legacy mode can process raw DSD pulses as PCM; domain planning is disabled");
    free(input);free(effect);
    return;
  }
  if (spec.combine==LSX_DSD_COMBINE_SEQUENCE && input_count>1 &&
      (current_input==0 || dsd_plan_only)) {
    lsx_dsd_plan_spec part=spec;
    segments=input_count;
    series=lsx_calloc(segments,sizeof(*series));
    for (i=0;i<segments;i++) {
      part.inputs=&input[i];part.input_count=1;
      if (!lsx_dsd_plan_build(&part,&series[i],error,sizeof(error))) {
        lsx_fail("P05 preflight segment %lu: %s",(unsigned long)i,error);
        dsd_free_sequence(series,segments);free(input);free(effect);exit(2);
      }
      if (i && output_method!=sox_multiple &&
          (series[i].output_rate!=series[0].output_rate ||
           series[i].output_channels!=series[0].output_channels ||
           series[i].output_bits!=series[0].output_bits ||
           series[i].output_encoding!=series[0].output_encoding)) {
        lsx_fail("P05 sequence segments disagree on the single output header; select a compatible destination or separate outputs");
        dsd_free_sequence(series,segments);free(input);free(effect);exit(2);
      }
      if (!series[i].executable && !dsd_plan_only) {
        lsx_fail("P05 preflight segment %lu: %s; no output created",(unsigned long)i,
            series[i].unavailable_reason?series[i].unavailable_reason:"unimplemented DSP");
        dsd_free_sequence(series,segments);free(input);free(effect);exit(2);
      }
    }
    active=&series[0];
  } else {
    if (spec.combine==LSX_DSD_COMBINE_SEQUENCE && input_count>1) {
      spec.inputs=&input[current_input];spec.input_count=1;
    }
    if (!lsx_dsd_plan_build(&spec,&plan,error,sizeof(error))) {
      lsx_fail("P05 preflight: %s",error);
      lsx_dsd_plan_free(&plan);free(input);free(effect);exit(2);
    }
  }
  /* Verify format negotiation against the actual selected output handler.
   * A handler adjustment after opening is not an acceptable DSD plan. */
  if (!spec.output_is_null &&
      (has_dsd_input || spec.output_native_capable || has_new_effect)) {
    sox_encodinginfo_t resolved=ofile->encoding;
    unsigned wanted=active->output_channels;
    size_t k;
    sox_bool rate_ok=handler->write_rates==NULL;
    resolved.encoding=active->output_encoding;
    resolved.bits_per_sample=active->output_bits;
    if (handler->write_formats && !sox_format_supports_encoding(
          ofile->filename,ofile->filetype,&resolved)) {
      lsx_fail("P05 preflight: selected endpoint encoding/precision is unsupported by %s",kind);
      if (series) dsd_free_sequence(series,segments);
      else lsx_dsd_plan_free(&plan);
      free(input);free(effect);exit(2);
    }
    if (handler->write_rates) for (k=0;handler->write_rates[k];k++)
      if (handler->write_rates[k]==active->output_rate) rate_ok=sox_true;
    if (!rate_ok || ((handler->flags & SOX_FILE_CHANS) &&
        !((wanted==1 && (handler->flags & SOX_FILE_MONO)) ||
          (wanted==2 && (handler->flags & SOX_FILE_STEREO)) ||
          (wanted==4 && (handler->flags & SOX_FILE_QUAD))))) {
      lsx_fail("P05 preflight: output handler would coerce a planned rate or channel count");
      if (series) dsd_free_sequence(series,segments);
      else lsx_dsd_plan_free(&plan);
      free(input);free(effect);exit(2);
    }
  }
  /* Reuse P04's established layout contract.  This call only constructs
   * metadata and does not open a file or start an effect.  Its temporary
   * WAV permutation is recomputed by the actual output open path. */
  {
    sox_signalinfo_t saved_signal=ofile->signal;
    sox_encodinginfo_t saved_encoding=ofile->encoding;
    sox_dsd_layout_t *layout;
    ofile->signal.channels=active->output_channels;
    ofile->signal.rate=active->output_rate;
    ofile->encoding.encoding=active->output_encoding;
    ofile->encoding.bits_per_sample=active->output_bits;
    layout=dsd_plan_output(ofile->filename,ofile->filetype);
    sox_dsd_layout_free(layout);
    free(dsd_output_permutation);
    dsd_output_permutation=NULL;
    dsd_output_permutation_count=0;
    ofile->signal=saved_signal;
    ofile->encoding=saved_encoding;
  }

  /* The plan is published before starting any DSP or opening the audio header.
   * Sequence reporting contains all independently validated segments. */
  if (dsd_plan_only) {
    /* Planning never opens audio, but publishing its JSON is still a file
     * write: apply the same input/overwrite policy as execution reports. */
    dsd_report_validate_destination();
    if (dsd_report_path && strcmp(dsd_report_path,"-")) {
      report=lsx_fopen(dsd_report_path,"w");
      if (!report) {lsx_fail("cannot open --dsd-report destination");exit(2);}
    } else report=stdout;
    if (series) {
      fputs("{\n  \"schema\": \"sox.dsd.sequence.v1\",\n  \"segments\": [\n",report);
      for (i=0;i<segments;i++) {
        lsx_dsd_plan_spec part=spec;
        part.inputs=&input[i];part.input_count=1;
        lsx_dsd_plan_json(report,&part,&series[i]);
        fputs(i+1<segments?",\n":"\n",report);
      }
      fputs("  ]\n}\n",report);
    } else lsx_dsd_plan_json(report,&spec,active);
    if (report!=stdout && fclose(report)) {lsx_fail("cannot write --dsd-report");exit(2);}
  }
  if (dsd_plan_only) {
    if (series) dsd_free_sequence(series,segments);
    else lsx_dsd_plan_free(&plan);
    free(input);free(effect);
    success=1;exit(0);
  }
  if (!active->executable) {
    lsx_fail("P05 preflight: %s; plan with --dsd-plan (no output created)",
        active->unavailable_reason?active->unavailable_reason:"DSP is not yet implemented");
    if (series) dsd_free_sequence(series,segments);
    else lsx_dsd_plan_free(&plan);
    free(input);free(effect);exit(2);
  }
  if (has_dsd_input || active->output_domain==LSX_DOP_TRANSPORT || active->encode_count) {
    if (active->output_domain==LSX_PCM_AUDIO &&
        !ofile_encoding_options.encoding && !ofile_encoding_options.bits_per_sample &&
        active->output_bits!=24 && !spec.output_is_null)
      lsx_warn("P05: signed 24-bit unavailable; selecting %u-bit PCM encoding %u",
          active->output_bits,(unsigned)active->output_encoding);
    ofile->signal.rate=active->output_rate;
    ofile->signal.channels=active->output_channels;
    if (active->output_bits) ofile->encoding.bits_per_sample=active->output_bits;
    ofile->encoding.encoding=active->output_encoding;
  }
  /* Transfer the executable plan, not a second independently guessed graph.
   * Keep the source format's native signal/encoding untouched. */
  if (dsd_policy.mode==LSX_DSD_MODE_AUTO) {
    size_t k=0,j;
    dsd_runtime_plan=*active;
    memset(active,0,sizeof(*active));
    dsd_runtime_active=sox_true;
    dsd_decode_before=lsx_calloc(spec.effect_count+1,sizeof(*dsd_decode_before));
    dsd_encode_before=lsx_calloc(spec.effect_count+1,sizeof(*dsd_encode_before));
    dsd_consume_leading=dsd_runtime_plan.input_decode_count && spec.effect_count &&
        !strcmp(effect[0].name,"dsdpcm");
    if (dsd_consume_leading) k=1;
    for (j=0;j<dsd_runtime_plan.step_count;j++) {
      char const *name=dsd_runtime_plan.steps[j].name;
      if (!strcmp(name,"implicit_dsdpcm")) ++dsd_decode_before[k];
      else if (!strcmp(name,"implicit_pcmdsd")) dsd_encode_before[k]=j+1;
      else if (k<spec.effect_count && !strcmp(name,effect[k].name)) {
        if (!strcmp(name,"pcmdsd"))
          lsx_pcmdsd_set_reference(user_efftab[k],dsd_runtime_plan.steps[j].reference);
        ++k;
      }
    }
    for (j=0;j<input_count;j++) {
      lsx_dsd_plan_input const *in;
      size_t index=spec.combine==LSX_DSD_COMBINE_SEQUENCE && input_count>1?
          current_input:j;
      if (spec.combine==LSX_DSD_COMBINE_SEQUENCE && input_count>1 && j!=current_input)
        continue;
      in=&dsd_runtime_plan.inputs[spec.combine==LSX_DSD_COMBINE_SEQUENCE &&
          input_count>1?0:index];
      files[j]->dsd_target_hz=in->decoder_before_combiner?
          (uint32_t)in->effective_rate:0;
      files[j]->dsd_profile=spec.policy.decode;
      files[j]->dsd_level=spec.policy.level;
      files[j]->dsd_bandwidth=spec.policy.bandwidth;
      files[j]->dsd_clip=spec.policy.clip;
      if (dsd_consume_leading && in->decoder_before_combiner) {
        files[j]->dsd_profile=effect[0].dsd.profile_specified?
            effect[0].dsd.profile:spec.policy.decode;
        files[j]->dsd_level=effect[0].dsd.level_specified?
            effect[0].dsd.level:spec.policy.level;
      }
    }
    if (dsd_runtime_plan.input_decode_count) {
      combiner_signal.rate=dsd_runtime_plan.combiner_rate;
      combiner_signal.channels=dsd_runtime_plan.combiner_channels;
      combiner_signal.precision=SOX_SAMPLE_PRECISION;
      combiner_signal.length=SOX_UNKNOWN_LEN;
      combiner_encoding.encoding=SOX_ENCODING_SIGN2;
      combiner_encoding.bits_per_sample=32;
    }
    if (dsd_runtime_plan.input_decode_count || dsd_runtime_plan.graph_decode_count ||
        dsd_runtime_plan.encode_count)
      ofile->signal.length=SOX_UNKNOWN_LEN;
  }
  /* Retain authoritative preflight facts without enabling graph routing
   * for the explicit NATIVE mode. */
  if (dsd_report_path && !dsd_plan_only &&
      dsd_policy.mode!=LSX_DSD_MODE_AUTO) {
    dsd_report_plan=*active;
    memset(active,0,sizeof(*active));
  }
  if (series) dsd_free_sequence(series,segments);
  else lsx_dsd_plan_free(&plan);
  free(input);free(effect);
}


/* P14: source statistics are collected at the actual native reader boundary,
 * before volume, the P08 adapter, graph FIR or any mastering bandwidth loss.
 * The hot path is an empty branch when reporting was not selected. */
static int dsd_observe_input(file_t *f,const sox_sample_t *bits,size_t samples)
{
  uint32_t hz;
  if (!dsd_report_active || f->ft->encoding.encoding!=SOX_ENCODING_DSD)
    return 1;
  if (!lsx_dsd_integer_rate(f->ft->signal.rate,&hz) ||
      (samples % f->ft->signal.channels)) return 0;
  if (!f->dsd_source_stats) {
    f->dsd_source_stats=lsx_dsd_stats_create(f->ft->signal.channels,hz,0);
    if (!f->dsd_source_stats) return 0;
  }
  return lsx_dsd_stats_feed(f->dsd_source_stats,bits,
      samples/f->ft->signal.channels);
}

/* Resolve direct stdout and /dev/stdout-style aliases by stream identity.
 * The audio and JSON must never share the same output byte stream. */
static int dsd_path_is_stdout(const char *path)
{
  struct stat stream,path_stat;
  if (!path) return 0;
  if (!strcmp(path,"-")) return 1;
  return !fstat(fileno(stdout),&stream) && !lsx_stat(path,&path_stat) &&
      stream.st_dev==path_stat.st_dev && stream.st_ino==path_stat.st_ino;
}

/* Destination validation is shared by P05 plan-only JSON and P14 execution
 * JSON.  It deliberately does not activate a runtime observer or open files. */
static void dsd_report_validate_destination(void)
{
  struct stat target,source;
  size_t i;
  if (!dsd_report_path) return;
  if (!dsd_plan_only && dsd_path_is_stdout(dsd_report_path) &&
      (!ofile->filename || dsd_path_is_stdout(ofile->filename) ||
       (ofile->ft && dsd_path_is_stdout(ofile->ft->filename)))) {
    lsx_fail("--dsd-report conflicts with audio on stdout; select a separate file");
    exit(2);
  }
  if (!strcmp(dsd_report_path,"-")) return; /* JSON to stdout. */
  if (ofile->filename && !strcmp(dsd_report_path,ofile->filename)) {
    lsx_fail("--dsd-report cannot replace the audio output");exit(2);
  }
  if (!lsx_stat(dsd_report_path,&target)) {
    for (i=0;i<input_count;i++)
      if (files[i]->ft && !lsx_stat(files[i]->ft->filename,&source) &&
          source.st_dev==target.st_dev && source.st_ino==target.st_ino) {
        lsx_fail("--dsd-report cannot overwrite an input carrier");exit(2);
      }
    if (ofile->filename && !lsx_stat(ofile->filename,&source) &&
        source.st_dev==target.st_dev && source.st_ino==target.st_ino) {
      lsx_fail("--dsd-report cannot overwrite the audio output");exit(2);
    }
    if (!overwrite_permitted(dsd_report_path)) {
      lsx_fail("--dsd-report overwrite refused");exit(2);
    }
  }
}

static void dsd_report_preflight_destination(void)
{
  if (!dsd_report_path || dsd_report_active) return;
  dsd_report_validate_destination();
  dsd_report_ctx=lsx_dsd_report_create();
  if (!dsd_report_ctx) {lsx_fail("cannot allocate --dsd-report context");exit(2);}
  lsx_dsd_report_enable(dsd_report_ctx);
  dsd_report_active=sox_true;
}

/* In an ordinary command the output is opened only after P05 planning.
 * Relative spellings such as ./out.dsf and out.dsf can name the same
 * not-yet-existing file. Compare their identities as soon as the audio
 * writer has created the destination, before processing a single sample.
 * Failure uses normal cleanup, which removes the uncompleted output. */
static void dsd_report_check_open_output_alias(void)
{
  struct stat audio,report;
  if (!dsd_report_path || !strcmp(dsd_report_path,"-") ||
      !ofile->ft || !ofile->ft->filename) return;
  if (!lsx_stat(ofile->ft->filename,&audio) &&
      !lsx_stat(dsd_report_path,&report) &&
      audio.st_dev==report.st_dev && audio.st_ino==report.st_ino) {
    lsx_fail("--dsd-report cannot replace the audio output (aliased destination)");
    /* No report may be written during failure cleanup to the same open
     * stream. Cleanup still destroys the observer and unlinks partial audio. */
    dsd_report_active=sox_false;
    exit(2);
  }
}

static int dsd_report_publish(char const *status)
{
  FILE *out;
  size_t i;
  const lsx_dsd_stats **stats;
  sox_dsd_stream_info_t *infos;
  const sox_dsd_layout_t **layouts;
  const sox_format_t **source_formats;
  uint64_t writer_clips=dsd_output_clip_total;
  int ok;
  if (!dsd_report_active || dsd_report_published) return SOX_SUCCESS;
  stats=calloc(input_count?input_count:1,sizeof(*stats));
  infos=calloc(input_count?input_count:1,sizeof(*infos));
  layouts=calloc(input_count?input_count:1,sizeof(*layouts));
  source_formats=calloc(input_count?input_count:1,sizeof(*source_formats));
  if (!stats || !infos || !layouts || !source_formats) {
    free(stats);free(infos);free(layouts);free(source_formats);return SOX_EOF;
  }
  for (i=0;i<input_count;i++) {
    stats[i]=files[i]->dsd_source_stats;
    source_formats[i]=files[i]->ft;
    infos[i].version=1;infos[i].size=sizeof(*infos);
    if (!files[i]->ft ||
        sox_dsd_get_stream_info(files[i]->ft,&infos[i])!=SOX_DSD_OK)
      memset(&infos[i],0,sizeof(*infos));
    if (files[i]->ft) {
      sox_dsd_layout_t *copy=NULL;
      if (sox_dsd_get_layout(files[i]->ft,&copy)==SOX_DSD_OK)
        layouts[i]=copy;
    }
  }
  if (ofile->ft) writer_clips=ofile->ft->clips;
  out=!strcmp(dsd_report_path,"-")?stdout:lsx_fopen(dsd_report_path,"w");
  if (!out) {
    lsx_fail("cannot open --dsd-report destination: %s",strerror(errno));
    ok=SOX_EOF;
  } else {
    lsx_dsd_report_json(out,dsd_report_ctx,
        dsd_runtime_active?&dsd_runtime_plan:
        dsd_report_plan.output_channels?&dsd_report_plan:NULL,stats,input_count,
        infos,layouts,source_formats,output_samples,writer_clips,
        dsd_adapter_clips_total,mixing_clips,status,VERSION);
    ok=ferror(out)?SOX_EOF:SOX_SUCCESS;
    if (out==stdout) {
      if (fflush(out)) ok=SOX_EOF;
    } else if (fclose(out)) ok=SOX_EOF;
    if (ok!=SOX_SUCCESS)
      lsx_fail("failed to write --dsd-report destination");
  }
  for(i=0;i<input_count;i++)sox_dsd_layout_free((sox_dsd_layout_t *)layouts[i]);
  free(stats);free(infos);free(layouts);free(source_formats);
  if (ok==SOX_SUCCESS)dsd_report_published=sox_true;
  return ok;
}

static int process(void)
{         /* Input(s) -> Balancing -> Combiner -> Effects -> Output */
  int flow_status;

  create_user_effects();

  calculate_combiner_signal_parameters();
  set_combiner_and_output_encoding_parameters();
  calculate_output_signal_parameters();
  preflight_dsd();
  dsd_report_preflight_destination();
  open_output_file();
  dsd_report_check_open_output_alias();
  if (dsd_runtime_active &&
      (ofile->ft->signal.rate!=dsd_runtime_plan.output_rate ||
       ofile->ft->signal.channels!=dsd_runtime_plan.output_channels ||
       ofile->ft->encoding.encoding!=dsd_runtime_plan.output_encoding ||
       ofile->ft->encoding.bits_per_sample!=dsd_runtime_plan.output_bits)) {
    lsx_fail("P08: output handler disagrees with preflight domain/rate/channel/encoding");
    exit(2);
  }

  if (!effects_chain)
    effects_chain = sox_create_effects_chain(&combiner_encoding,
                                             &ofile->ft->encoding);
  add_effects(effects_chain);

  if (very_first_effchain)
    optimize_trim();

#if defined(HAVE_TERMIOS_H) || defined(HAVE_CONIO_H)
  if (stdin_is_a_tty) {
    if (show_progress && is_player && !interactive) {
      lsx_debug("automatically entering interactive mode");
      interactive = sox_true;
    }
  } else if (interactive) {
    /* User called for interactive mode, but ... */
    lsx_warn("standard input has to be a terminal for interactive mode");
    interactive = sox_false;
  }
#endif
#ifdef HAVE_TERMIOS_H
  /* Prepare terminal for interactive mode and save the original termios
     settings. Do this only once, otherwise the "original" settings won't
     be original anymore after a second call to process() (next/restarted
     effects chain). */
  if (interactive && !original_termios_saved) {
    struct termios modified_termios;

    original_termios_saved = sox_true;
    tcgetattr(fileno(stdin), &original_termios);
    modified_termios = original_termios;
    modified_termios.c_lflag &= ~(ICANON | ECHO);
    modified_termios.c_cc[VMIN] = modified_termios.c_cc[VTIME] = 0;
    tcsetattr(fileno(stdin), TCSANOW, &modified_termios);
  }
#endif
#if defined(F_GETFL) && defined(F_SETFL) && defined(O_NONBLOCK)
  if (interactive) {
    int fd = fileno(stdin);
    int flags = fcntl(fd, F_GETFL);
    if (flags == -1) {
      lsx_warn("error getting flags on stdin descriptor: %s", strerror(errno));
    } else if (!(flags & O_NONBLOCK)) {
      if (fcntl(fd, F_SETFL, flags | O_NONBLOCK) == -1)
        lsx_warn("error setting non-blocking on stdin: %s", strerror(errno));
    }
  }
#endif

#ifdef TIOCGWINSZ
  get_termwidth(0);
#ifdef SIGWINCH
  setsig(SIGWINCH, get_termwidth);
#endif
#endif

  setsig(SIGTERM, sigint); /* Stop gracefully, as soon as we possibly can. */
  setsig(SIGINT , sigint); /* Either skip current input or behave as SIGTERM. */
  if (very_first_effchain) {
    struct timeval now;
    double d;
    gettimeofday(&now, NULL);
    d = now.tv_sec - load_timeofday.tv_sec + (now.tv_usec - load_timeofday.tv_usec) / TIME_FRAC;
    lsx_debug("start-up time = %g", d);
  }
  flow_status = sox_flow_effects(effects_chain, update_status, NULL);

  /* Don't return SOX_EOF if
   * 1) input reach EOF and there are more input files to process or
   * 2) output didn't return EOF (disk full?) there are more
   *    effect chains.
   * For case #2, something else must decide when to stop processing.
   */
  if (flow_status != LSX_EFF_FATAL &&
      ((input_eof && current_input < input_count) ||
      (!output_eof && current_eff_chain < eff_chain_count)))
    flow_status = SOX_SUCCESS;

  return flow_status;
}

static void display_SoX_version(FILE * file)
{
#if HAVE_SYS_UTSNAME_H
  struct utsname uts;
#endif
  const sox_version_info_t* info = sox_version_info();

#ifdef VERSION
  fprintf(file, "%s:      SoX DSD v%s\n", sox_globals.myname, VERSION);
#else
  fprintf(file, "%s:      SoX DSD v%s%s%s\n",
      sox_globals.myname,
      info->version,
      info->version_extra ? "-" : "",
      info->version_extra ? info->version_extra : "");
#endif

  if (sox_globals.verbosity > 3) {
    if (info->distro)
      fprintf(file, "issue:    %s\n", info->distro);
#if HAVE_SYS_UTSNAME_H
    if (!uname(&uts))
      fprintf(file, "uname:    %s %s %s %s %s\n", uts.sysname, uts.nodename,
          uts.release, uts.version, uts.machine);
#endif
    if (info->compiler)
        fprintf(file, "compiler: %s\n", info->compiler);
    if (info->arch)
        fprintf(file, "arch:     %s\n", info->arch);
  }
}

static int strcmp_p(const void *p1, const void *p2)
{
  return strcmp(*(const char **)p1, *(const char **)p2);
}

static void display_supported_formats(void)
{
  size_t i, formats;
  char const * * format_list;
  char const * const * names;

  sox_format_init();
  for (i = formats = 0; sox_format_fns[i].fn; ++i) {
    char const * const *names = sox_format_fns[i].fn()->names;
    while (*names++)
      formats++;
  }
  lsx_valloc(format_list, formats);

  printf("AUDIO FILE FORMATS:");
  for (i = formats = 0; sox_format_fns[i].fn; ++i) {
    sox_format_handler_t const * handler = sox_format_fns[i].fn();
    if (!(handler->flags & SOX_FILE_DEVICE))
      for (names = handler->names; *names; ++names)
        if (!strchr(*names, '/'))
          format_list[formats++] = *names;
  }
  qsort((void*)format_list, formats, sizeof(*format_list), strcmp_p);
  for (i = 0; i < formats; i++)
    /* Only list duplicates once */
    if (i == 0 || (i > 0 && strcmp(format_list[i], format_list[i - 1])))
      printf(" %s", format_list[i]);
  putchar('\n');

  printf("PLAYLIST FORMATS: m3u pls\nAUDIO DEVICE DRIVERS:");
  for (i = formats = 0; sox_format_fns[i].fn; ++i) {
    sox_format_handler_t const * handler = sox_format_fns[i].fn();
    if ((handler->flags & SOX_FILE_DEVICE) && !(handler->flags & SOX_FILE_PHONY))
      for (names = handler->names; *names; ++names)
        format_list[formats++] = *names;
  }
  qsort((void*)format_list, formats, sizeof(*format_list), strcmp_p);
  for (i = 0; i < formats; i++)
    printf(" %s", format_list[i]);
  putchar('\n');

  free((void*)format_list);
}

static void display_supported_effects(void)
{
  size_t i;
  const sox_effect_handler_t *e;

  printf("EFFECTS:");
  for (i = 0; sox_effect_fns[i]; i++) {
    e = sox_effect_fns[i]();
    if (e && e->name && !(e->flags & SOX_EFF_INTERNAL))
      printf(" %s", e->name);
  }
  putchar('\n');
}

static void usage(void)
{
  const sox_version_info_t * info = sox_version_info();
  size_t i;
  static char const * const lines1[] = {
"SPECIAL FILENAMES (infile, outfile):",
"-                        Pipe/redirect input/output (stdin/stdout); may need -t",
"-d, --default-device     Use the default audio device (where available)",
"-n, --null               Use the `null' file handler; e.g. with synth effect",
"-p, --sox-pipe           Alias for `-t sox -'"
  };
  static char const * const linesPopen[] = {
"\nSPECIAL FILENAMES (infile only):",
"\"|program [options] ...\" Pipe input from external program (where supported)",
"http://server/file       Use the given URL as input file (where supported)"
  };
  static char const * const lines2[] = {
"",
"GLOBAL OPTIONS (gopts) (can be specified at any point before the first effect):",
"--buffer BYTES           Set the size of all processing buffers (default 8192)",
"--clobber                Don't prompt to overwrite output file (default)",
"--no-clobber             Prompt to overwrite output file",
"--combine concatenate    Concatenate all input files (default for sox, rec)",
"--combine sequence       Sequence all input files (default for play)",
"--combine mix, -m        Mix multiple input files",
"--combine mix-power      Mix to equal power",
"--combine merge, -M      Merge multiple input files",
"-D, --no-dither          Don't dither automatically",
"--dft-min NUM            Minimum size (log2) for DFT processing (default 10)",
"--dsd-layout ROLES       Comma-separated output role assignment: FL,FR,FC,LFE,BL,BR,SL,SR,MONO",
"--dsd-layout-loss error|warn  Reject channel-identity loss (default), or warn",
"--dsd-mode auto|native|legacy  Opt in to P08 domain routing; default remains legacy",
"--dsd-decode conservative|mastering|wideband|legacy|decode.mastering.v2.dsd<rate>",
"                         Unpinned auto reconstruction defaults to mastering v2; explicit mastering/conservative select v1",
"--dsd-encode mastering|legacy|experimental|encode.mastering.v1.dsd<rate>",
"                         Mastering encoding is active for native DSD64 to DSD1024; guards remain enforced",
"--dsd-level preserve|sacd  Decoder level convention",
"--dsd-clip warn|error    Graph-boundary clipping policy",
"--dsd-bandwidth adapt|strict  PCM reconstruction passband policy",
"--dsd-report PATH       Write final versioned DSD conversion report (or - for stdout)",
"--dsd-plan              Print preflight JSON and exit before output open",
"--effects-file FILENAME  File containing effects and options",
"-G, --guard              Use temporary files to guard against clipping",
"-h, --help               Display version number and usage information",
"-h NAME                  Show info of effect or format NAME",
"--help-effect NAME       Show usage of effect NAME, or NAME=all for all",
"--help-format NAME       Show info on format NAME, or NAME=all for all",
"--i, --info              Behave as soxi(1)",
"--input-buffer BYTES     Override the input buffer size (default: as --buffer)",
"--interactive            Be interactive (on when playing or with --keymap)",
"--keymap X:effect.param(+|-|*|/|=)N",
"                         When key X is pressed, adjust the effect's parameter",
"                         linearly, logarithmically or set it to a value",
  };
  static char const * const linesMagic[] = {
"--magic                  Use `magic' file-type detection"
  };
  static char const * const linesThreads[] = {
"--multi-threaded         Enable parallel effects channels processing"
  };
  static char const * const lines3[] = {
"--norm                   Guard (see --guard) and normalize",
"--play-rate-arg ARG      Default `rate' argument for auto-resample with `play'",
"--plot gnuplot|octave    Generate script to plot response of filter effect",
"-q, --no-show-progress   Run in quiet mode, the opposite of -S",
"--replay-gain track|album|off  Default: off (sox, rec), track (play)",
"-R                       Use default random numbers (same on each run of SoX)",
"-S, --show-progress      Display progress while processing audio data",
"--multi-threaded         Enable parallel effects channels processing",
"--temp DIRECTORY         Specify the directory to use for temporary files",
"-T, --combine multiply   Multiply samples of corresponding channels from all",
"                         input files (instead of concatenating)",
"--version                Display version number of SoX and exit",
"-V[LEVEL]                Increment or set verbosity level (default 2); levels:",
"                           1: failure messages",
"                           2: warnings",
"                           3: details of processing",
"                           4-6: increasing levels of debug messages",
"FORMAT OPTIONS (fopts):",
"Input file format options need only be supplied for files that are headerless.",
"Output files will have the same format as the input file where possible and not",
"overridden by any of various means including providing output format options.",
"",
"-v|--volume FACTOR       Input file volume adjustment factor (real number)",
"--ignore-length          Ignore input file length given in header; read to EOF",
"-t|--type FILETYPE       File type of audio",
"-e|--encoding ENCODING   Set encoding (ENCODING may be one of signed-integer,",
"                         unsigned-integer, floating-point, mu-law, a-law,",
"                         ima-adpcm, ms-adpcm, gsm-full-rate)",
"-b|--bits BITS           Encoded sample size in bits",
"-N|--reverse-nibbles     Encoded nibble-order",
"-X|--reverse-bits        Encoded bit-order",
"--endian little|big|swap Encoded byte-order; swap means opposite to default",
"-L/-B/-x                 Short options for the above",
"-c|--channels CHANNELS   Number of channels of audio data; e.g. 2 = stereo",
"-r|--rate RATE           Sample rate of audio",
"-C|--compression FACTOR  Compression factor for output format",
"--add-comment TEXT       Append output file comment",
"--comment TEXT           Specify comment text for the output file",
"--comment-file FILENAME  File containing comment text for the output file",
#if HAVE_GLOB_H
"--no-glob                Don't `glob' wildcard match the following filename",
#endif
""};

  if (!(sox_globals.verbosity > 2)) {
    display_SoX_version(stdout);
    putchar('\n');
  }

  printf("Usage summary: [gopts] [[fopts] infile]... [fopts]%s [effect [effopt]]...\n\n",
         sox_mode == sox_play? "" : " outfile");
  for (i = 0; i < array_length(lines1); ++i)
    puts(lines1[i]);
  if (info->flags & sox_version_have_popen)
    for (i = 0; i < array_length(linesPopen); ++i)
      puts(linesPopen[i]);
  for (i = 0; i < array_length(lines2); ++i)
    puts(lines2[i]);
  if (info->flags & sox_version_have_magic)
    for (i = 0; i < array_length(linesMagic); ++i)
      puts(linesMagic[i]);
  if (info->flags & sox_version_have_threads)
    for (i = 0; i < array_length(linesThreads); ++i)
      puts(linesThreads[i]);
  for (i = 0; i < array_length(lines3); ++i)
    puts(lines3[i]);
  display_supported_formats();
  display_supported_effects();
  printf("EFFECT OPTIONS: effect dependent; see --help-effect\n");
}

static int usage_effect(char const * name)
{
  size_t i;

  if (strcmp("all", name) && !sox_find_effect(name)) {
    printf("Cannot find an effect called `%s'\n", name);
    display_supported_effects();
    return SOX_EOF;
  }
  else {
    sox_bool first = sox_true;

    for (i = 0; sox_effect_fns[i]; i++) {
      const sox_effect_handler_t *e = sox_effect_fns[i]();
      if (e && e->name &&
          /* Don't list internal effects in "all" output but do so
           * if they explicitly ask for --help-effect input or output */
          ((!strcmp("all", name) && !(e->flags & SOX_EFF_INTERNAL)) ||
           !strcmp(e->name, name))) {
        char const * * linep;
        if (first) first = sox_false;
        else printf("\n");
        printf("%s %s\n", e->name, e->usage? e->usage : "");
        linep = (char const * *) e->extra_usage;
        if (linep)
          while (*linep)
            printf("  %s\n", *linep++);
        if (e->flags & SOX_EFF_INTERNAL)
          printf("  `%s' is libSoX-only\n", e->name);
      }
    }
  }
  return SOX_SUCCESS;
}

static void usage_format1(sox_format_handler_t const * f)
{
  printf("Format: %s\n", f->names[0]);
  printf("Description: %s\n", f->description);
  if (f->names[1]) {
    char const ** names; /* Local copy of the pointers except the first one */
    char const ** namep; /* Loop variable */
    size_t nitems = 0;

    while (f->names[nitems]) nitems++;
    lsx_valloc(names, nitems);
    nitems--; /* We don't want the first canonical name */
    /* nitems + 1 to copy the terminating NULL */
    memcpy(names, f->names + 1, (nitems + 1) * sizeof(*names));

    qsort((void*)names, nitems, sizeof(*names), strcmp_p);
    printf("Also handles:");
    for (namep = names; *namep; ++namep)
      printf(" %s", *namep);
    putchar('\n');
  }
  if (f->flags & SOX_FILE_CHANS) {
    printf("Channels restricted to:");
    if (f->flags & SOX_FILE_MONO) printf(" mono");
    if (f->flags & SOX_FILE_STEREO) printf(" stereo");
    if (f->flags & SOX_FILE_QUAD) printf(" quad");
    putchar('\n');
  }
  if (f->write_rates) {
    sox_rate_t const * p = f->write_rates;
    printf("Sample rate is restricted to:");
    while (*p)
      printf(" %g", *p++);
    putchar('\n');
  }
  printf("Reads: %s\n", f->read? "yes" : "no");
  if (f->write) {
    if (f->write_formats) {
      sox_encoding_t e;
      unsigned i, s;
#define enc_arg(T) (T)f->write_formats[i++]
      i = 0;
      puts("Writes:");
      /* This looks odd, but the entries in a format's write_formats are, e.g.
       * {ENCODING1, precision1a, precision1b, 0, ENCODING2, precision2, 0, 0}
       * so alternating between sox_encoding_t and unsigned is correct.
       */
      while ((e = enc_arg(sox_encoding_t))) {
        do {
          unsigned prec;
          s = enc_arg(unsigned);
          prec = sox_precision(e, s);
          /* The mp3 format handler sets the precision on startup.
           * Both LAME and Twolame encoders take floating point input
           * (24-bit mantissa + 1-bit sign) but set it to 24.
           */
          if (prec == 0 && (e == SOX_ENCODING_MP1 ||
                            e == SOX_ENCODING_MP2 ||
                            e == SOX_ENCODING_MP3))
            prec = 24;
          if (prec) {
            printf("  ");
            if (s)
              printf("%2u-bit ", s);
            printf("%s (%u-bit precision)\n", sox_encodings_info[e].desc, prec);
          }
        } while (s);
      }
    }
    else puts("Writes: yes");
  }
  else puts("Writes: no");
}

static int usage_format(char const * name)
{
  sox_format_handler_t const * f;
  unsigned i;

  if (strcmp("all", name)) {
    /* Help for just one format */
    if (!(f = sox_find_format(name, sox_false))) {
      printf("Cannot find a format called `%s'\n", name);
      display_supported_formats();
      return SOX_EOF;
    } else {
      usage_format1(f);
    }
  } else {
    /* Help for all formats */
    sox_bool first = sox_true;

    sox_format_init();  /* So it lists dynamic formats; format-specific help
                         * will load the modules if it doesn't find one */
    for (i = 0; sox_format_fns[i].fn; ++i) {
      sox_format_handler_t const * f = sox_format_fns[i].fn();
      if (!(f->flags & SOX_FILE_PHONY)) {
        if (first) first = sox_false;
        else printf("\n");
        usage_format1(f);
      }
    }
  }
  return SOX_SUCCESS;
}

static void read_comment_file(sox_comments_t * comments, char const * const filename)
{
  int c;
  size_t text_length = 100;
  char * text = lsx_malloc(text_length + 1);
  FILE * file = lsx_fopen(filename, "r");

  if (file == NULL) {
    lsx_fail("cannot open comment file `%s'", filename);
    exit(1);
  }
  do {
    size_t i = 0;

    while ((c = getc(file)) != EOF && !strchr("\r\n", c)) {
      if (i == text_length)
        text = lsx_realloc(text, (text_length <<= 1) + 1);
      text[i++] = c;
    }
    if (ferror(file)) {
      lsx_fail("error reading comment file `%s'", filename);
      exit(1);
    }
    if (i) {
      text[i] = '\0';
      sox_append_comment(comments, text);
    }
  } while (c != EOF);

  fclose(file);
  free(text);
}

static char const * const getoptstr =
  "+b:c:de:hk:mnpqr:t:v:xA:BC:DGLMNRSTV::X";

static lsx_option_t const long_options[] = {
  /*
   * The order and position of these must correspond to the numbers
   * in the huge case statement in parse_gopts_and_fopts()
   */
  {"add-comment"     , lsx_option_arg_required, NULL, 0}, /* 0 */
  {"buffer"          , lsx_option_arg_required, NULL, 0},
  {"combine"         , lsx_option_arg_required, NULL, 0},
  {"comment-file"    , lsx_option_arg_required, NULL, 0},
  {"comment"         , lsx_option_arg_required, NULL, 0},
  {"endian"          , lsx_option_arg_required, NULL, 0}, /* 5 */
  {"input-buffer"    , lsx_option_arg_required, NULL, 0},
  {"interactive"     , lsx_option_arg_none    , NULL, 0},
  {"help-effect"     , lsx_option_arg_required, NULL, 0},
  {"help-format"     , lsx_option_arg_required, NULL, 0},
  {"no-glob"         , lsx_option_arg_none    , NULL, 0}, /* 10 */
  {"plot"            , lsx_option_arg_required, NULL, 0},
  {"replay-gain"     , lsx_option_arg_required, NULL, 0},
  {"version"         , lsx_option_arg_none    , NULL, 0},
  {"output"          , lsx_option_arg_required, NULL, 0},
  {"effects-file"    , lsx_option_arg_required, NULL, 0}, /* 15 */
  {"temp"            , lsx_option_arg_required, NULL, 0},
  {"single-threaded" , lsx_option_arg_none    , NULL, 0},
  {"ignore-length"   , lsx_option_arg_none    , NULL, 0},
  {"norm"            , lsx_option_arg_optional, NULL, 0},
  {"magic"           , lsx_option_arg_none    , NULL, 0}, /* 20 */
  {"play-rate-arg"   , lsx_option_arg_required, NULL, 0},
  {"clobber"         , lsx_option_arg_none    , NULL, 0},
  {"no-clobber"      , lsx_option_arg_none    , NULL, 0},
  {"multi-threaded"  , lsx_option_arg_none    , NULL, 0},
  {"dft-min"         , lsx_option_arg_required, NULL, 0}, /* 25 */
  {"dsd-layout"      , lsx_option_arg_required, NULL, 0}, /* 26 */
  {"dsd-layout-loss" , lsx_option_arg_required, NULL, 0}, /* 27 */
  {"dsd-mode"        , lsx_option_arg_required, NULL, 0}, /* 28 */
  {"dsd-decode"      , lsx_option_arg_required, NULL, 0}, /* 29 */
  {"dsd-encode"      , lsx_option_arg_required, NULL, 0}, /* 30 */
  {"dsd-level"       , lsx_option_arg_required, NULL, 0}, /* 31 */
  {"dsd-clip"        , lsx_option_arg_required, NULL, 0}, /* 32 */
  {"dsd-bandwidth"   , lsx_option_arg_required, NULL, 0}, /* 33 */
  {"dsd-report"      , lsx_option_arg_required, NULL, 0}, /* 34 */
  {"dsd-plan"        , lsx_option_arg_none    , NULL, 0}, /* 35 */

  /*
   * These instead are indexed by their letters, which limits the
   * above section to a maximum of 64 entries.
   */
  {"bits"            , lsx_option_arg_required, NULL, 'b'},
  {"channels"        , lsx_option_arg_required, NULL, 'c'},
  {"compression"     , lsx_option_arg_required, NULL, 'C'},
  {"default-device"  , lsx_option_arg_none    , NULL, 'd'},
  {"no-dither"       , lsx_option_arg_none    , NULL, 'D'},
  {"encoding"        , lsx_option_arg_required, NULL, 'e'},
  {"help"            , lsx_option_arg_none    , NULL, 'h'},
  {"keymap"          , lsx_option_arg_required, NULL, 'k'},
  {"null"            , lsx_option_arg_none    , NULL, 'n'},
  {"no-show-progress", lsx_option_arg_none    , NULL, 'q'},
  {"pipe"            , lsx_option_arg_none    , NULL, 'p'},
  {"rate"            , lsx_option_arg_required, NULL, 'r'},
  {"reverse-bits"    , lsx_option_arg_none    , NULL, 'X'},
  {"reverse-nibbles" , lsx_option_arg_none    , NULL, 'N'},
  {"show-progress"   , lsx_option_arg_none    , NULL, 'S'},
  {"type"            , lsx_option_arg_required, NULL, 't'},
  {"volume"          , lsx_option_arg_required, NULL, 'v'},
  {"guard"           , lsx_option_arg_none    , NULL, 'G'},

  {NULL, 0, NULL, 0}
};

static int opt_index(int val)
{
  int i;
  for (i = 0; long_options[i].name; ++i)
    if (long_options[i].val == val)
      return i;
  return -1;
}

static lsx_enum_item const combine_methods[] = {
  LSX_ENUM_ITEM(sox_,sequence)
  LSX_ENUM_ITEM(sox_,concatenate)
  LSX_ENUM_ITEM(sox_,mix)
  {"mix-power", sox_mix_power},
  LSX_ENUM_ITEM(sox_,merge)
  LSX_ENUM_ITEM(sox_,multiply)
  {0, 0}};

enum {ENDIAN_little, ENDIAN_big, ENDIAN_swap};
static lsx_enum_item const endian_options[] = {
  LSX_ENUM_ITEM(ENDIAN_,little)
  LSX_ENUM_ITEM(ENDIAN_,big)
  LSX_ENUM_ITEM(ENDIAN_,swap)
  {0, 0}};

static lsx_enum_item const plot_methods[] = {
  LSX_ENUM_ITEM(sox_plot_,off)
  LSX_ENUM_ITEM(sox_plot_,octave)
  LSX_ENUM_ITEM(sox_plot_,gnuplot)
  LSX_ENUM_ITEM(sox_plot_,data)
  {0, 0}};

enum {
  encoding_signed_integer, encoding_unsigned_integer, encoding_floating_point,
  encoding_ms_adpcm, encoding_ima_adpcm, encoding_oki_adpcm,
  encoding_gsm_full_rate, encoding_u_law, encoding_a_law};

static lsx_enum_item const encodings[] = {
  {"signed-integer", encoding_signed_integer},
  {"unsigned-integer", encoding_unsigned_integer},
  {"floating-point", encoding_floating_point},
  {"ms-adpcm", encoding_ms_adpcm},
  {"ima-adpcm", encoding_ima_adpcm},
  {"oki-adpcm", encoding_oki_adpcm},
  {"gsm-full-rate", encoding_gsm_full_rate},
  {"u-law", encoding_u_law},
  {"mu-law", encoding_u_law},
  {"a-law", encoding_a_law},
  {0, 0}};

static int enum_option(char const * arg, int option_index, lsx_enum_item const * items)
{
  lsx_enum_item const * p = lsx_find_enum_text(arg, items, 0);
  if (p == NULL) {
    size_t len = 1;
    char * set = lsx_malloc(len);
    *set = 0;
    for (p = items; p->text; ++p) {
      set = lsx_realloc(set, len += 2 + strlen(p->text));
      strcat(set, ", "); strcat(set, p->text);
    }
    lsx_fail("--%s: `%s' is not one of: %s.",
        long_options[option_index].name, arg, set + 2);
    free(set);
    exit(1);
  }
  return p->value;
}

static char parse_gopts_and_fopts(file_t * f)
{
  const sox_version_info_t* info = sox_version_info();
  while (sox_true) {
    int c;
    int i; /* sscanf silently accepts negative numbers for %u :( */
    char dummy;     /* To check for extraneous chars in optarg. */

    switch (c=lsx_getopt(&optstate)) {
    case -1:        /* @ one of: file-name, effect name, end of arg-list. */
      return '\0'; /* i.e. not device. */

    /*
     * These numbers correspond to the positions of the long options
     * in long_options[] above
     */
    case 0:         /* Long options with no short equivalent. */
      switch (optstate.lngind) {
      case 0:
        if (optstate.arg)
          sox_append_comment(&f->oob.comments, optstate.arg);
        break;

      case 1:
#define SOX_BUFMIN 32
#define SOX_BUFMAX (1 << 30)  /* 1 GB */
        if (optstate.arg[0] == '-' || sscanf(optstate.arg, "%i %c", &i, &dummy) != 1) {
          lsx_fail("invalid buffer size `%s'", optstate.arg);
          exit(1);
        }
        if (i > SOX_BUFMAX || i < 0) {
          lsx_fail("buffer size `%s' must be <= %d", optstate.arg, SOX_BUFMAX);
          exit(1);
        }
        if (i < SOX_BUFMIN) {
          lsx_fail("buffer size `%s' must be >= %d", optstate.arg, SOX_BUFMIN);
          exit(1);
        }
        sox_globals.bufsiz = i;
        break;

      case 2:
        combine_method = enum_option(optstate.arg, optstate.lngind, combine_methods);
        break;

      case 3:
        sox_append_comment(&f->oob.comments, "");
        read_comment_file(&f->oob.comments, optstate.arg);
        break;

      case 4:
        sox_append_comment(&f->oob.comments, "");
        if (*optstate.arg)
          sox_append_comment(&f->oob.comments, optstate.arg);
        break;

      case 5:
        if (f->encoding.reverse_bytes != sox_option_default || f->encoding.opposite_endian) {
          lsx_fail("only one endian option per file is allowed");
          exit(1);
        }
        switch (enum_option(optstate.arg, optstate.lngind, endian_options)) {
          case ENDIAN_little: f->encoding.reverse_bytes = MACHINE_IS_BIGENDIAN; break;
          case ENDIAN_big: f->encoding.reverse_bytes = MACHINE_IS_LITTLEENDIAN; break;
          case ENDIAN_swap: f->encoding.opposite_endian = sox_true; break;
        }
        break;

      case 6:
        if (optstate.arg[0] == '-' || sscanf(optstate.arg, "%i %c", &i, &dummy) != 1) {
          lsx_fail("invalid buffer size `%s'", optstate.arg);
          exit(1);
        }
        if (i > SOX_BUFMAX || i < 0) {
          lsx_fail("buffer size `%s' must be <= %d", optstate.arg, SOX_BUFMAX);
          exit(1);
        }
        if (i < SOX_BUFMIN) {
          lsx_fail("buffer size `%s' must be >= %d", optstate.arg, SOX_BUFMIN);
          exit(1);
        }
        sox_globals.input_bufsiz = i;
        break;

      case 7:
#if defined(HAVE_TERMIOS_H) || defined(HAVE_CONIO_H)
        interactive = sox_true; break;
#else
        lsx_fail("interactive mode was not enabled at compile time");
        exit(1);
#endif
      case 8: exit(usage_effect(optstate.arg) == SOX_SUCCESS ? 0 : 1); break;
      case 9: exit(usage_format(optstate.arg) == SOX_SUCCESS ? 0 : 1); break;
      case 10: f->no_glob = sox_true; break;
      case 11:
        sox_effects_globals.plot = enum_option(optstate.arg, optstate.lngind, plot_methods);
        break;
      case 12: replay_gain_mode = enum_option(optstate.arg, optstate.lngind, rg_modes); break;
      case 13: display_SoX_version(stdout); exit(0); break;
      case 14: break;
      case 15: effects_filename = lsx_strdup(optstate.arg); break;
      case 16: sox_globals.tmp_path = lsx_strdup(optstate.arg); break;
      case 17: sox_globals.use_threads = sox_false; break;
      case 18: f->signal.length = SOX_IGNORE_LENGTH; break;
      case 19: do_guarded_norm = is_guarded = sox_true;
        if (optstate.arg) norm_level = lsx_strdup(optstate.arg);
        break;
      case 20:
        if (info->flags & sox_version_have_magic)
          sox_globals.use_magic = sox_true;
        else
          lsx_warn("this build of SoX does not include `magic'");
        break;
      case 21: play_rate_arg = lsx_strdup(optstate.arg);
               if (play_rate_arg[0] != '-') {
                   lsx_fail("--play-rate-arg must begin with `-')");
                   exit(1);
               }
               break;
      case 22: no_clobber = sox_false; break;
      case 23: no_clobber = sox_true; break;
      case 24: sox_globals.use_threads = sox_true; break;
      case 25:
        if (sscanf(optstate.arg, "%i %c", &i, &dummy) != 1 || i < 8 || i > 16) {
          lsx_fail("minimum DFT size must be in range 8 to 16");
          exit(1);
        }
        sox_globals.log2_dft_min_size = i;
        break;
      case 26:
        free(dsd_layout_assignment);
        dsd_layout_assignment=lsx_strdup(optstate.arg);
        break;
      case 27:
        if (!strcmp(optstate.arg,"error"))dsd_layout_loss_warn=sox_false;
        else if (!strcmp(optstate.arg,"warn"))dsd_layout_loss_warn=sox_true;
        else {lsx_fail("--dsd-layout-loss must be error or warn");exit(1);}
        break;
      case 28:
        if (!strcmp(optstate.arg,"auto"))dsd_policy.mode=LSX_DSD_MODE_AUTO;
        else if (!strcmp(optstate.arg,"native"))dsd_policy.mode=LSX_DSD_MODE_NATIVE;
        else if (!strcmp(optstate.arg,"legacy"))dsd_policy.mode=LSX_DSD_MODE_LEGACY;
        else {lsx_fail("--dsd-mode must be auto, native or legacy");exit(1);}
        dsd_mode_explicit=sox_true;
        break;
      case 29:
        {
          int profile;
          if (!lsx_dsd_profile_parse(optstate.arg,0,&profile,
                &dsd_policy.decode_pinned_native_hz)) {
            lsx_fail("--dsd-decode requires conservative, mastering, wideband, legacy, or a supported exact versioned decode ID");
            exit(1);
          }
          dsd_policy.decode=(lsx_dsd_decode)profile;
          dsd_policy.decode_specified=1;
          dsd_new_policy_explicit=sox_true;
        }
        break;
      case 30:
        {
          int profile;
          if (!lsx_dsd_profile_parse(optstate.arg,1,&profile,
                &dsd_policy.encode_pinned_native_hz)) {
            lsx_fail("--dsd-encode requires mastering, legacy, experimental, or a supported encode.mastering.v1.dsd* ID");
            exit(1);
          }
          dsd_policy.encode=(lsx_dsd_encode)profile;
          dsd_policy.encode_specified=1;
          dsd_new_policy_explicit=sox_true;
        }
        break;
      case 31:
        if (!strcmp(optstate.arg,"preserve"))dsd_policy.level=LSX_DSD_LEVEL_PRESERVE;
        else if (!strcmp(optstate.arg,"sacd"))dsd_policy.level=LSX_DSD_LEVEL_SACD;
        else {lsx_fail("--dsd-level must be preserve or sacd");exit(1);}
        dsd_policy.level_specified=1;
        dsd_new_policy_explicit=sox_true;break;
      case 32:
        if (!strcmp(optstate.arg,"warn"))dsd_policy.clip=LSX_DSD_CLIP_WARN;
        else if (!strcmp(optstate.arg,"error"))dsd_policy.clip=LSX_DSD_CLIP_ERROR;
        else {lsx_fail("--dsd-clip must be warn or error");exit(1);}
        dsd_new_policy_explicit=sox_true;break;
      case 33:
        if (!strcmp(optstate.arg,"adapt"))dsd_policy.bandwidth=LSX_DSD_BANDWIDTH_ADAPT;
        else if (!strcmp(optstate.arg,"strict"))dsd_policy.bandwidth=LSX_DSD_BANDWIDTH_STRICT;
        else {lsx_fail("--dsd-bandwidth must be adapt or strict");exit(1);}
        dsd_new_policy_explicit=sox_true;break;
      case 34:
        free(dsd_report_path);dsd_report_path=lsx_strdup(optstate.arg);
        dsd_new_policy_explicit=sox_true;break;
      case 35:dsd_plan_only=sox_true;break;
      default:
        lsx_fail("internal error processing long option");
        exit(1);
      }
      break;

    case 'G': is_guarded = sox_true; break;
    case 'm': combine_method = sox_mix; break;
    case 'M': combine_method = sox_merge; break;
    case 'T': combine_method = sox_multiply; break;

    case 'R':                   /* Useful for regression testing. */
      sox_globals.repeatable = sox_true;
      break;

    case 'd': case 'n': case 'p':
      return c;

    case 'h':
      if (optstate.argc < 3) {
        /* Plain -h or --help */
        usage(); exit(0);
      }
      for ( ; optstate.ind < optstate.argc; optstate.ind++) {
        /* --help-effect and --help-format */
        char *arg = optstate.argv[optstate.ind];
        sox_effect_handler_t const *handler;

        if (!strcmp(arg, "all")) {
          lsx_fail("Use --help-format all or --help-effect all");
          exit(1);
        }
        if ((handler = sox_find_effect(arg)) != NULL) {
          (void) usage_effect(arg);
          continue;
        }
        if (sox_find_format(arg, sox_false) != NULL) {
          (void) usage_format(arg);
          continue;
        }
        lsx_fail("Cannot find a format or effect called `%s'", arg);
        display_supported_formats();
        display_supported_effects();
        exit(1);
      }
      exit(0);

    case '?':
      lsx_fail("invalid option `%s'", optstate.argv[optstate.ind]);
      exit(1);

    case 't':
      f->filetype = optstate.arg;
      if (f->filetype[0] == '.')
        f->filetype++;
      break;

    case 'r': {
      char k = 0;
      size_t n = sscanf(optstate.arg, "%lf %c %c", &f->signal.rate, &k, &dummy);
      if (n < 1 || f->signal.rate <= 0 || (n > 1 && k != 'k') || n > 2) {
        lsx_fail("rate value `%s' is not a positive number", optstate.arg);
        exit(1);
      }
      f->signal.rate *= k == 'k'? 1000. : 1.;
      break;
    }

    case 'v':
      if (sscanf(optstate.arg, "%lf %c", &f->volume, &dummy) != 1) {
        lsx_fail("volume value `%s' is not a number", optstate.arg);
        exit(1);
      }
      uservolume = sox_true;
      if (f->volume < 0.0)
        lsx_report("volume adjustment is negative; "
                  "this will result in a phase change");
      break;

    case 'A':
      if (sscanf(optstate.arg, "%f %c", &sox_globals.A4, &dummy) != 1 ||
          /* !isfinite(sox_globals.A4) || */ sox_globals.A4 <= 0) {
        lsx_fail("concert pitch `%s' is not a positive number", optstate.arg);
        exit(1);
      }
      break;

    case 'c':
      if (sscanf(optstate.arg, "%d %c", &i, &dummy) != 1 || i <= 0) {
        lsx_fail("channels value `%s' is not a positive integer", optstate.arg);
        exit(1);
      }
      f->signal.channels = i;
      break;

    case 'C':
      if (sscanf(optstate.arg, "%lf %c", &f->encoding.compression, &dummy) != 1) {
        lsx_fail("compression value `%s' is not a number", optstate.arg);
        exit(1);
      }
      break;

    case 'b':
      if (sscanf(optstate.arg, "%d %c", &i, &dummy) != 1 || i <= 0) {
        lsx_fail("bits value `%s' is not a positive integer", optstate.arg);
        exit(1);
      }
      f->encoding.bits_per_sample = i;
      break;

    case 'e': switch (enum_option(optstate.arg, opt_index('e'), encodings)) {
      case encoding_signed_integer:   f->encoding.encoding = SOX_ENCODING_SIGN2;     break;
      case encoding_unsigned_integer: f->encoding.encoding = SOX_ENCODING_UNSIGNED;  break;
      case encoding_floating_point:   f->encoding.encoding = SOX_ENCODING_FLOAT;     break;
      case encoding_ms_adpcm:         f->encoding.encoding = SOX_ENCODING_MS_ADPCM;  break;
      case encoding_ima_adpcm:        f->encoding.encoding = SOX_ENCODING_IMA_ADPCM; break;
      case encoding_oki_adpcm:        f->encoding.encoding = SOX_ENCODING_OKI_ADPCM; break;
      case encoding_gsm_full_rate:           f->encoding.encoding = SOX_ENCODING_GSM;       break;
      case encoding_u_law: f->encoding.encoding = SOX_ENCODING_ULAW;
        if (f->encoding.bits_per_sample == 0)
          f->encoding.bits_per_sample = 8;
        break;
      case encoding_a_law: f->encoding.encoding = SOX_ENCODING_ALAW;
        if (f->encoding.bits_per_sample == 0)
          f->encoding.bits_per_sample = 8;
        break;
      }
      break;

    case 'L': case 'B': case 'x':
      if (f->encoding.reverse_bytes != sox_option_default || f->encoding.opposite_endian) {
        lsx_fail("only one endian option per file is allowed");
        exit(1);
      }
      switch (c) {
        case 'L': f->encoding.reverse_bytes   = MACHINE_IS_BIGENDIAN;    break;
        case 'B': f->encoding.reverse_bytes   = MACHINE_IS_LITTLEENDIAN; break;
        case 'x': f->encoding.opposite_endian = sox_true;            break;
      }
      break;
    case 'X': f->encoding.reverse_bits    = sox_option_yes;      break;
    case 'N': f->encoding.reverse_nibbles = sox_option_yes;      break;

    case 'S': show_progress = sox_option_yes; break;
    case 'q': show_progress = sox_option_no;  break;
    case 'D': no_dither = sox_true; break;

    case 'V':
      if (optstate.arg == NULL)
        ++sox_globals.verbosity;
      else {
        if (sscanf(optstate.arg, "%d %c", &i, &dummy) != 1 || i < 0) {
          sox_globals.verbosity = 2;
          lsx_fail("verbosity value `%s' is not a non-negative integer", optstate.arg);
          exit(1);
        }
        sox_globals.verbosity = (unsigned)i;
      }
      break;
    case 'k':
      /* --keymap D:dolbyb.gain+2 --keymap d:dolbyb.gain-2 */
      {
        char key[2], *effect, *field;
        char op[2];  /* "+", "-", "*", "/" or "=" */
        double step;
        char dummy; /* Trailing garbage */
        int n;

        n = sscanf(optstate.arg, "%c:%16m[a-z0-9].%16m[_a-z0-9]%1[+*/=-]%lg%c",
                   key, &effect, &field, op, &step, &dummy);
        if (n != 5) {
          lsx_fail("can't parse `%s' as key:effect.field[+-*/=]value; n=%d",
                   optstate.arg, n);
          exit(1);
        }
        key[1] = '\0';

        sox_keymap_add(lsx_strdup(key), effect, field, op[0], step);

        interactive = sox_true;
      }
      break;
    }
  }
}

static char const * device_name(char const * const type)
{
  char * name = NULL, * from_env = getenv("AUDIODEV");

  if (!type)
    return NULL;

  if (0
      || !strcmp(type, "sunau")
      || !strcmp(type, "oss" )
      || !strcmp(type, "ossdsp")
      || !strcmp(type, "alsa")
      || !strcmp(type, "ao")
      || !strcmp(type, "sndio")
      || !strcmp(type, "coreaudio")
      || !strcmp(type, "pulseaudio")
      || !strcmp(type, "waveaudio")
      )
    name = "default";

  return name? from_env? from_env : name : NULL;
}

static char const * try_device(char const * name)
{
  sox_format_handler_t const * handler = sox_find_format(name, sox_false);
  if (handler) {
    sox_format_t format, * ft = &format;
    lsx_debug("Looking for a default device: trying format `%s'", name);
    memset(ft, 0, sizeof(*ft));
    ft->filename = (char *)device_name(name);
    ft->priv = lsx_calloc(1, handler->priv_size);
    if (handler->startwrite(ft) == SOX_SUCCESS) {
      handler->stopwrite(ft);
      free(ft->priv);
      return name;
    }
    free(ft->priv);
  }
  return NULL;
}

static char const * set_default_device(file_t * f)
{
  /* Default audio driver type in order of preference: */
  if (!f->filetype) f->filetype = getenv("AUDIODRIVER");
/* On Windows the only available audio driver is waveaudio
 * but it is not autodetected so force it */
#ifdef _WIN32
  f->filetype = "waveaudio";
#else
  if (!f->filetype) f->filetype = try_device("coreaudio");
  if (!f->filetype) f->filetype = try_device("pulseaudio");
  if (!f->filetype) f->filetype = try_device("alsa");
  if (!f->filetype) f->filetype = try_device("waveaudio");
  if (!f->filetype) f->filetype = try_device("sndio");
  if (!f->filetype) f->filetype = try_device("oss");
  if (!f->filetype) f->filetype = try_device("sunau");
  if (!f->filetype && file_count) /*!rec*/
    f->filetype = try_device("ao");
#endif

  if (!f->filetype) {
    lsx_fail("sorry, there is no default audio device configured");
    exit(1);
  }
  return device_name(f->filetype);
}

static int add_file(file_t const * const opts, char const * const filename)
{
  file_t * f = lsx_malloc(sizeof(*f));

  *f = *opts;
  if (!filename) {
    lsx_fail("missing filename");
    exit(1);
  }
  f->filename = lsx_strdup(filename);
  lsx_revalloc(files, file_count + 1);
  files[file_count++] = f;
  return 0;
}

#if HAVE_GLOB_H
#ifndef GLOB_BRACE
#define GLOB_BRACE 0
#endif
#ifndef GLOB_TILDE
#define GLOB_TILDE 0
#endif
static int add_glob_file(file_t const * const opts, char const * const filename)
{
  glob_t globbuf;
  size_t i;

  if (opts->no_glob)
    return add_file(opts, filename);

  if (glob(filename, GLOB_BRACE | GLOB_TILDE | GLOB_NOCHECK, NULL, &globbuf)) {
    lsx_fail("glob: %s", strerror(errno));
    exit(1);
  }
  for (i = 0; i < globbuf.gl_pathc; ++i)
    add_file(opts, globbuf.gl_pathv[i]);
  globfree(&globbuf);
  return 0;
}
#else
  #define add_glob_file add_file
#endif

static void init_file(file_t * f)
{
  memset(f, 0, sizeof(*f));
  sox_init_encodinginfo(&f->encoding);
  f->volume = HUGE_VAL;
  f->replay_gain = HUGE_VAL;
}

static void parse_options_and_filenames(int argc, char **argv)
{
  char const * env_opts = getenv(SOX_OPTS);
  file_t opts, opts_none;
  init_file(&opts), init_file(&opts_none);

  if (sox_mode == sox_rec)
    add_file(&opts, set_default_device(&opts)), init_file(&opts);

  if (env_opts && *env_opts) {
    char * * argv2, * str = lsx_malloc(strlen(argv[0]) + strlen(env_opts) + 2);
    int argc2;
    strcpy(str, argv[0]);
    strcat(str, " ");
    strcat(str, env_opts);
    argv2 = strtoargv(str, &argc2);
    lsx_getopt_init(argc2, argv2, getoptstr, long_options, lsx_getopt_flag_opterr, 1, &optstate);
    if (parse_gopts_and_fopts(&opts)) {
      lsx_fail("invalid option for "SOX_OPTS);
      exit(1);
    }
    free(str);
    free(argv2);
  }

  lsx_getopt_init(argc, argv, getoptstr, long_options, lsx_getopt_flag_opterr, 1, &optstate);
  for (; optstate.ind < argc && !sox_find_effect(argv[optstate.ind]); init_file(&opts)) {
    char c = parse_gopts_and_fopts(&opts);
    if (c == 'n') { /* is null file? */
      if (opts.filetype != NULL && strcmp(opts.filetype, "null") != 0)
        lsx_warn("ignoring `-t %s'.", opts.filetype);
      opts.filetype = "null";
      add_file(&opts, "");
    }
    else if (c == 'd') /* is default device? */
      add_file(&opts, set_default_device(&opts));
    else if (c == 'p') { /* is sox pipe? */
      if (opts.filetype != NULL && strcmp(opts.filetype, "sox") != 0)
        lsx_warn("ignoring `-t %s'.", opts.filetype);
      opts.filetype = "sox";
      add_file(&opts, "-");
    }
    else if (optstate.ind >= argc || sox_find_effect(argv[optstate.ind]))
      break;
    else if (!sox_is_playlist(argv[optstate.ind]))
      add_glob_file(&opts, argv[optstate.ind++]);
    else if (sox_parse_playlist((sox_playlist_callback_t)add_file, &opts, argv[optstate.ind++]) != SOX_SUCCESS)
      exit(1);
  }
  if (env_opts && *env_opts) {
    lsx_report("using "SOX_OPTS"=%s", env_opts);
    reported_sox_opts = sox_true;
  }
  if (sox_mode == sox_play)
    add_file(&opts, set_default_device(&opts));
  else if (memcmp(&opts, &opts_none, sizeof(opts))) /* fopts but no file */
    add_file(&opts, device_name(opts.filetype));
}

static double soxi_total;
static size_t soxi_file_count;

typedef enum {Full, Type, Rate, Channels, Samples, Duration, Duration_secs,
    Bits, Bitrate, Precision, Encoding, Annotation} soxi_t;

static int soxi1(soxi_t const * type, char const * filename)
{
  sox_format_t * ft = sox_open_read(filename, NULL, NULL, NULL);
  double secs;
  uint64_t ws;
  char const * text = NULL;

  if (!ft)
    return 1;
  ws = ft->signal.length / max(ft->signal.channels, 1);
  secs = (double)ws / max(ft->signal.rate, 1);
  ++soxi_file_count;
  if (soxi_total >= 0 && !ws)
    soxi_total = -2;
  if (soxi_total >= 0) soxi_total += *type == Samples? ws : secs;

  switch (*type) {
    case Type: printf("%s\n", ft->filetype); break;
    case Rate: printf("%g\n", ft->signal.rate); break;
    case Channels: printf("%u\n", ft->signal.channels); break;
    case Samples: if (soxi_total ==-1) printf("%" PRIu64 "\n", ws); break;
    case Duration: if (soxi_total ==-1) printf("%s\n", str_time(secs)); break;
    case Duration_secs: if (soxi_total ==-1) printf("%f\n", secs); break;
    case Bits: printf("%u\n", ft->encoding.bits_per_sample); break;
    case Bitrate: size_and_bitrate(ft, &text); puts(text? text : "0"); break;
    case Precision: printf("%u\n", ft->signal.precision); break;
    case Encoding: printf("%s\n", sox_encodings_info[ft->encoding.encoding].desc); break;
    case Annotation: if (ft->oob.comments) {
      sox_comments_t p = ft->oob.comments;
      do printf("%s\n", *p); while (*++p);
    }
    break;
    case Full: display_file_info(ft, NULL, sox_false); break;
  }
  return !!sox_close(ft);
}

static void soxi_usage(int return_code)
{
  display_SoX_version(stdout);
  printf(
    "\n"
    "Usage: soxi [-V[level]] [-T] [-t|-r|-c|-s|-d|-D|-b|-B|-p|-e|-a] infile1 ...\n"
    "\n"
    "-V[n]\tIncrement or set verbosity level (default is 2)\n"
    "-T\tWith -s, -d or -D, display the total across all given files\n"
    "\n"
    "-t\tShow detected file-type\n"
    "-r\tShow sample-rate\n"
    "-c\tShow number of channels\n"
    ); printf(
    "-s\tShow number of samples (0 if unavailable)\n"
    "-d\tShow duration in hours, minutes and seconds (0 if unavailable)\n"
    "-D\tShow duration in seconds (0 if unavailable)\n"
    "-b\tShow number of bits per sample (0 if not applicable)\n"
    "-B\tShow the bitrate averaged over the whole file (0 if unavailable)\n"
    "-p\tShow estimated sample precision in bits\n"
    "-e\tShow the name of the audio encoding\n"
    "-a\tShow file comments (annotations) if available\n"
    "\n"
    "With no options, as much information as is available is shown for\n"
    "each given file.\n"
    );
  exit(return_code);
}

static int soxi(int argc, char * const * argv)
{
  static char const opts[] = "trcsdDbBpea?TV::";
  soxi_t type = Full;
  int opt, num_errors = 0;
  sox_bool do_total = sox_false;

  if (argc < 2)
    soxi_usage(0);
  lsx_getopt_init(argc, argv, opts, NULL, lsx_getopt_flag_opterr, 1, &optstate);
  while ((opt = lsx_getopt(&optstate)) > 0) /* act only on last option */
    if (opt == 'V') {
      int i; /* sscanf silently accepts negative numbers for %u :( */
      char dummy;     /* To check for extraneous chars in optstate.arg. */
      if (optstate.arg == NULL)
        ++sox_globals.verbosity;
      else {
        if (sscanf(optstate.arg, "%d %c", &i, &dummy) != 1 || i < 0) {
          sox_globals.verbosity = 2;
          lsx_fail("verbosity value `%s' is not a non-negative integer", optstate.arg);
          exit(1);
        }
        sox_globals.verbosity = (unsigned)i;
      }
    }
    else if (opt == 'T')
      do_total = sox_true;
    else if ((type = 1 + (strchr(opts, opt) - opts)) > Annotation)
      soxi_usage(1);

  if (type == Full)
    do_total = sox_true;
  else if (do_total && (type < Samples || type > Duration_secs)) {
    fprintf(stderr, "soxi: ignoring -T; n/a with other given option");
    do_total = sox_false;
  }
  soxi_total = -!do_total;
  for (; optstate.ind < argc; ++optstate.ind) {
    if (sox_is_playlist(argv[optstate.ind]))
      num_errors += (sox_parse_playlist((sox_playlist_callback_t)soxi1, &type, argv[optstate.ind]) != SOX_SUCCESS);
    else num_errors += soxi1(&type, argv[optstate.ind]);
  }
  if (type == Full) {
    if (soxi_file_count > 1 && soxi_total > 0)
      printf("Total Duration of %u files: %s\n", (unsigned)soxi_file_count, str_time(soxi_total));
  }
  else if (do_total) {
    if (soxi_total < 0)
      puts("0");
    else if (type == Duration)
      printf("%s\n", str_time(soxi_total));
    else printf("%f\n", soxi_total);
  }
  return num_errors;
}

static void set_replay_gain(sox_comments_t comments, file_t * f)
{
  rg_mode rg = replay_gain_mode;
  int try = 2; /* Will try to find the other GAIN if preferred one not found */
  size_t i, n = sox_num_comments(comments);

  if (rg != RG_off) while (try--) {
    char const * target =
      rg == RG_track? "REPLAYGAIN_TRACK_GAIN=" : "REPLAYGAIN_ALBUM_GAIN=";
    for (i = 0; i < n; ++i) {
      if (strncasecmp(comments[i], target, strlen(target)) == 0) {
        f->replay_gain = atof(comments[i] + strlen(target));
        f->replay_gain_mode = rg;
        return;
      }
    }
    rg ^= RG_track ^ RG_album;
  }
}

static void output_message(unsigned level, const char *filename, const char *fmt, va_list ap)
{
  char const * const str[] = {"FAIL", "WARN", "INFO", "DBUG"};
  if (sox_globals.verbosity >= level) {
    char base_name[128];
    sox_basename(base_name, sizeof(base_name), filename);
    if (show_progress == sox_option_yes) fprintf(stderr, "\n");
    fprintf(stderr, "%s %s %s: ", sox_globals.myname, str[min(level - 1, 3)], base_name);
    vfprintf(stderr, fmt, ap);
    fprintf(stderr, "\n");
  }
}

static sox_bool cmp_comment_text(char const * c1, char const * c2)
{
  return c1 && c2 && !strcasecmp(c1, c2);
}

#ifdef _WIN32
static int sox_main(int argc, char **argv)
#else
int main(int argc, char **argv)
#endif
{
  size_t i;
  char mybase[8];

  sox_globals.myname = argv[0];
  {
    /* Reduce argv[0] to bare program name for error reports.
     * On Windows, remove .exe too.
     */
#ifdef _WIN32
    char *slash = strrchr(sox_globals.myname, '\\');
    char *dot   = slash ? strrchr(slash, '.') : NULL;
    if (dot) *dot = '\0';
#else
    char *slash = strrchr(sox_globals.myname, '/');
#endif
    if (slash) sox_globals.myname = slash + 1;
  }

  if (argc < 2) { usage(); exit(1); }

  gettimeofday(&load_timeofday, NULL);
  sox_globals.output_message_handler = output_message;

  if (0 != sox_basename(mybase, sizeof(mybase), sox_globals.myname))
  {
    if (0 == lsx_strncasecmp(mybase, "play", 4))
      sox_mode = sox_play;
    else if (0 == lsx_strncasecmp(mybase, "rec", 3))
      sox_mode = sox_rec;
    else if (0 == lsx_strncasecmp(mybase, "soxi", 4))
      sox_mode = sox_soxi;
  }

  if (!sox_mode && argc > 1 &&
      (!strcmp(argv[1], "--i") || !strcmp(argv[1], "--info")))
    --argc, ++argv, sox_mode = sox_soxi;

  if (sox_init() != SOX_SUCCESS)
    exit(1);

  stdin_is_a_tty = isatty(fileno(stdin));
  errno = 0; /* Both isatty & fileno may set errno. */

  atexit(atexit_cleanup);

  if (sox_mode == sox_soxi)
    exit(soxi(argc, argv));

  parse_options_and_filenames(argc, argv);

#if _OPENMP && HAVE_GETENV && HAVE_SETENV && HAVE_EXECVP
  /* Circumvent nasty defect in OpenMP whereby multiple invocations of SoX
   * in parallel become a hundred times slower. Do a lot of careful checking
   * because if OMP_WAITPOLICY isn't set, we'll go into an infinite loop.
   */
  if (sox_globals.use_threads && !getenv("OMP_WAIT_POLICY")) {
    if (setenv("OMP_WAIT_POLICY", "PASSIVE", 0) == 0 &&
        getenv("OMP_WAIT_POLICY") != NULL) {
      argv[argc] = NULL;  /* Make sure it's NULL-terminated */
      lsx_report("execing myself to set OMP_WAIT_POLICY");
      execvp(argv[0], argv);
      lsx_warn("can't exec myself to set OMP_WAIT_POLICY");
    }
  }
#endif

  if (sox_globals.verbosity > 2)
    display_SoX_version(stderr);

  input_count = file_count ? file_count - 1 : 0;

  if (file_count) {
    sox_format_handler_t const * handler =
      sox_write_handler(ofile->filename, ofile->filetype, NULL);
    is_player = handler &&
      (handler->flags & SOX_FILE_DEVICE) && !(handler->flags & SOX_FILE_PHONY);
  }

  if (combine_method == sox_default)
    combine_method = is_player? sox_sequence : sox_concatenate;

  /* Allow e.g. known length processing in this case */
  if (combine_method == sox_sequence && input_count == 1)
    combine_method = sox_concatenate;

  /* Make sure we got at least the required # of input filenames */
  if (input_count < 1) {
    lsx_fail("no input filenames specified. For help say `%s -h'", sox_globals.myname);
    exit(1);
  }

  /* Check for misplaced input/output-specific options */
  for (i = 0; i < input_count; ++i) {
    if (files[i]->encoding.compression != HUGE_VAL) {
      lsx_fail("a compression factor can be given only for an output file");
      exit(1);
    }
    if (files[i]->oob.comments != NULL) {
      lsx_fail("comments can be given only for an output file");
      exit(1);
    }
  }
  if (ofile->volume != HUGE_VAL) {
    lsx_fail("-v can only be given for an input file; use `gain' or `vol'");
    exit(1);
  }
  if (ofile->signal.length != SOX_UNSPEC) {
    lsx_fail("--ignore-length can only be given for an input file");
    exit(1);
  }

  for (i = 0; i < input_count; i++) {
    size_t j;
    file_t * f;

    /* Open in reverse order when recording (see below) */
    j = (sox_mode == sox_rec) ? input_count - 1 - i : i;
    f = files[j];

    /* When mixing audio, default to input side volume adjustments that will
     * make sure no clipping will occur.  Users probably won't be happy with
     * this, and will override it, possibly causing clipping to occur. */
    if (combine_method == sox_mix && !uservolume)
      f->volume = 1.0 / input_count;
    else if (combine_method == sox_mix_power && !uservolume)
      f->volume = 1.0 / sqrt((double)input_count);

    if (sox_mode == sox_rec && !j) {       /* Set the recording parameters: */
      if (input_count > 1) {               /* from the (just openned) next */
        f->signal = files[1]->ft->signal;  /* input file, or from the output */
        f->encoding = files[1]->ft->encoding;
      } else {
        f->signal = files[1]->signal;      /* file (which is not open yet). */
        f->encoding = files[1]->encoding;
      }
    }
    files[j]->ft = sox_open_read(f->filename, &f->signal, &f->encoding, f->filetype);
    if (!files[j]->ft)
      /* sox_open_read() will call lsx_warn for most errors.
       * Rely on that printing something. */
      exit(2);
    if (show_progress == sox_option_default &&
        (files[j]->ft->handler.flags & SOX_FILE_DEVICE) != 0 &&
        (files[j]->ft->handler.flags & SOX_FILE_PHONY) == 0)
      show_progress = sox_option_yes;
  }

  if (replay_gain_mode == RG_default)
    replay_gain_mode = is_player?
      input_count > 1 &&               /* Simple heuristic to determine if */
      cmp_comment_text(                /* replay-gain should be in album mode */
          sox_find_comment(files[0]->ft->oob.comments, "artist"),
          sox_find_comment(files[1]->ft->oob.comments, "artist")) &&
      cmp_comment_text(
          sox_find_comment(files[0]->ft->oob.comments, "album"),
          sox_find_comment(files[1]->ft->oob.comments, "album"))?
      RG_album : RG_track : RG_off;

  for (i = 0; i < input_count; i++)
    set_replay_gain(files[i]->ft->oob.comments, files[i]);

#ifndef _WIN32
  setsig(SIGPIPE, SIG_IGN);
#endif

  /* Loop through the rest of the arguments looking for effects */
  add_eff_chain();
  parse_effects(argc, argv);
  eff_chain_count++;
  /* Note: Purposely not calling add_eff_chain() to save some
   * memory although it would be more consistent to do so.
   */

  /* Not the best way for users to do this; now deprecated in favour of soxi. */
  if (!show_progress && !nuser_effects[current_eff_chain] &&
      ofile->filetype && !strcmp(ofile->filetype, "null")) {
    for (i = 0; i < input_count; i++)
      report_file_info(files[i]);
    exit(0);
  }

  if (!sox_globals.repeatable) {/* Re-seed PRNG? */
    struct timeval now;
    gettimeofday(&now, NULL);
    sox_globals.ranqd1 = (int32_t)(now.tv_sec - now.tv_usec);
  }

  /* Save things that sox_sequence needs to be reinitialized for each segued
   * block of input files.*/
  ofile_signal_options = ofile->signal;
  ofile_encoding_options = ofile->encoding;

  /* If user specified an effects filename then use that file
   * to load user effects.  Free any previously specified options
   * from the command line.
   */
  if (effects_filename)
  {
    read_user_effects(effects_filename);
  }

  {
    int status;
    int finalization_failed = 0;
    /* Inspect fatal flow status before the final-input EOF condition: the
     * last output block can fail after the input counter has advanced. */
    while ((status=process()) != SOX_EOF && !user_abort)
    {
      if (status == LSX_EFF_FATAL) {finalization_failed = 1;break;}
      if (current_input >= input_count) break;
      if (advance_eff_chain() == SOX_EOF)
        break;

      if (!save_output_eff)
      {
        if (close_output_checked() != SOX_SUCCESS) {
          finalization_failed = 1;
          break;
        }
      }
    }
    if (user_abort) finalization_failed = 1;
    sox_delete_effects_chain(effects_chain);
    effects_chain = NULL;
    if (finalization_failed) {
      delete_eff_chains();
      cleanup(); /* On failure, cleanup removes a partial regular output. */
      return 2;
    }
  }
  delete_eff_chains();

  for (i = 0; i < file_count; ++i)
    if (files[i]->ft->clips != 0)
      lsx_warn(i < input_count?"`%s' input clipped %" PRIu64 " samples" :
                              "`%s' output clipped %" PRIu64 " samples; decrease volume?",
          (files[i]->ft->handler.flags & SOX_FILE_DEVICE)?
                       files[i]->ft->handler.names[0] : files[i]->ft->filename,
          (uint64_t)(files[i]->ft->clips));

  if (mixing_clips > 0)
    lsx_warn("mix-combining clipped %" PRIu64 " samples; decrease volume?", mixing_clips);

  for (i = 0; i < file_count; i++)
    if (files[i]->volume_clips > 0)
      lsx_warn("`%s' balancing clipped %" PRIu64 " samples; decrease volume?",
          files[i]->filename, files[i]->volume_clips);

  /* The output file must be closed *after* collecting its clip statistics,
   * but before announcing completion.  A failed close is a failed command. */
  if (ofile->ft && close_output_checked() != SOX_SUCCESS) {
    cleanup();
    return 2;
  }

  /* Final status is published only after the output writer closes cleanly.
   * A reporting failure is a command failure, not a completed conversion. */
  if (dsd_report_publish("complete")!=SOX_SUCCESS) {
    cleanup();
    return 2;
  }
  if (show_progress) {
    if (user_abort)
      fprintf(stderr, "Aborted.\n");
    else if (user_skip && sox_mode != sox_rec)
      fprintf(stderr, "Skipped.\n");
    else
      fprintf(stderr, "Done.\n");
  }

  success = 1; /* Signal success to cleanup so the output file isn't removed. */

  cleanup();

  return 0;
}

#ifdef _WIN32

# ifndef _MSC_VER

#  include <windows.h>

# else

/* Do not include windows.h because of double definition of
 * __timeb64; replace this by local definitions */

#define CP_UTF8 65001
typedef int             BOOL;
typedef const wchar_t*  LPCWSTR;
typedef wchar_t*        LPWSTR;
typedef unsigned int    UINT;

LPWSTR* __stdcall CommandLineToArgvW (LPCWSTR, int*);
LPWSTR  __stdcall GetCommandLineW();
UINT    __stdcall GetConsoleOutputCP (void);
BOOL    __stdcall SetConsoleOutputCP (UINT);
char*             win32_utf16_to_utf8 (const wchar_t*);

# endif

static UINT g_old_output_cp = ((UINT)-1);

static void lsx_init_console(void)
{
  g_old_output_cp = GetConsoleOutputCP();
  SetConsoleOutputCP(CP_UTF8);
}

static void lsx_uninit_console(void)
{
  if(g_old_output_cp != ((UINT)-1)) {
    SetConsoleOutputCP(g_old_output_cp);
  }
}

static void lsx_init_commandline_arguments(int *argc, char ***argv)
{
  int i, nArgs;
  LPWSTR *szArglist;

  szArglist = CommandLineToArgvW(GetCommandLineW(), &nArgs);

  if(NULL == szArglist) {
    fprintf(stderr, "\nFATAL: CommandLineToArgvW failed\n\n");
    exit(-1);
  }

  lsx_valloc(*argv, nArgs);
  *argc = nArgs;

  for(i = 0; i < nArgs; i++)
    (*argv)[i] = win32_utf16_to_utf8(szArglist[i]);

  LocalFree(szArglist);
}

static void lsx_free_commandline_arguments(int *argc, char ***argv)
{
  int i = 0;

  if(*argv != NULL) {
    for(i = 0; i < *argc; i++) {
      if((*argv)[i] != NULL) {
        free((*argv)[i]);
        (*argv)[i] = NULL;
      }
    }
    free(*argv);
    *argv = NULL;
  }
}

int main(void)
{
  int sox_argc;
  char **sox_argv;
  int exit_code;

  lsx_init_console();
  lsx_init_commandline_arguments(&sox_argc, &sox_argv);

  exit_code = sox_main(sox_argc, sox_argv);

  lsx_uninit_console();
  lsx_free_commandline_arguments(&sox_argc, &sox_argv);

  return exit_code;
}

#endif /* _WIN32 */
