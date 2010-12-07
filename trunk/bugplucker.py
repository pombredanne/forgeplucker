#!/usr/bin/env python

"""
bugplucker.py -- extract bugtracker state from hosting sites.

usage: bugplucker.py [-hv?] [-f type] [-u user] [-p password] [-d page] [-o format] [-PTSFDWBNK] "site/project"

  -h -? : displays this help message

  -f ForgeType : (optional) extract for the ForgeType forge - list of
	supported forges with '-f help'. If option is not provided, try to guess from the URL.

  -u user : user's login on the forge (if none provided, then use
	LOGNAME env var's value)

  -p password : provide user's connection password to the forge

  -n : timeless ?

  -P : extracts informations on users in the project

  -B : extract contents of the project forums

  -F : extract contents of the file release system of the project

  -T : extract contents of project trackers

  -i val : extract one particular issue ?

  -D : extract contents of the project's documents manager

  -W : extract contents of the project wiki

  -S : resporitories ?

  -v1 -v2 : verbose : v1 : all downloaded pages are displayed / v2 : page contents is displayed too

  -d page : dumps content of a specific page

  -N : News ?
  
  -K : Tasks ?
  
  -o format : (optional) choose a particular output format

State is dumped to standard output in JSON.

This code is Copyright (c) 2009 by Eric S. Raymond.  New BSD license applies.
For the terms of this license, see the file COPYING included with this
distribution.

Requires Python 2.6.
"""

import sys, os, re, time, calendar
from forgeplucker import *

def usage():
    print __doc__
    for cls in handler_classes:
        print "-" * 72
        print cls.__doc__
    raise SystemExit, 0

def notify(msg):
        sys.stderr.write(sys.argv[0] + ": __main__ : " + msg + "\n")

def error(msg, code):
    print >>sys.stderr, msg
    raise SystemExit, code

output_formats = ('default', 'coclico', 'oslccmv2json')

