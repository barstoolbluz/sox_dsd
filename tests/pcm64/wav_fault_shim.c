/* Linux-only deterministic FD race and stdio fault injections for Phase02A.
 * Compile as -shared -fPIC -ldl; never build into libSoX. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/syscall.h>

/* Write a deterministic trace on the raw syscall path: a test cannot
 * pass its injection case merely because its interposer was not reached. */
static void trace_event(char c)
{
  const char *path=getenv("PCM64_TRACE");
  int fd;
  if (!path) return;
#ifdef SYS_openat
  fd=(int)syscall(SYS_openat,AT_FDCWD,path,O_WRONLY|O_CREAT|O_APPEND,0600);
#else
  fd=open(path,O_WRONLY|O_CREAT|O_APPEND,0600);
#endif
  if (fd>=0) { (void)write(fd,&c,1); close(fd); }
}

static int in_rewrite=0;
static int matches(FILE *stream)
{
  char probe[128], resolved[4096];
  const char *want=getenv("PCM64_TEST_TARGET");
  ssize_t len;
  if (!stream || !want || fileno(stream)<0) return 0;
  snprintf(probe,sizeof(probe),"/proc/self/fd/%d",fileno(stream));
  len=readlink(probe,resolved,sizeof(resolved)-1);
  if (len<0) return 0;
  resolved[len]=0;
  return !strcmp(want,resolved);
}

int open(const char *path,int flags,...)
{
  static int (*real_open)(const char *,int,...) = NULL;
  static int swapped=0;
  const char *swap_path=getenv("PCM64_SWAP_PATH");
  const char *swap_to=getenv("PCM64_SWAP_TO");
  mode_t mode=0;
  if (!real_open) real_open=dlsym(RTLD_NEXT,"open");
  if (flags & O_CREAT) {
    va_list ap;
    va_start(ap,flags);
    mode=(mode_t)va_arg(ap,int);
    va_end(ap);
  }
  if (!swapped && swap_path && swap_to && !strcmp(path,swap_path)) {
    swapped=1;
    trace_event('S');
    unlink(path);
    symlink(swap_to,path); /* changes link and target after approval */
  }
  return real_open(path,flags,mode);
}

/* In a generate call, the probe's stat(path) can see a safe referent,
 * then another actor can retarget the symlink before the writer's first
 * lstat(path).  Exercise this window deterministically. */
int lstat(const char *path, struct stat *st)
{
  static int (*real_lstat)(const char *, struct stat *) = NULL;
  static int swapped = 0;
  const char *path_to_swap=getenv("PCM64_SWAP_BEFORE_APPROVAL_PATH");
  const char *new_target=getenv("PCM64_SWAP_BEFORE_APPROVAL_TO");
  if (!real_lstat) real_lstat=dlsym(RTLD_NEXT,"lstat");
  if (!swapped && path_to_swap && new_target && !strcmp(path,path_to_swap)) {
    swapped=1;
    trace_event('T');
    unlink(path);
    symlink(new_target,path);
  }
  return real_lstat(path,st);
}

FILE *fdopen(int fd,const char *mode)
{
  static FILE *(*real_fdopen)(int,const char *)=NULL;
  if (!real_fdopen) real_fdopen=dlsym(RTLD_NEXT,"fdopen");
  if (getenv("PCM64_FAIL_FDOPEN")) { trace_event('D'); errno=EMFILE;return NULL; }
  return real_fdopen(fd,mode);
}

int setvbuf(FILE *stream,char *buf,int mode,size_t size)
{
  static int (*real_setvbuf)(FILE *,char *,int,size_t)=NULL;
  if (!real_setvbuf) real_setvbuf=dlsym(RTLD_NEXT,"setvbuf");
  if (getenv("PCM64_FAIL_SETVBUF") && matches(stream)) {
    trace_event('V');errno=ENOMEM;return -1;
  }
  return real_setvbuf(stream,buf,mode,size);
}

size_t fread(void *ptr,size_t size,size_t nmemb,FILE *stream)
{
  static size_t (*real_fread)(void *,size_t,size_t,FILE *)=NULL;
  const char *short_read=getenv("PCM64_SHORT_READ");
  const char *off=getenv("PCM64_DATA_OFFSET");
  if (!real_fread) real_fread=dlsym(RTLD_NEXT,"fread");
  if (short_read && matches(stream) && off && ftello(stream)>=atoll(off) &&
      size==1 && nmemb>3) { trace_event('R');nmemb=3; }
  return real_fread(ptr,size,nmemb,stream);
}

size_t fwrite(const void *ptr,size_t size,size_t nmemb,FILE *stream)
{
  static size_t (*real_fwrite)(const void *,size_t,size_t,FILE *)=NULL;
  const char *short_write=getenv("PCM64_SHORT_WRITE");
  const char *off=getenv("PCM64_DATA_OFFSET");
  if (!real_fwrite) real_fwrite=dlsym(RTLD_NEXT,"fwrite");
  static size_t stdout_written=0;
  const char *stdout_limit=getenv("PCM64_FAIL_STDOUT_PAYLOAD_WRITE");
  if (stdout_limit && fileno(stream)==STDOUT_FILENO && size==1 && nmemb>7 &&
      stdout_written >= (size_t)atoll(stdout_limit)) {
    trace_event('P');nmemb=7;
  } else if (getenv("PCM64_FAIL_REWRITE_WRITE") && in_rewrite &&
      matches(stream) && size==1 && nmemb>7) {
    trace_event('J');nmemb=7;
  } else if (short_write && matches(stream) && off && ftello(stream)>=atoll(off) &&
      size==1 && nmemb>7) { trace_event('W');nmemb=7; }
  {
    size_t written=real_fwrite(ptr,size,nmemb,stream);
    if (fileno(stream)==STDOUT_FILENO) stdout_written+=written*size;
    return written;
  }
}

int fclose(FILE *stream)
{
  static int (*real_fclose)(FILE *)=NULL;
  int inject=getenv("PCM64_FAIL_FCLOSE") && matches(stream);
  int rc;
  if (!real_fclose) real_fclose=dlsym(RTLD_NEXT,"fclose");
  rc=real_fclose(stream);
  if (inject) {trace_event('C');errno=EIO;return EOF;}
  return rc;
}

/* Phase 03 finalization fault points. No production source is instrumented.
 * Each site checks the actual retained descriptor rather than a path name,
 * and leaves a trace so an untriggered interposer cannot claim success. */
int fseeko(FILE *stream,off_t offset,int whence)
{
  static int (*real_seek)(FILE *,off_t,int)=NULL;
  off_t old;
  if (!real_seek) real_seek=dlsym(RTLD_NEXT,"fseeko");
  old=ftello(stream);
  if (matches(stream) && whence==SEEK_SET && offset==0 && old>0) {
    if (getenv("PCM64_FAIL_REWRITE_SEEK")) {
      trace_event('H');errno=EIO;return -1;
    }
    in_rewrite=1;
  }
  if (matches(stream) && getenv("PCM64_FAIL_SPARSE_TAIL") &&
      whence==SEEK_CUR && offset==-1) {
    trace_event('Z');errno=EIO;return -1;
  }
  return real_seek(stream,offset,whence);
}
int fflush(FILE *stream)
{
  static int (*real_flush)(FILE *)=NULL;
  if (!real_flush) real_flush=dlsym(RTLD_NEXT,"fflush");
  if (matches(stream) && getenv("PCM64_FAIL_FINAL_FLUSH")) {
    trace_event('F');errno=EIO;return EOF;
  }
  return real_flush(stream);
}
