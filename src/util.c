/* General purpose, i.e. non SoX specific, utility functions.
 * Copyright (c) 2007-8 robs@users.sourceforge.net
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

#include "sox_i.h"
#include <ctype.h>
#if HAVE_PIPE && HAVE_FORK
#include <unistd.h>
#include <sys/wait.h>
#include <pthread.h>
#include <signal.h>
#endif
#ifdef _WIN32
#include <windows.h>
#endif

/* Track only streams created by lsx_popen.  A fork/exec pipe must be waited
 * with waitpid(), never passed to libc pclose(); on Windows and other
 * no-fork platforms libc popen streams must still use pclose().
 * Entries are removed before closing a stream so a recycled FILE* cannot
 * accidentally inherit a previous child's identity. */
typedef struct lsx_child_pipe {
  FILE *stream;
#if HAVE_PIPE && HAVE_FORK
  pid_t pid;
#endif
  struct lsx_child_pipe *next;
} lsx_child_pipe;

static lsx_child_pipe *lsx_child_pipes;
#if HAVE_PIPE && HAVE_FORK
static pthread_mutex_t lsx_child_pipes_lock = PTHREAD_MUTEX_INITIALIZER;
#define LSX_PIPE_LOCK()   (void)pthread_mutex_lock(&lsx_child_pipes_lock)
#define LSX_PIPE_UNLOCK() (void)pthread_mutex_unlock(&lsx_child_pipes_lock)
#elif defined(_WIN32)
static SRWLOCK lsx_child_pipes_lock = SRWLOCK_INIT;
#define LSX_PIPE_LOCK()   AcquireSRWLockExclusive(&lsx_child_pipes_lock)
#define LSX_PIPE_UNLOCK() ReleaseSRWLockExclusive(&lsx_child_pipes_lock)
#else
/* No-fork POSIX builds with popen() still use the libc stream association.
 * These targets historically have no cross-thread process API. */
#define LSX_PIPE_LOCK()   ((void)0)
#define LSX_PIPE_UNLOCK() ((void)0)
#endif

static void lsx_track_child_pipe(FILE *stream,
#if HAVE_PIPE && HAVE_FORK
                                 pid_t pid
#else
                                 int unused LSX_UNUSED
#endif
)
{
  lsx_child_pipe *entry = lsx_malloc(sizeof(*entry));
  entry->stream = stream;
#if HAVE_PIPE && HAVE_FORK
  entry->pid = pid;
#endif
  LSX_PIPE_LOCK();
  entry->next = lsx_child_pipes;
  lsx_child_pipes = entry;
  LSX_PIPE_UNLOCK();
}

int lsx_is_child_pipe(FILE *stream)
{
  lsx_child_pipe *entry;
  int found = 0;
  if (!stream) return 0;
  LSX_PIPE_LOCK();
  for (entry = lsx_child_pipes; entry; entry = entry->next)
    if (entry->stream == stream) { found = 1; break; }
  LSX_PIPE_UNLOCK();
  return found;
}

/* Abort only children this library still owns, and only after the caller
 * has decided the transport cannot complete. SIGKILL prevents a stalled or
 * endless producer from holding the subsequent waitpid() indefinitely. */
void lsx_abort_child_pipe(FILE *stream)
{
#if HAVE_PIPE && HAVE_FORK
  lsx_child_pipe *entry;
  if (!stream) return;
  LSX_PIPE_LOCK();
  for (entry = lsx_child_pipes; entry; entry = entry->next)
    if (entry->stream == stream) {
      (void)kill(entry->pid, SIGKILL);
      break;
    }
  LSX_PIPE_UNLOCK();
#else
  (void)stream;
#endif
}

/* libc_pipe is true for user-provided `|command' streams; false for ordinary
 * file streams. Both cases may also hold an lsx_popen-owned child stream. */