if __name__ == '__main__':
    import getopt, json
    jdump = lambda x: json.dump(x, sys.stdout, sort_keys=True, indent=4)
    user = passwd = forgetype = None
    verbose = 0
    issue = None

    xml = timeless = permissions = repositories = dump = phpWiki = trackers = getDocs = frs = forums = news = tasks = format = False

    # Start with command-line args parsing
    (options, arguments) = getopt.getopt(sys.argv[1:], "f:d:i:no:p:PTSFDWBNKru:v:h?", ["help",])

    for (arg, val) in options:
        if arg in ('-h', '-?', '--help'):	# help
            usage()
        elif arg == '-u':	# user logging in
            user = val
        elif arg == '-p':	# user password
            passwd = val
        elif arg == '-P':	# extract users and Permissions
            permissions = True
        elif arg == '-S':	# extract Repositories ? (TODO: fix comment)
            repositories = True
        elif arg == '-F':	# extract File Release System
            frs = True	
        elif arg == '-B':	# extract Forums
            forums = True			
        elif arg == '-d':   # Dump contents of a specific page to standard output
            dump = True     
            page = val
        elif arg == '-n':	# timeless ? (TODO: fix comment)
            timeless = True
        elif arg == '-T':	# extract trackers
            trackers = True
        elif arg == '-D':	# extract content of docman
            getDocs = True
        elif arg == '-v':	# verbosity
            verbose = int(val)
        elif arg == '-W': 	# extract wiki
            phpWiki = True
        elif arg == '-N':	# News ? (TODO: fix comment)
            news = True
        elif arg == '-K':	# Tasks ? (TODO: fix comment)
            tasks = True
        elif arg == '-i':	# extract one particular issue ? (TODO: fix comment)
            issue = val
        elif arg == '-f':	# forge type
            if val == "help" :	# list supported forges
                print "Supported forge types for option", arg, ":"
                for cls in handler_classes:
                    print cls.__name__, " ",
                print
                raise SystemExit, 0

            for cls in handler_classes:
                if val == cls.__name__:
                    forgetype = cls
                    break
            else:
                error("%s: unknown forge type" % sys.argv[0], 1)
        elif arg == '-o': #output format
            if val == "help" : #list supported output formats
                print "Supported output formats for option", arg, ":"
                for format in output_formats:
                    print format,
                print
                raise SystemExit, 0
            else :
                for format in output_formats:
                    if val == format:
                        break
                else:
                    error("%s: unknown output format type '%s' !" % (sys.argv[0], val), 1)

    if len(arguments) == 0 :
        usage()

    # Now try and parse args to find host and project
    # several formats are supported :
    # 1 URL : http[s]://hostname/projname
    # 2 args :
    #  - hostname (or http[s]://hostname[/]
    #  - projname
    if len(arguments) > 2:
        error("host/project not understood", 1)
    elif len(arguments) == 2:
        hostarg = arguments[0]
        projarg = arguments[1]
    else:
        # then we must split arg along the /
        hostarg = arguments[0]
        projarg = None

    # For convenience, http[s] prefixed URLs will work
    if arguments[0].startswith("http://"):
        hostarg = arguments[0][7:]
    elif arguments[0].startswith("https://"):
        hostarg = arguments[0][8:]

    # split host in chunks along the '/'
    try:
        segments = hostarg.split("/")
        # remove trailing slashes
        if segments[-1] == '':
            segments = segments[:-1]
    except (ValueError, IndexError):
        error("usage: %s [options...] host/project" % sys.argv[0], 1)

    # if projname already provided, don't try and extract things from the host
    if projarg :
        if len(segments) > 1 :
            error("incorrect hostname : %s" % hostarg, 1)
        host = segments[0]
        project = projarg
    else :
        # TODO Here, should pass hostarg to the forge so that it constructs the right thing, depending on forge type
        host = "/".join(segments[:-1])
        project = segments[-1]

    if verbose:
        notify("host: %s" % host)
        notify("project: %s" % project)

    # try and guess the forge type from the URL if no -f option provided
    if forgetype is None:
        forgetype = get_forgetype(host)

    # Try to login as user
    (user, passwd) = get_credentials(user, passwd, host)
    if user is None or passwd is None:
        error("Error fetching authentication details for user %s at %s" % (user,host) + "\n" 
              + "provide user logname and password with : %s [...] -u username -p password" % sys.argv[0], 1)

    # Now, do the real job
    try:
        # Instantiate handler for that forge to pluck the project
        bt = forgetype(host, project)

        bt.verbosity = verbose
        if verbose :
            notify("verbosity : %d" % verbose)

        bt.login(user, passwd)

        # This is the main data structure that will be dumped out at the end
        data = {}
        
        # extract common core
        projectData = bt.pluck_project_data()
        data["project"] = projectData
        
        # extract additional data
        if phpWiki: #Not clean
            bt.pluck_wiki()
        if permissions:
            perms = bt.pluck_permissions()
            roles = bt.pluck_roles()
            #roles = canonicalize(roles)
            data["users"] = perms
            data["roles"] = roles
        if getDocs:
            docs = bt.pluck_docman()
            data["docman"] = docs
        if frs:
            frs = bt.pluck_frs()
            data['frs'] = frs
        if forums:
            forums = bt.pluck_forums()
            data['forums'] = forums
        if news:
            news = bt.pluck_news()
            data['news'] = news
        if tasks:
            tasks = bt.pluck_tasksTrackers()
            data['tasks'] = tasks
        elif repositories:
            repo = bt.pluck_repository_urls()
            data["repository"]=repo
        elif dump:
            page = bt.fetch(page,"Page to dump")
            print page
        elif issue: #modified to not only parse one case (either permissions, repositories or trackers)
            (tracker, issueid) = issue.split(":")
            issue = bt.pluck_artifact(tracker, issueid)
            data["issue"]=issue
        else:
            if not format or format == 'default' :
                trackers = True

        if trackers:
            bugs = bt.pluck_trackers(timeless=timeless)
            data["trackers"] = bugs

        if not format or format == 'default' :
            if verbose: notify('Outputing with format "default"')
            if permissions:
                jdump(data["users"])
            elif repositories:
                jdump(data["repository"])
            if issue:
                jdump(data["issue"])
            else:
                jdump(data["trackers"])
        elif format == 'coclico':
            if verbose: notify('Outputing with format "coclico"')
            # dump data as JSON
            coclico_data = {}
            for key in data:
                if key != 'trackers':
                    coclico_data[key] = data[key]
                else:
                    coclico_data['trackers'] = []
                    for tracker in data['trackers']['trackers']:
                        coclico_tracker = data['trackers']['trackers'][tracker]
                        coclico_tracker['type'] = tracker
                        coclico_data['trackers'].append(coclico_tracker)

            jdump(coclico_data)
            print
        elif format == 'oslccmv2json' :
            if verbose: notify('Outputing with format "oslccmv2json"')
            output_oslccmv2json(data)
        else :
            error ("output format '%s' not yet implemented" % format, 1)

    except ForgePluckerException, e:
        print >>sys.stderr, e.msg
        raise SystemExit, 1
    except urllib2.HTTPError, e:
        print >>sys.stderr, "%s: %d - %s" % (e.url, e.code, e.msg)
        raise SystemExit, 1
    except KeyboardInterrupt:
        pass

# End
