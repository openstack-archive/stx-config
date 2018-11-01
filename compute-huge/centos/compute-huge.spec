Summary: Initial compute node hugepages and reserved cpus configuration
Name: compute-huge
Version: 1.0
Release: %{tis_patch_ver}%{?_tis_dist}
License: Apache-2.0
Group: base
Packager: Wind River <info@windriver.com>
URL: unknown
Source0: %{name}-%{version}.tar.gz
Source1: LICENSE

BuildRequires: systemd-devel
Requires: systemd
Requires: python
Requires: /bin/systemctl

%description
Initial compute node hugepages and reserved cpus configuration

%define local_bindir /usr/bin/
%define local_etc_initd /etc/init.d/
%define local_etc_nova /etc/nova/
%define local_etc_goenabledd /etc/goenabled.d/

%define debug_package %{nil}

%prep
%setup

%build
make

%install
make install BINDIR=%{buildroot}%{local_bindir} \
     INITDDIR=%{buildroot}%{local_etc_initd} \
     GOENABLEDDIR=%{buildroot}%{local_etc_goenabledd} \
     NOVACONFDIR=%{buildroot}%{local_etc_nova} \
     SYSTEMDDIR=%{buildroot}%{_unitdir}

%post
/bin/systemctl enable affine-platform.sh.service >/dev/null 2>&1

%clean
rm -rf $RPM_BUILD_ROOT

%files

%defattr(-,root,root,-)

%{local_bindir}/*
%{local_etc_initd}/*
%{local_etc_goenabledd}/*
%config(noreplace) %{local_etc_nova}/compute_reserved.conf

%{_unitdir}/affine-platform.sh.service
