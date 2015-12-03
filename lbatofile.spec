Name:		lbatofile
Version:	0.1
Release:	1%{?dist}
Summary:	Map LBA to file

Group:		Applications/System
License:	GPL2
URL:		https://sourceforge.net/projects/lbatofile/
Source0:	lbatofile

BuildRequires:	
Requires:	

%description


%prep
%setup -q


%build
%configure
make %{?_smp_mflags}


%install
%make_install


%files
%doc



%changelog

