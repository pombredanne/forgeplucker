# -*- coding: utf-8 -*-
"""
Handler class for FusionForge

Contributed in the frame of the COCLICO project.

(C) 2010 Florian Dudouet - INRIA

"""

#import psycopg2 #@UnusedImport
import re
import copy
#import urllib2
import os
import sys

from htmlscrape import *
from generic import *
from forgeplucker.FusionForge_DocMan import FusionForge_DocMan

class FusionForge(GenericForge):
	"""
The FusionForge handler provides machinery for the FusionForge sites.

"""
	class Tracker(GenericForge.GenericTracker):
		
		def __init__(self, label, parent, projectbase):
			GenericForge.GenericTracker.__init__(self, parent, label)
			self.parent = parent
			self.optional = False
			self.chunksize = 50
			self.zerostring = None
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

		def getUrl(self):
			return self.projectbase

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
			return self.parent.narrow(text)

		def parse_followups(self, contents, bug):
			"Parse followups out of a displayed page in a bug or patch tracker."
	
			comments = []
			soup = BeautifulSoup(contents)
			soup = soup.find('div', title='Followups')
			# 5.0 has this :
			t = soup.find('table', attrs={'class': re.compile('.*listTable')})
			if not t :
				# then 4.8 which has only this :
				t = soup.find('table').find('table')
			if t:
				for tr in t.findAll("tr"):
					td=tr.find("td")
					if td:
						# if 4.8, then, has this :
						pre = td.find('pre')
						if pre:
							td = pre
						comment = {"class":"COMMENT"}
						m = re.search('Date: ([-0-9: ]+)', str(td.contents))
						if m:
							comment['date'] = self.parent.canonicalize_date(m.group(1))
							m = re.search('Sender: .*/users/([^/]*)/"', str(td.contents))
							if m:
								comment['submitter'] = m.group(1)
							comment['comment'] = td.contents[-1].strip()
				
							comments.append(comment)
			if comments :
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
		
		def update_extrafields(self, artifact, contents, vocabularies):
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
			"parse specific fields of FusionForge"
			#des champs spécifiques à fusionforge qu'il serait intéressant d'ajouter, peut ne rien faire en dehors d'appeler parse_followups et parse_attachments. méthode appelée par generic
 			artifact, vocabularies = self.update_extrafields(artifact, contents, vocabularies)

 			#get Detailed Description (uneditable thus unfetchable directly from form)
 			dD = None
			dDFound = False
			bs = BeautifulSoup(self.narrow(contents))
			# for 4.8
			for t in bs.findAll('table'):
				try :
					if t.find('thead').find('tr').find('td').contents[0] == 'Detailed description':
						dDFound = True
						dD = t.find('tr', attrs={'class': 'altRowStyleEven'}).find('td').find('pre').contents[0]
						dD = blocktext(dehtmlize(dD.strip()))
						break
				except AttributeError, e : # 
					if str(e) != "'NoneType' object has no attribute 'find'":
						raise
			# Try for 5.0
			if not dDFound:
				bs = BeautifulSoup(self.narrow(contents))
				for t in bs.findAll('table', attrs={'class': re.compile('.*listTable')}):
					try :
						if t.find('th').find('div').find('div').contents[0] == 'Detailed description':
							dDFound = True
							dD = t.find('tr').findNext('tr').find('td').contents[0]
							dD = blocktext(dehtmlize(dD.strip()))
							break
					except AttributeError, e : # 
						if str(e) != "'NoneType' object has no attribute 'find'":
							raise
 			if dD:
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

	def get_trackers(self):
		'''
		Get the list of trackers from the trackers page.
		Contrary to what ForgePlucker does normally it does not use the summary page to extract the links as this page only contains the default trackers and not the custom ones.
		'''
		trackers = []
		trackersPage = self.fetch('tracker/?group_id='+self.project_id, 'Fetching tracker list')
		trackersPage = BeautifulSoup(trackersPage)
		for table in trackersPage.findAll('table') :
			trs = table.findAll('tr')[1:]
			for tr in trs:
				a = tr.find('a')
				tPage = re.search('[^/]*//[^/]*.*/([^/]+/[^"/]*)', a['href']).group(1)
				tLabel = dehtmlize(a.contents[1]).strip()
				trackers.append({'label':tLabel, 'projectbase':tPage})

		self.trackers = []	

		defaults = {'Bugs': FusionForge.BugTracker, 
			    'Feature Requests': FusionForge.FeatureTracker, 
			    'Patches': FusionForge.PatchTracker, 
			    'Support': FusionForge.SupportTracker}
		for tracker in trackers:
			if self.verbosity >= 1:
				self.notify("found tracker: " + tracker['label'] + ':' + tracker['projectbase'])
			if tracker['label'] in defaults:
				self.trackers.append(defaults[tracker['label']](self, tracker['projectbase']))
			else:
				self.trackers.append(FusionForge.CustomTracker(self, tracker['label'], tracker['projectbase']))
		return self.trackers

	### PERMISSIONS/ROLES PARSING

	def user_page(self, username):
		return 'users/' + username
		
	def pluck_permissions(self):
		'''
		Get the permissions associated with each role in the project and return the corresponding array
		'''
		if self.verbosity >= 1:
			self.notify('plucking permissions from project/memberlist.php?group_id='+self.project_id)
		contents = self.fetch('project/memberlist.php?group_id=' + self.project_id, 'Roles page')
		perms = {}
		for (realname, username, role, skills) in self.table_iter(self.narrow(contents), '<table', 4, 'Roles Table', has_header=True):
			username = username.strip()
			perms[username] = {'role':role}
			perms[username]['real_name'] = realname
			perms[username]['URL'] = self.real_url(self.user_page(username))
			
		for user in perms:
			contents = self.narrow(self.fetch(self.user_page(user), 'User page'))
			mail = re.search('''sendmessage.php\?touser=[0-9]*">([^<]*)</a>''', contents, re.DOTALL).group(1).strip().replace(" @nospam@ ","@")
			perms[user]['mail'] = mail
			
		return perms
	
	def pluck_roles(self):
		'''
		Get the roles of each registered user of the project and returns the corresponding array
		'''
		roles = {}
		contents = self.fetch('project/admin/?group_id=' + self.project_id, 'Admin page')
		m = re.search('''<form action="roleedit.php\?group_id=[0-9]*" method.*<select name="role_id">(.*)</select>''', contents, re.DOTALL)

		# above is for 4.8, then if fails, for 5.0 :
		if not m:
			contents = self.fetch('project/admin/users.php?group_id=' + self.project_id, 'Admin page')
			m = re.search('''<form action="roleedit.php\?group_id=[0-9]*[^"]*" method.*<select name="role_id">(.*)</select>''', contents, re.DOTALL)

		n = re.findall('''<option value="([0-9]*)"[^>]*>(.*)</option>''', m.group(1))
		n.append(['1', 'Default'])#Default role for project creator, always #1
		n.append(['observer', 'Observer'])
		for i in range(0, len(n)):
			permissions = {}
			editpagecontents = self.fetch('project/admin/roleedit.php?group_id=' + self.project_id + '&role_id=' + n[i][0], 'Edit Role ' + n[i][1] + ' page')
			for (section, subsection, setting) in self.table_iter(editpagecontents, '<table>', 3, 'Edit Table', has_header=True, keep_html=True):
				subsection = dehtmlize(str(subsection)).strip()
				section = dehtmlize(str(section)).strip()
				t = re.findall('''<option value="[-\w]*" selected="selected">([^<]*)</option>''', str(setting))
				if subsection != '-':
					if len(t)>1:
						permissions[section + ':' + 'AnonPost' + ':' + subsection]=t[1]
					permissions[section + ':' + subsection] = t[0]
				elif len(t) != 1: #Exception for project Admin.
					permissions[section] = t[-1]
				else:
					permissions[section] = t[0]
			roles[n[i][1]] = permissions
		return roles
	
	### WIKI PARSING : COCLICO NEW FEATURE
	
	
	def pluck_wiki(self, state=False):
		'''
		Get the phpWiki associated with the project using its specialized export function
		@param state: if true, export last state of the wiki, else exports the last state and the pages history
		'''
		#TODO : Check admin state
		#Will pluck PhpWiki dump
		#if state = true : last state only, if state = false : last state + pages history
		#DL in same folder/phpwiki
		dl = self.fetch('plugins/wiki/index.php?zip=all&type=g&id=' + self.project_id, 'Wiki dump')
		rep_dest = self.project_name + '/PhpWiki'
		if not os.path.exists(self.project_name):
			os.mkdir(self.project_name)
		if not os.path.exists(rep_dest):
			os.mkdir(rep_dest)
		fnout = rep_dest + '/FullDump.zip'
		fout = open(fnout, "wb")
		fout.write(dl)
		fout.close
		
	### DOCMAN PARSING : COCLICO NEW FEATURE
	
	def pluck_docman(self):
		'''
		Get the Document Manager's data of the project and returns the corresponding array, plus downloads any attached files in the local directory $(PROJECT_NAME)/docman
		'''
		# First page of a docman admin web page.
		init_page = self.fetch('docman/admin/?group_id='+ self.project_id, 'main docman page')
		result = {}
		#get each category (active/deleted/hidden/private)
		m=re.findall('''<li><strong>(.*)</strong>(.*)''',init_page)
		#for each category
		for lis in m:
		#execute the recursive function at the root of this category
			result[lis[0]] = self.pluck_docman_list(init_page, docman_type = lis[0])
		return result

	def pluck_docman_list(self, contents, url = None, docman_type = None):
		'''
		Get the documents and directories at the specified page and return a corresponding array
		@param contents: The considered HTML to be parsed.
		@param url: The URL where this HTML can be retrieved
		@param docman_type: 
		'''		
		#TODO:Check usefulness of docman_type 
		result = {}
		#Init a FusionForge_DocMan instance, used to parse contents.
		docman = FusionForge_DocMan(contents, url = url, docman_type = docman_type)
		#Get a list of the content at the current level for the current type.
		d = docman.get_docman_list()
		#for each content at this level
		for el in d:
		#if not a list, then it's a directory
			if not (type(d[el]) is list):
			#recursive call to myself to get the content for this directory
				result[el] = self.pluck_docman_list(self.fetch('docman/admin/' + d[el], 'docman_explorer'), url = d[el], docman_type = docman_type)
			else:
		#else, it's a file
				finfo = FusionForge_DocMan(self.fetch('docman/admin/' + d[el][0], 'docfile'))
			#get its information
				result[el] = finfo.get_file_info()
				if result[el]:
			#create a directory and file to download the docfile
					rep_dest = self.project_name + '/docman'
					if not os.path.exists(self.project_name):
						os.mkdir(self.project_name)
					if not os.path.exists(rep_dest):
						os.mkdir(rep_dest)
					dl = self.fetch('docman/' + result[el]['url'], 'docman file fetching')
					fnout = rep_dest + '/' + result[el]['file_name']
					fout = open(fnout, "wb")
					fout.write(dl)
					fout.close()
				#update the url to a local url
					result[el]['url'] = fnout
				else:
				#file was an url:delete
					del result[el]
		return result

	### FRS PARSING : COCLICO NEW FEATURE

	def pluck_frs(self):
		'''
		Get the contents of the File Release System of the project and return a corresponding data array.
		This is the function which should be called from the extractor.
		'''
		temp = self.fetch('forum/forum.php?forum_id=1&group_id=6', 'frs file fetching')
		init_page = self.fetch('frs/admin/?group_id=' + self.project_id, 'main FRS Admin page')
		result = {}
		
		soup = BeautifulSoup(init_page)
		trs = soup.find('table').findAllNext('tr')[1:]
		
		for tr in trs:
			pk_name = tr.find('input', attrs={'name':'package_name'})['value']
			pk_stid = tr.find('option', attrs={'selected':'selected'})['value']
			pk_stname = tr.find('option', attrs={'selected':'selected'}).contents[0]
			pk_releases = tr.find('a',attrs={'href':re.compile('showreleases')})['href']
			pk_id = re.search('package_id=([0-9]*)', pk_releases).group(1)
			result[pk_name] = {}
			result[pk_name]['status']=pk_stname
			
			if pk_stid=='3':
				#Change status to active
				self.switch_pkg_status(pk_name, pk_id, 1)
			result[pk_name]['releases']=self.pluck_frs_releases(pk_releases)
			if pk_stid=='3':
				#Change status back to hidden
				self.switch_pkg_status(pk_name, 3)
		return result
	
	def switch_pkg_status(self, pk_name, pk_id, pk_stid=1):
		'''
		switch status id of a package from active to hidden and vice/versa
		@param pk_name: Name of the package
		@param pk_id: ID of the package
		@param pk_stid: Status id to be set for this package
		'''
		params = {'group_id':self.project_id, 'func':'update_package', 'package_id':pk_id, 'package_name':pk_name, 'status_id':pk_stid, 'submit':'Update'}
		self.fetch('frs/admin/index.php', 'Updating '+str(pk_name) + ' status to ' + str(pk_stid), params)
		return True
	
	
	def switch_rel_status(self, rel_edit, r_name, r_stid, r_date, r_notes, r_change):
		'''
		switch status id of a release from active to hidden and vice/versa
		@param pk_name: Name of the release
		@param pk_id: ID of the release
		@param pk_stid: Status id to be set for this release
		'''
		params = {'step1':1, 'release_date':r_date, 'release_name':r_name, 'status_id':r_stid, 'release_notes':r_notes, 'release_changes':r_change, 'preformatted':'on','submit':'Submit/Refresh'}
		self.fetch('frs/admin/'+str(rel_edit), 'Updating '+str(r_name) + ' status to ' + str(r_stid), params)
		return True
	
	def pluck_files_for_release(self, r_id, r_files):
		'''
		Get the files of a specified release
		@param r_id: the id of the release
		@param r_files: the array containing the current files, the new ones will be concatenated here
		'''
		init_page = self.fetch('frs/?group_id=' +self.project_id, 'Plucking files from main FRS pages...')
		soup = BeautifulSoup(init_page)
		r_tag = soup.find('a',attrs={'href':re.compile('release_id='+r_id)})
		for fname in r_files:
			furl = r_tag.findNext('a', {'href':re.compile(fname)})['href']
			
			rep_dest = self.project_name + '/frs'
			if not os.path.exists(self.project_name):
				os.mkdir(self.project_name)
			if not os.path.exists(rep_dest):
				os.mkdir(rep_dest)
			dl = self.fetch(furl, 'frs file fetching')
			fnout = rep_dest + '/' + fname
			fout = open(fnout, "wb")
			fout.write(dl)
			fout.close()
		#update the url to a local url
			r_files[fname]['url'] = fnout
		return r_files
		
	def pluck_frs_releases(self, pk_releases):
		'''
		Get the list of releases contained in the specified package and extract the content of these releases with the pluck_frs_release method 
		@param pk_releases: End of the url linking to a package
		'''
		result = {}
		init_page = self.fetch('frs/admin/' + pk_releases, 'Releases')
		soup = BeautifulSoup(init_page)
		trs = soup.find('table').findAllNext('tr')[1:]
		
		for tr in trs:
			rel_edit = tr.find('a')['href']
			rel_name, rel_data = self.pluck_frs_release(rel_edit)
			result[rel_name] = rel_data
			
		return result
	
	
	def pluck_frs_release(self, rel_edit):
		'''
		Get the content of a release, use pluck_files_for_release to get the linked files
		@param rel_edit: End of the url linking to the edit page of a release
		'''
		result = {}
		init_page = self.fetch('frs/admin/' + rel_edit, 'Release edit')
		soup = BeautifulSoup(init_page)
		r_date = soup.find('input',attrs={'name':'release_date'})['value']
		r_name = soup.find('input',attrs={'name':'release_name'})['value']
		r_status = soup.find('select',attrs={'name':'status_id'}).findNext('option',attrs={'selected':'selected'}).contents[0]
		try:
			r_notes = soup.find('textarea',attrs={'name':'release_notes'}).contents[0]
		except:
			r_notes=""
		try:
			r_change = soup.find('textarea',attrs={'name':'release_changes'}).contents[0]
		except:
			r_change=""
		
		r_files = {}
		
		table = soup.findAll('table')[2]
		trs = soup.findAll('table')[2].findAll('tr')[1:]
		i = 0
		while i<len(trs):
			tr = trs[i]
			fname = tr.find('td').contents[0]
			ftype = tr.find('select', {'name':'type_id'}).find('option', {'selected':'selected'}).contents[0]
			fprocessor = tr.find('select', {'name':'processor_id'}).find('option', {'selected':'selected'}).contents[0]
			fdate = trs[i+1].find('input', {'name':'release_time'})['value']
			r_files[fname]={'type':ftype,'processor':fprocessor,'date':fdate}
			i+=3
		
		r_id = re.search('release_id=([0-9]*)', rel_edit).group(1)
		if r_status == 'Hidden':
			self.switch_rel_status(rel_edit, r_name, 1, r_date, r_notes, r_change)
		r_files = self.pluck_files_for_release(r_id, r_files)
		if r_status == 'Hidden':
			self.switch_rel_status(rel_edit, r_name, 3, r_date, r_notes, r_change)
		result = {'date':r_date,'status':r_status,'release_notes':r_notes,'change_log':r_change,'files':r_files}
		return r_name, result
		
	###### TASKS PARSING : COCLICO NEW FEATURE
	
	class Task:
		## CLASSE DES TASKS
		def __init__(self, label, parent, projectbase):
			self.parent = parent
			self.optional = False
			self.chunksize = 50
			self.zerostring = None
			self.label = label
			self.projectbase = projectbase
			self.name_mappings = {
        		"bug_group_id": "group",
        		"category_id": "category",
        		"resolution_id": "resolution",
        		"status_id": "status"
        	}
			# l'auteur du bug n'est pas éditable et ne peut donc être récupérée par le crawler dans le formulaire, cette regexp ne sert qu'à lui
			self.submitter_re = '''<td><strong>Submitted by:</strong><br />\n[^(]*\(([^)]*)'''
			# la date n'est pas éditable et ne peut donc être récupérée par le crawler dans le formulaire
			self.date_re = '''()'''
			# vérifier les champs de formulaire à ignorer
			self.ignore = ("canned_response",
			"new_artifact_type_id",
			"words", "type_of_search", "start_month", "end_month")
			# identifie les ids d'artefacts (bug, patches...) : aid

			self.artifactid_re = r'/pm/task.php\?func=detailtask&amp;project_task_id=([0-9]+)&amp;group_id=[0-9]*&amp;group_project_id=[0-9]*'
			

		def access_denied(self, page, issue_id=None):
			"Vérifie si l'utilisateur n'a pas un accès en édition au tracker interrogé (il doit être au minimum tracker admin)"
			if "No Matching Tasks found" in page:
				return 0
			else:
				return issue_id is None and not "Mass Update" in page

		def has_next_page(self, page):
			"""
			Vérifie si la page contient un compteur indiquant qu'il existe une autre page dans la liste d'artefacts affichés.
			A vérifier avec 50 bugs ou avec les données réelles.
			"""
			return "Next &raquo;" in page

		def chunkfetcher(self, offset):
			"Get a bugtracker index page - all bug IDs, open and closed.."
			return self.projectbase + "&offset=%d&limit=100" % offset

		#fonctionne avec func=browse&func=detail&aid=X (rend le detail de X), mais très laid...
		def detailfetcher(self, issueid):
			"Generate a bug detail URL for the specified bug ID."
			return self.projectbase + '&func=detailtask&project_task_id=' + str(issueid)

		#TODO
		def narrow(self, text):
			"Get the section of text containing editable elements."
			#Look for <div id="maindiv">
			return text
	
		def parse_followups(self, contents):
			'''
			Parse followups out of a displayed page in a task tracker.
			@param contents: Web page of the artifact
			'''
			comments = []
			try:
				trs = contents.find('h3',text='Followups').findNext('table').findAll('tr')[1:]
				for tr in trs:	
					comment = {"class":"COMMENT"} #Useful?
					tds = tr.findAll('td')
					comment['comment'] = dehtmlize(''.join(map(str,tds[0].contents)))
					comment['date'] = self.parent.canonicalize_date(tds[1].contents[0])
					comment['submitter'] = tds[2].contents[0]
					comments.append(comment)
				comments.reverse()
			except AttributeError:
				#No registered followup
				pass
			return comments
		
		def parse_history(self, contents):
			'''
			Get the history of changes of the current task
			@param contents: Web page of the artifact
			'''
			history=[]
			try:
				trs = contents.find('h3',text='Task Change History').findNext('table').findAll('tr')[1:]
				for tr in trs:
					h = {"class":"HISTORY"}
					tds = tr.findAll('td')
					h['field'] = tds[0].contents[0]
					h['old'] = tds[1].contents[0]
					h['date'] = self.parent.canonicalize_date(tds[2].contents[0])
					h['by'] = tds[3].contents[0]
					history.append(h)
				history.reverse()
			except AttributeError:
				#No registered history
				pass
			return history
		
		def parse_linkedTasks(self, contents):
			'''
			Get the linked, required tasks of the current task
			@param contents: Web page of the artifact
			'''
			linked = []
			try:
				trs = contents.find('h3',text='Tasks That Depend on This Task').findNext('table').findAll('tr')[1:]
				for tr in trs:
					l = {"class":"LINKED_ARTIFACT"}
					tds = tr.findAll('td')
					l['task_id'] = tds[0].contents[0].next
					l['task_summary'] = tds[1].contents[0]
					linked.append(l)
				linked.reverse()
			except AttributeError:
				#No registered linked task
				pass
			return linked
			
		def custom(self, contents, artifact, vocabularies):
			'''
			Pluck the specificic properties of this plucker.
			@param contents: Web page of the artifact
			@param artifact: Artifact array as plucked by the basic extractor
			@param vocabularies: Vocabularies array as plucked by the basic extractor
			'''
			soupedContents = BeautifulSoup(contents)
