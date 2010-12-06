# -*- coding: utf-8 -*-
"""
Handler class for FusionForge

Contributed in the frame of the COCLICO project.

(C) 2010 Florian Dudouet - INRIA

"""

#import psycopg2 #@UnusedImport
import re
import copy
import urllib2
import os
import sys

from htmlscrape import *
from generic import *

class FusionForge(GenericForge):
	"""
The FusionForge handler provides machinery for the FusionForge sites.

"""
	class Tracker:
		
		def __init__(self, label, parent, projectbase):
			self.parent = parent
			self.optional = False
			self.chunksize = 50
			self.zerostring = None
			self.label = label
			self.projectbase = projectbase
			self.atid = re.search('atid=([0-9]*)', projectbase).group(1)
			self.name_mappings = {
				"bug_group_id": "group",
				"category_id": "category",
				"resolution_id": "resolution",
				"status_id": "status",
				
        		}
			# l'auteur du bug n'est pas éditable et ne peut donc être récupérée par le crawler dans le formulaire, cette regexp ne sert qu'à lui
			self.submitter_re = '''<tt><a href="\S*">([^<]*)</a></tt>'''
			# la date n'est pas éditable et ne peut donc être récupérée par le crawler dans le formulaire
			self.date_re = '''<td><strong>Date Submitted:</strong><br />\s*([^<]*)\s*<'''
			# vérifier les champs de formulaire à ignorer
			self.ignore = ("canned_response",
			"new_artifact_type_id",
			"words", "type_of_search")
			# identifie les ids d'artefacts (bug, patches...) : aid
			self.artifactid_re = r'/tracker/index.php\?func=detail&amp;aid=([0-9]+)&amp;group_id=[0-9]+&amp;atid=[0-9]+"'
			# # chaque tracker a également un atid propre, indépendant du projet et global (utilité?????). ex, bugs de projet A : id 1, patch de projet 1 : id 2, bug de projet 2 : id 3...
			
			# m = re.search('<a href="[^/]*//[^/]*/([^"]*)">.*%s</a>' % label, self.parent.basepage)
			
			# if m:
			# 	print m.groups()
			# 	self.projectbase = dehtmlize(m.group(1))
			# else:
			# 	raise ForgePluckerException("Le tracker '%s' n'a pas été trouvé" \
			# 		    % label)
			# m = re.search('<a href="[^"]*atid=([0-9]*)[^"]*">.*%s</a>' % label, self.parent.basepage)
			# print m.groups()
			# self.atid = m.group(1)

			#Update view mode to parse closed tickets by default
			self.trackerSwitchViewMode()

		def trackerSwitchViewMode(self):
			params = {'set':'custom','assigned_to':0,'status':100,'query_id':-1,'sort_col':'priority','_sort_ord':'DESC','submit':'Quick+Browse'}
			self.parent.fetch('tracker/index.php?group_id='+self.parent.project_id+'&atid='+self.atid, 'Updating '+self.atid + ' tracker\'s view mode', params)
			return True

		def access_denied(self, page, issue_id=None):
			'''
			Check if the user has edit access to the current tracker
			'''
			if "No items found" in page:
				return 0
			else:
				return issue_id is None and not "Mass Update" in page

		def has_next_page(self, page):
			"""
			Check if the current page contains a count indicating that another page of artifacts exists
			"""
			return "Next &raquo;" in page

		def chunkfetcher(self, offset):
			"Get a bugtracker index page - all bug IDs, open and closed.."
			return self.projectbase + "&offset=%d&limit=100" % offset

		def detailfetcher(self, issueid):
			"Generate a bug detail URL for the specified bug ID."
			return self.projectbase + '&func=detail&aid=' + str(issueid)

		def narrow(self, text):
			"Get the section of text containing editable elements."
			return text

		def parse_followups(self, contents, bug):
			"Parse followups out of a displayed page in a bug or patch tracker."
	
			comments = []
			soup = BeautifulSoup(contents)

			commentblock = soup.find(name='div', attrs={'title':"Followups"}).findAll("tr", {"class":re.compile("altRowStyle")})
	
			for tr in commentblock:	
				comment = {"class":"COMMENT"}

				m = re.search('Date: ([-0-9: ]+)\s*Sender:[^"]*"[^/]*//[^/]*/users/([^/]*)/"', str(tr)) #très améliorable...
				comment['date'] = self.parent.canonicalize_date(m.group(1))
				comment['submitter'] = m.group(2)
		
				m = re.search("</a>(.*)</pre>", str(tr), re.DOTALL)
				comment['comment'] = m.group(1).strip()
				
				comments.append(comment)
			comments.reverse()
			
			return comments

		def parse_history_table(self, contents, artifacts):
			"Get the change history attached to a tracker artifact."
			changes, filechanges, attachments, filelist = [], [], [], []
			

			for (field, old, date, by) in self.parent.table_iter(contents,
					r'<h3>Change Log:</h3>',
					4,
					"history",
					has_header=True):
				field, old, date, by = field.strip(), old.strip(), date.strip(), by.strip()
				if field in ('File Added', 'File Deleted'):
					filechanges.append((field, old, date, by))
				#if field not in ('close_date'):
				change = {'field':field, 'old':old, 'date':self.parent.canonicalize_date(date), 'by':by, 'class':'FIELDCHANGE'}
				changes.append(change)
			for (action, _file, date, by) in reversed(filechanges):
				fileid, filename = _file.split(':')
				filename = filename.strip()
				if action == 'File Added':
					attachment = {"class":"ATTACHMENT", "filename": filename, "by": by, "date": self.parent.canonicalize_date(date), "id": fileid}
					filelist.append(filename)
					attachments.append(attachment)
				elif action == 'File Deleted':
					for attachment in attachments:
						if attachment['id'] == fileid:
							attachment['deleted'] = self.parent.canonicalize_date(date)
			for attachment in attachments:
				try:		
					m = re.search('<a href="[^"]*/(tracker/[^"]*/%s)">Download</a></td>' % attachment['filename'], contents)
					dl = self.parent.fetch(m.group(1), "download")
					rep_dest = self.parent.project_name + '/' + self.type
					if not os.path.exists(self.parent.project_name):
						os.mkdir(self.parent.project_name)
					if not os.path.exists(rep_dest):
						os.mkdir(rep_dest)
					fnout = rep_dest + '/' + attachment['filename']
					fout = open(fnout, "wb")
					fout.write(dl)
					fout.close
					attachment['url'] = fnout
				except Exception, e:
					continue

			return changes, attachments
		
		def update_nodb(self, artifact, contents, vocabularies):
			"Find names of extra fields by parsing the html contents"
			tempKeys, tempValues, tempVocab = [], {}, {}
			for arti in artifact:
				if (arti[:13] == "extra_fields["):
					try:
						name = re.search('.*<strong>([a-zA-Z0-9_-|\s]*)[:|<br />|</strong>].*%s' % re.escape(arti), contents, re.DOTALL).group(1)
							
					except:
						print "extra field parsing error"
						continue

					tempValues[name] = artifact[arti]
					tempKeys.append(arti)
					try:
						tempVocab[name] = vocabularies[arti]

					except:
						continue
				else:
					tempValues[arti] = artifact[arti]
			for key in tempKeys:
				del artifact[key]
				try:
					del vocabularies[key]
				except:
					continue
			for value in tempValues:
				artifact[value] = tempValues[value]
			for vocab in tempVocab:
					vocabularies[vocab] = tempVocab[vocab]
			return artifact, vocabularies

		def custom(self, contents, artifact, vocabularies):
			"des champs spécifiques à fusionforge qu'il serait intéressant d'ajouter, peut ne rien faire en dehors d'appeler parse_followups et parse_attachments. méthode appelée par generic"
			artifact, vocabularies = self.update_nodb(artifact, contents, vocabularies)

			#get Detailed Description (uneditable thus unfetchable directly from form)
			dD = blocktext(dehtmlize(re.search('''<td>Detailed description</td></tr></thead><tr  class=".*"><td><pre>(.*)</pre></td></tr></table>.*</table>\n<br />\n<br />
''',contents,re.DOTALL).group(1).strip()))
			artifact['description'] = dD
			
			m = re.search('''Date Closed:</strong><br />\s*([^<]*)\s*<''', contents)
			if not (m == None):
				artifact['closed_at'] = self.parent.canonicalize_date(m.group(1).strip())
			artifact['comments'] = self.parse_followups(contents, artifact)
			artifact['history'], artifact['attachments'] = self.parse_history_table(contents, artifact)
			

	class BugTracker(Tracker):
		def __init__(self, parent, projectbase):
			FusionForge.Tracker.__init__(self, "Bugs", parent, projectbase)
			self.type = "bugs"
	class FeatureTracker(Tracker):
		def __init__(self, parent, projectbase):
			FusionForge.Tracker.__init__(self, "Feature Requests", parent, projectbase)
			self.type = "features"
	class PatchTracker(Tracker):
		def __init__(self, parent, projectbase):
			FusionForge.Tracker.__init__(self, "Patches", parent, projectbase)
			self.type = "patches"
	class SupportTracker(Tracker):
		def __init__(self, parent, projectbase):
			FusionForge.Tracker.__init__(self, "Support", parent, projectbase)
			self.type = "support"
	class CustomTracker(Tracker):
		'''
		This class is used to create a tracker object for any custom tracker
		'''
		def __init__(self, parent, nameTracker, projectbase):
			FusionForge.Tracker.__init__(self, nameTracker, parent, projectbase)
			self.type = 'custom'

	def getTrackers(self):
		'''
		Get the list of trackers from the trackers page.
		Contrary to what ForgePlucker does normally it does not use the summary page to extract the links as this page only contains the default trackers and not the custom ones.
		'''
		trackers = []
		trackersPage = self.fetch('tracker/?group_id='+self.project_id, 'Fetching tracker list')
		trackersPage = BeautifulSoup(trackersPage)
		trs = trackersPage.find('table').findAll('tr')[1:]
		for tr in trs:
			a = tr.find('a')
			tPage = re.search('[^/]*//[^/]*/([^"]*)',a['href']).group(1)
			tLabel = dehtmlize(a.contents[1]).strip()
			trackers.append({'label':tLabel, 'projectbase':tPage})
		return trackers

	# wrap the pluck_trackers() 
	def pluck_trackers(self, timeless=False):
		'''
		Get the trackers of the current fusionforge project. This is the method which should be called to initialize the extraction.
		@param timeless: Record the time of extraction if true
		'''
		
		listedTrackers = self.getTrackers()
		self.trackers = []	
		defaults = {'Bugs':FusionForge.BugTracker, 'Feature Requests':FusionForge.FeatureTracker, 'Patches':FusionForge.PatchTracker, 'Support':FusionForge.SupportTracker}
		for tracker in listedTrackers:
			if tracker['label'] in defaults:
				self.trackers.append(defaults[tracker['label']](self, tracker['projectbase']))
			else:
				self.trackers.append(FusionForge.CustomTracker(self, tracker['label'], tracker['projectbase']))
