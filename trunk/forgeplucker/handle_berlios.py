"""
Handler class for Berlios

Berlios appears to be running a very old version of FusionForge, rather
close to the ancestral Alexandria.
"""

import sys, os, re, time, calendar
from htmlscrape import *
from generic import *
from BeautifulSoup import BeautifulSoup

class Berlios(GenericForge):
    """
The Berlios handler provides bug-plucking machinery for the Berlios site.

The FusionForge site claims Berlios is a GForge/FusionForge instance, so this
code may generalize.

Things it doesn't grab yet:
* Tasks and task interdependencies.
* Forum and Document Manager state
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
            self.submitter_re = r"<TD><B>Submitted By:</B><BR>([^<]*)</TD>"
            self.date_re = "<TD><B>Date Submitted:</B><BR>([^<]*)</TD>"
            self.ignore = ("canned_response", "project_id")
        def access_denied(self, page, issue_id=None):
            return issue_id is None and not "Admin:" in page
        def has_next_page(self, page):
            return "Next 50" in page
        def narrow(self, text):
            "Get the section of text containing editable elements."
            formpart =  self.parent.skipspan(text, "FORM", 1)
            # Discard the dependency table, its selects can have multiple
            # values and confuse the form parser. This  is OK as the custom
            # hook will get passed the contents including that table.
            deps = formpart.find("Dependent on")
            if deps > -1:
                formpart = formpart[:deps]
            return formpart
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
            self.zerostring = "No Bugs Match Your Criteria"
            self.artifactid_re = r'<A HREF="/bugs/\?func=detailbug&bug_id=([0-9]+)&group_id=%s">' % parent.project_id
        def chunkfetcher(self, offset):
            "Get a bugtracker index page - all bug IDs, open and closed.."
            return "bugs/index.php?func=browse&group_id=%s&set=custom&offset=%d" % (self.parent.project_id, offset)
        def detailfetcher(self, issueid):
            "Generate a bug detail URL for the specified bug ID."
            return "bugs/?func=detailbug&bug_id=%d&group_id=%s" % \
                   (issueid, self.parent.project_id)
        def custom(self, contents, bug):
            m = re.search("<B>Original Submission:</B><BR>", contents)
            if not m:
                self.parent.error("no original-submission text")
            m = re.search(r"<H2>\[ [A-Za-z ]* #[0-9]+ \] ([^<]*)</H2>", \
                          contents)
            if not m:
                self.error("no summary found")
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
            self.zerostring = "No Feature Requests Match Your Criteria"
            self.artifactid_re = r'<A HREF="\?func=detailfeature&feature_id=([0-9]+)&group_id=%s">' % parent.project_id
        def chunkfetcher(self, offset):
            "Get a feature tracker index page - all bug IDs, open and closed.."
            return "feature/index.php?func=browse&group_id=%s&set=custom&offset=%d" % (self.parent.project_id, offset)
        def detailfetcher(self, issueid):
            "Generate a feature detail URL for the specified bug ID."
            return "feature/?func=detailfeature&feature_id=%d&group_id=%s" % \
                   (issueid, self.parent.project_id)
        def custom(self, contents, feature):
            m = re.search(r"<H2>\[ [A-Za-z ]* #[0-9]+ \] ([^<]*)</H2>", \
                          contents)
            if not m:
                self.error("no summary found")
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
            self.zerostring = "No Patches Match Your Criteria"
            self.artifactid_re = r'<A HREF="\?func=detailpatch&patch_id=([0-9]+)&group_id=%s">' % parent.project_id
        def chunkfetcher(self, offset):
            "Get a patch tracker index page - all bug IDs, open and closed.."
            return "patch/index.php?func=browse&group_id=%s&set=custom&offset=%d" % (self.parent.project_id, offset)
        def detailfetcher(self, issueid):
            "Generate a patch detail URL for the specified bug ID."
            return "patch/?func=detailpatch&patch_id=%d&group_id=%s" % \
                   (issueid, self.parent.project_id)
        def custom(self, contents, patch):
            m = re.search(r"<H2>\[ [A-Za-z ]* #[0-9]+ \] ([^<]*)</H2>", \
                          contents)
            if not m:
                self.error("no summary found")
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
        GenericForge.login(self, {
            'form_loginname':username,
            'form_pw':password,
            'stay_in_ssl':1,
            'return_to':"",
            'login':'Login With SSL'}, "Personal Page")
    def pluck_permissions(self):
        "Retrieve the developer roles table."
        page = self.fetch("project/admin/userperms.php?group_id=%s" % self.project_id, "Permissions Table")
        if not "Update Developer Permissions" in page:
            self.error("you need admin privileges to extract permissions",
                       ood=False)
        expected_features = [u'General',
                             u'Bug Tracking',
                             u'Task Manager',
                             u'Patch Manager',
                             u'Support Manager', 
                             u'Feature Manager',
                             u'Forums',
                             u'Doc. Manager']
        expected_roles = [u'Undefined',
                          u'Developer',
                          u'Project Manager',
                          u'Unix Admin', u'Doc Writer',
                          u'Tester',
                          u'Support Manager',
                          u'Graphic/Other Designer',
                          u'Doc Translator',
                          u'Editorial/Content Writer',
                          u'Packager (.rpm, .deb etc)',
                          u'Analysis / Design',
                          u'Advisor/Mentor/Consultant',
                          u'Distributor/Promoter',
                          u'Content Management',
                          u'Requirements Engineering',
                          u'Web Designer',
                          u'Porter (Cross Platform Devel.)']
        expected_trackerperms = [u'-', u'T', u'A,T', u'A']
        # Ignore all the site navigation crap, it's likely to mutate
        goodstuff = page.find('<FORM action="userperms.php" method="post">')
        if goodstuff == -1:
            self.error("permissions form not found where expected")
        else:
            page = page[goodstuff:]
        # First, drop out presentation-level tags
        page = page.replace('<br>', ' ')
        page = page.replace('<B>', '').replace('</B>', '')
        page = page.replace('<b>', '').replace('</b>', '')
        # FIXME: Should replace this with a caseblind regexp that accepts
        # all sizes
        page = page.replace('<FONT size="-1">', '').replace('</FONT>', '')
        page = page.replace('<font size="-1">', '').replace('</font>', '')
        tree = BeautifulSoup(page)
        # There should be only one table on the page.
        rows = tree.find("table").findAll("tr")
        # Check the role set for this table.  That's just the labels
        # in the first HTML row.
        features = map(lambda x: x.contents[0], rows.pop(0).findAll('td'))
        if features != expected_features:
            self.error("feature set %s is not as expected" % features)
        # Now we start on the actual data extraction
        capabilities = {}
        for (i, row) in enumerate(rows):
            if i % 2 == 0:
                person = row.td.contents[0]
                capabilities[person] = {}
            else:
                general = row.contents.pop(0)
                admincheck = general("input")[0]
                reltech = general("input")[1]
                (role, vocabulary) = select_parse(general.select)
                if vocabulary != expected_roles:
                    self.error('developer roles are not as expected')
                capabilities[person]["Role"] = role
                capabilities[person]["Admin"] ="checked" in `admincheck`
                capabilities[person]["Release Tech"] = "checked" in `reltech`
                permissions = map(select_parse, row.findAll("select"))
                # Second argument of zip() is not arbitrary, it's
                # ontology smoothing - we make Savane's names for
                # these to standard feature tags.
                for (feature, (permopt, vocabulary)) in zip((u'bugs',
                                                          u'tasks',
                                                          u'patches',
                                                          u'support', 
                                                          u'features'),
                                                         permissions[:5]):
                    if vocabulary != expected_trackerperms:
                        self.error("permissions vocabulary is not as expected")
                    perms = []
                    if 'T' in permopt:
                        perms.append('T')
                    # One bit of ontology smoothing here. In native
                    # Berlios terminology, the capability to modify
                    # items in an issue tracker is called
                    # "Administrator" and coded with an 'A'.  Savane
                    # terminology, in which this permission bit is
                    # tracker "Manager", is preferable - it's better
                    # to reserve the term "Administrator" for a member
                    # who can edit permissions.
                    if 'A' in permopt:
                        perms.append('M')
                    capabilities[person][feature] = perms
                for (feature, (permopt, vocabulary)) in zip((u'Forums',
                                                          u'Doc Manager'),
                                                         permissions[5:]):
                    capabilities[person][feature] = permopt!='-'
        return capabilities

# End
