# -*- coding: utf-8 -*-
"""
Output Handler class for OSLC-CM V2 in JSON

Contributed in the frame of the COCLICO project.

(C) 2010 Olivier Berger - Institut Telecom

The output format will use the PlanetForge ontology published at : 
  http://forge.projet-coclico.org/scm/loggerhead/wp2/documents/annotate/head%3A/ontology.html

References :
 - Example JSON OSLC-CM query results : http://open-services.net/bin/view/Main/CmSpecificationV2Samples?sortcol=table;table=up#Query_results_as_application_jso
 - "Open Services for Lifecycle Collaboration Change Management Specification Version 2.0" specification : http://open-services.net/bin/view/Main/CmSpecificationV2
 - OSLC Core Specification - JSON Representation Examples : http://open-services.net/bin/view/Main/OSLCCoreSpecJSONExamples
"""

import json, string, re

oslc_prefixes = { 'rdf' : 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                      'dcterms' : 'http://purl.org/dc/terms/',
                      'oslc': 'http://open-services.net/ns/core#',
                      'oslc_cm' : 'http://open-services.net/ns/cm#',
                      'forgeplucker' : 'http://planetforge.org/ns/forgeplucker_dump/',
                      'doap' : 'http://usefulinc.com/ns/doap#',
                      'sioc' : 'http://rdfs.org/sioc/ns#',
                      'foaf' : 'http://xmlns.com/foaf/0.1/',
                      'planetforge' : 'http://coclico-project.org/ontology/planetforge#'}

def username_to_resource(username, oslc_users):
    found = filter(lambda x: (x['foaf:accountName'] == username), oslc_users)
    if found :
        return found[0]['rdf:about']
    else :
        return username

oslc_mapping = {
                            # TODO : convert to real FOAF profile or lile
#                            'assigned_to': lambda x: {'predicate': 'dcterms:contributor', 'object': x},
                            'assigned_to': 'dcterms:contributor',
                            # TODO : convert to real FOAF profile or lile
#                            'submitter': lambda x: {'predicate': 'dcterms:creator', 'object': username_to_resource(comment['submitter'], oslc_users)},
                            'submitter': 'dcterms:creator',
                            #'Severity': None
                            #'Version': None
                            'id': 'dcterms:identifier',
                            #'attachments': []
                            #'Product': Software A
                            #'Operating System': Windows XP
                            #'Component': None
                            #'priority': 5 - Highest
                            'type': 'dcterms:type',
                            'description': 'dcterms:description',
                            'status': 'oslc_cm:status', 
                            #'URL': 
                            'date': 'dcterms:created',
                            #'Resolution': None
                            'summary': 'dcterms:title',
                            #'Hardware': All
                            
                            #'history': []
                            'closed_at': 'oslc_cm:closeDate'
                            }

def field_to_property(fieldname, shape, vocabulary):
    predicate = None
    if fieldname in oslc_mapping:
        predicate = oslc_mapping[fieldname]
    else :
        if fieldname in vocabulary:
            predicate = string.replace(string.capwords(fieldname), ' ', '')
            predicate = string.lower(predicate[:1])+predicate[1:]
            predicate = shape +'#'+ predicate
        else :
            predicate = fieldname
    return predicate
                        
