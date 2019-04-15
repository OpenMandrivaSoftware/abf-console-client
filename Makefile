#############################################################################
# File		: Makefile
# Package	: abf_console_client
# Author	: Anton Kirilenko <anton.kirilenko@rosalab.ru>
#############################################################################


PYTHON=python3
PYVER := $(shell $(PYTHON) -c 'import sys; print("%.3s" %(sys.version))')
PYSYSDIR := $(shell $(PYTHON) -c 'import sys; print(sys.prefix)')
PYLIBDIR = $(PYSYSDIR)/lib/python$(PYVER)
PKGDIR = $(PYLIBDIR)/site-packages

PREFIX=/usr
BINDIR=$(PREFIX)/bin
ETCDIR=/etc
MANDIR=$(PREFIX)/share/man
DATADIR=$(PREFIX)/share

FILES = abf/console/*.py abf/*.py abf/api/*.py

all:
	@echo "Nothing to do. Run 'make install' or 'make clean'"

clean:
	rm -f *~ *.pyc *.pyo
	
install:
	mkdir -p $(DESTDIR)$(PKGDIR) $(DESTDIR)$(BINDIR) $(DESTDIR)$(MANDIR)/man1
	cp -p --parents $(FILES) $(DESTDIR)$(PKGDIR)
	install -m0755 abf.py $(DESTDIR)$(BINDIR)/abf
	
	mkdir -p $(DESTDIR)$(DATADIR)/bash-completion
	mkdir -p $(DESTDIR)$(ETCDIR)/bash_completion.d
	mkdir -p $(DESTDIR)$(ETCDIR)/profile.d
	cp "bash_autocomplete" $(DESTDIR)$(DATADIR)/bash-completion/abf
	cp "abfcd.sh" $(DESTDIR)$(ETCDIR)/profile.d/abfcd.sh
	
	mkdir -p $(DESTDIR)$(ETCDIR)/abf/mock/configs/
	cp configs/* $(DESTDIR)$(ETCDIR)/abf/mock/configs/
	mkdir -p $(DESTDIR)/var/cache/abf/mock
	mkdir -p $(DESTDIR)/var/lib/abf/mock/src
	chmod 0777 $(DESTDIR)/var/lib/abf/mock -R
