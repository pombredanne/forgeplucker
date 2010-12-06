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

def output_oslccmv2json(data):
    oslc_data = {}
    oslc_prefixes = { 'rdf' : 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                      'dcterms' : 'http://purl.org/dc/terms/',
                      'oslc': 'http://open-services.net/ns/core#',
                      'oslc_cm' : 'http://open-services.net/ns/cm#',
                      'forgeplucker' : 'http://planetforge.org/ns/forgeplucker_dump/'}

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
    
    oslc_trackers = []
    
    # Treat all trackers
    trackers = data['trackers']
    for tracker in trackers:
        tracker_name = tracker['label']
    
        oslc_tracker = {'rdf:about' : tracker['url']}
        
        oslc_artifacts = []
        
        # Treat all artifacts of a tracker
        artifacts =  tracker['artifacts']
        for artifact in artifacts :
            
            oslc_changerequest = {'rdf:type': 'http://open-services.net/ns/cm#ChangeRequest'}
            
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
                            #'comments': 'oslc:discussion',
                            
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
                            'status_id': 'oslc_cm:status', 
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
                    print x, artifact[x]
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
    
    oslc_data['forgeplucker:trackers'] = oslc_trackers
    
    # pretty-print 
    print json.dumps(oslc_data, sort_keys=True, indent=4)