int lsx_close_pipe_or_file(FILE *stream, int libc_pipe)
{
  lsx_child_pipe **link, *entry = NULL;
  if (!stream) return 0;
  LSX_PIPE_LOCK();
  for (link = &lsx_child_pipes; *link; link = &(*link)->next) {
    if ((*link)->stream == stream) {
      entry = *link;
      *link = entry->next;
      break;
    }
  }
  LSX_PIPE_UNLOCK();
  if (entry) {
#if HAVE_PIPE && HAVE_FORK
    int status = 0, close_errno = 0, wait_error = 0;
    pid_t child = entry->pid;
    if (fclose(stream)) close_errno = errno;
    free(entry);
    /* EINTR must not turn a live downloader into an orphan. */
    while (waitpid(child, &status, 0) < 0) {
      if (errno == EINTR) continue;
      wait_error = errno;
      break;
    }
    if (close_errno || wait_error) {
      errno = close_errno ? close_errno : wait_error;
      return -1;
    }
    return status; /* native pclose() wait-status contract */
#else
    free(entry);
# if HAVE_POPEN
    return pclose(stream);
# else
    return fclose(stream);
# endif
#endif
  }
#if HAVE_POPEN
  if (libc_pipe) return pclose(stream);
#else
  (void)libc_pipe;
#endif
  return fclose(stream);
}

int lsx_strcasecmp(const char * s1, const char * s2)
{
#if defined(HAVE_STRCASECMP)
  return strcasecmp(s1, s2);
#elif defined(_MSC_VER)
  return _stricmp(s1, s2);
#else
  while (*s1 && (toupper((int)*s1) == toupper((int)*s2)))
    s1++, s2++;
  return toupper((int)*s1) - toupper((int)*s2);
#endif
}

int lsx_strncasecmp(char const * s1, char const * s2, size_t n)
{
#if defined(HAVE_STRCASECMP)
  return strncasecmp(s1, s2, n);
#elif defined(_MSC_VER)
  return _strnicmp(s1, s2, n);
#else
  while (--n && *s1 && (toupper((int)*s1) == toupper((int)*s2)))
    s1++, s2++;
  return toupper((int)*s1) - toupper((int)*s2);
#endif
}

/* A version of strtod() that disallows NaN which tends to provoke FPE.
 * Some versions of Linux fail on strings beginning with '+'
 * according to AC_FUNC_STRTOD() */
#undef strtod
double lsx_strtod(char const *nptr, char **endptr)
{
  char *orig_nptr = (char *)nptr;
  char *string = " +69";
  char *term = (char *)nptr;
  double value;

  /* Check for broken strtod */
  value = strtod(string, &term);
  if (value != 69 || term != string + 4) {
    while (*nptr == ' ') nptr++;
    if (*nptr == '+') nptr++;
  }

  /* The proper conversion */
  value = strtod(nptr, &term);
  if (term == nptr || isnan(value)) {
    if (endptr) *endptr = orig_nptr;
    return 0;
  }

  if (endptr) *endptr = term;
  return value;
}

/* A version of sscanf() that disallows infinites and NaNs.
 * Infinities could in theory be useful, like for dB levels,
 * but NaNs tend to provoke Floating Point Exceptions.
 *
 * Almost all uses of sscanf for floating point values start with %f or %lf
 * with one " %lg" in dat.c (reading textual FP sample values)
 * and one "%f,%f,%f" in synth.c, which can check for itself.
 */
int lsx_sscanf(const char *str, const char *format, ...)
{
  va_list va, va2;
  int retval;

  va_start(va, format);
#ifdef va_copy
  va_copy(va2, va);
#else
 /* "Some systems that do not supply va_copy() have __va_copy instead,
  * since that was the name used in the draft proposal. */
# ifdef __va_copy
  __va_copy(va2, va);
# else
  /* Generic fallback */
  memcpy(&va2, &va, sizeof(va_list));
# endif
#endif
  retval = vsscanf(str, format, va);

  /* float */
  if (retval > 0 && format[0] == '%' && format[1] == 'f') {
    float *ptr = va_arg(va2, float *);
    if (isnan(*ptr)) retval = 0;
  }

  /* double */
  if (retval > 0 && format[0] == '%' && format[1] == 'l' && format[2] == 'f') {
    double *ptr = va_arg(va2, double *);
    if (isnan(*ptr)) retval = 0;
  }

  va_end(va);
  return retval;
}

sox_bool lsx_strends(char const * str, char const * end)
{
  size_t str_len = strlen(str), end_len = strlen(end);
  return str_len >= end_len && !strcmp(str + str_len - end_len, end);
}

char const * lsx_find_file_extension(char const * pathname)
{
  /* First, chop off any path portions of filename.  This
   * prevents the next search from considering that part. */
  char const * result = LAST_SLASH(pathname);
  if (!result)
    result = pathname;

  /* Now look for an filename extension */
  result = strrchr(result, '.');
  if (result)
    ++result;
  return result;
}