#			Get comments
			artifact['comments'] = self.parse_followups(soupedContents)
#			Get history
			artifact['history'] = self.parse_history(soupedContents)
#			Get linked tasks
			artifact['linked_tasks'] = self.parse_linkedTasks(soupedContents)
#			Get the first comment of the task which cannot be modified and is the description of the task
			artifact['description'] = soupedContents.find('td', attrs={'colspan':'2'}).find('strong').nextSibling.nextSibling.strip() #Use colspan because the original comment + add comment box are always in a colspan 2 td with no id
#			Gather the number of the projected end moth of the task
			end_month = soupedContents.find('select',attrs={'name':'end_month'}).find('option', attrs={'selected':'selected'})['value'] #Maybe use a corresponding tab, Plucker give the content value, the name of the month (January, Feb..., etc) instead of the number
#			Format the end date as a normal date as used for comment or followups date
			end_date = artifact['end_year']+'-'+end_month+'-'+artifact['end_day']+' '+artifact['end_hour']+':'+artifact['end_minute']
#			Delete unused categories in the artifact and vocabularies. Could have been filtered from the start but would require more search in the soupedContents, unsure which way is the fastest
			del artifact['end_year'],artifact['end_day'],artifact['end_hour'],artifact['end_minute']
			del vocabularies['end_year'],vocabularies['end_day'],vocabularies['end_hour'],vocabularies['end_minute']
