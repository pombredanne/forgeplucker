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
    class Tracker():
        """Generic class for a SourceForge tracker"""
        def __init__(self,forge,atid):
            self.forge = forge
            self.group_id = forge.group_id
            self.atid = atid
            print 'atid:',self.atid
        def getbugids(self):
            forge = self.forge
            ids = []
            url = r'/tracker/?group_id='+self.group_id+r'&limit=100&atid='+self.atid
            while True:
                page = forge.fetch(url,"Bug list")
                print url
                ms = re.findall(r'/tracker/\?func=detail&aid=([0-9]*)&group_id='+self.group_id+r'&atid='+self.atid,page)
                if ms:
                    ids += ms
                else:
                    if ids:
                        self.forge.error("Can't get ALL (we got some) bugids in " + str(self))
                    else:
                        self.forge.error("Can't get bugids in " + str(self))
                m = re.search(r'href="([^ <>]*?)">Next',page)
                if m:
                    url = re.sub(r'&amp;',r'&',m.group(1))
                else:
                    return ids #There is no 'Next' button we have all bug ids
    def __init__(self, host, project_name):
        GenericForge.__init__(self, host, project_name)
        self.develop_page = self.fetch(self.project_page() + 'develop',"Develop page")
        self.group_id = self.getgroup_id()
        self.trackers = [
            #SourceForge.BugTracker(self),
            #SourceForge.SupportTracker(self),
            #SourceForge.PatchTracker(self),
            #SourceForge.FeatureTracker(self),
            ]
    def project_page(self):
        return "projects/%s/" % (self.project_name,)
    def getgroup_id(self):
        """Never run this, use self.group_id instead.
           This is only called in __init__"""
        page = self.develop_page
        m = re.search(r'/tracker/\?group_id=([0-9]*)',page)
        if m:
            return m.group(1)
        else:
            self.error("Unable to get group_id")
    def getbugatid(self):
        page = self.develop_page
        m = re.search(r'/tracker/\?group_id='+self.group_id+'&amp;atid=([0-9]*)">Bugs',page)
        if m:
            return m.group(1)
        else:
            self.error("Unable to get bugatid")
    def getbugTracker(self):
        return self.Tracker(self,self.getbugatid())
    def login(self, username, password):
        GenericForge.login(self, {
            'form_loginname':username,
            'form_pw':password,
            'return_to':"http://google.com",
            'login':'login'}, "Shopping")
# End
