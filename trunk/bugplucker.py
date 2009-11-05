#!/usr/bin/env python

"""
bugplucker.py -- extract bugtracker state from hosting sites.

usage: bugplucker.py [-hrv?] [-f type] [-u user] [-p password] site/project

State is dumped to standard output in JSON.

This code is Copyright (c) 2009 by Eric S. Raymond.  New BSD license applies.
For the terms of this license, see the file COPYING included with this
distribution.

Requires Python 2.6.
"""

import sys, os, re, urllib, urllib2, time, calendar, email.utils

class ForgePluckerException:
    def __init__(self, msg):
        self.msg = msg

#
# HTML parsing
#

def walk_table(text):
    "Parse out the rows of an HTML table."
    rows = []
    while True:
        oldtext = text
        # First, strip out all attributes for easier parsing
        text = re.sub('<TR[^>]+>', '<TR>', text, re.I)
        text = re.sub('<TD[^>]+>', '<TD>', text, re.I)
        text = re.sub('<tr[^>]+>', '<TR>', text, re.I)
        text = re.sub('<td[^>]+>', '<TD>', text, re.I)
        # Case-smash all the relevant HTML tags, we won't be keeping them.
        text = text.replace("</table>", "</TABLE>")
        text = text.replace("<td>", "<TD>").replace("</td>", "</TD>")
        text = text.replace("<tr>", "<TR>").replace("</tr>", "</TR>")
        text = text.replace("<br>", "<BR>")
        # Yes, Berlios generated \r<BR> sequences with no \n
        text = text.replace("\r<BR>", "\r\n")
        # And Berlios generated doubled </TD>s
        text = text.replace("</TD></TD>", "</TD>")
        # Now that the HTML table structure is canonicalized, parse it.
        if text == oldtext:
            break
    end = text.find("</TABLE>")
    if end > -1:
        text = text[:end]
    while True:
        m = re.search(r"<TR>\w*", text)
        if not m:
            break
        start_row = m.end(0)
        end_row = start_row + text[start_row:].find("</TR>")
        rowtxt = text[start_row:end_row]
        rowtxt = rowtxt.strip()
        if rowtxt:
            rowtxt = rowtxt[4:-5]	# Strip off <TD> and </TD>
            rows.append(re.split(r"</TD>\s*<TD>", rowtxt))
        text = text[end_row+5:]
    return rows

def dehtmlize(text):
    "Remove HTMLisms from text."
    # Gna! can sometimes embed input elements with a readonly attribute
    # and a value but no name. These are rendered as though they were
    # wrapped in <pre> or <listing>.  Rescue the value.
    text = re.sub('<input[^>]*readonly="readonly"[^>]*value="([^"]*)"[^>]*>',
                  "\n\\1\n", text, re.I)
    text = re.sub("<[^>]*>", "", text)
    text = text.replace("&quot;", '"')
    text = text.replace("&lt;",   '<')
    text = text.replace("&gt;",   '>')
    text = text.replace("\r\n",   '\n')
    return text

def blocktext(text):
    "Canonicalize whitespace around the text."
    return text.strip() + "\n"

def timestamp():
    "Timestamp in ISO time."
    return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(time.time()))