#			Register the date in the artifact as end_date
			artifact['end_date'] = self.parent.canonicalize_date(end_date)
#			Same for start date
			start_month = soupedContents.find('select',attrs={'name':'start_month'}).find('option', attrs={'selected':'selected'})['value']
			start_date = artifact['start_year']+'-'+start_month+'-'+artifact['start_day']+' '+artifact['start_hour']+':'+artifact['start_minute']
			del artifact['start_year'],artifact['start_day'],artifact['start_hour'],artifact['start_minute']
			del vocabularies['start_year'],vocabularies['start_day'],vocabularies['start_hour'],vocabularies['start_minute']
			artifact['start_date'] = self.parent.canonicalize_date(start_date)
			return True
		
	class CustomizableTaskTracker(Task):
		'''
		Basic TaskTrackerObject
		'''
		def __init__(self, parent, nameTracker, typeTracker, projectbase):
			FusionForge.Task.__init__(self, nameTracker, parent, projectbase)
			self.type = typeTracker
		
	def getTasksTrackers(self):	
		'''
		Parse the tasks initial page and return a list of dictionaries containing (tasks tracker name, tasks tracker type (default custom)).
		If type corresponds to one of the fixated types, register it
		'''
		tasksTrackers = []
		basepage = BeautifulSoup(self.basepage)
		tT = basepage.findAll('a', {'href':re.compile('task.php')})
		for t in tT:
			tPage = re.search('[^/]*//[^/]*/([^"]*)',t['href']).group(1)
			tLabel = t.contents[0]
			tasksTrackers.append({'label':tLabel, 'type':'custom', 'projectbase':tPage})
		return tasksTrackers
	
	def pluck_tasksTrackers(self, timeless=False):
		'''
		Initializes tasks plucking. This is the only method which should be called for tasks plucking. 
		Return the corresponding data for each tasks tracker of the project.
		@param timeless:Needed to register interval between beginning and end of scrapping
		'''
		self.trackers = [] #Reset trackers to empty
		for tasksTracker in self.getTasksTrackers():
			self.trackers.append(FusionForge.CustomizableTaskTracker(self, tasksTracker['label'], tasksTracker['type'], tasksTracker['projectbase']))
		return self.pluck_trackers(timeless, True)

	###### NEWS PARSING : COCLICO NEW FEATURE
	
	def pluck_news(self):
		'''
		Initializes the extraction of the news of a project. This is the only method which should be called from outside. 
		'''
		init_page = self.fetch('news/?group_id='+self.project_id, 'plucking main news page')	
		soup = BeautifulSoup(init_page)
		result = self.newsListParser(soup)
		return result
	
	
	def newsListParser(self, soup):
		'''
		Parse the list of news of the news list page
		@param soup: the souped html of the news' list page
		'''
		newsList = []
		links = soup.findAll('a',{'href':re.compile('forum/forum.php')})
		i = 0
		while i<len(links):
			newsList.append(links[i]['href'])
			if i<20: #nombre de news affichées en full
				i+=2
			else:
				i+=1
		result = []
		for news in newsList:
			result.append(self.newsParser(BeautifulSoup(self.fetch(news, 'plucking news'))))
		return result

	def newsParser(self, newsSoup):
		'''
		Parse a single news page
		@param news: a news page soup
		'''
		newsTable = newsSoup.find('table')
		poster_name = newsTable.find(text=re.compile('Posted')).next.strip()
		news_date = newsTable.find(text=re.compile('Date')).next.strip()
		news_summary = newsTable.find(text=re.compile('Summary')).next.contents[0]
		news_content=''
		for s in newsTable.find('p').contents:
			if s.string != None:
				news_content+=s.string
		news_content = news_content.strip().replace(' \r','\n')
