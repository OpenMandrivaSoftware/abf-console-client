Name:           abf-console-client
Version:        1.0
Release:        1
Summary:        Python API to ABF (https://abf.rosalinux.ru)
Group:          System/Configuration/Packaging
License:        GPLv2
URL:            http://wiki.rosalab.ru/en/index.php/ABF_Console_Client
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

Requires:       python-abf

%description
Console client for ABF (https://abf.rosalinux.ru). 


%prep
%setup -q -n %{name}

%install
rm -rf %{buildroot}
make install DESTDIR=$RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
%dir %{py_puresitedir}/abf/console
%{py_puresitedir}/abf/console/*.py*
%{_bindir}/abf