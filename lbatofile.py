#!/usr/bin/python
# Identify partition, LV, file containing a sector 

# Copyright (C) 2010,2012,2014,2015 Stuart D. Gathman
# Shared under GNU Public License v2 or later
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.

#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.

#   You should have received a copy of the GNU General Public License along
#   with this program; if not, write to the Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
from __future__ import print_function
from subprocess import Popen,PIPE

ID_LVM = (0x8e, 'E6D6D379-F507-44C2-A23C-238F2A3DF928')
ID_LINUX = (0x83, '0FC63DAF-8483-4772-8E79-3D69D8477DE4')
ID_EXT = 0x05
ID_RAID = 0xfd

verbose = False

def idtoname(id):
  if id in ID_LVM: return "Linux LVM"
  if id in ID_LINUX: return "Linux Filesystem"
  if id == ID_EXT: return "Extended Partition"
  if id == ID_RAID: return "Software RAID"
  try:
    return hex(id)
  except TypeError:
    return id

class Segment(object):
  __slots__ = ('pe1st','pelst','lvpath','le1st','lelst')
  def __init__(self,pe1st,pelst):
    self.pe1st = pe1st;
    self.pelst = pelst;
  def size(self):
    return self.pelst - self.pe1st + 1
  def __str__(self):
    return "Seg:%d-%d:%s:%d-%d" % (
      self.pe1st,self.pelst,self.lvpath,self.le1st,self.lelst)

def cmdoutput(cmd):
  if verbose:
    print('#',cmd)
  p = Popen(cmd, shell=True, stdout=PIPE)
  try:
    for ln in p.stdout:
      yield ln.decode()
  finally:
    p.stdout.close()
    p.wait()

def icheck(fs,blk):
  "Return inum from block number, or 0 if free space."
  for ln in cmdoutput("debugfs -R 'icheck %d' '%s' 2>/dev/null"%(blk,fs)):
    b,i = ln.strip().split(None,1)
    if not b[0].isdigit(): continue
    if int(b) == blk:
      if i.startswith('<'):
        return 0
      return int(i)
  raise ValueError('%s: invalid block: %d'%(fs,blk))

def ncheck(fs,inum):
  "Return filename from inode number, or None if not linked."
  for ln in cmdoutput("debugfs -R 'ncheck %d' '%s' 2>/dev/null"%(inum,fs)):
    i,n = ln.strip().split(None,1)
    if not i[0].isdigit(): continue
    if int(i) == inum:
      return n
  if inum == 8:
    return "<journal>"
  return None

def blkid(fs):
  "Return dictionary of block device attributes"
  d = {}
  for ln in cmdoutput("blkid -o export '%s'"%fs):
    k,v = ln.strip().split('=',1)
    d[k] = v
  return d

def getpvmap(pv):
  pe_start = 192 * 2
  pe_size = None
  free_start = 0
  seg = None
  segs = []
  for ln in cmdoutput("pvdisplay --units k -m '%s'"%pv):
    a = ln.strip().split()
    if not a: continue
    if a[0] == 'Physical' and a[4].endswith(':'):
      pe1st = int(a[2])
      pelst = int(a[4][:-1])
      seg = Segment(pe1st,pelst)
    if a[0] == 'VG':
      vg_name = a[2]
    elif seg and a[0] == 'Logical':
      if a[1] == 'volume':
        seg.lvpath = a[2]
      elif a[1] == 'extents':
        seg.le1st = int(a[2])
        seg.lelst = int(a[4])
        segs.append(seg)
    elif seg and a[0] == 'FREE':
        seg.lvpath = a[0]
        seg.le1st = free_start
        seg.lelst = free_start + seg.pelst - seg.pe1st
        free_start += seg.size()
        segs.append(seg)
    elif a[0] == 'PE' and a[1] == 'Size':
      if a[2] == "(KByte)":
        pe_size = int(a[3]) * 2
      elif a[3] == 'KiB':
        pe_size = int(float(a[2])) * 2
  if segs:
    for ln in cmdoutput("pvs --units k -o+pe_start '%s'"%pv):
      a = ln.split()
      if a[0] == pv:
        lst = a[-1]
        if lst.lower().endswith('k'):
          pe_start = int(float(lst[:-1]))*2
          return vg_name,pe_start,pe_size,segs
  return None

def findlv(pv,sect):
  res = getpvmap(pv)
  if not res: return None
  vg_name,pe_start,pe_size,m = res
  if sect < pe_start:
    # FIXME: not necessarily an error, unless we can't read metadata
    return vg_name,sect,"<meta data>"
  pe = int((sect - pe_start)/pe_size)
  pebeg = pe * pe_size + pe_start
  peoff = sect - pebeg
  for s in m:
    if s.pe1st <= pe <= s.pelst:
      if s.lvpath == 'FREE':
        return vg_name,sect,"FREE"
      le = s.le1st + pe - s.pe1st
      return s.lvpath,le * pe_size + peoff,"Logical Volume"
  # FIXME: distinguish between FREE space and unusable sectors
  return vg_name,sect,"<free space>"

