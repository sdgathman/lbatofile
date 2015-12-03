Name:		lbatofile
Version:	0.1
Release:	1%{?dist}
Summary:	Map LBA to file

Group:		Applications/System
License:	GPL2+
URL:		https://github.com/sdgathman/lbatofile
Source0:	https://github.com/sdgathman/%{name}/archive/%{name}-%{version}.tar.gz

Requires:	python >= 2.6, e2fsprogs, lvm2
%if 0%{?rhel} == 6
Requires:	util-linux-ng
%else
Requires:	util-linux
%endif

%description
When you have a bad sector on storage media, modern drives will repair the
sector when you write to it. However, you would like to know what file is
damaged by the missing data. In many cases, the bad sector will be in free
space. Or the file is one that you can delete and restore from elsewhere.
lbatofile.py will "drill down" starting from any block device and LBA within
that block device (which is usually a whole disk), and invoke linux utilities
to interpret the partition tables, LVM metadata, or filesystems containing the
LBA.

%prep
%setup -qn %{name}-%{name}-%{version}

%build

%install
mkdir -p %{buildroot}/%{_sbindir}
cp -p lbatofile.py %{buildroot}/%{_sbindir}/lbatofile

%files
%doc README.md LICENSE
%{_sbindir}/lbatofile

%changelog
* Wed Dec  2 2015 Stuart Gathman <stuart@gathman.org> 0.1-1
- Initial package