#
# Instrumented page fetching
#

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
    def error(self, msg):
        "Error hook, can be overridden in subclasses."
        raise ForgePluckerException(sys.argv[0] + ": " + self.where + ": " + msg + "\n")
    def isodate(self, date):
        "Canonicalize a date to ISO, catching errorss and reporting location."
        try:
            return self.canonicalize_date(date)
        except ValueError, e:
            self.error("malformed date %s" % date)
    def login(self, params, checkstring):
        "Log in to the site."
        if self.verbosity >= 1:
            self.notify("dispatching to " + self.__class__.__name__)
        response = self.fetch(self.login_url(), "Login Page", params)
        if checkstring not in response:
            self.error("authentication failure on login")
    def pluck_tracker_ids(self, tracker):
        "Fetch the ID list from the specified tracker."
        chunk_offset = 0
        continued = True
        admin = False
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
                    self.error("missing continuation page " + indexpage)
            elif tracker.zerostring and tracker.zerostring in page:
                return None
            if tracker.access_denied(page):
                self.parent.error("Tracker technician access was denied.")
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
            self.error("Tracker technician access was denied.")
        artifact = {"class":"ARTIFACT", "id":bugid}
        m = re.search(tracker.submitter_re, contents)
        if not m:
            self.error("no submitter")
        submitter = m.group(1)
        m = re.search(tracker.date_re,contents)
        if not m:
            self.error("no date")
        artifact["submitter"] = submitter
        artifact["date"] = self.isodate(m.group(1).strip())
        formpart = tracker.narrow(contents)
        for m in re.finditer('<SELECT NAME="([^"]*)">', formpart, re.I):
            key = m.group(1)
            startselect = m.start(0)
            endselect = re.search("</SELECT>", formpart[startselect:], re.I)
            if endselect is None:
                raise self.error("closing </SELECT> missing for %s" % key)
            else:
                selectpart = formpart[startselect:startselect+endselect.start(0)]
            possible = []
            selected = None
            for m in re.finditer('<OPTION([^>]*)>([^<]*)</OPTION>', selectpart, re.I):
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
            if verbose >= 2:
                print "Input name %s has value '%s'" % (name, value)
            artifact[name] = dehtmlize(value)
        # Hand off to the tracker classlet's custom hook 
        tracker.custom(contents, artifact)
        return artifact
    def pluck_artifactlist(self, tracker):
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
        return {"class":"TRACKER",
                    "type":tracker.type,
                    "vocabularies":vocabularies,
                    "interval":(before, after),
                    "artifacts":artifacts}
    def pluck_bugs(self, sample=False):
        "Pull the buglist, wrapping it with metadata. about the operation."
        self.sample = sample
        trackerdata = []
        before = timestamp()
        for tracker in self.trackers:
            content = self.pluck_artifactlist(tracker)
            if content is not None:
                trackerdata.append(content)
        after = timestamp()
        trackerdata = {
            "class":"PROJECT",
            "forgetype":self.__class__.__name__,
            "host" : self.host,
            "project" : self.project_name,
            "interval" : (before, after),
            "format_version":1,
            "sample":self.sample,
            "trackers":trackerdata,
            }
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
        if raw.lower() in ("none", "anonymous"):
            cooked["nick"] = "None"
        else:
            (name, mailaddr) = email.utils.parseaddr(raw)
            if not name and not mailaddr:
                self.error('cannot get identity from "%s"' % raw)
            if name:
                cooked['name'] = name
            if email:
                if '@' in mailaddr:
                    cooked['email'] = mailaddr
                else:
                    # Handles 'name <nick>' as we see on Savane
                    cooked['nick'] = mailaddr
        return cooked
#
# SourceForge
#

class SourceForge(GenericForge):
    """
The SourceForge handler provides bug-plucking machinery for the SourceForge
site.

This code does not capture custom trackers.
"""
    def __init__(self, host, project_name):
        GenericForge.__init__(self, host, project_name);
        self.trackers = [
            #SourceForge.BugTracker(self),
            #SourceForge.SupportTracker(self),
            #SourceForge.PatchTracker(self),
            #SourceForge.FeatureTracker(self),
            ]
    def login(self, username, password):
        mainpage =  "projects/%s/" % self.project_name
        m = re.search(r'\?group_id=([0-9]*)',
                      self.fetch(mainpage, "Project Page"))
        if m:
            self.project_id = int(m.group(1))
        else:
            self.error("can't find a project ID for %s" % self.project_name)
        GenericForge.login(self, {
            'form_loginname':username,
            'form_pw':password,
            'stay_in_ssl':"1",
            'return_to':"",
            'login':'Login With SSL'}, "Member Since:")

#
# Berlios
#

