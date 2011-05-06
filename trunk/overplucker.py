#!/usr/bin/env python
import tempfile, os, sys,re, getopt, shutil, tarfile
#import scp, paramiko
from forgeplucker import *
import subprocess


class mainExtract(object):

	def __init__(self, address, projectName, www_username, www_password, tempSaveFolder, outputDir, typeF = 'FusionForge', useLocalServer = False, getSCM = True, getMailings = True, getWiki = False, getTrackers=False, getTasks = False, getNews = False, getFRS=False, getForums = False, getDocs = False):
		self.address = address
		self.projectName = projectName
		self.www_username = self.ssh_username = www_username
		self.www_password = self.ssh_username = www_password
		self.tempSaveFolder = tempSaveFolder
		self.typeF = typeF
		self.useLocalServer = useLocalServer
		self.getSCM = getSCM
		self.getMailings = getMailings
		self.getWiki = getWiki
		self.getTrackers = getTrackers
		self.getTasks = getTasks
		self.getNews = getNews
		self.getFRS = getFRS
		self.getForums = getForums
		self.getDocs = getDocs
		self.outputDir = outputDir
	
	def setSSH(self, ssh_username = None, pKeyPassword = None, usePKeyPwd = True, ssh_password = None,):
		if ssh_password != None:
			self.ssh_password = ssh_password
		if ssh_username != None:
			self.ssh_username = ssh_username
		if usePKeyPwd:
			self.pKeyPassword = pKeyPassword
			privatekeyfile = os.path.expanduser('~/.ssh/id_rsa')
			self.mykey = paramiko.RSAKey.from_private_key_file(privatekeyfile, self.pKeyPassword)
	def setMailings(self, mailingServerAddress = None, mailman = '/var/lib/mailman/'):
		self.mailingServerAddress = mailingServerAddress
		self.mailman = mailman
		
	def setSCM(self, scmServerAddress = None):
		self.scmServerAddress = scmServerAddress
		
	def init_bugplucker(self):
		param_string = '-u %s -p %s -f FusionForge -v1 -o coclico -P '%(self.www_username, self.www_password)
		if self.getWiki:
			param_string += '-W '
		if self.getTrackers:
			param_string += '-T '
		if self.getDocs:
			param_string += '-D '
		if self.getTasks:
			param_string += '-K '
		if self.getNews:
			param_string += '-N '
		if self.getFRS:
			param_string += '-F '
		if self.getForums:
			param_string += '-B '
		if self.getDocs:
			param_string += '-D '
		
		param_string += self.address
	
		res=os.popen(os.getcwd()+"/bugplucker.py "+ param_string).read()
		try: #a modifier avec des exists moins ignobles
			os.mkdir(self.tempSaveFolder+'/Plucker/')
		except:
			pass
		rolPer = open(self.tempSaveFolder+'/Plucker/JSON_Pluck.txt',"w")
		
		rolPer.write(res)
		rolPer.close()
		#TODO: Add a "target" to bugplucker so one can specify where files should be downloaded (instead of current dir)
		try:
			shutil.move('./'+self.projectName, self.tempSaveFolder+'/Plucker/'+self.projectName)
		except:
			pass
		
	def extract(self):
		
		if self.getSCM:
			self.getSVN()
			self.getGIT()
		if self.getMailings:
			self.getMailingListsName()
		self.init_bugplucker()

	def getCVS(self, incremental=False):
	    return True
			
	def getGIT(self, incremental=False):
		if not os.path.isdir('/gitroot/'+self.projectName):
			return False
		if self.useLocalServer:
			#Copy gitroot dir
			shutil.copytree('/gitroot/'+self.projectName, self.tempSaveFolder+'/SCM/GIT')
			
	def getSVN(self, incremental=False):
		'''
		Retrieve SVN from local or distant server
		@param incremental: Default no, retrieve only the latest version, otherwise retrieve the whole history
		'''
		if not os.path.isdir('/svnroot/'+self.projectName):
			return False
		try: 
		#TODO:Check existence of said folder
			os.mkdir(self.tempSaveFolder+'/SCM/')
			os.mkdir(self.tempSaveFolder+'/SCM/SVN/')
		except:
			pass
		if self.useLocalServer:
			#svnadmindump from local
			fout = open(self.tempSaveFolder+'/SCM/SVN/'+self.projectName+'.svndump', "wb")
			subprocess.call(['svnadmin', 'dump', '/svnroot/'+self.projectName], stdout=fout)
			fout.close()
		else:
			ssh = paramiko.SSHClient()
			ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			ssh.connect(self.scmServerAddress, username = self.ssh_username, pkey=self.mykey)
			ssh.exec_command('svnadmin dump /svnroot/'+self.projectName+' > /tmp/'+self.projectName+'.svndump')
			sftp = ssh.open_sftp()
			sftp.get('/tmp/'+self.projectName+'.svndump', self.tempSaveFolder+'/SCM/SVN/'+self.projectName+'.svndump')
			ssh.close()

	def getMailingListsName(self,status='private'):
		'''
		Get name of each mailing list associated to current project
		@param status:
		'''
		try:
			os.mkdir(self.tempSaveFolder+'/mailings/')
		except:
			pass
		if self.useLocalServer:
			process = subprocess.Popen(['find', self.mailman+'archives/'+status+'/', '-maxdepth', '1', '-type', 'd', '-name', self.projectName.lower()+'-*', '-not', '-name', '*.mbox'], stdout = subprocess.PIPE)
			mlListsString = process.communicate()[0]
			mlLists = mlListsString.split('\n')[:-1]
			for ml in mlLists:
				self.getMailingByName(ml)
		else:
			transport = paramiko.Transport(self.mailingServerAddress)
			#Todo ask for the right key if multiple
			transport.connect(username = self.ssh_username, pkey = self.mykey)
			session = transport.open_sftp_client()
			mlList = session.listdir(self.mailman+status+'/')#TODO:Update with +archives
			for ml in mlList:
				if re.match(self.projectName.lower()+'-', ml) and not re.match('.*mbox', ml):
					self.getMailingByName(ml)
			transport.close()

	def getMailingByName(self,mailingListName, status='private'):
		'''
		Copy content of archive folder recursively 
		@param mailingListName:
		@param status:
		'''
		listName = os.path.basename(mailingListName)
		#Mailing list archive server may be different from www server
		#Todo : Paramiko support for entire python support
		localSave = self.tempSaveFolder+'/mailings/'+listName
		#make temp subdir of mailingListName
		try:
			os.mkdir(localSave)
			os.mkdir(localSave+'/archives')
			os.mkdir(localSave+'/archives/private')
			os.mkdir(localSave+'/lists')
		except:
			pass

		if self.useLocalServer:
			subprocess.call(['cp', '-r', mailingListName, localSave+'/archives/private'])
			subprocess.call(['cp', '-r', mailingListName+'.mbox', localSave+'/archives/private'])
			subprocess.call(['cp', '-r', self.mailman+'lists/'+listName, localSave+'/lists'])
		else:	
			transport = paramiko.Transport(self.mailingServerAddress)
			transport.connect(username = self.ssh_username, pkey = self.mykey)
			scpC = scp.SCPClient(transport)
			scpC.get_rp(self.mailman + status + '/' + mailingListName + '/', localSave)#TODO:Update with archives
			transport.close()
		
	def makeArchive(self):
		tar = tarfile.open(os.getcwd()+'/'+self.projectName+'.tar.gz','w:gz')
		for name in os.listdir(self.tempSaveFolder):
			tar.add(self.tempSaveFolder+'/'+name, arcname = self.projectName+'/'+name)
		tar.close()
		if self.outputDir != ".":
			shutil.move(os.getcwd()+'/'+self.projectName+'.tar.gz', self.outputDir+'/'+self.projectName+'.tar.gz')	
	
	def delete_query(self, name):
		query = 'The following temporary directory '+name+' will be permanently deleted, please confirm. yes (y)/ no (n) : y/n? '
		results = {'y':True, 'n':False}
		while query[0].lower() not in results:
		    query = raw_input(query)
		return results[query]