lsx_enum_item const * lsx_find_enum_text(char const * text, lsx_enum_item const * enum_items, int flags)
{
  lsx_enum_item const * result = NULL; /* Assume not found */
  sox_bool sensitive = !!(flags & lsx_find_enum_item_case_sensitive);

  while (enum_items->text) {
    if ((!sensitive && !lsx_strcasecmp(text, enum_items->text)) ||
        ( sensitive && !    strcmp(text, enum_items->text)))
      return enum_items;    /* Found exact match */
    if ((!sensitive && !lsx_strncasecmp(text, enum_items->text, strlen(text))) ||
        ( sensitive && !    strncmp(text, enum_items->text, strlen(text)))) {
      if (result != NULL && result->value != enum_items->value)
        return NULL;        /* Found ambiguity */
      result = enum_items;  /* Found sub-string match */
    }
    ++enum_items;
  }
  return result;
}

lsx_enum_item const * lsx_find_enum_value(unsigned value, lsx_enum_item const * enum_items)
{
  for (;enum_items->text; ++enum_items)
    if (value == enum_items->value)
      return enum_items;
  return NULL;
}

int lsx_enum_option(int c, char const * arg, lsx_enum_item const * items)
{
  lsx_enum_item const * p = lsx_find_enum_text(arg, items, sox_false);
  if (p == NULL) {
    size_t len = 1;
    char * set = lsx_malloc(len);
    *set = 0;
    for (p = items; p->text; ++p) {
      set = lsx_realloc(set, len += 2 + strlen(p->text));
      strcat(set, ", "); strcat(set, p->text);
    }
    lsx_fail("-%c: `%s' is not one of: %s.", c, arg, set + 2);
    free(set);
    return INT_MAX;
  }
  return p->value;
}

char const * lsx_sigfigs3(double number)
{
  static char const symbols[] = "\0kMGTPEZY";
  static char string[16][10];   /* FIXME: not thread-safe */
  static unsigned n;            /* ditto */
  unsigned a, b, c;
  sprintf(string[n = (n+1) & 15], "%#.3g", number);
  switch (sscanf(string[n], "%u.%ue%u", &a, &b, &c)) {
    case 2: if (b) return string[n]; /* Can fall through */ goto one;
    case 1: one: c = 2; break;
    case 3: a = 100*a + b; break;
  }
  if (c < array_length(symbols) * 3 - 3) switch (c%3) {
    case 0: sprintf(string[n], "%u.%02u%c", a/100,a%100, symbols[c/3]); break;
    case 1: sprintf(string[n], "%u.%u%c"  , a/10 ,a%10 , symbols[c/3]); break;
    case 2: sprintf(string[n], "%u%c"     , a          , symbols[c/3]); break;
  }
  return string[n];
}

char const * lsx_sigfigs3p(double percentage)
{
  static char string[16][10];
  static unsigned n;
  sprintf(string[n = (n+1) & 15], "%.1f%%", percentage);
  if (strlen(string[n]) < 5)
    sprintf(string[n], "%.2f%%", percentage);
  else if (strlen(string[n]) > 5)
    sprintf(string[n], "%.0f%%", percentage);
  return string[n];
}