class Berlios(GenericForge):
    """
The Berlios handler provides bug-plucking machinery for the Berlios site.

The FusionForge site claims Berlios is a GForge/FusionForge instance, so this
code may generalize.

Things it doesn't grab yet:
* Tasks and task interdependencies.
* Mantis bugs.

Bug, feature-request, and patch trackers always exist in conjunction
with any given project, and are simply empty if no artifacts have been
submitted to them.
"""
# For an example with Mantis bugs, see the codeblocks project.
    class Tracker:
        def __init__(self, parent):
            self.parent = parent
            self.optional = False
            self.chunksize = 50
            self.zerostring = None
            self.submitter_re = r"<TD><B>Submitted By:</B><BR>([^<]*)</TD>"
            self.date_re = "<TD><B>Date Submitted:</B><BR>([^<]*)</TD>"
            self.ignore = ("canned_response", "project_id")
        def access_denied(self, page, issue_id=None):
            return issue_id is None and not "Admin:" in page
        def has_next_page(self, page):
            return "Next 50" in page
        def narrow(self, text):
            "Get the section of text containing editable elements."
            return self.parent.skipspan(text, "FORM", 1)
        def parse_followups(self, contents):
            "Parse followups out of a displayed page in a bug or patch tracker."
            comments = []
            for (sc, date, submitter) in self.parent.table_iter(contents,
                                                                "<H3>Followups</H3>",
                                                                3,
                                                                "followup",
                                                                has_header=True):
                comments.append({"class":"COMMENT",
                                 'submitter': self.parent.identity(submitter),
                                 'date': self.parent.isodate(date),
                                 'comment': blocktext(sc)})
            return comments
        def parse_history_table(self, contents, report):
            "Get the change history attached to a tracker artifact."
            report["history"] = []
            for (field, old, date, by) in self.parent.table_iter(contents,
                                                     "Change History</H3>",
                                                     4,
                                                     "history",
                                                     has_header=True):
                if old.startswith("1969"):
                    old = 'Never'
                date = self.parent.isodate(date)
                # The close-date field is redundant with the timestamp
                # on the status field, so omit it.  It appesrs to be
                # leakage from an implementation bug.
                if field == 'close_date':
                    continue
                if field not in report:
                    self.parent.notify("uncovered field '%s' in history"%field)
                    continue
                report["history"].append({"class":"FIELDCHANGE",
                                          'field': field,
                                          'old': old,
                                          'date':date,
                                          'by': by})
                # Fill in missing new-value fields
                history = report['history']
                for i in range(len(history)):
                    for j in range(i):
                        if history[i-j-1]['field'] == history[i]['field']:
                            history[i-j-1]['new'] == history[i]['old']
                            break;
                for i in range(len(history)):
                    if 'new' not in history[i]:
                        history[i]['new'] = report[history[i]['field']]
    class BugTracker(Tracker):
        def __init__(self, parent):
            Berlios.Tracker.__init__(self, parent)
            self.type = "bugs"
            self.artifactid_re = r'<A HREF="/bugs/\?func=detailbug&bug_id=([0-9]+)&group_id=%s">' % parent.project_id
        def chunkfetcher(self, offset):
            "Get a bugtracker index page - all bug IDs, open and closed.."
            return "bugs/index.php?func=browse&group_id=%s&set=custom&offset=%d" % (self.parent.project_id, offset)
        def detailfetcher(self, bugid):
            "Generate a bug detail URL for the specified bug ID."
            return "bugs/?func=detailbug&bug_id=%d&group_id=%s" % \
                   (bugid, self.parent.project_id)
        def custom(self, contents, bug):
            m = re.search("<B>Original Submission:</B><BR>", contents)
            if not m:
                self.parent.error("no original-submission text")
            m = re.search(r"<H2>\[ [A-Za-z ]* #[0-9]+ \] ([^<]*)</H2>", \
                          contents)
            if not m:
                self.error("no summary")
            bug["summary"] = dehtmlize(m.group(1))
            # We're done with the header metadata, simplify life.
            contents = contents[m.end(0):]
            submission = None
            m = re.search("<B>Original Submission:</B>(.*)<H3>No Followups Have Been Posted", contents, re.DOTALL)
            if m:
                submission = m.group(1)
            else:
                m = re.search("<B>Original Submission:</B>(.*)<H3>Followups</H3>", contents, re.DOTALL)
                if m:
                    submission = m.group(1)
            if not submission:
                self.parent.error("mangled submission comment")
            # Ontological smoothing: submission comment becomes comment 0
            bug['comments'] = [{"class":"COMMENT",
                                'submitter':self.parent.identity(bug['submitter']),
                                'date': bug['date'],
                                'comment': blocktext(dehtmlize(submission))}]
            del bug['submitter']
            del bug['date']
            contents = contents[m.end(0):]
            bug["comments"] += self.parse_followups(contents)
            bug["dependents"] = []
            for (bugnum, bugname) in self.parent.table_iter(contents,
                                                "<H3>Other Bugs That Depend on This Bug</H3>",
                                                2,
                                                "dependency",
                                                has_header=True):
                bug["dependents"].append(int(bugnum))
            self.parse_history_table(contents, bug)
    class FeatureTracker(Tracker):
        def __init__(self, parent):
            Berlios.Tracker.__init__(self, parent)
            self.type = "feature"
            self.artifactid_re = r'<A HREF="\?func=detailfeature&feature_id=([0-9]+)&group_id=%s">' % parent.project_id
        def chunkfetcher(self, offset):
            "Get a feature tracker index page - all bug IDs, open and closed.."
            return "feature/index.php?func=browse&group_id=%s&set=custom&offset=%d" % (self.parent.project_id, offset)
        def detailfetcher(self, bugid):
            "Generate a feature detail URL for the specified bug ID."
            return "feature/?func=detailfeature&feature_id=%d&group_id=%s" % \
                   (bugid, self.parent.project_id)
        def custom(self, contents, feature):
            m = re.search(r"<H2>\[ [A-Za-z ]* #[0-9]+ \] ([^<]*)</H2>", \
                          contents)
            if not m:
                self.error("no summary")
            # Delete fields that will be redundant with comment headers 
            del feature['date']
            del feature['submitter']
            feature["summary"] = dehtmlize(m.group(1))
            feature["comments"] = []
            for m in re.finditer("<PRE>([^>]*)</PRE>", contents):
                message = m.group(1).strip()
                # Strangely, Berlios feature comments look like RFC22
                # with Date: and Sender: headers first.
                m = re.match("Date: (.*)\n", message)
                if not m:
                    self.parent.error("missing Date in message")
                else:
                    date = self.parent.isodate(m.group(1))
                    message = message[m.end(0):]
                m = re.match("Sender: (.*)\n", message)
                if not m:
                    self.parent.error("missing Sender in message")
                else:
                    submitter = m.group(1)
                    message = message[m.end(0):]
                feature["comments"].append({"class":"COMMENT",
                                            'date':date,
                                            'submitter':self.parent.identity(submitter),
                                            'comment':blocktext(dehtmlize(message))})
            self.parse_history_table(contents, feature)
    class PatchTracker(Tracker):
        def __init__(self, parent):
            Berlios.Tracker.__init__(self, parent)
            self.type = "patches"
            self.artifactid_re = r'<A HREF="\?func=detailpatch&patch_id=([0-9]+)&group_id=%s">' % parent.project_id
        def chunkfetcher(self, offset):
            "Get a patch tracker index page - all bug IDs, open and closed.."
            return "patch/index.php?func=browse&group_id=%s&set=custom&offset=%d" % (self.parent.project_id, offset)
        def detailfetcher(self, bugid):
            "Generate a patch detail URL for the specified bug ID."
            return "patch/?func=detailpatch&patch_id=%d&group_id=%s" % \
                   (bugid, self.parent.project_id)
        def custom(self, contents, patch):
            m = re.search(r"<H2>\[ [A-Za-z ]* #[0-9]+ \] ([^<]*)</H2>", \
                          contents)
            if not m:
                self.error("no summary")
            patch['summary'] = dehtmlize(m.group(1))
            # Ontological smoothing.  Interpret a patch as an attachment
            attacher = patch['submitter']
            del patch['submitter']
            m = re.search(r'<A HREF="(/patch/download.php\?id=([0-9]*))">', contents)
            if not m:
                self.parent.error("can't find patch URL")
            filename = m.group(1)
            fileid = m.group(2)
            patch["attachments"] = [{
                "class":"ATTACHMENT",
                "filename": filename,
                "by": self.parent.identity(attacher),
                "date": patch['date'],
                "id": fileid,
                # No filename in this case 
                }]
            del patch['date']

            patch["comments"] = self.parse_followups(contents)
            self.parse_history_table(contents, patch)

    def __init__(self, host, project_name):
        GenericForge.__init__(self, host, project_name);
        self.project_id = self.numid_from_name(self.project_name)
        self.trackers = [
            Berlios.BugTracker(self),
            Berlios.FeatureTracker(self),
            Berlios.PatchTracker(self),
            ]
    def project_page(self, project):
        return "projects/%s/" % (project,)
    def numid_from_name(self, name):
        mainpage = self.project_page(name)
        # There are lots of CGI links with the ID in it we could look for.
        # Every project has a bugtracker, so we'll look for that one.
        m = re.search(r'/bugs/\?group_id=([0-9]*)', self.fetch(mainpage, "Project Page"))
        if m:
            return m.group(1)
        else:
            raise ForgePluckerException("can't find a project ID for %s" % name)
    @staticmethod
    def canonicalize_date(localdate):
        "Canonicalize dates to ISO form. Assumes dares are in local time."
        t = time.strptime(localdate, "%Y-%b-%d %H:%M")
        secs = time.mktime(t)	# Local time to seconds since epoch
        t = time.gmtime(secs)	# Seconds since epoch to UTC time in structure
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", t)
    def login(self, username, password):
        response = GenericForge.login(self, {
            'form_loginname':username,
            'form_pw':password,
            'stay_in_ssl':1,
            'return_to':"",
            'login':'Login With SSL'}, "Personal Page")

