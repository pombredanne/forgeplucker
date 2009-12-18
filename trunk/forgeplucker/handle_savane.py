import sys, os, re, time, calendar
from htmlscrape import *
from generic import *
from BeautifulSoup import BeautifulSoup

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
            m = re.search("([0-9]+) matching items? - Items [0-9]+ to ([0-9]+)", page)
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
                url = self.parent.host + m.group(1)
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
                    'url': url
                    })
            if ("No files currently attached" in contents) != (len(artifact["attachments"])==0):
                self.parent.error("garbled file-attachment section")
            # Capture votes
            artifact['votes'] = None
            if "There is 1 vote so far." in contents:
                artifact['votes'] = 0
            else:
                m = re.search("There are ([0-9]*) votes so far.", contents)
                if m:
                    artifact['votes'] = int(m.group(1))
            if artifact['votes'] is None:
                self.parent.error('cannot find vote indication')
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
            if contents.find("Items that depend on this one: None found")==-1:
                dpstart = contents.find("Items that depend on this one")
                if dpstart > -1:
                    tail = contents[dpstart:]
                    for m in re.finditer(r'\([a-zA-Z ]* #([0-9]+), [a-zA-Z ]*\)', tail):
                        artifact["dependents"].append(int(m.group(1)))
                    if not artifact["dependents"]:
                        self.parent.error("garbled dependency table")
                else:
                    self.error("missing both dependency table and no-depemdencies message")
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
        GenericForge.login(self, {
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
    def pluck_permissions(self):
        "Retrieve the developer roles table."
        expected_features = [u'Support Tracker',
                             u'Bug Tracker',
                             u'Task Tracker',
                             u'Patch Tracker',
                             u'Cookbook Manager',
                             u'News Manager']
        # This maps some features to standard names. 
        feature_map = ('support', 'bugs', 'tasks', 'patch', 'Cookbook', 'News')
        permission_map = {u'Group Default': None,
                          u'None': [],
                          u'Technician': ['T'],
                          u'Manager':['M'],
                          u'Techn. & Manager':['T', 'M']}
        page = self.fetch("project/admin/userperms.php?group=%s" % self.project_name, "Permissions Table")
        if not "Update Permissions" in page:
            self.error("you need admin privileges to extract permissions",
                       ood=False)
        # Ignore all the site navigation crap, it's likely to mutate
        goodstuff = page.find('<form action="/project/admin/userperms.php" method="post">')
        if goodstuff == -1:
            self.error("permissions form not found where expected")
        else:
            page = page[goodstuff:]
        trailing = page.find("</form>")
        if trailing == -1:
            self.error("expected trailing </form> element not found")
        else:
            page = page[:trailing+7]
        # Actual parsing begins here
        form = BeautifulSoup(page)
        # Extract feature headings
        defaults = form("table")[1]
        features = map(lambda x: x.contents[0], defaults.tr.findAll("th"))
        if features != expected_features:
            self.error("feature set %s is not as expected" % features)
        # Extract group default permissions
        defvals = map(lambda x: x.contents[3].strip(), defaults.findAll("td"))
        for d in defvals:
            if not d.startswith("(") or not d.endswith(")"):
                self.error("default group values were not as expected")
        defvals = map(lambda x: x[1:-1].strip(), defvals)
        dfltmap = dict(zip(features, defvals))
        # Extract actual permissions. The [1:] discards the header row
        capabilities = {}
        permissions = form("table")[2].findAll("tr")[1:]
        for row in permissions:
            fields = map(lambda x: x.contents, row.findAll("td"))
            namefield = fields[0]
            baseperms = fields[1]
            try:
                trackerperms = map(lambda x: select_parse(x[1])[0], fields[2:])
            except:
                self.error("tracker permissions were not as expected")
            try:
                name = namefield[1].contents[0]
            except:
                self.error("name field in permissions was not as expected")
            person = dehtmlize(name)
            capabilities[person] = {}
            admin = trusted = False
            if "You are Admin" in baseperms[0]:
                admin = True
            else:
                admin_input = baseperms[1]
                if not 'admin' in `admin_input`:
                    self.error("admin checkbox not found where expected")
                else:
                    admin = 'checked' in `admin_input`
            if admin:
                trusted = True
            for field in baseperms:
                if 'input' in `field` and 'privacy' in `field` and "checked" in `field`:
                    trusted = True
            capabilities[person]["Admin"] = admin
            capabilities[person]["Trusted"] = trusted
            for (feature, value, default) in zip(feature_map, trackerperms, defvals):
                if permission_map[value] is None:
                    value = permission_map[default]
                capabilities[person][feature] = value 
        return capabilities
# End