int lsx_open_dllibrary(
  int show_error_on_failure,
  const char* library_description,
  const char* const library_names[] UNUSED,
  const lsx_dlfunction_info func_infos[],
  lsx_dlptr selected_funcs[],
  lsx_dlhandle* pdl)
{
  int failed = 0;
  lsx_dlhandle dl = NULL;

  /* Track enough information to give a good error message about one failure.
   * Let failed symbol load override failed library open, and let failed
   * library open override missing static symbols.
   */
  const char* failed_libname = NULL;
  const char* failed_funcname = NULL;

#ifdef HAVE_LIBLTDL
  if (library_names && library_names[0])
  {
    const char* const* libname;
    if (lt_dlinit())
    {
      lsx_fail(
        "Unable to load %s - failed to initialize ltdl.",
        library_description);
      return 1;
    }

    for (libname = library_names; *libname; libname++)
    {
      lsx_debug("Attempting to open %s (%s)", library_description, *libname);
      dl = lt_dlopenext(*libname);
      if (dl)
      {
        size_t i;
        lsx_debug("Opened %s (%s)", library_description, *libname);
        for (i = 0; func_infos[i].name; i++)
        {
          union {lsx_dlptr fn; lt_ptr ptr;} func;
          func.ptr = lt_dlsym(dl, func_infos[i].name);
          selected_funcs[i] = func.fn ? func.fn : func_infos[i].stub_func;
          if (!selected_funcs[i])
          {
            lt_dlclose(dl);
            dl = NULL;
            failed_libname = *libname;
            failed_funcname = func_infos[i].name;
            lsx_debug("Cannot use %s (%s) - missing function \"%s\"", library_description, failed_libname, failed_funcname);
            break;
          }
        }

        if (dl)
          break;
      }
      else if (!failed_libname)
      {
        failed_libname = *libname;
      }
    }

    if (!dl)
      lt_dlexit();
  }
#endif /* HAVE_LIBLTDL */

  if (!dl)
  {
    size_t i;
    for (i = 0; func_infos[i].name; i++)
    {
      selected_funcs[i] =
          func_infos[i].static_func
          ? func_infos[i].static_func
          : func_infos[i].stub_func;
      if (!selected_funcs[i])
      {
        if (!failed_libname)
        {
          failed_libname = "static";
          failed_funcname = func_infos[i].name;
        }

        failed = 1;
        break;
      }
    }
  }

  if (failed)
  {
    size_t i;
    for (i = 0; func_infos[i].name; i++)
      selected_funcs[i] = NULL;
#ifdef HAVE_LIBLTDL
#define LTDL_MISSING ""
#else
#define LTDL_MISSING " (Dynamic library support not configured.)"
#endif /* HAVE_LIBLTDL */
    if (failed_funcname)
    {
      if (show_error_on_failure)
        lsx_fail(
          "Unable to load %s (%s) function \"%s\"." LTDL_MISSING,
          library_description,
          failed_libname,
          failed_funcname);
      else
        lsx_report(
          "Unable to load %s (%s) function \"%s\"." LTDL_MISSING,
          library_description,
          failed_libname,
          failed_funcname);
    }
    else if (failed_libname)
    {
      if (show_error_on_failure)
        lsx_fail(
          "Unable to load %s (%s)." LTDL_MISSING,
          library_description,
          failed_libname);
      else
        lsx_report(
          "Unable to load %s (%s)." LTDL_MISSING,
          library_description,
          failed_libname);
    }
    else
    {
      if (show_error_on_failure)
        lsx_fail(
          "Unable to load %s - no dynamic library names selected." LTDL_MISSING,
          library_description);
      else
        lsx_report(
          "Unable to load %s - no dynamic library names selected." LTDL_MISSING,
          library_description);
    }
  }

  *pdl = dl;
  return failed;
}

void lsx_close_dllibrary(
  lsx_dlhandle dl UNUSED)
{
#ifdef HAVE_LIBLTDL
  if (dl)
  {
    lt_dlclose(dl);
    lt_dlexit();
  }
#endif /* HAVE_LIBLTDL */
}

/* Our own version of popen() that doesn't use the shell, adapted from
 * android.googlesource.com/platform/bionic/+/3884bfe/libc/unistd/popen.c
 * derived from software written by Ken Arnold and published in
 * UNIX Review, Vol. 6, No. 8.
 */