class Savane(GenericForge):
    """
The Savane handler provides bug-plucking machinery for a Savane
site. It is used for Gna! and Savannah.

The status of all trackers (bug, patch, support, and task) is extracted.
"""
# There are two minor variants of Savane. The original Savane is used on Gna!,
# SavaneCleanup on Savannah. The date formats differ, see the canonicalize_date
# method.
#
# Bug tracker extraction is verified on both Savane and SavaneCleanup,
# All other trackers are verified only on Savane.
#
# For a project with a patch and support manager manager and without a
# bug manager, see Savannah Bayonne. For a project with a task
# manager, see Beaver.  For a project with more than 50 artifacts in a
# tracker, see Gna! Wesnoth or ClanLib Savannah
    class Tracker:
        "Generic tracker classlet for Savane."
        def __init__(self, parent):
            self.parent = parent
            self.optional = True
            self.chunksize = 50
            self.zerostring = "No matching items found"
            self.artifactid_re = r'<a href="\?([0-9]+)">'
            # This may yield anchor markup around the submitter name.
            # Sometimes it's present, if the submitter is a known user
            self.submitter_re = r'Submitted by:&nbsp;</td>\s*<td[^>]*>(<a[^>]*>[^<]*</a>|[^<]+)</td>'
            self.date_re = r'Submitted on:[^<]*</td>\s*<td[^>]*>([^<]*)</td>'
            self.ignore = ('canned_response',
                           'comment_type_id',
                           'depends_search_only_artifact',
                           'depends_search_only_project',
                           'reassign_change_artifact',
                           "add_cc",
                           "cc_comment",
                           "new_vote")
        def access_denied(self, page, issue_id=None):
            return issue_id is not None and re.search("This task has [0-9]+ encouragements? so far.", page)
        def has_next_page(self, page):
            m = re.search("([0-9]+) matching items - Items [0-9]+ to ([0-9]+)", page)
            if not m:
                self.parent.error("missing item count header")
            else:
                return int(m.group(1)) > int(m.group(2))
        def chunkfetcher(self, offset):
            "Get a tracker index page - all artifact IDs, open and closed.."
            return "%s/index.php?go_report=Apply&group=%s&func=browse&set=custom&chunksz=50&offset=%d" % (self.type, self.parent.project_name, offset)
        def detailfetcher(self, artifactid):
            "Generate a detail URL for the specified artifact ID."
            return "%s/index.php?%d" % (self.type, artifactid)
        def narrow(self, text):
            "Get the section of text containing editable elements."
            return self.parent.skipspan(text, "form", 1)
        def custom(self, contents, artifact):
            # Parse comments, then trim them off the front -- they can have
            # things in them that confuse later parsing.  For an example,
            # see https://gna.org/bugs/index.php?6264
            artifact['comments'] = self.parent.parse_followups(contents)
            astart = contents.find('<a name="attached">')
            if astart == -1:
                self.error("can't find attachments section")
            else:
                contents = contents[astart:]
            # Capture attachments.
            artifact["attachments"] = []
            for m in re.finditer(r'<a href="([^"]*)">file #([0-9]+): &nbsp;([^<]*)</a> added by (<a href="[^"]*">[^<]*</a>|None) <span class="smaller">\((.*)\)', contents):
                url = m.group(1)
                fileid = m.group(2)
                filename = m.group(3)
                attacher = dehtmlize(m.group(4))
                rest = m.group(5)
                # Parse the comment part
                commentfields = map(lambda x: x.strip(), rest.split(" - "))
                commentfields.pop(0)
                mimetype = description = None
                if commentfields:
                    mimetype = dehtmlize(commentfields.pop(0))
                    if commentfields:
                        description = dehtmlize(commentfields.pop(0))
                artifact["attachments"].append({
                    "class":"ATTACHMENT",
                    "filename": filename,
                    "id": fileid,
                    "by": self.parent.identity(attacher),
                    "mimetype": mimetype,
                    'description': description,
                    })
            if ("No files currently attached" in contents) != (len(artifact["attachments"])==0):
                self.parent.error("garbled file-attachment section, possible version-skew problem (%d items)." % len(artifact["attachments"]))
            # Capture votes
            artifact['votes'] = None
            if "There is 1 vote so far." in contents:
                artifact['votes'] = 0
            else:
                m = re.search("There are ([0-9]*) votes so far.", contents)
                if m:
                    artifact['votes'] = int(m.group(1))
            if artifact['votes'] is None:
                self.parent.error('cannot find a vote indication')
            # Capture the history list
            artifact["history"] = []
            for (date,
                 by,
                 field,
                 old,
                 dummy,
                 new) in self.parent.table_iter(contents,
                                                "latest change",
                                                6,
                                                "history",
                                                has_header=True):
                # Savane leaves the Date and Changed-by fields blank
                # (actually, containing &nbsp;) when they represent
                # the second or later field changes made at one time.
                if date[-1].isdigit():
                    date = self.parent.isodate(date)
                elif date == '&nbsp;':
                    date = artifact['history'][-1]['date']
                if by == '&nbsp;':
                    by = artifact['history'][-1]['by']
                artifact["history"].append({"class":"FIELDCHANGE",
                                        'field': field,
                                        'old': old,
                                        'new': new,
                                        'date':date,
                                        'by': by})
            # Capture the CC list. It is expected that modifications to
            # this will be in the history, which is why we don't
            # capture who added this entry here.
            artifact["subscribers"] = []
            ccstart = contents.find("Carbon-Copy")
            if ccstart > -1:
                tail = contents[ccstart:]
                for m in re.finditer('<a[^>]*>([^<]*)</a> added by <a[^>]*>[^<]*</a> <span class="smaller">\(([^)]*)\)</span>', tail):
                    subscriber = m.group(1)
                    reason = m.group(2)
                    artifact["subscribers"].append({"subscriber":self.parent.identity(subscriber),
                                                    "reason":reason})
            # Capture the dependency list, if present
            artifact["dependents"] = []
            dpstart = contents.find("Items that depend on this one")
            if dpstart > -1:
                tail = contents[dpstart:]
                for m in re.finditer(r'\([a-zA-Z ]* #([0-9]+), [a-zA-Z ]*\)', tail):
                    artifact["dependents"].append(int(m.group(1)))            
    class BugTracker(Tracker):
        def __init__(self, parent):
            Savane.Tracker.__init__(self, parent)
            self.type = "bugs"
    class PatchTracker(Tracker):
        def __init__(self, parent):
            Savane.Tracker.__init__(self, parent)
            self.type = "patch"
    class TaskTracker(Tracker):
        def __init__(self, parent):
            Savane.Tracker.__init__(self, parent)
            self.type = "task"
    class SupportTracker(Tracker):
        def __init__(self, parent):
            Savane.Tracker.__init__(self, parent)
            self.type = "support"
    def __init__(self, host, project_name):
        GenericForge.__init__(self, host, project_name);
        self.host = host
        self.project_name = project_name
        self.verbosity = 0
        self.trackers = [Savane.BugTracker(self),
                         Savane.SupportTracker(self),
                         Savane.TaskTracker(self),
                         Savane.PatchTracker(self)]
    @staticmethod
    def canonicalize_date(date):
        "Canonicalize Savane dates to ISO."
        # SavaneCleanup dates will look like this: Fri 22 Jun 2001
        # 09:54:07 AM UTC. The timezone is variable according to the
        # user's preferences; sometimes SavaneCleanup omits the
        # timezone. Beware that strptime(3) doesn't actually interpret
        # %Z, it only barfs on bad values. So we have to do it.
        #
        # Savane dates may look like this: "Sun Jul 27 11:08:45 2008"
        # (note the absence of timezone and that time and year are swapped)
        # or like this: "Thursday 10/15/2009 at 06:40".
        if date == '-':			# Gna! sometimes generates these
            return 'None'
        if '/' in date:			# Gna! date
            t = time.strptime(date, "%A %m/%d/%y at %H:%M")
        elif date[-1].isalpha():	# Savannah date with timezone
            t = time.strptime(date, "%a %d %b %Y %H:%M:%S %p %Z")
        else:				# Savannah date without timezone
            t = time.strptime(date, "%a %b %d %H:%M:%S %Y")
        if "UTC" in date or "GMT" in date:
            secs = calendar.timegm(t)	# struct time in UTC to secs since epoch
        else:
            secs = time.mktime(t)	# struct local time to secs since epoch
        t = time.gmtime(secs)		# secs since epoch to struct UTC time
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", t)
    def login(self, username, password):
        response = GenericForge.login(self, {
            'uri':'/',
            'form_loginname':username,
            'form_pw':password,
            'stay_in_ssl':1,
            'brotherhood':1,
            'login':'Login'}, "My Incoming Items")
    def parse_followups(self, contents):
        "Parse followups out of a displayed page in a bug or patch tracker."
        comments = []
        # Look for the anchor Savane creates for the Discussion section.
        begin = contents.find('href="#discussion"')
        if begin == -1:
            self.notify("no discussion")
        else:
            contents = contents[begin:].replace("<br />", "<br/>")
            # There's no decorative header element in this table.
            for row in walk_table(contents):
                if len(row) > 1 and "Spam posted by" in row[1]:
                    continue
                try:
                    # Savane comments have *two* column elements per comment,
                    # one for date and text, the second for the user.
                    (comment, submitter) = row
                    date = comment.split("<br/>")[0]
                    comment = "\n".join(comment.split("<br/>")[1:])
                    # Submitter's name may have HTML markup in it.
                    # But first toss everything after <br/>, it's image
                    # cruft.
                    submitter = submitter.split("<br/>")[0]
                    # Throw out everything past the terminating comma
                    # If this leads to an ill-formed date, because somebody
                    # moved the punctuation, isodate() should throw an error
                    m = re.search("<[^>]+>([^<]+),", date)
                    if not m:
                        self.error("date field garbled")
                    date = self.isodate(m.group(1))
                    # Comment may have HTML in it. Do normal markup
                    # stripping,but first deal with the funky way that
                    # Savane emits paragraph delimiters.
                    comment = comment.replace("\n\n", "\n")
                    comment = comment.replace("\n</p>\n<p>", "\n")
                    comment = blocktext(dehtmlize(comment))
                    # Stash the result.
                    comments.append({"class":"COMMENT",
                                     'submitter':self.identity(submitter),
                                     'date':date,
                                     'comment':comment})
                except ValueError:
                    raise self.parent.error("mangled followup,")
        return comments

