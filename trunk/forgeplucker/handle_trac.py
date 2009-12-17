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
            self.type = "Bug"
            self.submitter_re = r"""<td headers="h_reporter" class="searchable">([^<]*)</td>"""
            self.date_re = r'<p>Opened <a class="timeline" href="[a-zA-Z/]*\?from=([-0-9A-Z%:]+)'
            self.ignore = ('q','reporter')
        def access_denied(self, page, issue_id=None):
            return issue_id is not None and not "Ticket #" in page
        def has_next_page(self, page):
            if re.search("""title="Next Page">""", page):
                return True
            else:
                return False
        def detailfetcher(self, artifactid):
            "Generate a detail URL for the specified artifact ID."
            return "%s/ticket/%d" % (self.parent.project_name, artifactid)
        def narrow(self, text):
            "Get the section of text containing editable elements."
            return text #TODO
        def custom(self,contents,artifact):
            comments, history, attachments = [], [], []
            if contents.find(r'<h2>Change History</h2>') != -1:
                soup = BeautifulSoup(contents[contents.find(r'<h2>Change History</h2>'):]).find(name='div',attrs={'id':'changelog'})
                for tag in soup.findAll(name='div',attrs={'class':'change'}):
                    attachment = False
                    comment = blocktext(dehtmlize(str(tag.find(name='div',attrs={'class':'comment searchable'}))))
                    date = self.parent.canonicalize_date(str(tag.find(name='a',attrs={'class':'timeline'})['title']))
                    by = re.search(" ago by ([a-zA-Z0-9_]+)\s*?</h3>",str(tag)).group(1)
                    changes = tag.find(name='ul',attrs={'class':'changes'})
                    if changes != None:
                        for change in changes.findAll(name='li'):
                            fieldcontents = map(lambda x: str(x.string),change.findAll('em'))
                            field = str(change.find('strong').string)
                            if len(fieldcontents) == 1:
                                old = None
                            elif len(fieldcontents) == 2:
                                old = fieldcontents.pop(0)
                            else:
                                self.parent.error("Error reading field contents " + str(fieldcontents))
                            new = fieldcontents[0]
                            if field == 'attachment':
                                attachment = True
                                attachments.append({'class': 'ATTACHMENT',
                                                    'by': by,
                                                    'date': date,
                                                    'description': comment,
                                                    'url': self.parent.host + '/' + self.parent.project_name + '/attachment/ticket/' + str(artifact['id']) + '/' + new,
                                                    'filename': new})
                            else:
                                history.append({'field':field,
                                                'old': old,
                                                'new': new,
                                                'date': date,
                                                'by':by,
                                                'class':'FIELDCHANGE'})
                    if comment != '\n' and not attachment:   #If a change/comment is the adding of an attachment then comment
                        comments.append({'class': 'COMMENT', #is the attachment comment
                                         'comment': comment,
                                         'date': date,
                                         'submitter': by})
            artifact['comments'] = comments
            artifact['history'] = history
            artifact['attachments'] = attachments
    @staticmethod
    def canonicalize_date(localdate):
        return remhex(localdate).split('+')[0]
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