#		news_content = dehtmlize(''.join(blocktext(str(s)) for s in newsTable.find('p').contents)) #Couldn't make a correct code to handle both the <br /> and the \n without either too many \n or none at all... replaced by the length above code
		news_forum = self.forumParser(newsSoup, 5, 4, 3)
		result = {'poster_name':poster_name, 'date':news_date,'summary':news_summary,'news_content':news_content,'forum':news_forum}
		return result
		
		
	def mailingListsListing(self, soup):
		mailinglists = []
		trs = soup.find('table').findAll('tr')[1:]
		for tr in trs:
			tds = tr.findAll('td')
			fHref = tds[0].find('a')['href']
			mailinglists.append(fHref)
		return mailinglists
		
	def taskTrackersListing(self, soup):
		task_trackers = []
		trs = soup.find('table').findAll('tr')[1:]
		for tr in trs:
			tds = tr.findAll('td')
			fHref = tds[0].find('a')['href']
			task_trackers.append(fHref)
		return task_trackers

	def scmListing(self, soup):
		scm = scm_type = None
		tts = soup.findAll('tt')
		for tt in tts:
			m = re.search('([^ ]+) checkout .* (http.*)', tt.contents[0])
			if m:
				scm_type = m.group(1)
				scm = m.group(2)
				break
		return scm_type, scm

	###### FORUM PARSING : COCLICO NEW FEATURE
	
	def pluck_forums(self):
		'''
		Initializes forums parsing. This is the method which should be called from the outside
		'''
		if self.verbosity >= 1:
			self.notify('plucking forums from forum/?group_id='+self.project_id)
		init_page = self.fetch('forum/?group_id='+self.project_id, 'plucking main forum page')
		soup = BeautifulSoup(init_page)
		result = self.forumsParser(soup)
		return result
	
	class Message():
		'''
		When parsing a forum, the method creates a Message object for each message found. This object provides methods to retrieve the informations such as content, linked file ... of the initialized message
		'''
		def __init__(self, parent, href, index):
			'''
			Intializes the Message object and retrieves information using the retrieveInfo method
			@param parent: Fusionforge class, needed to get fetch method access
			@param href: Message url
			@param index: index of the message table in the list of tables of the page
			'''
			self.parent = parent
			self.href = href
			self.index = index
			self.messagesObjects = []
			self.infos = self.retrieveInfo()
			
		def retrieveInfo(self):
			'''
			Retrieve the info of the message : submitter, date, attached file, subject, content
			'''
			message = self.parent.fetch(self.href, 'Retrieving message info for msg_id '+self.href)
			message = BeautifulSoup(message)
			table = message.findAll('table')[self.index]
			submitter_login = table.find('a', {'href':re.compile('/users/')}).contents[0]
			date = table.find(text=re.compile('DATE:'))[6:]
			if table.find(text=re.compile('No attachment')) != None:
				#No attachment
				attachment = {}
			else:
				#attachment found
				fhref = table.find('a',{'href':re.compile('javascript:manageattachments')})
				fname = table.find('a',{'href':re.compile('javascript:manageattachments')}).contents[1]
				furl = re.search(":manageattachments\('([^']*)", fhref['href']).group(1)
				rep_dest = self.parent.project_name + '/forum'
				if not os.path.exists(self.parent.project_name):
					os.mkdir(self.parent.project_name)
				if not os.path.exists(rep_dest):
					os.mkdir(rep_dest)
				dl = self.parent.fetch(furl, 'forum attachment file fetching')
				fnout = rep_dest + '/' + fname
				fout = open(fnout, "wb")
				fout.write(dl)
				fout.close()
				attachment = {'name':fname, 'url':fnout}
			subject = table.find(text=re.compile('SUBJECT:'))[9:]
			content = re.search('<p>&nbsp;</p>(.*)</td></tr></table>',str(table),re.DOTALL).group(1)
			return {'submitter':submitter_login, 'date':date, 'attachment':attachment, 'subject':subject, 'content':content}
	
		def addChild(self, message):
			'''
			Add a message to the current message children
			@param message: an object Message
			'''
			self.messagesObjects.append(message)
			
		def toDict(self):
			'''
			Used to extract a dictionary recursively of the content of this message and of each of its children. Called once on each level 0 message.
			'''
			messagesList = []
			for message in self.messagesObjects:
				messagesList.append(message.toDict())
			self.infos['children']=messagesList
			return self.infos
	
	def forumParser(self, soup, nextTableIndex = 2, dataTableIndex = 1, messageTableIndex = 0):
		'''
		Parse the content of the forum
		@param soup: soupedContent of the forum page to parse
		@param nextTableIndex: Index of the table containing the 'Previous Page'/'Next Page' in the whole page
		@param dataTableIndex: Index of the table containing the messages in the whole page
		@param messageTableIndex: Index of the table containing the message content when viewing a single message rather than the whole forum
		'''
		liste_ids = []
		nextPage = True
		listeMessagesObjects = []
		while nextPage:
			liste = []
			tables = soup.findAll('table')
			nextTable = tables[nextTableIndex]
			dataTable = tables[dataTableIndex]
			trs = dataTable.findAll('tr')[1:]
			for tr in trs:
				href = tr.find('a')['href']
				#check each time?
				#print href
				msg_id = re.search('msg_id=([0-9]*)', href).group(1)
				if not msg_id in liste_ids:
					liste_ids.append(msg_id)
					depth = (len(str(tr.contents[0]).split(';'))-1)/3
					if depth == 0:
						try:
							listeMessagesObjects.append(liste[0])
						except:
							pass
						msg = self.Message(self, href, messageTableIndex)
						try:
							liste[0] = msg
						except:
							liste.append(msg) 
					else:
						msg = self.Message(self, href, messageTableIndex)
						liste[depth-1].addChild(msg)
						try:
							liste[depth] = msg
						except:
							liste.append(msg)
				else:
					liste = []
			if len(liste)>0:
				listeMessagesObjects.append(liste[0])
			
			hasNextPage = nextTable.find(text=' Next Messages')
			if hasNextPage == None:
				nextPage = False
			else:
				nextPageHtml = self.fetch(hasNextPage.findPrevious('a')['href'], 'Fetching next forum page')
				soup = BeautifulSoup(nextPageHtml)
		
		listeMessagesDicts = []
		for message in listeMessagesObjects:
			listeMessagesDicts.append(message.toDict())	
		return listeMessagesDicts

	def forumAdminParser(self, soup):
		'''
		Parse the content of the admin page of the forum
		@param soup:
		'''
		anon_posts = soup.find('input', {'name':'allow_anonymous', 'checked':'checked'}).next.strip()
		is_public = soup.find('input', {'name':'is_public', 'checked':'checked'}).next.strip()
		moderation = soup.find('select',{'name':'moderation_level'}).find('option',{'selected':'selected'}).contents[0]
		email_posts_to = soup.find('input',{'name':'send_all_posts_to'})['value']
		dictParams = {'allow_anonymous_posts':anon_posts,'is_public':is_public, 'moderation_level':moderation, 'email_posts_to':email_posts_to}
		return dictParams 
	
	def forumMonitorParser(self, soup):
		'''
		Parse the content of the monitoring users table
		@param soup:
		'''
		listeUsers = []
		trs = soup.find('table').findAll('tr')[1:]
		for tr in trs:
			listeUsers.append(tr.find('td').contents[0])
		return listeUsers
	
	def forumSwitchViewMode(self, fId):
		'''
		Switch view mode to Threaded (only mode parsed)
		@param fId: forum Id
		'''
		self.fetch('forum/forum.php?set=custom&forum_id='+str(fId)+'&style=threaded&max_rows=25&submit=Change+View', 'Updating '+str(fId) + ' view mode to Threaded')
		return True

	def forumsListing(self, soup):
		forums = []
		trs = soup.find('table').findAll('tr')[1:]
		for tr in trs:
			tds = tr.findAll('td')
			fHref = tds[0].find('a')['href']
			fId = re.search('forum_id=([0-9]*)', fHref).group(1)
			fUrl = 'forum/'+fHref
			fName = tds[0].find('a').contents[1][6:]
			fDesc = tds[1].contents[0]
			self.forumSwitchViewMode(fId)
			fAdminUrl = 'forum/admin/index.php?group_id='+self.project_id+'&change_status=1&group_forum_id='+fId
			fMonitorUrl = '/forum/admin/monitor.php?group_id='+self.project_id+'&group_forum_id='+fId
			forums.append({'name':fName, 'description':fDesc, 'URL':fUrl, 'adminUrl':fAdminUrl, 'monitoring_usersUrl':fMonitorUrl})
		return forums
		
	def forumsParser(self, soup):
		'''
		Fetch a list of forums from the souped contents of the forums page, initializes the extraction ot the content of each forum and the admin parameters
		@param soup: Souped contents of the forums page
		'''
		forums = []
		frs = self.forumsListing(soup)
		for f in frs:
			fName = f['name']
			fDesc = f['description']
			fUrl = f['URL']
			fAdminUrl = f['adminUrl']
			fMonitorUrl = f['monitoring_usersUrl']
			fId = re.search('forum_id=([0-9]*)', fUrl).group(1)
			self.forumSwitchViewMode(fId)
			fAdminContent = self.forumAdminParser(BeautifulSoup(self.fetch(fAdminUrl, 'forum admin content download. forum name:'+fName)))
			fMonitorContent = self.forumMonitorParser(BeautifulSoup(self.fetch(fMonitorUrl, 'forum monitoring users content download. forum name:'+fName)))
			fContent = self.forumParser(BeautifulSoup(self.fetch(fUrl, 'forum content downloading. forum name:'+fName))) 
			forums.append({'name':fName, 'description':fDesc, 'content':fContent, 'admin':fAdminContent, 'monitoring_users':fMonitorContent})
		return forums
		
	
	###### END FORUM PARSING

	class ProjectDescription:
		"Project description"
		def __init__(self):
			pass
