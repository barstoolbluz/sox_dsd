/* Test-only Linux interposer: pause a report writer after fdopen succeeds,
 * before it can publish JSON. The parent can close its FIFO reader and then
 * resume the child, so SIGPIPE handling is tested without a scheduling race.
 * Never linked into SoX or its libraries. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>

FILE *fdopen(int fd, const char *mode)
{
  typedef FILE *(*fdopen_fn)(int, const char *);
  static fdopen_fn next;
  FILE *stream;
  struct stat st;
  if (!next) next = (fdopen_fn)dlsym(RTLD_NEXT, "fdopen");
  if (!next) return NULL;
  stream = next(fd, mode);
  if (stream && getenv("SOX_PCM64_STOP_REPORT_FIFO") &&
      !fstat(fd, &st) && S_ISFIFO(st.st_mode))
    raise(SIGSTOP);
  return stream;
}
