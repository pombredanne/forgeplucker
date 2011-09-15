import sys
import json
import pprint 
import urllib2, base64
import zipfile
import logging
logging.basicConfig(level=logging.DEBUG, filename='output.log')

class Redmine:
    def __init__(self, username, password, url):
        self.username = username
        self.password = password
        self.url = url
        bs = base64.encodestring('%s:%s' % (username, password))
        self.bs = bs.replace('\n', '')
        self.log = logging.getLogger("redmine")
                        
        # dictonnary to translate data         
        self.dict = {
            'status' : { 
                'New' : 1,
                'Open' : 2,
                'RESOLVED' : 3,
                'Feedback' : 4,
                'Closed' : 5,
                'Rejected' : 6
                }
        }
        self.users = {}
        
    def tr(self, a, key):
        try :
            return self.dict[key][a[key]]
        except Exception as e :
            self.log.error
            (str(e))
            return ''
            
    def uid(self, realname):
        return self.users[realname]['id']
        
    def push(self, path, data_json, method = 'POST'):
        url = self.url + path
        request = urllib2.Request(url, data_json,
                                  {'content-type': 'application/json'})
        request.add_header("Authorization", "Basic %s" % self.bs)
        request.get_method = lambda: method
        try:
            response = urllib2.urlopen(request)
            return json.load(response)
        except urllib2.HTTPError as e:
            print e
            print data_json
            print
            self.log.error(str(e) + ' '+ str(data_json))

    
class Loader:
    def __init__(self, jsonfile, username, password, url):
        self.log = logging.getLogger("loader")
        self.redmine = Redmine(username, password, url)
        self.data = json.loads(open(jsonfile).read())

        
    def project(self):
        data = self.data['project']
        self.project_name = data['project']
        self.log.info("Create project %s" % data['project'])
        js = {
            'project': {
                'identifier': self.project_name,
                'name': self.project_name, 
                'description' : data['description'].encode('iso8859-2')
                }
            }
        data_json = json.dumps(js)
        try: 
            return self.redmine.push('/projects.json', data_json)
        except urllib2.HTTPError as e:
            self.log.error("Project already exist ? \n %s" %e )


    def users(self):    
        """
        "users": {
            "admin": {
                "mail": "help.et.gforge@inria.fr", 
                "real_name": "Local GForge Admin ", 
                "role": "Administrateur"
        }, 

        """
        self.log.info("users loading in progress")
        for login, values in self.data['users'].items() : 
            self.log.debug(str(values))
            realname = values['real_name']
            lastname = realname.split(' ')[-1]
            if len(lastname) == 0 :
                    lastname = realname
            js = {
                "user": {
                "login": login,
                "firstname" : ' '.join(realname.split(' ')[:-1]),
                "lastname" : lastname,
                "mail": values['mail'], 
                }
            }
            data_json = json.dumps(js)
            try:    
                user = self.redmine.push('/users.json', data_json)
                self.redmine.users[realname] = user 
                self.log.info('push user \n' + str(user)) 
            except Exception as e:
                self.log.error(str((e, js)))
    
    def trackers(self):
        self.log.info("trackers loading in progress")
        data = self.data['trackers'] 
        for tracker in data:
            for a in tracker['artifacts']:
                iid = self.create_issue(a)                       
                self.update_issue(iid, a)   
                self.update_issue_assigned_to(iid, a)   
                    
    def create_issue(self, a):
        js = {
            "issue": {
            "project_id": self.project_name,
            "subject": a.get('summary', 'None'),
            "description" : a.get('description'),
            "start_date" : a.get('date'),
            "created_on" : a.get('date'),
            "update_on" : a.get('date')
            }
        }
        data_json = json.dumps(js)        
        issue = self.redmine.push('/issues.json', data_json)
        return issue['issue']['id']

    def update_issue(self, iid, a):
        js = {
            "issue": {
                "status_id" : self.redmine.tr(a, 'status')
            }
        }
        data_json = json.dumps(js)
        self.log.debug('update issue \n %s', js)        
        try:
            self.redmine.push('/issues/%d.json' % iid, data_json, method = 'PUT')
        except Exception as e:            
            self.log.error(str(e))
            
    def update_issue_assigned_to(self, iid, a):
        self.log.debug('update issue assigned_to \n %s' % a)        
        self.log.debug('update issue assigned_to \n %s' % a['assigned_to'])        
        print 'update issue %s assigned_to %s' % (iid, a['assigned_to'])        

        realname = a['assigned_to']
        try: 

            uid = self.redmine.users[realname]['user']['id']
            js = {
                "issue": {
                    "assigned_to_id" : uid
                }
            }
            data_json = json.dumps(js)
            self.log.debug('update issue assigned_to \n %s', js)        
            self.redmine.push('/issues/%d.json' % iid, data_json, method = 'PUT')
        except Exception as e :
            print e
            self.log.error(str(e))
    

def import_zip(filepath):
    user = 'admin'
    pwd = 'admin'    
    url = 'http://durex/redmine'

    logging.info("Import in progress" + filepath)
    z = zipfile.ZipFile(filepath)
    jsonfile = z.extract('Plucker/JSON_Pluck.txt')
    
    loader = Loader(jsonfile, user, pwd, url)

    project = loader.project()
    loader.users()        

    print "Project created"
    print "now add user \"%s\"  as manager of the project %s\n" % (user, project['project']['name'])
    print "add other users with all permissions to the project"
    msg = "reply [yes], when it's done\n"
        
    chmod_done = 'no'
    while chmod_done != 'yes' :
        chmod_done = raw_input(msg)

    loader.trackers()        
     

if __name__ == '__main__':








    import_zip(sys.argv[1])