def output_oslccmv2json_trackers(data, oslc_project, oslc_users):

    oslc_trackers = []

    if not ('trackers' in data) :
        return oslc_trackers

    data = data['trackers']

    # Treat all trackers
    trackers = data['trackers']

    for tracker in trackers:
        tracker = trackers[tracker]

        tracker_name = tracker['label']
    
        oslc_tracker = {'rdf:about' : tracker['url']}

        oslc_shape = {'rdf:type' : 'oslc:ResourceShape'}
        project_url = oslc_project['rdf:about']
        if not 'id' in tracker :
            tracker['id'] = re.search('atid=([0-9]*)', tracker['url']).group(1)
        if not 'URI' in tracker :
            tracker['URI'] = project_url+'/tracker/'+ tracker['id']
        oslc_shape['rdf:about'] = tracker['URI']+'/shape'

        vocabulary = tracker['vocabulary']
        for field in vocabulary:
            oslc_property = {'rdf:type' : 'oslc:Property'}
            fieldname = string.replace(string.capwords(field), ' ', '')
            fieldname = string.lower(fieldname[:1])+fieldname[1:]
            oslc_property['oslc:name'] = fieldname
            oslc_property['dcterms:title'] = field
            if 'multi' in vocabulary[field]:
                oslc_property['oslc:occurs'] = 'http://open-service.net/ns/core#Zero-or-many'
            else:
                oslc_property['oslc:occurs'] = 'http://open-service.net/ns/core#Zero-or-one'
            values = vocabulary[field]['values']
            if len(values):
                oslc_property['oslc:allowedValue'] = []
            for allowed_val in values:
                oslc_property['oslc:allowedValue'].append(allowed_val)

            if not 'oslc:property' in oslc_shape:
                oslc_shape['oslc:property'] = []
            oslc_shape['oslc:property'].append(oslc_property)
 
        if 'oslc:property' in oslc_shape :
            oslc_tracker['forgeplucker:vocabulary'] = oslc_shape
        
        oslc_artifacts = []
        
        # Treat all artifacts of a tracker
        artifacts =  tracker['artifacts']
        for artifact in artifacts :
            
            oslc_changerequest = {'rdf:type': 'http://open-services.net/ns/cm#ChangeRequest'}

            url = None
            if 'URL' in artifact:
                url = artifact['URL']
            if not url:
                url = tracker['URI'] + '/artifact/%d' % artifact['id']
                
            oslc_changerequest['rdf:about'] = url
            
            # check that artifact['class'] == 'ARTIFACT'
            
            # TODO : this should be dependent on forges probably
            # Mapping for plucked attributes :
            #  can be a litteral if no conversion is necessary
            #  or a lambda returning a dictionnary with new 'predicate' name and new converted 'object' value 

            # Treat all fields of an artifact
            for x in artifact :
                #try:
                    #print x, artifact[x]
                    if x in oslc_mapping:
                        mapping = oslc_mapping[x]
                        # mapping_type = type(mapping).__name__
                        # if mapping_type == 'function' :
                        #     transformed = mapping(artifact[x])
                        #     predicate = transformed['predicate']
                        #     object = transformed['object']
                        #     oslc_changerequest[predicate] = object
                        # elif mapping_type == 'str' :
                        value = artifact[x]
                        if mapping in ['dcterms:contributor', 'dcterms:creator'] :