if __name__ == '__main__':
	user = passwd = typeF = None
	
	forgetype = FusionForge #temp
	verbose = 1
	
	useLocalServer = repository = trackers = mailings = phpWiki = mediaWiki = docs = frs = forums = news = tasks = False
	outputDir = "."
	
	(options, arguments) = getopt.getopt(sys.argv[1:], "R:TANFBDM:W:vlo:t:u:p:")
	for (arg, val) in options:
		if arg == '-R':
			repository = True
			scmAddress = val
		elif arg == '-T':
			trackers = True
		elif arg == '-M':
			mailings = True
			mailingAddress = val
		elif arg == '-W':
			if val == 'phpWiki':
				phpWiki = True
			elif val == 'mediaWiki':
				mediaWiki = True
		elif arg == '-t':
			typeF = val
		elif arg == '-u':
			user = val
		elif arg == '-p':
			passwd = val
		elif arg == '-v':
			verbose = val
		elif arg == '-l':
			useLocalServer = True
		elif arg == '-o':
			outputDir = val
		elif arg == '-A':
			trackers = docs = frs = forums = news = tasks = True 
		elif arg == '-N':
			news = True
		elif arg == '-F':
			frs = True	
		elif arg == '-B':
			forums = True
		elif arg == '-D':
			docs = True
		elif arg == '-K':
			tasks = True
	tempLink = arguments[len(arguments)-1]
	if tempLink.startswith("http://"):
		tempLink = tempLink[7:]
	elif tempLink.startswith("https://"):
		tempLink = tempLink[8:]
	try:
		segments = tempLink.split("/")
	except (ValueError, IndexError):
		print >>sys.stderr, "usage: %s [options...] host/project" % sys.argv[0]
		raise SystemExit, 1
	
	host = "/".join(segments[:-1])
	project = segments[-1]
	(user, passwd) = get_credentials(user, passwd, host)

	if user is None or passwd is None:
		print >>sys.stderr, "Error fetching authentication details for user %s at %s" % (user,host)
		print >>sys.stderr, "usage: %s [-hnrv?] [-i itemspec] -u username -p password -f forgetype host project" % sys.argv[0]
		raise SystemExit, 1
	try:
		bt = forgetype(host, project)
		bt.verbosity = verbose
		bt.login(user, passwd)
		tempDir = tempfile.mkdtemp()
		myForge = mainExtract(arguments[0], project, user, passwd, tempDir, outputDir, typeF, useLocalServer, repository, mailings, phpWiki, trackers, tasks, news, frs, forums, docs )
		if repository:
			myForge.setSCM(scmAddress)
		if mailings:
			myForge.setMailings(mailingAddress)
		if not useLocalServer:
			myPwd = "pwd"
			myForge.setSSH('root',myPwd )
		myForge.extract()
		myForge.makeArchive()
		
		if myForge.delete_query(tempDir):
			subprocess.call(['rm', '-rf', tempDir])
		
	except Exception, e:
		print e
		
		