def canonicalize(issues):
    "Canonicalize issue data."
    name_mappings = {
        "bug_group_id": "group",
        "category_id": "category",
        "category_version_id": "category_version",	# Savane
        #'comment_type_id', 'comment_type',		# Savane
        "fix_release_id": "fix_release_version",	# Savane
        "feature_status_id": "status",			# Berlios
        "feature_category_id": "category",		# Berlios
        "patch_status_id": "status",			# Berlios
        "patch_category_id": "category",		# Berlios
        "plan_release_id": "plan_release_version",	# Savane
        "platform_version_id": "platform_version",	# Savane
        "reproducibility_id": "reproducibility",	# Savane
        "resolution_id": "resolution",
        "size_id": "size",				# Savane
        "status_id": "status",
        }
    for tracker in issues['trackers']:
        # Delete range info for assigned_to field, it's not actually useful
        # to treat it as a vocablary.
        del tracker['vocabularies']['assigned_to']
        # Perform name smoothing so we have a semi-standard set of attributes
        # across all forges and tracker types.
        for (rough, smooth) in name_mappings.items():
            if rough in tracker['vocabularies']:
                tracker['vocabularies'][smooth] = tracker['vocabularies'][rough]
                del tracker['vocabularies'][rough]
            for artifact in tracker['artifacts']:
                if rough in artifact:
                    if smooth in artifact:
                        raise ForgePluckerException(sys.argv[0] + ": name collision on %s" % smooth)
                    artifact[smooth] = artifact[rough]
                    del artifact[rough]
                    for change in artifact['history']:
                        if change['field'] == rough:
                            change['field'] = smooth
    return issues

