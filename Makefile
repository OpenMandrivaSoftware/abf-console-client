#############################################################################
# File		: Makefile
# Package	: abf_console_client
# Author	: Anton Kirilenko <anton.kirilenko@rosalab.ru>
#############################################################################


PYTHON=python
PYVER := $(shell $(PYTHON) -c 'import sys; print "%.3s" %(sys.version)')
PYSYSDIR := $(shell $(PYTHON) -c 'import sys; print sys.prefix')
PYLIBDIR = $(PYSYSDIR)/lib/python$(PYVER)
PKGDIR = $(PYLIBDIR)/site-packages

BINDIR=/usr/bin
ETCDIR=/etc
MANDIR=/usr/share/man
USRSHAREDIR=/usr/share


FILES = abf/console/*.py

all:
	@echo "Nothing to do. Run 'make install' or 'make clean'"

clean:
	rm -f *~ *.pyc *.pyo
	

	
install:
	mkdir -p $(DESTDIR)$(PKGDIR) $(DESTDIR)$(BINDIR) $(DESTDIR)$(MANDIR)/man1
	cp -p --parents $(FILES) $(DESTDIR)$(PKGDIR)
	cp -p "abf.py" $(DESTDIR)$(BINDIR)"/abf"
	
	mkdir -p $(DESTDIR)$(USRSHAREDIR)"/bash-completion"
	cp "bash_autocomplete" $(DESTDIR)$(USRSHAREDIR)"/bash-completion/abf"
	ln -s $(USRSHAREDIR)"/bash-completion/abf" $(ETCDIR)"/bash_completion.d/abf"

	

