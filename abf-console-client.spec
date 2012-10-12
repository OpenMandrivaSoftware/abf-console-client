Name:           abf-console-client
Version:        1.1
Release:        2
Summary:        Python API to ABF (https://abf.rosalinux.ru)
Group:          System/Configuration/Packaging
License:        GPLv2
URL:            http://wiki.rosalab.ru/en/index.php/ABF_Console_Client
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

Requires:       python-abf >= 1.1-2
Requires:       python-beaker
Requires:       python-rpm
Requires:       git

%description
Console client for ABF (https://abf.rosalinux.ru). 


%prep
%setup -q -n %{name}

%install
rm -rf %{buildroot}
make install DESTDIR=$RPM_BUILD_ROOT
ln -s %{_datadir}/bash-completion/abf %{buildroot}/%{_sysconfdir}/bash_completion.d/abf


%files
%defattr(-,root,root,-)
%dir %{py_puresitedir}/abf/console
%{py_puresitedir}/abf/console/*.py*
%{_bindir}/abf

#bash_completion files
%{_datadir}/bash-completion/abf 
%{_sysconfdir}/bash_completion.d/abf
