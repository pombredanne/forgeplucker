# Makefile for the forgeplucker project documentation

%.html: %.xml
	xmlto xhtml-nochunks $<

%.html: %.txt
	asciidoc $<

XML = forgeplucker.xml
TXT = forgeplucker-plan.txt jailbreaking-the-forges.txt savant.txt FAQ.txt \
	handler-howto.txt forge-identification.txt forge-ontology.txt
WEB = index.txt
DOCS = $(XML) $(TXT)
ALL = $(SOURCES) $(DOCS) $(WEB) $(MISC)

all: sitecopy

html: $(XML:.xml=.html) $(DOCS:.txt=.html) $(WEB:.txt=.html)

# This assumes a Gna layout in which checkins to the website directory
# (a peer of trunk) are propagated to the actual webspace via a 
# postcommit hook.
sitecopy: html
	cp *.html ../../website

clean:
	rm -f *.html *~
