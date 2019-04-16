%global helm_folder  /usr/lib/helm
%global helmchart_version 0.1.0

Summary: Node Feature Discovery Helm charts
Name: node-feature-discovery 
Version: 0.3.0
Release: %{tis_patch_ver}%{?_tis_dist}
License: Apache-2.0
Group: base
Packager: Wind River <info@windriver.com>
URL: https://github.com/kubernetes-sigs/node-feature-discovery

Source0: %{name}-%{version}.tar.gz

BuildArch: noarch

BuildRequires: helm

%description
Node Feature Discovery Helm charts

%prep
%setup

%build
# initialize helm and build the toolkit
# helm init --client-only does not work if there is no networking
# The following commands do essentially the same as: helm init
%define helm_home  %{getenv:HOME}/.helm
mkdir  %{helm_home}
mkdir  %{helm_home}/repository
mkdir  %{helm_home}/repository/cache
mkdir  %{helm_home}/repository/local
mkdir  %{helm_home}/plugins
mkdir  %{helm_home}/starters
mkdir  %{helm_home}/cache
mkdir  %{helm_home}/cache/archive

# Stage a repository file that only has a local repo
cp repositories.yaml %{helm_home}/repository/repositories.yaml

# Stage a local repo index that can be updated by the build
cp index.yaml %{helm_home}/repository/local/index.yaml

# Host a server for the charts
helm serve --repo-path . &
helm repo rm local
helm repo add local http://localhost:8879/charts

# Make the charts. These produce a tgz file
make node-feature-discovery 

# terminate helm server (the last backgrounded task)
kill %1

%install
install -d -m 755 ${RPM_BUILD_ROOT}/opt/extracharts
install -p -D -m 755 *.tgz ${RPM_BUILD_ROOT}/opt/extracharts

%files
%defattr(-,root,root,-)
/opt/extracharts/*
