# -*- coding: utf-8 -*-
"""
Output Handler class for OSLC-CM V2 in JSON

Contributed in the frame of the COCLICO project.

(C) 2010 Olivier Berger - Institut Telecom

References :
 - Example JSON OSLC-CM query results : http://open-services.net/bin/view/Main/CmSpecificationV2Samples?sortcol=table;table=up#Query_results_as_application_jso
 - "Open Services for Lifecycle Collaboration Change Management Specification Version 2.0" specification : http://open-services.net/bin/view/Main/CmSpecificationV2
 - OSLC Core Specification - JSON Representation Examples : http://open-services.net/bin/view/Main/OSLCCoreSpecJSONExamples
"""

import json

def output_oslccmv2json_trackers(data):

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
        
        oslc_artifacts = []
        
        # Treat all artifacts of a tracker
        artifacts =  tracker['artifacts']
        for artifact in artifacts :
            
            oslc_changerequest = {'rdf:type': 'http://open-services.net/ns/cm#ChangeRequest'}

            url = None
            if 'URL' in artifact:
                url = artifact['URL']
            if not url:
                url = tracker['url'] + '/%d' % artifact['id']
                
            oslc_changerequest['rdf:about'] = url
            
            # check that artifact['class'] == 'ARTIFACT'
            
            # TODO : this should be dependent on forges probably
            # Mapping for plucked attributes :
            #  can be a litteral if no conversion is necessary
            #  or a lambda returning a dictionnary with new 'predicate' name and new converted 'object' value 
            oslc_mapping = {
                            #'comments': 'oslc:discussion' TODO
                            
                            # TODO : convert to real FOAF profile or lile
                            'assigned_to': lambda x: {'predicate': 'dcterms:contributor', 'object': x},
                            # TODO : convert to real FOAF profile or lile
                            'submitter': lambda x: {'predicate': 'dcterms:creator', 'object': x},
                            
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
                            }

            # Treat all fields of an artifact
            for x in artifact :
                #try:
                    #print x, artifact[x]
                    if x in oslc_mapping:
                        mapping = oslc_mapping[x]
                        mapping_type = type(mapping).__name__
                        if mapping_type == 'function' :
                            transformed = mapping(artifact[x])
                            predicate = transformed['predicate']
                            object = transformed['object']
                            oslc_changerequest[predicate] = object
                        elif mapping_type == 'str' :
                            oslc_changerequest[mapping] = artifact[x]
                        else :
                            print >>sys.stderr, 'Incorrect mapping in oslc_mapping'
                            raise SystemExit, 1
                    else :
                        predicate = 'forgeplucker:' + x
                        oslc_changerequest[predicate] = artifact[x]
                        
                #except TypeError:
                #    print x,
                #print
                
                # treat submitter's target resource
                
                # treat assigned_to target resource
                
                # treat comments target resource
                
            oslc_artifacts.append(oslc_changerequest)

        oslc_tracker['oslc:results'] = oslc_artifacts
        
        oslc_trackers.append(oslc_tracker)

    return oslc_trackers    

def output_oslccmv2json(data):
    oslc_data = {}
    oslc_prefixes = { 'rdf' : 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                      'dcterms' : 'http://purl.org/dc/terms/',
                      'oslc': 'http://open-services.net/ns/core#',
                      'oslc_cm' : 'http://open-services.net/ns/cm#',
                      'forgeplucker' : 'http://planetforge.org/ns/forgeplucker_dump/',
                      'doap' : 'http://usefulinc.com/ns/doap#',
                      'sioc' : 'http://rdfs.org/sioc/ns#',
                      'foaf' : 'http://xmlns.com/foaf/0.1/'}

    project = data['project']
    
    #the_class = project['class']
    # TODO check that the_class == 'PROJECT'
    #format_version = project['format_version']
    # TODO check that format_version == 1
    
    host = project['host']
    project_name = project['project']
    project_dump_url = 'http://' + host + '/forgeplucker_dump/oslccmv2json/' + project_name + '/' 
    
    # Initialize top-level OSLC JSON dump
    
    oslc_data['prefixes'] = oslc_prefixes
    oslc_data['rdf:about'] = project_dump_url
    oslc_data['rdf:type'] = 'http://planetforge.org/ns/forgeplucker_dump/project_dump#'
    
    oslc_project = {}
    oslc_project['rdf:about'] = project['URL']
    oslc_project['doap:name'] = project_name
    oslc_project['dcterms:description'] = project['description']
    oslc_project['dcterms:created'] = project['registered']
    oslc_project['doap:homepage'] = project['homepage']


    oslc_persons = []
    oslc_admin_users = []
    oslc_regular_users = []
#    print data['users']
    for user in data['users']:
        oslc_user = {}
        oslc_person = {}

        user_data=data['users'][user]
        oslc_user['rdf:about'] = user_data['URL']
        oslc_user['rdf:type'] = [oslc_prefixes['sioc']+'User', oslc_prefixes['foaf']+'OnlineAccount']
        oslc_user['foaf:accountName'] = user
        oslc_user['sioc:email'] = user_data['mail']
        
        oslc_person['rdf:about'] = user_data['URL'] + '#me'
        oslc_person['rdf:type'] = oslc_prefixes['foaf']+'Person'
        oslc_person['foaf:name'] = user_data['real_name']
        oslc_person['foaf:holdsAccount'] = user_data['URL']

        if user_data['role'] == 'Admin' :
            oslc_admin_users.append(oslc_user)
        else:
            oslc_regular_users.append(oslc_user)
        oslc_persons.append(oslc_person)

    oslc_project['sioc:scope_of'] = []
    oslc_data['forgeplucker:users'] = []
    if oslc_admin_users:
        scope_of_admin = {}
        scope_of_admin['rdf:type'] = oslc_prefixes['sioc']+'Role'
        scope_of_admin['sioc:name'] = "project_admins"
        scope_of_admin['sioc:function_of'] = []
        for u in oslc_admin_users:
            scope_of_admin['sioc:function_of'].append(u['rdf:about'])
            oslc_data['forgeplucker:users'].append(u)
        oslc_project['sioc:scope_of'].append(scope_of_admin)
    if oslc_regular_users:
        scope_of_regular = {}
        scope_of_regular['rdf:type'] = oslc_prefixes['sioc']+'Role'
        scope_of_regular['sioc:name'] = "project_developers"
        scope_of_regular['sioc:function_of'] = []
        for u in oslc_regular_users:
            scope_of_regular['sioc:function_of'].append(u['rdf:about'])
            oslc_data['forgeplucker:users'].append(u)
        oslc_project['sioc:scope_of'].append(scope_of_regular)

    oslc_data['forgeplucker:persons'] = oslc_persons
    
    oslc_data['forgeplucker:project'] = oslc_project

    oslc_trackers = output_oslccmv2json_trackers(data)
    if oslc_trackers:
        oslc_data['forgeplucker:trackers'] = output_oslccmv2json_trackers(data)
    
    # pretty-print 
    print json.dumps(oslc_data, sort_keys=True, indent=4)