def getmdmap():
  with open('/proc/mdstat','rt') as fp:
    m = []
    for ln in fp:
      if ln.startswith('md'):
        a = ln.split(':')
        raid = a[0].strip()
        devs = []
        a = a[1].split()
        for d in a[2:]:
          devs.append(d.split('[')[0])
        m.append((raid,a[0],a[1],devs))
    return m

def parse_sfdisk(s):
  for ln in s:
    try:
      if not ln.strip(): continue
      part,desc = ln.split(':')
      if part.startswith('/dev/'):
        d = {}
        for p in desc.split(','):
          try:
            name,val = p.split('=')
            name = name.strip().lower()
            if name in ('id','type'):
              try:
                d['id'] = int(val,16)
              except:
                d['id'] = val
            else:
              d[name] = int(val)
          except ValueError:
            d[p.strip().lower()] = ''
        yield part.strip(),d
    except ValueError:
      continue

def findpart(wd,lba):
  s = cmdoutput("sfdisk -d '%s'"%wd)
  parts = [ (part,d['start'],d['size'],d['id']) for part,d in parse_sfdisk(s) ]
  for part,start,sz,Id in parts:
    if Id == ID_EXT: continue
    if start <= lba < start + sz:
      print(part,Id)
      return part,lba - start,idtoname(Id)
  return None

class AbstractLayout(object):
  def checkId(self,attrs): return self
  def __call__(self,wd,lba): return None

class PartitionLayout(AbstractLayout):
  def checkId(self,attrs):
    if not attrs or attrs.get('PTTYPE','') in ('dos','gpt'): return self
    return None
  def __call__(self,wd,lba):
    return findpart(wd,lba)

class LVM2Layout(AbstractLayout):
  def checkId(self,attrs):
    if attrs.get('TYPE','') == 'LVM2_member': return self
    return None
  def __call__(self,wd,lba):
    return findlv(wd,lba)
    
class RAIDLayout(AbstractLayout):
  def checkId(self,attrs):
    if attrs.get('TYPE','') == 'linux_raid_member': return self
    return None
  def __call__(self,part,lba):
    for md,status,raidlev,devs in getmdmap():
      for dev in devs:
        if part == "/dev/"+dev:
          part = "/dev/"+md
          # FIXME: handle striped RAID formats (raid10,raid5,raid0,...)
          if raidlev != 'raid1':
            return md,lba,raidlev+' not supported'
          # FIXME: handle raid superblock at beginning of blkdev
          return part,lba,status+' '+raidlev
    return None

class EXTLayout(AbstractLayout):
  def checkId(self,attrs):
    if attrs.get('TYPE','').startswith('ext'): return self
    return None
  def __call__(self,bd,sect):
    blksiz = 4096
    blk = int(sect * 512 / blksiz)
    print("fs=%s block=%d %s"%(bd,blk,'extfs'))
    inum = icheck(bd,blk)
    if inum:
      fn = ncheck(bd,inum)
      print("file=%s inum=%d"%(fn,inum))
    else:
      print("<free space>")
    return None

class LayoutManager(AbstractLayout):
  def __init__(self):
    self.layouts = []

  def register(self,layout):
    if layout not in self.layouts:
      self.layouts.append(layout)

  def __call__(self,wd,lba):
    if not wd.startswith('/'): return None
    attrs = blkid(wd)
    if verbose: print(attrs)
    for layout in self.layouts:
      if layout.checkId(attrs):
        if verbose: print(layout)
        res = layout(wd,lba)
        if res: return res
    return None

def usage(msg=None):
  if msg:
    print(msg,file=sys.stderr)
  print("Usage:	lbatofile.py [-v] /dev/blkdev sector",file=sys.stderr)
  sys.exit(2)

def main(argv):
  try:
    opts,argv = getopt.getopt(argv[1:],'v')
  except getopt.GetoptError as x:
    usage(x)
  if len(argv) != 2: usage()
  for opt,val in opts:
    if opt == '-v':
      global verbose
      verbose = True
  mgr = LayoutManager()
  mgr.register(PartitionLayout())
  mgr.register(LVM2Layout())
  mgr.register(RAIDLayout())
  mgr.register(EXTLayout())
  wd = argv[0]
  lba = int(argv[1])
  res = wd,lba,"Whole Disk"
  while res: 
    part,sect,desc = res
    print(part,sect,desc)
    res = mgr(part,sect)

if __name__ == '__main__':
  import sys,getopt
  main(sys.argv)
