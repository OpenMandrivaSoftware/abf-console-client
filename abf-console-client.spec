Name:           abf-console-client
Version:        1.6
Release:        2
Summary:        Console client for ABF (https://abf.rosalinux.ru)
Group:          System/Configuration/Packaging
License:        GPLv2
URL:            http://wiki.rosalab.ru/en/index.php/ABF_Console_Client
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

Requires:       python-abf >= %{version}-%{release}
Requires:       python-beaker
Requires:       python-rpm
Requires:       git
Requires:       python-yaml
Requires:       python-magic

%description
Console client for ABF (https://abf.rosalinux.ru). 



%package -n     python-abf
Summary:        Python API for ABF (https://abf.rosalinux.ru)
Group:          System/Configuration/Packaging
Provides:       python-abf = %{version}-%{release}

%description -n python-abf
%{name} is the python API to ABF (https://abf.rosalinux.ru).
It contains a set of basic operations, done with either HTML 
parsing or through ABF json API. It also provides datamodel to
operate with.


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
%{_sysconfdir}/profile.d/abfcd.sh


%files -n python-abf
%defattr(-,root,root,-)
%dir %{py_puresitedir}/abf
%dir %{py_puresitedir}/abf/api
%{py_puresitedir}/abf/*.py*
%{py_puresitedir}/abf/api/*.py*