#		def extract(self, contents):
			
			
## FusionForge.__init__

	def __init__(self, host, project_name, params = False):
		"""			"""
		GenericForge.__init__(self, host, project_name, params)
		
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
			raise ForgePluckerException("No matching id found for project %s" % project_name)


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
		# POST data in the login form
		GenericForge.login(self, 
				   {
				'form_loginname':username,
				'form_pw':password,
				'login':'login'},
				   'href="'+ self.real_url('account/logout.php') +'">')


	def narrow(self, text):
		"Get the section of text containing editable elements."
		soupedContents = BeautifulSoup(text)
		text = soupedContents.find('div', id='gforge-content')
		if not text:
			text = soupedContents.find('div', id='maindiv')
		return str(text)

	def pluck_project_data(self):
		project_page = self.project_page(self.project_name)
		page = self.fetch(project_page, "Project summary")
		mainsoup = BeautifulSoup(self.narrow(page))
		
		description = None
		shortdesc = None
		fieldset = mainsoup.find('fieldset')
		# 4.8
		if fieldset:
			description = fieldset.find('table').find('tr').find('td').find('p').contents
			description = dehtmlize(''.join(map(str,description)))
		else: #5.0
			shortdesc = mainsoup.find('h2').contents[0]
			description = mainsoup.find('p').contents[0]

		registered = None
		for p in mainsoup.findAll('p'):
			m = re.search('Registered:&nbsp;([-0-9: ]+)', str(p.contents[0]))
			if m:
				registered = self.canonicalize_date(m.group(1))
				break

		homepage = None
		trackers = None
		public_forums = None
		docman = None
		mailing_lists = None
		task_trackers = None
		scm = None
		news = None
		frs = None

		public_areas = None
		for t in mainsoup.findAll('table'):
			tr = t.find('tr', attrs={'class': 'tableheading'})
			if tr:
				td = tr.find('td').findNext('td').find('span').contents[0]
				if td == 'Public Areas' :
					public_areas = t
					break
		if public_areas:
			#print 'public_areas:', public_areas
			t = public_areas.find('tr').findNext('tr').findNext('tr').find('td').find('table', attrs={'class': 'tablecontent'})
			a = t.find('a')
			while a:
				for l in a.contents:
					if l == '&nbsp;Project Home Page':
						homepage = a['href']
					if l == '&nbsp;Tracker':
						trackers = self.get_trackers()
					if l == '&nbsp;Public Forums':
						init_page = self.fetch('forum/?group_id='+self.project_id, 'plucking main forum page')
						soup = BeautifulSoup(self.narrow(init_page))
						public_forums = self.forumsListing(soup)
					if l == '&nbsp;DocManager: Project Documentation':
						docman = a['href']
					if l == '&nbsp;Mailing Lists':
						init_page = self.fetch('mail/?group_id='+self.project_id, 'plucking main mailing lists page')
						soup = BeautifulSoup(self.narrow(init_page))
						mailing_lists = self.mailingListsListing(soup)
					if l == '&nbsp;Task Manager':
						init_page = self.fetch('pm/?group_id='+self.project_id, 'plucking main tasks page')
						soup = BeautifulSoup(self.narrow(init_page))
						task_trackers = self.taskTrackersListing(soup)
					if l == '&nbsp;SCM Repository':
						init_page = self.fetch('scm/?group_id='+self.project_id, 'plucking scm page')
						soup = BeautifulSoup(self.narrow(init_page))
						scm = self.scmListing(soup)
						
				a = a.findNext('a')

			a = public_areas.find('a')
			while a:
				for l in a.contents:
					if l == '[News archive]':
						news = a['href']
						break
				a = a.findNext('a')

		for a in mainsoup.findAll('a'):
			for l in a.contents:
				if l == '[View All Project Files]':
					frs = a['href']
					break
			if frs:
				break

		data = {"class":"PROJECT",
			"forgetype":self.__class__.__name__,
			"host" : self.host,
			"project" : self.project_name,
			"description" : description,
			"registered" : registered,
			"homepage": homepage,
			"URL": self.real_url(project_page),
			"format_version": 1 }

		forge = self.real_url('')

		tools = {}

		if shortdesc:
			data['shortdesc'] = shortdesc

		if trackers:
			data['trackers_list'] = []
			for t in trackers:
				url = self.real_url(t.getUrl())
				data['trackers_list'].append(url)
				provided_by = forge+'#tracker'
				tools[url] = { 'provided_by': provided_by }
				if not provided_by in tools:
					tools[provided_by] = { 'type': 'TrackersTool'}

		if public_forums:
			data['public_forums'] = []
			for f in public_forums:
				url = self.real_url(f['URL'])
				data['public_forums'].append(url)
				provided_by = forge+'#forum'
				tools[url] = { 'provided_by': provided_by }
				if not provided_by in tools:
					tools[provided_by] = { 'type': 'ForumsTool'}
				
		if docman:
			data['docman'] = docman
			provided_by = forge+'#docman'
			tools[docman] = { 'provided_by': provided_by }
			if not provided_by in tools:
				tools[provided_by] = { 'type': 'DocumentsTool'}

		if mailing_lists:
			data['mailing_lists'] = mailing_lists
			for m in mailing_lists:
				provided_by = forge+'#mailman'
				tools[m] = { 'provided_by': provided_by }
				if not provided_by in tools:
					tools[provided_by] = { 'type': 'MailingListTool'}

		if task_trackers:
			data['task_trackers'] = task_trackers
			for t in task_trackers:
				provided_by = forge+'#taskstracker'
				tools[t] = { 'provided_by': provided_by }
				if not provided_by in tools:
					tools[provided_by] = { 'type': 'TaskTool'}

		if scm:
			scm_type, scm = scm
			data['scm_type'] = scm_type
			data['scm'] = scm
			provided_by = forge+'#'+scm_type
			tools[scm] = { 'provided_by': provided_by }
			if not provided_by in tools:
				tools[provided_by] = { 'type': 'ScmTool'}


		if news:
			data['news'] = news
			provided_by = forge+'#news'
			tools[news] = { 'provided_by': provided_by }
			if not provided_by in tools:
				tools[provided_by] = { 'type': 'NewsTool'}

		if frs:
			data['frs'] = frs
			provided_by = forge+'#frs'
			tools[frs] = { 'provided_by': provided_by }
			if not provided_by in tools:
				tools[provided_by] = { 'type': 'FilesReleasesTool'}

		data['tools'] = tools

		return data
