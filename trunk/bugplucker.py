#!/usr/bin/env python

"""
bugplucker.py -- extract bugtracker state from hosting sites.

usage: bugplucker.py [-hrv?] [-f type] [-u user] [-p password] site/project

  -h -? : displays this help message

  -f ForgeType : (optional) extract for the ForgeType forge - list of
	supported forges with '-f help'. If option is not provided, try to guess from the URL.

  -u user : user's login on the forge (if none provided, then use
	LOGNAME env var's value)

  -p password : provide user's connection password to the forge

  -n : timeless ?

  -P : extracts informations on users in the project

  -i val : extract one particular issue ?

  -S : resporitories ?

  -v1 -v2 : verbose : v1 : all downloaded pages are displayed / v2 : page contents is displayed too

  -d page : dumps content of a specific page

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

if __name__ == '__main__':
    import getopt, json
    jdump = lambda x: json.dump(x, sys.stdout, sort_keys=True, indent=4)
    user = passwd = forgetype = None
    verbose = 0
    issue = None
    timeless = permissions = repositories = dump = False
    (options, arguments) = getopt.getopt(sys.argv[1:], "f:d:i:np:PSu:v:h?", ["help",])
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
        elif arg == '-d':   # Dump contents of a specific page to standard output
            dump = True     
            page = val
        elif arg == '-n':	# timeless ? (TODO: fix comment)
            timeless = True
        elif arg == '-v':	# verbosity
            verbose = int(val)
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
    # For convenience, so pasting URLs will work
    if arguments[0].startswith("http://"):
        arguments[0] = arguments[0][7:]
    if arguments[0].startswith("https://"):
        arguments[0] = arguments[0][8:]
    try:
        segments = arguments[0].split("/")
    except (ValueError, IndexError):
        print >>sys.stderr, "usage: %s [options...] host/project" % sys.argv[0]
        raise SystemExit, 1
    host = "/".join(segments[:-1])
    project = segments[-1]
    if forgetype is None:
        forgetype = get_forgetype(host)

    # Try to login as user
    (user, passwd) = get_credentials(user, passwd, host)
    if user is None or passwd is None:
        error("Error fetching authentication details for user %s at %s" % (user,host) + "\n" 
              + "provide user logname and password with : %s [...] -u username -p password" % sys.argv[0], 1)
    try:
        # Instantiate handler for that forge to pluck the project
        bt = forgetype(host, project)

        bt.verbosity = verbose
        if verbose :
            notify("verbosity : %d" % verbose)

        bt.login(user, passwd)
        if permissions:
            perms = bt.pluck_permissions()
            jdump(perms)
        elif repositories:
            perms = bt.pluck_repository_urls()
            jdump(perms)
        elif dump:
            page = bt.fetch(page,"Page to dump")
            print page
        elif issue: #modified to not only parse one case (either permissions, repositories or trackers)
            (tracker, issueid) = issue.split(":")
            issue = bt.pluck_artifact(tracker, issueid)
            jdump(issue)
        else:
            bugs = bt.pluck_trackers(timeless=timeless)
            jdump(bugs)
    except ForgePluckerException, e:
        print >>sys.stderr, e.msg
        raise SystemExit, 1
    except urllib2.HTTPError, e:
        print >>sys.stderr, "%s: %d - %s" % (e.url, e.code, e.msg)
        raise SystemExit, 1
    except KeyboardInterrupt:
        pass

# End
