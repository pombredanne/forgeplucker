#!/usr/bin/env python

# This script should probe a web app's page to detect if it's a page
# rendered by a supported forge, and if possible find if it's a
# project's page.
# Then, it could report to the user if it can extract data and which kind of.
#
# Supported formats to detect which forge it is :
#
# * The Forge-Identification Meta Header http://home.gna.org/forgeplucker/forge-identification.html
# * Application Metadata RDFa present in the page (http://webofdata.wordpress.com/2010/01/06/announcing-application-metadata/)
# * Ad-hoc detection

"""
probe.py -- identifies the forge hosting a project at provided URL

usage: probe.py [-hv?] URL

  -h -? : displays this help message

"""

import urllib2, sys, re
from BeautifulSoup import BeautifulSoup

class Forge:

    def __init__(self, url='', name='', software=''):
        self.url = str(url)
        self.name = name
        self.software = software
        self.swvariant = ''
        self.version = None

    def __str__(self):
        s = 'URL: '+ self.url +"\n" + \
            'Name: ' + self.name +"\n" + \
            'Software: ' + self.software
        if self.swvariant :
            s += ' - ' + self.swvariant
        if self.version :
            s += "\n" + 'Version: ' + self.version
        return s

    def check_homepage(self, url):
        """Returns the forge's homepage provided a project's page URL and a forge type"""
        import urlparse
        if self.software == 'Savane':
            back_to_homepage = re.compile('Back to (.*) Homepage',re.I)
            response = urllib2.urlopen(url)
            the_page = response.read()
            soup = BeautifulSoup(the_page)

            links = soup.findAll('a')
            href=None
            forge=None
            for link in links:

                for tag in link.findAll(alt=back_to_homepage) :
                    alt = tag['alt']
                    m = back_to_homepage.match(alt)
                    forge = m.group(1)
                    break

                if forge:
                    href=link['href']
                    href=urlparse.urljoin(url, href)
                    break
            self.url = str(href)
            self.name = forge

        if self.software == 'FusionForge':
            response = urllib2.urlopen(url)
            the_page = response.read()
            soup = BeautifulSoup(the_page)

            # First FF 4.8 inherited from GForge
            links = soup.findAll('a', id='gforge-home', title='Home')
            href=None
            for link in links:
                href=link['href']
                break

            # If not matched, then try with more recent FF
            if not href:
                links = soup.findAll('a')
                href=None
                for link in links:
                    for tag in link.findAll(alt='FusionForge Home') :
                        href=link['href']
                        break

            # try with Evolvis variant
            if not href:
                headblock = soup.find('span', {'class': 'headblock'})
                a = headblock.find('a', {'class': 'headlink'})
                href = a['href']
                href=urlparse.urljoin(url, href)

            if href :
                self.url = str(href)

        if self.software == 'Redmine':
            response = urllib2.urlopen(url)
            the_page = response.read()
            soup = BeautifulSoup(the_page)

            # First FF 4.8 inherited from GForge
            links = soup.findAll('a', {'class': 'home'})
            href=None
            for link in links:
                href=link['href']
                href=urlparse.urljoin(url, href)
                break

            title = soup.find('title')
            title = title.text
            redmine_overview_title = re.compile('.* - Overview - (.*)')
            m = redmine_overview_title.match(title)
            name = m.group(1)
            self.name = name

            if href :
                self.url = str(href)
            
            

    def check_version(self):

        import copy
        import RDF

        if self.software == 'FusionForge':
            response = urllib2.urlopen(self.url)
            the_page = response.read()

            # hack to suppress news, which tend to mess with the validity of the document
            # <div class="one-news ... <!-- class="one-news" -->
            the_page = the_page.replace("\n",'')
            myMassage = [(re.compile('<div class="one-news.*<!-- class="one-news" -->'), lambda match: '')]
            myNewMassage = copy.copy(BeautifulSoup.MARKUP_MASSAGE)
            myNewMassage.extend(myMassage)

            soup = BeautifulSoup(the_page, markupMassage=myNewMassage)

            version = None

            divs = soup.findAll('div', id='ft')
            for div in divs:
                text = div.text
                running_version = re.compile('This site is running FusionForge version (.*)')
                m = running_version.match(text)
                version = m.group(1)
                break

            if version:
                self.version = version

            # The following will apply only for FF > 5.1 which includes RDFa
            myMassage = [(re.compile('(<body[^>]*>)(.*)(<div id="ft")'), lambda match: match.group(1) + match.group(3) + ' xmlns:planetforge="http://coclico-project.org/ontology/planetforge#"')]
            myNewMassage = copy.copy(BeautifulSoup.MARKUP_MASSAGE)
            myNewMassage.extend(myMassage)

            soup = BeautifulSoup(the_page, markupMassage=myNewMassage)

            storage=RDF.Storage(storage_name="hashes",
                                name="test",
                                options_string="new='yes',hash-type='memory',dir='.'")
            if storage is None:
              raise "new RDF.Storage failed"

