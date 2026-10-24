NAME     = kachalka
VERSION  = 1.0.1
APP_ID   = ru.kachalka.Kachalka
PREFIX  ?= /usr
BINDIR   = $(PREFIX)/bin
DATADIR  = $(PREFIX)/share
APPDIR   = $(DATADIR)/$(NAME)

.PHONY: all install run tarball rpm clean

all:
	@echo "Используйте: make install | make run | make rpm"

run:
	python3 -m kachalka

install:
	install -d $(DESTDIR)$(APPDIR)/kachalka $(DESTDIR)$(BINDIR) \
	    $(DESTDIR)$(DATADIR)/applications
	install -m 644 kachalka/*.py kachalka/style.css $(DESTDIR)$(APPDIR)/kachalka/
	sed 's|@DATADIR@|$(APPDIR)|' bin/kachalka.in > $(DESTDIR)$(BINDIR)/kachalka
	chmod 755 $(DESTDIR)$(BINDIR)/kachalka
	install -m 644 data/$(APP_ID).desktop $(DESTDIR)$(DATADIR)/applications/
	for s in 32 48 64 128 256 512; do \
	    install -d $(DESTDIR)$(DATADIR)/icons/hicolor/$${s}x$${s}/apps; \
	    install -m 644 data/icons/$${s}x$${s}/$(APP_ID).png \
	        $(DESTDIR)$(DATADIR)/icons/hicolor/$${s}x$${s}/apps/$(APP_ID).png; \
	done

# Исходный архив для rpmbuild (ALT-стиль: несжатый .tar)
tarball:
	mkdir -p rpmbuild/SOURCES
	tar --exclude=rpmbuild --exclude='__pycache__' --exclude='*.pyc' \
	    --transform 's|^\.|$(NAME)-$(VERSION)|' \
	    -cf rpmbuild/SOURCES/$(NAME)-$(VERSION).tar .

# Сборка пакета: результат в rpmbuild/RPMS/noarch/
rpm: tarball
	mkdir -p rpmbuild/SPECS rpmbuild/BUILD rpmbuild/RPMS rpmbuild/SRPMS
	cp $(NAME).spec rpmbuild/SPECS/
	rpmbuild -ba --define "_topdir $(CURDIR)/rpmbuild" rpmbuild/SPECS/$(NAME).spec

clean:
	rm -rf rpmbuild
	find . -name __pycache__ -type d -exec rm -rf {} +