#				
		return GenericForge.pluck_trackers(self, timeless)

	def pluck_permissions(self):
		'''
		Get the permissions associated with each role in the project and return the corresponding array
		'''
		contents = self.fetch('project/memberlist.php?group_id=' + self.project_id, 'Roles page')
		perms = {}
		for (realname, username, role, skills) in self.table_iter(contents, '<table>', 4, 'Roles Table', has_header=True):
			perms[username.strip()] = {'role':role}
			perms[username.strip()]['real_name'] = realname
			
		for user in perms:
			contents = self.fetch('users/' + user, 'User page')
			mail = re.search('''sendmessage.php\?touser=[0-9]*">([^<]*)</a>''', contents, re.DOTALL).group(1).strip().replace(" @nospam@ ","@")
			perms[user]['mail'] = mail
			
		return perms
	
## FusionForge.__init__

	def __init__(self, host, project_name):
		"""			"""
		GenericForge.__init__(self, host, project_name)	
		
		self.basepage = self.fetch(self.project_page(project_name),
				"Main page")
		m = re.search(r'\?group_id=([0-9]*)', self.basepage)

		# #self.verbosity = 2

		# # some trackers may be private, so may not be displayed in project's homepage
		# project_homepage = self.fetch(self.project_page(project_name),
		# 		  "Main page")
		# #print project_homepage
		# m = re.search(r'/tracker/\?group_id=([0-9]*)', project_homepage)

		if m:
			#print m.group(0)
			self.project_id = m.group(1)
			#self.basepage = self.fetch('tracker/', "Trackers page", params={'group_id': self.project_id})
			#print "basepage :",self.basepage
		else:
			raise ForgePluckerException("Pas d'id correspondant au projet %s" % project_name)


	# Overloaded to customize FF paths 'host/projects/unixname'
	def project_page(self, project):
		"Computes project address"
		return "projects/%s/" % (project,)

	# def tracker_list_page(self):
	# 	"Computes project address"
	# 	return "tracker/?group_id=%s/" % group_id

## DATE

	@staticmethod
	def canonicalize_date(localdate):
		"Canonicalize dates to ISO form. Assumes dates are in local time."
		t = time.strptime(localdate, "%Y-%m-%d %H:%M")
		secs = time.mktime(t)	# Local time to seconds since epoch
		t = time.gmtime(secs)	# Seconds since epoch to UTC time in structure
		return time.strftime("%Y-%m-%dT%H:%M:%SZ", t)

## LOGIN

	def login(self, username, password):
		GenericForge.login(self, {
	'form_loginname':username,
	'form_pw':password,
	'return_to':"/account",
	'login':'login'}, "Preferences")


