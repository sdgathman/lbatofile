#!/usr/bin/python
# Identify partition, LV, file containing a sector 

# Copyright (C) 2010,2012 Stuart D. Gathman
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

from subprocess import Popen,PIPE

ID_LVM = 0x8e
ID_LINUX = 0x83
ID_EXT = 0x05
ID_RAID = 0xfd

def idtoname(id):
  if id == ID_LVM: return "Linux LVM"
  if id == ID_LINUX: return "Linux Filesystem"
  if id == ID_EXT: return "Extended Partition"
  if id == ID_RAID: return "Software RAID"
  return hex(id)

class Segment(object):
  __slots__ = ('pe1st','pelst','lvpath','le1st','lelst')
  def __init__(self,pe1st,pelst):
    self.pe1st = pe1st;
    self.pelst = pelst;
  def __str__(self):
    return "Seg:%d-%d:%s:%d-%d" % (
      self.pe1st,self.pelst,self.lvpath,self.le1st,self.lelst)

def cmdoutput(cmd):
  p = Popen(cmd, shell=True, stdout=PIPE)
  try:
    for ln in p.stdout:
      yield ln
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
  seg = None
  segs = []
  for ln in cmdoutput("pvdisplay --units k -m %s"%pv):
    a = ln.strip().split()
    if not a: continue
    if a[0] == 'Physical' and a[4].endswith(':'):
      pe1st = int(a[2])
      pelst = int(a[4][:-1])
      seg = Segment(pe1st,pelst)
    elif seg and a[0] == 'Logical':
      if a[1] == 'volume':
	seg.lvpath = a[2]
      elif a[1] == 'extents':
	seg.le1st = int(a[2])
	seg.lelst = int(a[4])
	segs.append(seg)
    elif a[0] == 'PE' and a[1] == 'Size':
      if a[2] == "(KByte)":
	pe_size = int(a[3]) * 2
      elif a[3] == 'KiB':
	pe_size = int(float(a[2])) * 2
  if segs:
    for ln in cmdoutput("pvs --units k -o+pe_start %s"%pv):
      a = ln.split()
      if a[0] == pv:
        lst = a[-1]
	if lst.lower().endswith('k'):
	  pe_start = int(float(lst[:-1]))*2
	  return pe_start,pe_size,segs
  return None

def findlv(pv,sect):
  res = getpvmap(pv)
  if not res: return None
  pe_start,pe_size,m = res
  if sect < pe_start:
    raise Exception("Bad sector in PV metadata area")
  pe = int((sect - pe_start)/pe_size)
  pebeg = pe * pe_size + pe_start
  peoff = sect - pebeg
  for s in m:
    if s.pe1st <= pe <= s.pelst:
      le = s.le1st + pe - s.pe1st
      return s.lvpath,le * pe_size + peoff

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
	m.append((raid,devs))
    return m

def parse_sfdisk(s):
  for ln in s:
    try:
      part,desc = ln.split(':')
      if part.startswith('/dev/'):
        d = {}
        for p in desc.split(','):
	  name,val = p.split('=')
	  name = name.strip()
	  if name.lower() == 'id':
	    d[name] = int(val,16)
	  else:
	    d[name] = int(val)
	yield part.strip(),d
    except ValueError:
      continue

def findpart(wd,lba):
  s = cmdoutput("sfdisk -d %s"%wd)
  parts = [ (part,d['start'],d['size'],d['Id']) for part,d in parse_sfdisk(s) ]
  for part,start,sz,Id in parts:
    if Id == ID_EXT: continue
    if start <= lba < start + sz:
      return part,lba - start,Id
  return None

def usage():
  print >>sys.stderr,"""\
Usage:	lbatofile.py /dev/blkdev sector"""
  sys.exit(2)

def main(argv):
  if len(argv) != 3: usage()
  wd = argv[1]
  lba = int(argv[2])
  print wd,lba,"Whole Disk"
  res = findpart(wd,lba)
  if not res:
    print "LBA is outside any partition"
    sys.exit(1)
  part,sect,Id = res
  print part,sect,idtoname(Id)
  if Id == ID_LVM:
    bd,sect = findlv(part,sect)
    # FIXME: problems if LV is snapshot
  elif Id == ID_LINUX:
    bd = part
  else:
    if Id == ID_RAID:
      for md,devs in getmdmap():
	for dev in devs:
	  if part == "/dev/"+dev:
	    part = "/dev/"+md
	    break
        else: continue
	break
    res = findlv(part,sect)
    if res:
      print "PV =",part
      bd,sect = res
    else:
      bd = part
  blksiz = 4096
  blk = int(sect * 512 / blksiz)
  p = blkid(bd)
  try:
    t = p['TYPE']
  except:
    print bd,p
    raise
  print "fs=%s block=%d %s"%(bd,blk,t)
  if t.startswith('ext'):
    inum = icheck(bd,blk)
    if inum:
      fn = ncheck(bd,inum)
      print "file=%s inum=%d"%(fn,inum)
    else:
      print "<free space>"

if __name__ == '__main__':
  import sys
  main(sys.argv)
