import os
from lbatofile import getpvmap
from time import sleep

def mdcheck(pv,sync_min,sync_max):
  # output script
  a = pv.split('/')
  os.chdir('/sys/block/'+a[-1]+'/md')
  with open('sync_action','rt') as fp:
    s = fp.read().strip()
  if s != 'idle':
    print('%s: %s in progress',pv,s)
    return None
  with open('sync_max','wt') as fp: fp.write('max')
  with open('sync_min','wt') as fp: fp.write('%ld'%sync_min)
  with open('sync_max','wt') as fp: fp.write('%ld'%sync_max)
  with open('sync_action','wt') as fp: fp.write('check')
  n = sync_min
  while n < sync_max:
    sleep(5)
    with open('sync_completed','rt') as fp:
      s = fp.read().strip()
      print(s)
      n = int(s.split('/')[0].strip())
  with open('mismatch_cnt','rt') as fp:
    s = fp.read().strip()
  with open('sync_action','wt') as fp: fp.write('idle')
  mismatch_cnt = int(s)
  return mismatch_cnt

def main(argv):
  pv = argv[1]
  lv = argv[2]
  res = getpvmap(pv)
  if not res: return None
  vg_name,pe_start,pe_size,m = res
  print(vg_name,pe_start,pe_size,)
  sfx = '/'+lv
  totcnt = 0
  for s in m:
    if s.lvpath.endswith(sfx):
      sync_min = s.pe1st*pe_size+pe_start
      sync_max = s.pelst*pe_size+pe_start+pe_size
      print(s)
      print('   ',sync_min,sync_max)
      n = mdcheck(pv,sync_min,sync_max)
      totcnt += n
  print('mismatch_cnt =',totcnt)

if __name__ == '__main__':
  import sys,getopt
  main(sys.argv)
