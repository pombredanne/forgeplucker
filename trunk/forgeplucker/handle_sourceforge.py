"""
Handler class for SourceForge.

This doesn't work yet.  It's a stub.
"""
from htmlscrape import *
from generic import *

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

# End