def xml_dump(issues, fp=sys.stdout):
    "XML dump of bugtracker state.  NOT YET fully implemented."
    def xmlize(txt):
        txt = txt.replace('<', '&#60;')
        txt = txt.replace('>', '&#62;')
        txt = txt.replace('&', '&#38;')
        txt = txt.replace('"', '&#34;')
        return txt
    def identity_dump(identity, indent=0):
        if type(identity) != type({}) or 'class' not in identity or identity['class'] != 'IDENTITY':
            raise ValueError
            #raise ForgePluckerException(sys.argv[0] + ': illegal identity specification "%s"\n' % identity)
        # FIXME: Needs to be replaced with some sort of FOAF thing
        idump = (' ' * indent) + "<identity"
        for (key, val) in identity.items():
            if key != "class":
                idump += ' "%s"="%s"' % (key, val)
        idump += "/>"
        return idump
    fp.write('<trackers>\n')
    for tracker in issues['trackers']:
        fp.write('  <tracker id="%s">\n' % tracker['type'])
        fp.write('    <capture-begins>%s</capture-begins>\n' \
                 % tracker['interval'][0])
        fp.write('    <artifacts>\n')
        for artifact in tracker['artifacts']:
            fields = artifact.keys()
            fields.remove("class")	# Always 'ARTIFACT'
            fp.write('    <artifact id="%s">\n' % artifact['id'])
            fields.remove("id")
            # List in case we get more attributes we want to move up front 
            for field in ('summary', "assigned_to"):
                fp.write('      <%s>%s</%s>\n' % (field,artifact[field],field))
                fields.remove(field)
            selects = tracker['vocabularies'].keys()
            selects.sort()
            for field in selects:
                fp.write('      <attribute name="%s" value="%s"/>\n' % (field,artifact[field]))
                fields.remove(field)
            if 'comments' in artifact:
                if artifact['comments']:
                    fp.write('      <comments>\n')
                for (i, comment) in enumerate(artifact['comments']):
                    fp.write('        <comment number="%d">\n' % i)
                    fp.write('          <submitter>\n')
                    fp.write(identity_dump(comment['submitter'], indent=12))
                    fp.write('          </submitter>\n')
                    fp.write('          <date>%s</date>\n' % comment['date'])
                    fp.write('          <text>\n')
                    fp.write(xmlize(comment['comment']))
                    fp.write('          </text>\n')
                    fp.write('        </comment>\n')
                if artifact['comments']:
                    fp.write('      </comments>\n')
                fields.remove("comments")
            if 'attachments' in artifact:
                if artifact['attachments']:
                    fp.write('      <attachments>\n')
                for (i, attachment) in enumerate(artifact['attachments']):
                    fp.write('        <attachment number="%d">\n' % i)
                    for (field, value) in attachment.items():
                        if field != 'class':
                            continue
                        elif field == 'attacher':
                            fp.write(identity_dump(comment['attacher'], indent=10))
                        else:
                            fp.write('          <%s>%s<%s>\n' \
                                     % (field, xmlize(value), field))
                    fp.write('        </attachment>\n')
                fp.write('      </attachments>\n')
                if artifact['attachments']:
                    fields.remove("attachments")
            if 'history' in artifact:
                if artifact['history']:
                    fp.write('      <history>\n')
                for (i, fieldchange) in enumerate(artifact['history']):
                    fp.write('        <change number="%d">\n' % i)
                    for (field, value) in fieldchange.items():
                        if field != 'class':
                            fp.write('          <%s>%s<%s>\n' \
                                     % (field, xmlize(value), field))
                    fp.write('        </change>\n')
                if artifact['history']:
                    fp.write('      </history>\n')
                fields.remove("history")
            if 'dependents' in artifact:
                if artifact['dependents']:
                    fp.write('      <dependents>\n')
                for bugid in artifact['dependents']:
                    fp.write('        <dependent>%d</dependent>\n' % bugid)
                if artifact['dependents']:
                    fp.write('      </dependents>\n')
                fields.remove("dependents")
            if 'subscribers' in artifact:
                if artifact['subscribers']:
                    fp.write('      <subscribers>\n')
                for person in artifact['subscribers']:
                    fp.write('        <subscriber>\n')
                    fp.write('          <identity>\n')
                    fp.write(identity_dump(person['subscriber'], indent=12))
                    fp.write('          </identity>\n')
                    fp.write('          <reason>\n')
                    fp.write('          <reason>\n')
                    fp.write(person['reason'])
                    fp.write('        <subscriber>\n')
                if artifact['subscribers']:
                    fp.write('      </subscribers>\n')
                fields.remove("subscribers")
            if fields:
                raise ForgePluckerException(sys.argv[0] + ": no dump logic for fields %s in %s\n" % (fields, artifact))
            fp.write('    <artifact>\n')
        fp.write('    </artifacts>\n')
        fp.write('    <vocabularies>\n')
        for (field, vocabulary) in tracker['vocabularies'].items(): 
            fp.write('      <select attribute="%s">\n' % field)
            for value in vocabulary:
                fp.write('        </value>%s</value>\n' % value)
            fp.write('      <select>\n')
        fp.write('    </vocabularies>\n')
        fp.write('    <capture-ends>%s</capture-ends>\n' \
                 % tracker['interval'][1])
        fp.write('  </tracker>\n')
    fp.write('</trackers>\n')

