"""
Handler class for SourceForge.

This doesn't work yet.  It's a stub.
"""
import re

from htmlscrape import *
from generic import *

class SourceForge(GenericForge):
    """
The SourceForge handler provides bug-plucking machinery for the SourceForge
site.

This code will capture custom trackers.
"""
    class Tracker:
        def __init__(self, label, parent):
            self.parent = parent
            self.optional = False
            self.chunksize = 100
            self.zerostring = None
            self.submitter_re = r'''<label>Submitted:</label>
? *<p>
? *.*?\( *(?:<a href=".*?">)(\w*)(?:</a>)|\w* *\) - (.*?)
? *</p>''' #This triple quoted string is ugly, but captures identation style
            self.date_re = r'''<label>Submitted:</label>
? *<p>
? *.*?\( *[^)]* *\) - (.*?)
? *</p>'''
            self.ignore = ("canned_response",
                           "words")
            self.artifactid_re = r'/tracker/\?func=detail&aid=([0-9]+)&group_id=[0-9]+&atid=[0-9]+"'
            m = re.search('<a href="([^"]*)">%s</a>' % label,
                          self.parent.basepage)
            if m:
                self.projectbase = dehtmlize(m.group(1))
            else:
                raise ForgePluckerException("can't find tracker labeled '%s'" \
                                            % label)
        def access_denied(self, page, issue_id=None):
            return issue_id is None and not "Mass Update" in page
        def has_next_page(self, page):
            return "Next &raquo;" in page
        def chunkfetcher(self, offset):
            "Get a bugtracker index page - all bug IDs, open and closed.."
            return self.projectbase + "?offset=%d&limit=100" % offset
        def detailfetcher(self, issueid):
            "Generate a bug detail URL for the specified bug ID."
            return self.projectbase + '&func=detail&aid=' + str(issueid)
        def narrow(self, text):
            "Get the section of text containing editable elements."
            return text
        def custom(self,contents,bug):
            bug['history']=[] #FIXME This is stub
            m = re.search(r'<input type="checkbox" name="is_private" [^>]* />',contents)
            bug['private'] = 'checked' in m.group(0)
    class BugTracker(Tracker):
        def __init__(self, parent):
            SourceForge.Tracker.__init__(self, "Bugs", parent)
            self.type = "bugs"
    class FeatureTracker(Tracker):
        def __init__(self, parent):
            SourceForge.Tracker.__init__(self, "Feature Requests", parent)
            self.type = "features"
    class PatchTracker(Tracker):
        def __init__(self, parent):
            SourceForge.Tracker.__init__(self, "Patches", parent)
            self.type = "patches"
    class SupportTracker(Tracker):
        def __init__(self, parent):
            SourceForge.Tracker.__init__(self, "Support Requests", parent)
            self.type = "support"
    def __init__(self, host, project_name):
        GenericForge.__init__(self, host, project_name)
        self.basepage = self.fetch(self.project_page(project_name)+'develop',
                                   "Develop page")
        m = re.search(r'/tracker/\?group_id=([0-9]*)', self.basepage)
        if m:
            self.project_id = m.group(1)
        else:
            raise ForgePluckerException("can't find a project ID for %s" % name)
        self.trackers = [
            SourceForge.BugTracker(self),
            SourceForge.FeatureTracker(self),
            SourceForge.SupportTracker(self),
            SourceForge.PatchTracker(self),
            ]
    def project_page(self, project):
        return "projects/%s/" % (project,)
    @staticmethod
    def canonicalize_date(localdate):
        "Canonicalize dates to ISO form. Assumes dares are in local time."
        t = time.strptime(localdate, "%Y-%m-%d %H:%M")
        secs = time.mktime(t)	# Local time to seconds since epoch
        t = time.gmtime(secs)	# Seconds since epoch to UTC time in structure
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", t)
    def login(self, username, password):
        GenericForge.login(self, {
            'form_loginname':username,
            'form_pw':password,
            'return_to':"/account",
            'login':'login'}, "Preferences")

# End
