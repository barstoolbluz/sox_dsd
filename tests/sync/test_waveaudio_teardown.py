#!/usr/bin/env python3
"""Compile and run exact production waveOut drain/stop bodies with WinMM shims.

This is a deterministic failure-ownership probe, NOT a native Windows proof.
A native Windows/MSVC build and hardware qualification remain required.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

PREFIX=r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#define num_buffers 4
#define WHDR_INQUEUE 16
#define WHDR_DONE 1
#define WHDR_PREPARED 2
#define MMSYSERR_NOERROR 0
#define WAVERR_STILLPLAYING 33
#define SOX_SUCCESS 0
#define SOX_EOF -1
#define WAIT_OBJECT_0 0
#define WAIT_TIMEOUT 258
#define WAIT_FAILED 0xFFFFFFFFu
typedef uint32_t DWORD;
typedef uint64_t ULONGLONG;
typedef unsigned MMRESULT;
typedef void *HANDLE, *HWAVEIN, *HWAVEOUT;
typedef struct { DWORD dwFlags, dwBufferLength; } WAVEHDR;
typedef struct {
  HWAVEIN hin;
  HWAVEOUT hout;
  HANDLE block_finished_event;
  WAVEHDR *headers;
  char *data;
  size_t buf_len;
  unsigned current;
  unsigned char sample_shift;
} priv_t;
typedef struct {
  void *priv;
  struct {double rate; unsigned channels;} signal;
} sox_format_t;
static int scenario, freed, event_closed, errors, unprepared, driver_open;
static ULONGLONG clock_now;
static priv_t *active;
static void tracked_free(void *p) { if (p) { ++freed; free(p); } }
#define free tracked_free
#define lsx_fail_errno(ft,code,...) (void)(ft),(void)(code),++errors
static void fail(sox_format_t *ft, unsigned code, char const *context)
{ (void)ft;(void)code;(void)context;++errors; }
static DWORD GetLastError(void) {return 5;}
static ULONGLONG GetTickCount64(void) {return clock_now;}
static DWORD WaitForSingleObject(HANDLE event, DWORD millis) {
  (void)event;
  clock_now+=millis;
  if (scenario==6) return WAIT_TIMEOUT;
  for (unsigned i=0;i<num_buffers;i++)active->headers[i].dwFlags|=WHDR_DONE;
  return WAIT_OBJECT_0;
}
static int CloseHandle(HANDLE handle) { (void)handle;event_closed++;return 1;}
static MMRESULT waveInReset(HWAVEIN h) { (void)h;return scenario==3?5:0; }
static MMRESULT waveInUnprepareHeader(HWAVEIN h,WAVEHDR *head,unsigned size) {
  (void)h;(void)head;(void)size;unprepared++;
  return scenario==3 ? WAVERR_STILLPLAYING:0;
}
static MMRESULT waveInClose(HWAVEIN h) {
  (void)h; if (scenario==3)return WAVERR_STILLPLAYING;
  driver_open=0;return 0;
}
static MMRESULT waveOutReset(HWAVEOUT h) {
  (void)h;return scenario==1?5:0;
}
static MMRESULT waveOutUnprepareHeader(HWAVEOUT h,WAVEHDR *head,unsigned size) {
  (void)h;(void)head;(void)size;unprepared++;
  return scenario==1 ? WAVERR_STILLPLAYING : 0;
}
static MMRESULT waveOutClose(HWAVEOUT h) {
  (void)h;
  if (scenario==1 || scenario==2)return WAVERR_STILLPLAYING;
  driver_open=0;return 0;
}
'''
SUFFIX=r'''
static int run_case(int mode) {
  sox_format_t ft;
  priv_t priv;
  int ret, expected, expected_frees, expected_closes, expected_unprep;
  memset(&ft,0,sizeof ft);memset(&priv,0,sizeof priv);
  ft.priv=&priv;ft.signal.rate=44100;ft.signal.channels=1;
  scenario=mode;freed=event_closed=errors=unprepared=0;
  driver_open = mode !=4;
  clock_now=10000;
  priv.headers=calloc(num_buffers,sizeof(WAVEHDR));
  priv.data=malloc(4096);
  priv.block_finished_event=(HANDLE)(uintptr_t)1;
  if (!priv.headers||!priv.data)return 30;
  priv.hout= mode==3 || mode==4 ? NULL:(HWAVEOUT)(uintptr_t)2;
  priv.hin=mode==3?(HWAVEIN)(uintptr_t)3:NULL;
  for (int i=0;i<num_buffers;i++) {
    priv.headers[i].dwFlags = mode==4?0:(WHDR_PREPARED|WHDR_DONE);
    priv.headers[i].dwBufferLength=1024;
  }
  if (mode==6) for(int i=0;i<num_buffers;i++)priv.headers[i].dwFlags=WHDR_PREPARED|WHDR_INQUEUE;
  active=&priv;
  ret=stop(&ft);
  expected=(mode==0 || mode==4)?0:-1;
  expected_frees=(mode==1 || mode==2 || mode==3)?0:2;
  expected_closes=(mode==1 || mode==2 || mode==3)?0:1;
  expected_unprep=mode==4?0:4;
  if (ret!=expected || freed!=expected_frees ||
      event_closed!=expected_closes || unprepared!=expected_unprep ||
      (driver_open && (freed||event_closed)) ||
      (driver_open && !priv.headers)) {
    fprintf(stderr,"bad mode %d: result %d, freed %d, event %d, unprepared %d, open %d\n",
            mode, ret, freed,event_closed,unprepared,driver_open);
    return 31;
  }
  printf("PASS scenario=%d error=%d freed=%d event_closed=%d driver_open=%d\n",
         mode,ret,freed,event_closed,driver_open);
  return 0;
}
int main(void) {
  for(int scenario_id=0;scenario_id<=6;scenario_id++) {
    if(scenario_id==5)continue;
    int ret=run_case(scenario_id);
    if(ret)return ret;
  }
  return 0;
}
'''


def extract(source: str):
    start=source.index('static int drain_output(')
    end=source.index('static unsigned check_format(', start)
    body=source[start:end]
    if 'waveOutUnprepareHeader' not in body or 'device_still_owns_memory' not in body:
        raise AssertionError('source no longer contains expected Windows teardown implementation')
    return body


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--cc',default='cc')
    args=ap.parse_args()
    source=(args.source/'src/waveaudio.c').read_text()
    with tempfile.TemporaryDirectory(prefix='sox-waveaudio-') as temp:
        path=Path(temp)
        (path/'mock.c').write_text(PREFIX+extract(source)+SUFFIX)
        cc=subprocess.run([args.cc,'-std=c99','-Wall','-Wextra','-Werror',
                           '-o',str(path/'mock'),str(path/'mock.c')],
                          capture_output=True,text=True,timeout=30)
        if cc.returncode:
            raise AssertionError('WinMM teardown mock compilation failed: '+cc.stderr[-1500:])
        run=subprocess.run([str(path/'mock')],capture_output=True,text=True,timeout=30)
        if run.returncode or run.stdout.count('PASS scenario=')!=6:
            raise AssertionError('WinMM teardown mock failed: '+run.stderr+' '+run.stdout)
        print(json.dumps({'status':'PASS','source':'exact delivered drain/stop C functions',
                          'native_windows':False,'cases':run.stdout.strip().splitlines()},
                         sort_keys=True))

if __name__=='__main__':
    main()