#            RDF.debug(1)

            model=RDF.Model(storage)
            if model is None:
              raise "new RDF.model failed"

            #parser=RDF.Parser(name='raptor')
#            parser=RDF.Parser(name='rdfa', mime_type='application/xhtml+xml')
            parser=RDF.Parser(name='rdfa')
            if parser is None:
              raise "Failed to create RDF.Parser raptor"

            def error_handler(code, level, facility, message, line, column, byte, file, uri):
                print 'error_handler', code, level, facility, message, line, column, byte, file, uri
                pass

            #parser.parse_into_model(model, self.url, handler=error_handler)
            #response = urllib2.urlopen(self.url)
            #the_page = response.read()
            the_page = soup.prettify()
#            print the_page
            parser.parse_string_into_model(model, the_page, self.url, handler=error_handler)

            print "Printing all statements"
            for s in model.as_stream():
                print "Statement:",s

            q = RDF.Query("SELECT ?p ?o WHERE (<"+self.url+"> ?p ?o)")
            print "Querying for page meta-data"
            for result in q.execute(model):
                print "{"
                for k in result:
                    print "  "+k+" = "+str(result[k])
                print "}"
        

def find_powered_by_ala_fusionforge(url) :
    """Matches the presence of a <a> including and <img> whose alt is "Powered By xxxx and matches on FusionForge and http://fusionforge.org/"""
    powered_by_re = re.compile('Powered By ?(.*)',re.I)
    response = urllib2.urlopen(url)
    the_page = response.read()
    soup = BeautifulSoup(the_page)

    links = soup.findAll('a')
    href=None
    forge=None
    for link in links:
        # FusionForge case : an img inside a a
        for tag in link.findAll(alt=powered_by_re) :
            alt = tag['alt']
            m = powered_by_re.match(alt)
            forge = m.group(1)
            break
        # Savane case : a link containing text
        for text in link.findAll(text=powered_by_re) :
            m = powered_by_re.match(text)
            forge = m.group(1)
            break
        if forge:
            href=link['href']
            break

    if href == 'http://fusionforge.org/' and forge == 'FusionForge':
        return Forge(software='FusionForge')
    if forge and forge[:6] == 'Savane':
        r = Forge(software='Savane')
        r.swvariant = forge
        return r

    # Try Redmine
    if not forge:
        divs = soup.findAll('div', id='footer')
        for div in divs:
            if powered_by_re.match(div.text):
                links = div.findAll('a')
                for link in links:
                    href = link['href']
                    forge = link.text
                    break
                if forge == 'Redmine' and href == 'http://www.redmine.org/' :
                    return Forge(software=forge)

    # Try forge identification meta header
    if not forge:
        forge_identification = re.compile('([^:]+):([^:]+)(:.*)?')
        metas = soup.findAll('meta', {'name' : 'Forge-Identification'})
        for meta in metas:
            content = meta['content']
            m = forge_identification.match(content)
            forge = m.group(1)
            version = m.group(2)
            options = m.group(3)
            r = Forge(software=forge)
            r.swvariant = forge + "_" + version
            break
        if forge:
            return r

    return None


def usage():
    print __doc__
    raise SystemExit, 0

if __name__ == '__main__':
    import getopt

    (options, arguments) = getopt.getopt(sys.argv[1:], "h?", ["help",])
    for (arg, val) in options:
        if arg in ('-h', '-?', '--help'):	# help
            usage()

    if len(arguments) == 0 :
        usage()
 
    url = sys.argv[1]
    forge = find_powered_by_ala_fusionforge(url)
    if forge:
        forge.check_homepage(url)
        forge.check_version()
        print 'Identified forge :', forge
        sys.exit(0)
    else:
        print 'Could not identify forge at', url
        sys.exit(1)

                    

# accepts a URL as input

# check if meta-data embedded (RDFa or others)

# check if pointer to base URL of its forge

# then check the forge's home page for more meta-data
