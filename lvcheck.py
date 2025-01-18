#!/usr/bin/python3

import os
import sys
from lbatofile import getpvmap
from time import sleep

def sync_range(sync_min = 0,sync_max = None):
  if sync_min > 0 or not sync_max:
    with open('sync_max','wt') as fp: fp.write('max')
  with open('sync_min','wt') as fp: fp.write('%ld'%sync_min)
  if sync_max:
    with open('sync_max','wt') as fp: fp.write('%ld'%sync_max)

def sync_action(action = None):
  if action:
    with open('sync_action','wt') as fp: fp.write(action)
    return action
  with open('sync_action','rt') as fp:
    s = fp.read().strip()
  return s

def mdcheck(pv,sync_min,sync_max):
  # output script
  a = pv.split('/')
  os.chdir('/sys/block/'+a[-1]+'/md')
  s = sync_action()
  if s != 'idle':
    print('%s: %s in progress',pv,s)
    return None
  sync_range(sync_min,sync_max)
  sync_action('check')
  n = sync_min
  while n < sync_max:
    sleep(5)
    with open('sync_completed','rt') as fp:
      s = fp.read().strip()
      n = int(s.split('/')[0].strip())
      pct = (n - sync_min)*100 / (sync_max - sync_min)
      print(n,'/',sync_max,"%d%%"%pct)
  with open('mismatch_cnt','rt') as fp:
    s = fp.read().strip()
  sync_action('idle')
  mismatch_cnt = int(s)
  return mismatch_cnt

def main(argv):
  if len(argv) < 3:
      print('Usage: %s /dev/mdxxx lvname'%argv[0])
      sys.exit(2)
  pv = argv[1]
  lv = argv[2]
  res = getpvmap(pv)
  if not res: return None
  vg_name,pe_start,pe_size,m = res
  print(vg_name,pe_start,pe_size,)
  sfx = '/'+lv
  totcnt = 0
  n = -1
  for s in m:
    if s.lvpath.endswith(sfx) or s.lvpath == lv:
      sync_min = s.pe1st*pe_size+pe_start
      sync_max = s.pelst*pe_size+pe_start+pe_size
      print(s)
      print('   ',sync_min,sync_max)
      n = mdcheck(pv,sync_min,sync_max)
      totcnt += n
  if n >= 0:  sync_range()    # reset sync range
  print('mismatch_cnt =',totcnt)

if __name__ == '__main__':
  import sys,getopt
  main(sys.argv)
