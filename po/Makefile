# the domain name for gettext
PGOAL = abf-console-client

# python files to search translatable strings in
PY_FILES = ../abf/*py ../abf.py ../abf/console/*py ../abf/api/*py

POFILES = $(wildcard *.po)
MOFILES = $(POFILES:%.po=%.mo)
LANGS = $(POFILES:%.po=%)

top_srcdir=..
PREFIX = $(RPM_BUILD_ROOT)/usr
DATADIR = $(PREFIX)/share
LOCALEDIR=$(DATADIR)/locale

all: $(MOFILES)

%.mo: %.po
	msgfmt -c -o $@ $<

update_n_merge: $(PGOAL).pot merge

merge:
	@for n in $(POFILES); do \
		echo "Merging $$n"; \
		msgmerge "$$n" $(PGOAL).pot > "$$n"t; \
		mv -f "$$n"t "$$n"; \
	done

$(PGOAL).pot: $(PY_FILES)
	xgettext -L Python $(PY_FILES) -o $@

install:
	for l in $(LANGS); do \
		install -d $(LOCALEDIR)/$$l/LC_MESSAGES; \
		install -m 644 $$l.mo $(LOCALEDIR)/$$l/LC_MESSAGES/$(PGOAL).mo; \
	done

clean:
	@rm -rf *.mo *.pof *.pog $(POFILES:%=%t) $(PL_CFILES) desktopstuff.pot $(PGOAL)_tmp.pot