#                            print 'creator:', mapping, value
                            value = username_to_resource(value, oslc_users)
                            if mapping == 'dcterms:contributor' and value == 'Nobody' :
                                continue
                        oslc_changerequest[mapping] = value
                        #else :
                        #    print >>sys.stderr, 'Incorrect mapping in oslc_mapping'
                        #    raise SystemExit, 1
                    else :
                        if x not in vocabulary:
                            if x in ['URL', 'class']:
                                continue
                            if x == 'attachments':
                                if len(artifact[x]):
                                    rdf_attachments = []
                                    attachments = artifact[x]
                                    for attachment in attachments:
                                        rdf_attachment = {'rdf:about': attachment['uri']}
                                        rdf_attachment['dcterms:creator'] = username_to_resource(attachment['by'], oslc_users)
                                        rdf_attachment['dcterms:created'] = attachment['date']
                                        rdf_attachment['sioc:name'] = attachment['filename']
                                        rdf_attachment['dcterms:identifier'] = attachment['id']
                                        rdf_attachment['forgeplucker:rawdump'] = attachment['url']
                                        rdf_attachments.append(rdf_attachment)
                                    oslc_changerequest['sioc:attachment'] = rdf_attachments
                                continue
                            if x == 'comments' :
                                if len(artifact[x]):
                                    oslc_discussion = { 'rdf:type': 'oslc:Discussion' }
                                    comments = artifact[x]
                                    oslc_discussion['oslc:comment'] = []
                                    for comment in comments :
                                        oslc_comment = {'rdf:type': 'oslc:Comment'}
                                        oslc_comment['dcterms:description'] = comment['comment']
                                        oslc_comment['dcterms:created'] = comment['date']
                                        oslc_comment['dcterms:creator'] = username_to_resource(comment['submitter'], oslc_users)
                                        oslc_discussion['oslc:comment'].append(oslc_comment)
                                    predicate = 'oslc:discussion'
                                    oslc_changerequest[predicate] = oslc_discussion
                                continue
                            if x == 'history':
                                if len(artifact[x]):
                                    
                                    rdf_history = {'rdf:type': 'forgeplucker:ResourceHistory'}
                                    rdf_changes = []
                                    
                                    for fact in artifact[x]:
                                        by = fact['by']
                                        date = fact['date']
                                        field = fact['field']
                                        old = fact['old']
                                        shape = tracker['URI']+'/shape'
                                        rdf_changes.append({'rdf:type': 'forgeplucker:PropertyChange',
                                                            'dcterms:contributor': username_to_resource(by, oslc_users),
                                                            'dcterms:modified': date,
                                                            'oslc:property' : field_to_property(field, shape, vocabulary),
                                                            'forgeplucker:oldValue': old})
                                    rdf_history['forgeplucker:changes'] = rdf_changes
                                    oslc_changerequest['forgeplucker:history'] = rdf_history
                                continue
                            predicate = x
                        else :
                            if not 'oslc:instanceShape' in  oslc_changerequest:
                                oslc_changerequest['oslc:instanceShape'] = oslc_shape['rdf:about']
                            prefix = 'oslc_shape'+tracker['id']
                            if not 'prefixes' in oslc_tracker:
                                oslc_tracker['prefixes'] = {}
                            oslc_tracker['prefixes'][prefix] = tracker['URI']+'/shape#'
                            predicate = string.replace(string.capwords(x), ' ', '')
                            predicate = string.lower(predicate[:1])+predicate[1:]
                            #predicate = tracker['URI']+'/shape#'+predicate
                            predicate = prefix+':'+predicate
                        oslc_changerequest[predicate] = artifact[x]
                        
                #except TypeError:
                #    print x,
                #print
                
                # treat submitter's target resource
                
                # treat assigned_to target resource
                
                # treat comments target resource
                
            oslc_artifacts.append(oslc_changerequest)

        oslc_tracker['oslc:results'] = oslc_artifacts

        oslc_tracker['rdf:type'] = oslc_prefixes['planetforge']+'Tracker'
        oslc_tracker['sioc:name'] = tracker_name
        
        oslc_trackers.append(oslc_tracker)

    return oslc_trackers    

