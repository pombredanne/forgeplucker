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
            self.ignore = ('q',
                           'reporter',
                           'action_reassign_reassign_owner',
                           'action_resolve_resolve_resolution',
                           'field_reporter') # Captured by submitter_re
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
            oldCC = None
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
                                new = fieldcontents[0]
                            elif len(fieldcontents) == 2:
                                old = fieldcontents[0]
                                new = fieldcontents[1]
                            else:
                                del old, new # Make this crash if these (stale) varibles are accessed
                            if field == 'attachment':
                                attachment = True
                                attachments.append({'class': 'ATTACHMENT',
                                                    'by': by,
                                                    'date': date,
                                                    'description': comment,
                                                    'url': self.parent.host + '/' + self.parent.project_name + '/raw-attachment/ticket/' + str(artifact['id']) + '/' + new,
                                                    'filename': new})
                            else:
                                if field in ('status','resolution'):
                                    artifact[field] = new
                                elif field == 'cc':
                                    new = fieldcontents
                                    old = oldCC
                                    oldCC = fieldcontents
                                history.append({'field':field,
                                                'old': old,
                                                'new': new,
                                                'date': date,
                                                'by':by,
                                                'class':'FIELDCHANGE'})
                    if comment != '\n' and not attachment:   #If a change is the adding of an attachment then comment
                        comments.append({'class': 'COMMENT', #is the attachment comment
                                         'comment': comment,
                                         'date': date,
                                         'submitter': by})
            if 'status' not in artifact:
                artifact['status'] = 'new'
            if 'resolution' not in artifact:
                artifact['resolution'] = None
            artifact['comments'] = comments
            artifact['history'] = history
            artifact['attachments'] = attachments

            if artifact['field_cc'] != "":
                artifact['field_cc'] = artifact['field_cc'].split(', ')
            else:
                artifact['field_cc'] = []

            if artifact['field_keywords'] != "":
                artifact['field_keywords'] = artifact['field_keywords'].split()
            else:
                artifact['field_keywords'] = []
            
            artifact['type'] = artifact['field_type']
            del artifact['field_type']

            m = re.search(r'<th id="h_owner">Owned by:</th>\s*<td headers="h_owner">([a-zA-Z0-9_]+)\s*</td>',contents)
            if m.group(1) == 'somebody':
                artifact['assigned_to'] = None
            else:
                artifact['assigned_to'] = m.group(1)
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
        page = self.fetch(self.project_name + "/query?format=csv&max=2147483647&order=id&col=id","List of ids")
        ids = page.strip().split('\r\n')[1:] # Will only fetch the first 2147483647 bugs
        return map(int,ids)                   # If this is a problem for you, your software is seriously buggy
    def pluck_permissions(self):
        contents = self.fetch('https://sourceforge.net/apps/trac/forgepluckertes/admin/general/perm', 'Permissions Page')
        permissions = {}
        for (subject, perms) in self.table_iter(contents, '<table class="listing" id="permlist">',
               2, 'Permissions Table', has_header=True, keep_html=True):
            subject = subject.string
            permissions[subject] = []
            for perm in perms.findAll('label'):
                permissions[subject].append(perm.string)
        return permissions