# List handler classes here, we'll introspect on them in a bit
handlers = (SourceForge, Berlios, Savane)

# Map well-known hosting sites to forge system types. We'd try using
# pattern-matching on the site main page for this, but forge adnmins
# customize their front pages a lot and unambiguous cues about
# forge type aren't so easy to find.
site_to_type = {
    "sourceforge.net": SourceForge,
    "developer.berlios.de": Berlios,
    "savannah.gnu.org": Savane,
    "savannah.nongnu.org": Savane,
    "gna.org": Savane,
}

if __name__ == '__main__':
    import getopt, pprint, netrc
    pp = pprint.PrettyPrinter(indent=4)
    user = passwd = forgetype = None
    verbose = 0
    issue = None
    help = sample = xml = False
    (options, arguments) = getopt.getopt(sys.argv[1:], "f:i:p:rsu:v:h?")
    for (arg, val) in options:
        if arg in ('-h', '-?'):
            print __doc__
            for cls in [Berlios, Savane]:
                print "-" * 72
                print cls.__doc__
            raise SystemExit, 0
        elif arg == '-u':
            user = val
        elif arg == '-p':
            passwd = val
        elif arg == '-r':
            xml = True
        elif arg == '-s':
            sample = True
        elif arg == '-v':
            verbose = int(val)
        elif arg == '-i':
            issue = val
        elif arg == '-f':
            for cls in handlers:
                if val == cls.__name__:
                    forgetype == cls
                    break
            else:
                print >>sys.stderr, "%s: unknown forge type" % sys.argv[0]
                raise SystemExit, 1
    try:
        (host, project) = arguments[0].split("/")
    except (ValueError, IndexError):
        print >>sys.stderr, "usage: %s [options...] host/project" % sys.argv[0]
        raise SystemExit, 1
    if user is None:
        user = os.getenv("LOGNAME")
    if passwd is None:
        passwords = netrc.netrc()
        auth = passwords.authenticators(host)
        if auth and auth[0] == user:
            passwd = auth[2]
            if not forgetype and auth[1]:
                forgetype = auth[1]
    if not forgetype and host in site_to_type:
        forgetype = site_to_type[host]
    if user is None or passwd is None or forgetype is None:
        print >>sys.stderr, "usage: %s [-hrv?] [-i itemspec] -u username -p password -f forgetype host project" % sys.argv[0]
        raise SystemExit, 1
    try:
        bt = forgetype(host, project)
        bt.verbosity = verbose
        bt.login(user, passwd)
        if issue:
            (tracker, bugid) = issue.split(":")
            issue = bt.pluck_artifact(tracker, bugid)
            pp.pprint(issue)
        else:
            bugs = bt.pluck_bugs(sample=sample)
            bugs = canonicalize(bugs)
            if xml:
                xml_dump(bugs)
            else:
                pp.pprint(bugs)
    except ForgePluckerException, e:
        print >>sys.stderr, e.msg
        raise SystemExit, 1
    except urllib2.HTTPError, e:
        print >>sys.stderr, "%s: %d - %s" % (e.url, e.code, e.msg)
        raise SystemExit, 1
