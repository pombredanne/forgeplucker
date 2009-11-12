"""
The GenericForge class is the framework code for fiftching state from
forges.  Handler classes are expected to derive from this, adding and
overriding methods where necessary.
"""

import sys, os, re, urllib, urllib2, time, calendar, email.utils
from htmlscrape import *

class ForgePluckerException(Exception):
    def __init__(self, msg):
        self.msg = msg

class GenericForge:
    "Machinery for generic SourceForge-descended forges."
    def __init__(self, host, project_name):
        "Set up opener with support for authentication cookies."
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
            if not url.startswith("https"):
                url = os.path.join("https://%s/" % self.host + url)
            opener = self.opener.open(url, params)
            page = opener.read()
            if self.verbosity == 1:
                self.notify(legend + ": " + url)
            elif self.verbosity >= 2:
                print >>sys.stderr, legend, url
                print >>sys.stderr, "=" * 79
                print >>sys.stderr, opener.info()
                print >>sys.stderr, "-" * 79
                print >>sys.stderr, page
                print >>sys.stderr, "=" * 79
            return page
        except urllib2.HTTPError, e:
            if softfail:
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
            self.error("malformed date %s" % date)
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
        bugids = []
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
                bugid = int(m.group(1))
                if bugid not in bugids:
                    bugids.append(bugid)
            if not self.sample and tracker.has_next_page(page):
                continued = True
            chunk_offset += tracker.chunksize
        if self.verbosity >= 1:
            self.notify("%d artifact IDs for tracker '%s': %s" % (len(bugids), tracker.type, bugids))
        if tracker.zerostring and not bugids:
            self.error("expecting nonempty ID list in %s tracker" % tracker.type)
        return bugids
    def pluck_artifact(self, tracker, bugid, vocabularies=None):
        "Get a dictionary representing a single artifact in a tracker."
        # Enable this to be called with string arguments for debugging purposes
        if type(tracker) == type(""):
            for candidate in self.trackers:
                if candidate.type == tracker:
                    tracker = candidate
                    break
            else:
                self.error("can't find any tracker of type '%s'" % tracker)
        if type(bugid) == type(""):
            bugid = int(bugid)
        # Actual logic starts here  
        contents = self.fetch(tracker.detailfetcher(bugid), "Detail page")
        # Modification access to the tracker is required
        if tracker.access_denied(contents, bugid):
            self.error("tracker technician access to bug details was denied.", ood=False)
        artifact = {"class":"ARTIFACT", "id":bugid}
        m = re.search(tracker.submitter_re, contents)
        if not m:
            self.error("no submitter found")
        submitter = m.group(1)
        m = re.search(tracker.date_re,contents)
        if not m:
            self.error("no date")
        artifact["submitter"] = submitter
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
            selected = None
            for m in re.finditer('<OPTION([^>]*)>([^<]*)', selectpart, re.I):
                #Once was '<OPTION([^>]*)>([^<]*)</OPTION>'
                #The preceding is due to following extract from sourceforge html (as emitted by -v 2)
                #<select NAME="priority"><OPTION VALUE="1" >1 - Lowest<OPTION VALUE="2" >2<OPTION...
                possible.append(m.group(2))
                if "selected" in m.group(1) or "SELECTED" in m.group(1):
                    if selected:
                        raise self.error("multiple selections for %s" % key)
                    selected = m.group(2)
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
        tracker.custom(contents, artifact)
        return artifact
    def pluck_artifactlist(self, tracker, timeless):
        "Gather artifact information on a specified tracker."
        artifacts = []
        vocabularies = {}
        trackerwhere = self.where
        before = timestamp()
        idlist = self.pluck_tracker_ids(tracker)
        if idlist is None:
            return None	# Optional tracker didn't exist
        # Empty tracker returns an empty list rather than None;
        # This will be passed through to the report structure.
        if self.sample and idlist:
            idlist = idlist[-1:]
        for bugid in idlist:
            artifacts.append(self.pluck_artifact(tracker, bugid, vocabularies))
        self.where = trackerwhere
        after = timestamp()
        artifacts = {"class":"TRACKER",
                     "type":tracker.type,
                     "vocabularies":vocabularies,
                     "artifacts":artifacts}
        # The timestamps screw up regression tests,
        # so we need to be able to suppress them.
        if not timeless:
            artifacts["interval"] = (before, after)
        return artifacts
    def pluck_bugs(self, sample=False, timeless=False):
        "Pull the buglist, wrapping it with metadata. about the operation."
        self.sample = sample
        trackerdata = []
        before = timestamp()
        for tracker in self.trackers:
            content = self.pluck_artifactlist(tracker, timeless)
            if content is not None:
                trackerdata.append(content)
        after = timestamp()
        trackerdata = {
            "class":"PROJECT",
            "forgetype":self.__class__.__name__,
            "host" : self.host,
            "project" : self.project_name,
            "format_version":1,
            "sample":self.sample,
            "trackers":trackerdata,
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
        for dummy in range(count):
            skipindex = text.find("</%s>" % tag)
            if skipindex == -1:
                self.error("missing expected </%s> element" % tag)
            else:
                text = text[skipindex+len(tag)+3:]
        startform = text.find("<" + tag)
        endform = text.find("</%s>" % tag)
        return text[startform:endform]
    def table_iter(self, contents, header, cols, errtag, has_header=False):
        "Iterate through a tracker tabular report."
        begin = contents.find(header)
        if begin > -1:
            followups = walk_table(contents[begin:])
            if followups:
                if has_header:
                    followups.pop(0)
                for row in followups:
                    if len(row) != cols:
                        self.error(errtag+" has wrong width (%d, expecting %d)"
                                   % (len(row), cols))
                    else:
                        yield map(dehtmlize, row)
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
