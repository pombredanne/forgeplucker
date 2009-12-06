"""
Handler class for generic Trac sites.

<description here>
"""

import sys, os, re, time, calendar
from htmlscrape import *
from generic import *

class Trac(GenericForge):
    """
The Trac handler provides bug-plucking machinery for Trac sites.

"""
    class Tracker:
        def __init__(self, parent):
            self.parent = parent
            self.optional = False
            self.chunksize = 50
            self.type = "Bug"
            self.zerostring = "Error: Invalid Ticket Number"
            self.artifactid_re = r"""<td class="id"><a href="[^"]+" title="[^"]+">#(\d+)</a></td>"""
            self.submitter_re = r"""<td headers="h_reporter" class="searchable">([^<]*)</td>"""
            self.date_re = r"""<a class="timeline" href="[^"]*" title="(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+\d{4}) in Timeline">"""
            self.ignore = () #TODO
        def access_denied(self, page, issue_id=None):
            return issue_id is not None and not "Ticket #" in page
        def has_next_page(self, page):
            if re.search("""title="Next Page">""", page):
                return True
            else:
                return False
        def chunkfetcher(self, offset):
            """Get a bugtracker index page - all open tickets."""
            page = 1 + ((offset) // self.chunksize)
            return "%s/query?max=%d&page=%d&order=id&col=id&col=summary&col=owner" % (self.parent.project_name, self.chunksize, page)
        def detailfetcher(self, artifactid):
            "Generate a detail URL for the specified artifact ID."
            return "%s/ticket/%d" % (self.parent.project_name, artifactid)
        def narrow(self, text):
            "Get the section of text containing editable elements."
            return text #TODO
        def custom(self, contents, artifact):
            # Parse comments
            artifact['comments'] = []
            # Capture attachments.
            artifact["attachments"] = [] #TODO
            # Capture the history list
            artifact["history"] = [] #TODO
            # Capture the CC list. 
            artifact["subscribers"] = [] #TODO
    @staticmethod
    def canonicalize_date(localdate):
        return localdate.split("+")[0]
    def __init__(self, host, project):
        GenericForge.__init__(self, host, project)
        self.trackers = [ Trac.Tracker(self) ]
    def login(self, username, password):
        """Log in to the site."""
        if self.verbosity >= 1:
            self.notify("dispatching to " + self.__class__.__name__)
        password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(None, self.host, username, password)
        self.opener = urllib2.build_opener(urllib2.HTTPBasicAuthHandler(password_mgr),
                                           urllib2.HTTPCookieProcessor())
        response = self.fetch(self.login_url(), "Login Page")
        if "logged in as" not in response:
            self.error("authentication failure on login", ood=False)
    def login_url(self):
        "Generate the site's account login page URL."
        return self.project_name + "/login"
    def pluck_tracker_ids(self,tracker):
        ids,num = [],0
        firstpage = page = self.fetch(self.project_name + "/query?format=csv&max=2147483647&order=id&col=id","List of ids")
        while "html" not in page:
            ids += page.strip().split('\r\n')[1:]
            num += 1
            page = self.fetch(self.project_name + "/query?format=csv&max=2147483647&order=id&col=id&page=" + str(num),"List of ids")
            if page == firstpage:
                break
        return map(int,ids)

# End