FILE * lsx_popen(char ** argv, char type,
#if (HAVE_PIPE && HAVE_FORK) || !HAVE_POPEN
LSX_UNUSED
#endif
                 int filename_index)
{
#if HAVE_PIPE && HAVE_FORK
  FILE *iop;
  int pdes[2];
  pid_t child;
#elif HAVE_POPEN
  FILE *iop;
  char *quoted_filename;
  char *p, *q;
  char *command;
  char *filename = argv[filename_index];
  size_t filename_len;
  int nchars;
  int i;
#endif
  char mode[3];

  mode[0] = type;
#ifdef _WIN32
  mode[1] = 'b'; mode[2] = '\0';
#else
  mode[1] = '\0';
#endif

#if HAVE_PIPE && HAVE_FORK
  if (type != 'r' && type != 'w') {
    errno = EINVAL;
    return NULL;
  }
  if (pipe(pdes) < 0) {
    return NULL;
  }
  child = fork();
  switch (child) {
    int i;

  case -1:      /* Error. */
    close(pdes[0]);
    close(pdes[1]);
    return NULL;

  case 0:        /* Child. */
    /* Close all other file descriptors except
     * stdin, in case the input file is "-" and
     * stderr in case the program spouts errors.
     * stdout will be closed by dup2().
     */
    for (i=3; ; i++) {
      if (i == pdes[0] || i == pdes[1]) continue;
      if (close(i) != 0) break;
    }
    if (type == 'r') {
      close(pdes[0]);
      if (pdes[1] != 1) {
        dup2(pdes[1], 1);
        close(pdes[1]);
      }
    } else {
      close(pdes[1]);
      if (pdes[0] != 0) {
        dup2(pdes[0], 0);
        close(pdes[0]);
      }
    }
    execvp(argv[0], argv);
    _exit(127);
    /* NOTREACHED */
  }
  /* In the parent, retain the exact child PID until the matching close. */
  if (type == 'r') {
    close(pdes[1]);
    iop = fdopen(pdes[0], mode);
    if (!iop) close(pdes[0]);
  } else {
    close(pdes[0]);
    iop = fdopen(pdes[1], mode);
    if (!iop) close(pdes[1]);
  }
  if (!iop) {
    int saved_errno = errno, status;
    while (waitpid(child, &status, 0) < 0 && errno == EINTR) {}
    errno = saved_errno;
    return NULL;
  }
  lsx_track_child_pipe(iop, child);
  return iop;

#elif HAVE_POPEN

  /* Quote special characters in the filename. */
  /* On Unix, single quote the complete filename.  An embedded single quote
   * needs four extra characters: close quote, escaped quote, open quote.
   * Windows uses the existing escape syntax and can require one escape per
   * input character. */
  filename_len = strlen(filename);
  if (filename_len > ((size_t)-1 - 3) / 4) {
    errno = EOVERFLOW;
    return NULL;
  }
  quoted_filename = lsx_malloc(filename_len * 4 + 3);
#ifdef _WIN32
  /* popen() hands the command to cmd.exe, but cmd is not the only thing that
   * splits it up: after cmd is done, the child's own C runtime parses what is
   * left into argv, and it splits on unquoted whitespace all over again.
   *
   * Escaping a space with ^ only satisfies the first of those. The caret is
   * consumed by cmd, and the child then sees a bare space and splits there,
   * so ffmpeg reading `my file.m4a' is handed `my' and `file.m4a' as two
   * arguments, opens neither, and writes nothing -- which reaches SoX as
   * "premature EOF" rather than as an error.
   *
   * Double quotes are understood by both, so quote the whole name instead.
   * Windows filenames cannot contain " < > | ? * so there is nothing inside
   * that needs escaping, with one exception: a run of backslashes just before
   * the closing quote would escape it, so those are doubled.
   *
   * Not fixed here: cmd expands %VAR% inside double quotes too, and there is
   * no way to escape a percent sign on a command line, only in a batch file.
   * A filename containing one will still fail.
   */
  q = quoted_filename;
  *q++ = '"';
  for (p = filename; *p; p++)
    *q++ = *p;
  for (p = filename + filename_len; p > filename && p[-1] == '\\'; p--)
    *q++ = '\\';
  *q++ = '"';
  *q = '\0';
#else
  q = quoted_filename;
  *q++ = '\'';
  for (p=filename; *p; ++p) {
    if (*p == '\'') {
      *q++ = '\'';
      *q++ = '\\';
      *q++ = '\'';
      *q++ = '\'';
    } else
      *q++ = *p;
  }
  *q++ = '\'';
  *q = '\0';
#endif

  argv[filename_index] = quoted_filename;

  /* Make a command-line from the argv list */
  nchars = 0;
  for (i=0; argv[i]; i++) nchars += strlen(argv[i]) + 1;
  nchars++; /* and a nul */
  command = lsx_malloc(nchars); *command = '\0';
  for (i=0; argv[i]; i++) {
    if (i > 0) strcat(command, " ");
    strcat(command, argv[i]);
  }
  free(quoted_filename);
  iop = popen(command, mode);
  free(command);
  if (iop) lsx_track_child_pipe(iop, 0);
  return iop;

#else

  lsx_fail("this build of SoX can't open programs on a pipe");
  return NULL;

#endif
}
