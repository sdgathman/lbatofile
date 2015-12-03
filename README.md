# lbatofile
For linux admins.

When you have a bad sector on storage media, modern drives will repair the sector when you write to it.  However, you would
like to know what file is damaged by the missing data.  In many cases, the bad sector will be in free space.  Or the file is one
that you can delete and restore from elsewhere.  lbatofile.py will "drill down" starting from any block device and LBA within that
block device (which is usually a whole disk), and invoke linux utilities to interpret the partition tables, LVM metadata, or 
filesystems containing the LBA.
