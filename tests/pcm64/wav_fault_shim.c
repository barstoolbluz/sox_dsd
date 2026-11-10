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
    unlink(path);
    symlink(swap_to,path); /* changes link and target after approval */
  }
  return real_open(path,flags,mode);
}

FILE *fdopen(int fd,const char *mode)
{
  static FILE *(*real_fdopen)(int,const char *)=NULL;
  if (!real_fdopen) real_fdopen=dlsym(RTLD_NEXT,"fdopen");
  if (getenv("PCM64_FAIL_FDOPEN")) { errno=EMFILE;return NULL; }
  return real_fdopen(fd,mode);
}

int setvbuf(FILE *stream,char *buf,int mode,size_t size)
{
  static int (*real_setvbuf)(FILE *,char *,int,size_t)=NULL;
  if (!real_setvbuf) real_setvbuf=dlsym(RTLD_NEXT,"setvbuf");
  if (getenv("PCM64_FAIL_SETVBUF") && matches(stream)) {
    errno=ENOMEM;return -1;
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
      size==1 && nmemb>3) nmemb=3;
  return real_fread(ptr,size,nmemb,stream);
}

size_t fwrite(const void *ptr,size_t size,size_t nmemb,FILE *stream)
{
  static size_t (*real_fwrite)(const void *,size_t,size_t,FILE *)=NULL;
  const char *short_write=getenv("PCM64_SHORT_WRITE");
  const char *off=getenv("PCM64_DATA_OFFSET");
  if (!real_fwrite) real_fwrite=dlsym(RTLD_NEXT,"fwrite");
  if (short_write && matches(stream) && off && ftello(stream)>=atoll(off) &&
      size==1 && nmemb>7) nmemb=7;
  return real_fwrite(ptr,size,nmemb,stream);
}

int fclose(FILE *stream)
{
  static int (*real_fclose)(FILE *)=NULL;
  int inject=getenv("PCM64_FAIL_FCLOSE") && matches(stream);
  int rc;
  if (!real_fclose) real_fclose=dlsym(RTLD_NEXT,"fclose");
  rc=real_fclose(stream);
  if (inject) {errno=EIO;return EOF;}
  return rc;
}
