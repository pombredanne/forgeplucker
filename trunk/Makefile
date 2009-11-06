# Makefile for the forgeplucker project

SOURCES = bugplucker.py
DOCS = README COPYING docs/*.txt docs/*.xml
MISC = Makefile
ALL = $(SOURCES) $(DOCS) $(MISC)

dist: $(ALL)
	tar -czf forgeplucker.tar.gz $(ALL)

check:
	pychecker --limit=100 --no-classattr bugplucker.py

clean:
	rm -f *.pyc forgeplucker.tar.gz typescript *~


