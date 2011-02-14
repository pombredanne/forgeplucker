'''
Created on 1 juil. 2010

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
		finfo = {}
		try:
			soup = BeautifulSoup(self.contents)
			fgivenname = soup.find('input', attrs={'name':'title'})['value']
			fdesc = soup.find('input', attrs={'name':'description'})['value']
			flanguage = soup.find('select', attrs={'name':'language_id'}).find('option', attrs={'selected':'selected'}).contents[0]
			furl = soup.find(text=fgivenname).previous['href'][3:]
			fname = furl.split('/')[-1]
			if furl[:4] == 'view':
				finfo =  {'class':'FILE','given_name':fgivenname, 'file_name' : fname, 'description':fdesc, 'language':flanguage, 'url':furl}
			else:
				finfo = False
			return finfo
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
	
	
