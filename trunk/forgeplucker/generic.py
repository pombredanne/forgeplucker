"""
The GenericForge class is the framework code for fetching state from
forges.  Handler classes (at least for Alexandria-descended forges)
are expected to derive from this, adding and overriding methods where
necessary.
"""

import sys, os, re, urllib, urllib2, time, calendar, email.utils
from htmlscrape import *
from cache import CacheHandler

class ForgePluckerException(Exception):
    def __init__(self, msg):
        self.msg = msg

class GenericForge:
    "Machinery for generic SourceForge-descended forges."
    def __init__(self, host, project_name, params = False):
        "Set up opener with support for authentication cookies."
        self.use_cache = False
        if params and 'use_cache' in params:
            self.use_cache = params['use_cache']
        if self.use_cache :
            self.opener = urllib2.build_opener(CacheHandler("cache"), urllib2.HTTPCookieProcessor())
        else :
            self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        self.host = host
        self.project_name = project_name
        self.verbosity = 0
        self.where = "%s/%s" % (self.host, self.project_name)
    def fetch(self, url, legend, params={}, softfail=False):
        "Instrumented page fetcher, takes optional paremeter dictionary."
        self.where = url
        if params:
            params = urllib.urlencode(params)
        else:
            params = None
        try:
            if not url.startswith("http"):
                url = "https://%s/" % self.host + url

            if self.verbosity == 1:
                self.notify(legend + ": " + url)
            elif self.verbosity >= 2:
                print >>sys.stderr, legend, url
                print >>sys.stderr, "=" * 79

            opener = self.opener.open(url, params)

            if 'x-local-cache' in opener.info():

                if self.verbosity >= 2:
                    self.notify('Loaded from cache')

                if not self.use_cache:
                    if self.verbosity >= 2:
                        print >>sys.stderr, opener.info()
                        print >>sys.stderr, "-" * 79
                    self.opener.recache()
                    if self.verbosity >= 2:
                        self.notify('Not using cache : re-loaded from network')

            if self.verbosity >= 2:
                print >>sys.stderr, opener.info()
                print >>sys.stderr, "-" * 79
                
            page = opener.read()

            if self.verbosity >= 2:
                print >>sys.stderr, page
                print >>sys.stderr, "=" * 79

            return page

        except urllib2.HTTPError, e:
            if softfail:
                if self.verbosity >= 1:
                    self.notify("fetch of %s failed, error %s" % (url, e))
                return None
            else:
                raise e
    def notify(self, msg):
        "Notification hook, can be overridden in subclasses."
        sys.stderr.write(sys.argv[0] + ": " + self.where + ": " + msg + "\n")
    def error(self, msg, ood=True):
        "Error hook, can be overridden in subclasses."
        if ood:
            msg += " - handler class probably out of date"
        raise ForgePluckerException(sys.argv[0] + ": " + self.where + ": " + msg + "\n")
    def isodate(self, date):
        "Canonicalize a date to ISO, catching errorss and reporting location."
        try:
            return self.canonicalize_date(date)
        except ValueError:
            self.error("malformed date \"%s\"" % date)
    def login(self, params, checkstring):
        "Log in to the site."
        if self.verbosity >= 1:
            self.notify("dispatching to " + self.__class__.__name__)
        response = self.fetch(self.login_url(), "Login Page", params)
        if checkstring not in response:
            self.error("authentication failure on login", ood=False)
    def pluck_tracker_ids(self, tracker):
        "Fetch the ID list from the specified tracker."
        chunk_offset = 0
        continued = True
        issueids = []
        while continued:
            continued = False
            indexpage = tracker.chunkfetcher(chunk_offset)
            page = self.fetch(indexpage,
                              "Index page", softfail=tracker.optional)
            if page is None:
                if chunk_offset == 0:	# Soft failure to fetch first page
                    if self.verbosity >= 1:
                        self.notify("'%s' tracker is not configured" % tracker.type)
                    return None
                else:
                    self.error("missing continuation page "+indexpage,ood=False)
            elif tracker.zerostring and tracker.zerostring in page:
                return None
            if tracker.access_denied(page):
                self.error("Tracker technician access to bug index was denied")
            for m in re.finditer(tracker.artifactid_re, page):
                issueid = int(m.group(1))
                if issueid not in issueids:
                    issueids.append(issueid)
            if tracker.has_next_page(page):
                continued = True
            chunk_offset += tracker.chunksize
        if self.verbosity >= 1:
            self.notify("%d artifact IDs for tracker '%s': %s" % (len(issueids), tracker.type, issueids))
        if tracker.zerostring and not issueids:
            self.error("expecting nonempty ID list in %s tracker" % tracker.type)
        return issueids
    def pluck_artifact(self, tracker, issueid, vocabularies=None):
        "Get a dictionary representing a single artifact in a tracker."
        # Enable this to be called with string arguments for debugging purposes
        if type(tracker) == type(""):
            for candidate in self.trackers:
                if candidate.type == tracker:
                    tracker = candidate
                    break
            else:
                self.error("can't find any tracker of type '%s'" % tracker)
        if type(issueid) == type(""):
            issueid = int(issueid)
        # Actual logic starts here  
        contents = self.fetch(tracker.detailfetcher(issueid), "Detail page")
        # Modification access to the tracker is required
        if tracker.access_denied(contents, issueid):
            self.error("tracker technician access to bug details was denied.", ood=False)
        artifact = {"class":"ARTIFACT", "id":issueid, "type": tracker.type}
        m = re.search(tracker.submitter_re, contents)
        if not m:
            self.error("no submitter found")
        submitter = m.group(1)
        #TODO:Task need no date
        m = re.search(tracker.date_re,contents)
        if not m:
            self.error("no date")
        artifact["submitter"] = submitter
        if not m.group(1)=='':
            artifact["date"] = self.isodate(m.group(1).strip())
        formpart = tracker.narrow(contents)
        for m in re.finditer('<SELECT [^>]*?NAME="([^"]*)"[^>]*>', formpart, re.I):
            key = m.group(1)
            startselect = m.start(0)
            endselect = re.search("</SELECT>", formpart[startselect:], re.I)
            if endselect is None:
                raise self.error("closing </SELECT> missing for %s" % key)
            else:
                selectpart = formpart[startselect:startselect+endselect.start(0)]
            possible = []
            selected = []
            isMultiField = False
            if re.search(re.escape('][]'),m.group(1)):
                isMultiField = True
            for m in re.finditer('<OPTION([^>]*)>([^<]*)', selectpart, re.I):
                #Once was '<OPTION([^>]*)>([^<]*)</OPTION>'
                #The preceding is due to following extract from sourceforge html (as emitted by -v 2)
                #<select NAME="priority"><OPTION VALUE="1" >1 - Lowest<OPTION VALUE="2" >2<OPTION...
                possible.append(m.group(2))
                if "selected" in m.group(1) or "SELECTED" in m.group(1):
                    selected.append(m.group(2))
            if len(selected)==1 and not isMultiField:
                selected = selected[0]
            if len(selected)==0:
                selected = None
            if not possible:
                raise self.error("can't parse <SELECT> for %s" % key)
            if not selected:
                selected = possible[0]
            if key not in tracker.ignore:
                artifact[key] = selected
                if vocabularies is not None:
                    vocabularies[key] = possible
        for m in re.finditer('<INPUT[^>]*TEXT[^>]*>', formpart, re.I):
            input_element = m.group(0)
            v = re.search('value="([^"]*)"', input_element)
            if not v:
                continue
            value = v.group(1)
            # It appears that if you embed <pre> (or perhaps <listing>)
            # in a comment, Gna! for some reason processes it into an INPUT
            # element with the attribute READONLY and no name. Example at
            # http://gna.org/bugs/index.php?14407.  What we need to do is
            # skip it here and remove that markup where we process comments,
            # splicing in the value.
            if 'readonly="readonly"' in input_element:
                continue
            n = re.search('name="([^"]*)"', input_element, re.I)
            if not n:
                raise self.error("missing NAME attribute in %s" % input_element)
            name = n.group(1)
            if name in tracker.ignore:
                continue
            #if verbose >= 2:
            #    print "Input name %s has value '%s'" % (name, value)
            artifact[name] = dehtmlize(value)
        # Hand off to the tracker classlet's custom hook 
        tracker.custom(contents, artifact, vocabularies)
        for (rough, smooth) in tracker.name_mappings.items():
            if smooth in artifact and self.verbosity > 0:
                self.error("name collision on %s" % smooth)
            if rough in artifact:
                artifact[smooth] = artifact[rough]
                del artifact[rough]
            for change in artifact['history']:
                if change['field'] == rough:
                    change['field'] = smooth
        return artifact
    def pluck_artifactlist(self, tracker, vocabularies, timeless):
        "Gather artifact information on a specified tracker."
        artifacts = []
        idlist = self.pluck_tracker_ids(tracker)
        if idlist is None:
            return []	# Optional tracker didn't exist
        for issueid in idlist:
            artifacts.append(self.pluck_artifact(tracker, issueid, vocabularies))
        return artifacts
    def get_trackers(self):
        return self.trackers
    def pluck_trackers(self, timeless=False):
        "Pull the buglist, wrapping it with metadata about the operation."
        trackers = {}
        before = timestamp()
        for tracker in self.get_trackers():
            vocabulary, trackers[tracker.type] = {}, {}
            content = self.pluck_artifactlist(tracker, vocabulary, timeless)
            if content is not None:
                trackers[tracker.type]["artifacts"] = content
            url = tracker.projectbase
            if not url.startswith("http"):
                url = "https://%s/" % self.host + url
            trackers[tracker.type]["vocabulary"] = vocabulary
            trackers[tracker.type]["label"] = tracker.label #adding label support to trackers
            trackers[tracker.type]["url"] = url
            # Smooth the vocabulary    
            for (rough, smooth) in tracker.name_mappings.items():
                if rough in vocabulary:
                    vocabulary[smooth] = vocabulary[rough]
                    del vocabulary[rough]
            # Delete range info for assigned_to field, it's not actually useful
            # to treat it as a vocablary.
            if 'assigned_to' in vocabulary:
                del vocabulary['assigned_to']
            trackers[tracker.type]["vocabulary"] = vocabulary
        after = timestamp()
        trackerdata = {
            "class":"PROJECT",
            "forgetype":self.__class__.__name__,
            "host" : self.host,
            "project" : self.project_name,
            "format_version":1,
            "trackers": trackers,
            }
        # See above
        if not timeless:
            trackerdata["interval"] = (before, after)
        return trackerdata
    def login_url(self):
        "Generate the site's account login page URL."
        # Works for SourceForge, Berlios, Savannah, and Gna!.
        # Override in derived classes if necessary.
        return "account/login.php"
    def skipspan(self, text, tag, count):
        "Skip to content enclosed by nth instance of specified tags."
        for dummy in range(count):
            skipindex = text.find("</%s>" % tag)
            if skipindex == -1:
                self.error("missing expected </%s> element" % tag)
            else:
                text = text[skipindex+len(tag)+3:]
        startform = text.find("<" + tag)
        endform = text.find("</%s>" % tag)
        return text[startform:endform]
    def table_iter(self, text, header, cols, errtag, has_header=False, keep_html=False):
        """An implementation of table_iter in BeautifulSoup"""
        rows = []
        header_passed=False
        begin = text.find(header)
        if begin != -1:
            text = text[begin:]
            soup = BeautifulSoup(text)
            result = soup.find(name='table')
            if result != None:
                trs = result.findAll(name='tr')
                if has_header:
                    trs = trs[1:]
                for tr in trs:
                    tds = tr.findAll(name=['td','th'])
                    if cols != None and len(tds) != cols:
                        self.error(errtag+" has wrong width (%d, expecting %d)"
                                       % (len(tds), cols))
                    if keep_html:
                        yield tds
                    else:
                        yield map(lambda x: dehtmlize(str(x)),tds)
    def identity(self, raw):
        "Parse an identity object from a string."
        cooked = {"class":"IDENTITY",}
        raw = dehtmlize(raw.strip())
        if raw.lower() in ("none", "anonymous","nobody"):
            cooked["nick"] = "None"
        else:
            (name, mailaddr) = email.utils.parseaddr(raw)
            if not name and not mailaddr:
                self.error('cannot get identity from "%s"' % raw, ood=False)
            if name:
                cooked['name'] = name
            if email:
                if '@' in mailaddr:
                    cooked['email'] = mailaddr
                else:
                    # Handles 'name <nick>' as we see on Savane
                    cooked['nick'] = mailaddr
        return cooked

    # To be implemented in subclasses
    def pluck_project_data(self):
        '''
        Should return basic project data (type of forge, hostname, project name, format version of this plucker) and returns the corresponding array
        '''
        self.error("Not yet implemented")
        
    # May be implemented in subclasses
    def pluck_wiki(self):
        '''    '''
        self.error("Not yet implemented")
    # May be implemented in subclasses
    def pluck_permissions(self):
        '''    '''
        self.error("Not yet implemented")
    # May be implemented in subclasses
    def pluck_roles(self):
        '''    '''
        self.error("Not yet implemented")
    # May be implemented in subclasses
    def pluck_docman(self):
        '''    '''
        self.error("Not yet implemented")
    # May be implemented in subclasses
    def pluck_frs(self):
        '''    '''
        self.error("Not yet implemented")
    # May be implemented in subclasses
    def pluck_forums(self):
        '''    '''
        self.error("Not yet implemented")
    # May be implemented in subclasses
    def pluck_news(self):
        '''    '''
        self.error("Not yet implemented")
    # May be implemented in subclasses
    def pluck_tasksTrackers(self):
        '''    '''
        self.error("Not yet implemented")
    # May be implemented in subclasses
    def pluck_repository_urls(self):
        '''    '''
        self.error("Not yet implemented")
