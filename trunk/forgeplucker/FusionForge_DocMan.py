'''
Created on 1 juil. 2010

@author: fdudouet
'''

'''
Created on 6 mai 2010

@author: fdudouet
'''
import re, pprint

from htmlscrape import *
from generic import *
from BeautifulSoup import *
class FusionForge_DocMan(object):
	def __init__(self, contents, docman_type = None, url = None):
		'''
		Launch the parsing
		@param contents: FusionForge Docman page
		'''
		#if type specified (meaning we're not at the docman root, we're extracting content from a category) and url is not set (we are at the root of this category)
		if docman_type and not url:
			m = re.search('<strong>'+str(docman_type)+'</strong>(.*)', contents)
			self.contents = m.group(1)
			#self.contents = contents
		else:
		#we have an url to refine our search, no need to extract a part of the content (except for performance)
			self.contents = contents
		
		self.url = url
		self.type = type
		
	def get_docman_list(self):
		'''
		Get DocMan (launcher method)
		'''
		result = {}
		soup = BeautifulSoup(self.contents)
		#url = none, means no particular href to search
		if self.type:
			if not self.url:
				#get all links from self.contents
				li = soup.findAll('a', attrs={"href":re.compile('index.php.*')})
				for html in li:
					result[html.contents[0]] = html['href']
			else:
				uls = soup.find('a', href=self.url).findNextSiblings('ul', limit=2)
				if len(uls) > 1:
					#uls[0] = directories
					li = uls[0].findAll('a', attrs={"href":re.compile('index.php.*')})
					for html in li:
						result[html.contents[0]] = html['href']
					#uls[1] = files
					li = uls[1].findAll('a', attrs={"href":re.compile('index.php.*')})
					for html in li:
						result[html.contents[0]] = [html['href']]
				else:
					li = uls[0].findAll('a', attrs={"href":re.compile('index.php.*')})
					if re.search("editdoc", str(li[0])):
						#files
						for html in li:
							result[html.contents[0]] = [html['href']]
					else:
						#docs - unused
						for html in li:
							result[html.contents[0]] = html['href']
			return result
		else:
			return False
			
	
	def get_file_info(self):
		'''
		Retrieve documents infos from the list
		@param x: the list
		'''
		try:
			soup = BeautifulSoup(self.contents)
			fgivenname = soup.find('input', attrs={'name':'title'})['value']
			fdesc = soup.find('input', attrs={'name':'description'})['value']
			flanguage = soup.find('select', attrs={'name':'language_id'}).find('option', attrs={'selected':'selected'}).contents[0]
			furl = soup.find(text=fgivenname).previous['href'][3:]
			fname = furl.split('/')[-1]
			return {'class':'FILE','given_name':fgivenname, 'file_name' : fname, 'description':fdesc, 'language':flanguage, 'url':furl}
		except AttributeError, e:
			return False
	
	def find_last_dirname(self,level):
		'''
		Retrieve the last dirname of the current level. Useful to find directories relations
		@param level: the level of the repository to check, beginning from 0
		'''
		if level == 0:
			last_rep = ""
		else:
			for i in range(0, len(self.docman[level])):
				last_rep = self.docman[level][i][2]
		return last_rep
	
	def job(self,M, type, result = None):
		'''
		Recursive function to retrieve the dictionary containing all of the docman information
		@param M: Input list
		'''
		result = {}
		soup = BeautifulSoup(M)
#		for ul in soup.findAll('ul'):
#			for li in ul.findAll('li'):
#				infos =  li.find('a')
#				group_doc_id = re.search('''&selected_doc_group_id=([0-9]*)''',infos['href']).group(1)
#				if(not group_doc_id in self.added):
#					result[infos.contents[0]] = self.job(self.fetch('docman/admin/' + infos['href']))
#					self.added.append(group_doc_id)
		urls = soup.findAll('a')
		for url in urls:
			if url['href'][:11] == 'index.php?g':
				group_doc_id = re.search('''&selected_doc_group_id=([0-9]*)''',url['href']).group(1)
				if not group_doc_id in self.addedDirs:
					self.addedDirs.append(group_doc_id)
					#type is active, hidden, deleted...
					print self.fetch('docman/admin/' + url['href'], 'toto')
					result[url.contents[0]] = self.job(self,self.find_list(self.fetch('docman/admin/' + url['href'], 'directory'), type))
			elif url['href'][:11] == 'index.php?e':
				fname = url.contents[0]
				if not fname in self.addedFiles:
					result[fname]=self.get_info(self.fetch('docman/admin/' + url['href'], 'file'))
		
		return result
#				self.job(m, i + 1)
	
	#parse whole page again... instantiate another object?
	def find_list(self, contents, type):
		m=re.search('<li><strong>'+type+'</strong>(.*)',contents)
		return m
	
	def find_lists(self):
		'''
		Retrieve the list of list to be parsed from the whole page
		'''
		m=re.findall('''<li><strong>(.*)</strong>(.*)''',self.contents)
		return m
	
	def refactor_docman(self):
		'''
		Refactor the list to make a dictionary
		TODO: Do it directly...
		'''
		docm = {}
		for i in self.docman:
			for j in self.docman[i]:
				if j[0] == 0:
					docm[j[2]] = {}
					docm[j[2]]["previous_dir"]=j[1]
				if j[0] == 1:
					if docm[j[1]].has_key("files"):
						docm[j[1]]["files"].append(j[2])
					else:
						docm[j[1]]["files"]=[j[2]]
		return docm
if __name__ == "__main__":
	
	f = open("C:/Users/fdudouet.IRISA/Downloads/fusionforge.irisa.fr.htm")
	contents = f.read()
	toto = Admin_FusionForge_DocMan(contents)
	
	pp = pprint.PrettyPrinter(indent=4)
	doc = toto.get_docman()
#	while it.hasNext():
#		print it.next()
#		print k
	pp.pprint(doc)
#	for k in doc:
#		if doc[k].has_key('files'):
#			for file in doc[k]['files']:
#				print file[0][1]
#				print file[1]
#				
#	for d in doc:
#		#for each level
#		for el in doc[d]:
#			if el[0]==0:
#				#directory
#				print el
#			elif el[0]==1:
#				print el
#	toto.refactor_docman()
	
	

