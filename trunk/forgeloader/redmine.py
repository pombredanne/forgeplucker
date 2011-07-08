import sys
import json
import httplib2
import urllib2, base64
import zipfile
import logging
logging.basicConfig(level=logging.DEBUG)

class Redmine:
    def __init__(self, username, password, url):
        self.username = username
        self.password = password
        self.url = url
        bs = base64.encodestring('%s:%s' % (username, password))
        self.bs = bs.replace('\n', '')
        
    def push(self, path, data_json):
        url = self.url+path
        request = urllib2.Request(url, data_json,
                                  {'content-type': 'application/json'})
        request.add_header("Authorization", "Basic %s" % self.bs)   
        return urllib2.urlopen(request)

    
class Loader:
    def __init__(self, jsonfile, username, password, url):
        self.log = logging.getLogger("pluck_loader")
        self.redmine = Redmine(username, password, url)
        self.data = json.loads(open(jsonfile).read())

        # load project info
        self.project()
        # load artefact 
        self.trackers()

        
    def project(self):
        data = self.data['project']
        self.project_name = data['project']
        self.log.info("Create project " + data['project'])
        js = {
            'project': {
                'identifier': self.project_name,
                'name': self.project_name, 
                'description' : data['description'].encode('iso8859-2')
                }
            }
        data_json = json.dumps(js)
        self.redmine.push('/projects.json', data_json)

        
    def trackers(self):
        self.log.info("trackers loading in progress")
        data = self.data['trackers'] 
        for tracker in data:
            for a in tracker['artifacts']:
                print '-'*80
                print 'SOURCE : ', a
                try: 
                    js = {
                        "issue": {
                            "project_id": self.project_name,
                            "subject": a['summary'],
                            "description" : a['description'],
                            "start_date" : a['date'],
                            "created_on" : a['date'],
                            "update_on" : a['date']
                            }
                        }
                    data_json = json.dumps(js)
                    print 'JSON : ', js 
                    self.redmine.push('/issues.json', data_json)
                except Exception as e:
                    print '?-'*40
                    print e
                    print a
                    print '?-'*40
                    

        
def import_zip(filepath):
    logging.info("Import in progress" + filepath)
    z = zipfile.ZipFile(filepath)
    jsonfile = z.extract('Plucker/JSON_Pluck.txt')
    Loader(jsonfile, 'admin', 'admin', 'http://durex/redmine')
    #return data


#file = "tests/data/coclico/Plucker/JSON_Pluck.txt"
#file = "tests/data/abilix/Plucker/JSON_Pluck.txt"

import_zip(sys.argv[1])

#if __name__ == '__main__':
#    import_json(sys.argv[1])
