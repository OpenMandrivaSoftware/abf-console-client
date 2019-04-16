#############################################################################
# File		: Makefile
# Package	: abf_console_client
# Author	: Anton Kirilenko <anton.kirilenko@rosalab.ru>
#############################################################################


PYTHON=python3
PYTHON_BIN := $(shell which $(PYTHON))
PYVER := $(shell $(PYTHON) -c 'import sys; print("%.3s" %(sys.version))')
PYSYSDIR := $(shell $(PYTHON) -c 'import sys; print(sys.prefix)')
PYLIBDIR = $(PYSYSDIR)/lib/python$(PYVER)
PKGDIR = $(PYLIBDIR)/site-packages

PREFIX=/usr
BINDIR=$(PREFIX)/bin
ETCDIR=/etc
MANDIR=$(PREFIX)/share/man
DATADIR=$(PREFIX)/share

######### default config #############
MOCK = mock
default_url = https://abf.openmandriva.org
default_filestore_url = http://file-store.openmandriva.org
def_bp = cooker
######### /default config ############

FILES = abf/console/*.py abf/*.py abf/api/*.py

all:
	@echo "Nothing to do. Run 'make install' or 'make clean'"

clean:
	rm -f *~ *.pyc *.pyo
	
install:
	mkdir -p $(DESTDIR)$(PKGDIR) $(DESTDIR)$(BINDIR) $(DESTDIR)$(MANDIR)/man1
	cp -p --parents $(FILES) $(DESTDIR)$(PKGDIR)
	install -m0755 abf.py $(DESTDIR)$(BINDIR)/abf
	
	# set default config values
	sed -i -e "s,https://abf.openmandriva.org,$(default_url),g" \
		-e "s,http://file-store.openmandriva.org,$(default_filestore_url),g" \
		-e "s,cooker,$(def_bp),g" \
		$(DESTDIR)$(PKGDIR)/abf/console/config.py

	# TODO: set mock as a varibale at runtime
	sed -i -e "s,mock_urpm,m0ck_urpm,g" $(DESTDIR)$(BINDIR)/abf
	sed -i -e "s,mock,$(MOCK),g" $(DESTDIR)$(BINDIR)/abf
	sed -i -e "s,m0ck_urpm,mock_urpm,g" $(DESTDIR)$(BINDIR)/abf

	if [ "$(PYTHON)" != python3 ] && [ -x $(PYTHON_BIN) ]; then \
		sed -i -e "s,#!/usr/bin/env python3,#!$(PYTHON_BIN),g" $(DESTDIR)$(BINDIR)/abf ; fi

	mkdir -p $(DESTDIR)$(DATADIR)/bash-completion
	mkdir -p $(DESTDIR)$(ETCDIR)/bash_completion.d
	mkdir -p $(DESTDIR)$(ETCDIR)/profile.d
	cp "bash_autocomplete" $(DESTDIR)$(DATADIR)/bash-completion/abf
	cp "abfcd.sh" $(DESTDIR)$(ETCDIR)/profile.d/abfcd.sh
	
	mkdir -p $(DESTDIR)$(ETCDIR)/abf/$(MOCK)/configs/
	cp configs/* $(DESTDIR)$(ETCDIR)/abf/$(MOCK)/configs/
	mkdir -p $(DESTDIR)/var/cache/abf/$(MOCK)
	mkdir -p $(DESTDIR)/var/lib/abf/$(MOCK)/src
	chmod 0777 $(DESTDIR)/var/lib/abf/$(MOCK) -R