def output_oslccmv2json(data):
    oslc_data = {}

    project = data['project']
    
    #the_class = project['class']
    # TODO check that the_class == 'PROJECT'
    #format_version = project['format_version']
    # TODO check that format_version == 1
    
    host = project['host']
    forge = 'https://' + host + '/'
    project_name = project['project']
    project_dump_url = 'http://' + host + '/forgeplucker_dump/oslccmv2json/' + project_name + '/' 
    
    # Initialize top-level OSLC JSON dump
    
    oslc_data['prefixes'] = oslc_prefixes
    oslc_data['rdf:about'] = project_dump_url
    oslc_data['rdf:type'] = 'http://planetforge.org/ns/forgeplucker_dump/project_dump#'
    
    oslc_project = {}
    oslc_project['rdf:about'] = project['URL']
    oslc_project['rdf:type'] = oslc_prefixes['planetforge']+'ForgeProject'
    oslc_project['doap:name'] = project_name
    if 'shortdesc' in project:
        oslc_project['doap:shortdesc'] = project['shortdesc']
    oslc_project['dcterms:description'] = project['description']
    oslc_project['dcterms:created'] = project['registered']
    oslc_project['doap:homepage'] = project['homepage']
    oslc_project['planetforge:hosted_by'] = forge

    # TODO : export roles
    oslc_roles = []
    i = 0
    roles_number = {}
    for role in data['roles']:
        oslc_role = {}
        oslc_role['rdf:type'] = oslc_prefixes['sioc']+'Role'
        oslc_role['sioc:name'] = role
        oslc_roles.append(oslc_role)
        roles_number[role] = i
        i += 1

    oslc_persons = []
    oslc_users = []

    for user in data['users']:
        oslc_user = {}
        oslc_person = {}

        user_data=data['users'][user]
        user_url = user_data['URL']
        oslc_user['rdf:about'] = user_url
        oslc_user['rdf:type'] = [oslc_prefixes['sioc']+'User', oslc_prefixes['foaf']+'OnlineAccount']
        oslc_user['foaf:accountName'] = user
        oslc_user['sioc:email'] = user_data['mail']
        
        oslc_person['rdf:about'] = user_url + '#me'
        oslc_person['rdf:type'] = oslc_prefixes['foaf']+'Person'
        oslc_person['foaf:name'] = user_data['real_name']
        oslc_person['foaf:holdsAccount'] = user_url

        i = roles_number[user_data['role']]
        oslc_role = oslc_roles[i]
        if not 'sioc:function_of' in oslc_role:
            oslc_role['sioc:function_of'] = []
        oslc_role['sioc:function_of'].append(user_url)

        oslc_persons.append(oslc_person)
        oslc_users.append(oslc_user)

    oslc_data['forgeplucker:persons'] = oslc_persons
    oslc_data['forgeplucker:users'] = oslc_users

    oslc_project['sioc:scope_of'] = oslc_roles
    
    oslc_trackers = output_oslccmv2json_trackers(data, oslc_project, oslc_users)

    project_trackers=[]
    if oslc_trackers:
        oslc_data['forgeplucker:trackers'] = oslc_trackers
        for tracker in oslc_trackers:
            project_trackers.append(tracker['rdf:about'])
        oslc_project['sioc:has_space'] = project_trackers
    else :
        if 'trackers_list' in project:
            if not 'sioc:has_space' in oslc_project:
                oslc_project['sioc:has_space'] = []
            for t in project['trackers_list']:
                oslc_project['sioc:has_space'].append(t)
        
    if 'public_forums' in project:
        if not 'sioc:has_space' in oslc_project:
            oslc_project['sioc:has_space'] = []
        for f in project['public_forums']:
            oslc_project['sioc:has_space'].append(f)
    if 'docman' in project:
        if not 'sioc:has_space' in oslc_project:
            oslc_project['sioc:has_space'] = []
        oslc_project['sioc:has_space'].append(project['docman'])
    if 'mailing_lists' in project:
        if not 'sioc:has_space' in oslc_project:
            oslc_project['sioc:has_space'] = []
        for l in project['mailing_lists']:
            oslc_project['sioc:has_space'].append(l)
    if 'task_trackers' in project:
        if not 'sioc:has_space' in oslc_project:
            oslc_project['sioc:has_space'] = []
        for l in project['task_trackers']:
            oslc_project['sioc:has_space'].append(l)
    if 'scm_type' in project:
        if not 'sioc:has_space' in oslc_project:
            oslc_project['sioc:has_space'] = []
        oslc_project['sioc:has_space'].append(project['scm'])
    if 'news' in project:
        if not 'sioc:has_space' in oslc_project:
            oslc_project['sioc:has_space'] = []
        oslc_project['sioc:has_space'].append(project['news'])
    if 'frs' in project:
        if not 'sioc:has_space' in oslc_project:
            oslc_project['sioc:has_space'] = []
        oslc_project['sioc:has_space'].append(project['frs'])

    oslc_data['forgeplucker:project'] = oslc_project

    tools = project['tools']
    oslc_tools = [{'rdf:type': 'planetforge:ForgeService',
                   'rdf:about': forge}]
    for t in tools :
        oslc_tool = {'rdf:about': t}
        tool = tools[t]
        if 'type' in tool:
            ttype = tool['type']
            oslc_tool['rdf:type'] = 'planetforge:'+ttype
        if 'provided_by' in tool:
            oslc_tool['planetforge:provided_by'] = tool['provided_by']
        if 'name' in tool:
            oslc_tool['planetforge:name'] = tool['name']
        # TODO : version of tools
        oslc_tools.append(oslc_tool)
            
    oslc_data['forgeplucker:tools'] = oslc_tools

    # pretty-print 
    print json.dumps(oslc_data, sort_keys=True, indent=4)
