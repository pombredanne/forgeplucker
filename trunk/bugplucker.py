#!/usr/bin/env python

"""
bugplucker.py -- extract bugtracker state from hosting sites.

usage: bugplucker.py [-hrv?] [-f type] [-u user] [-p password] site/project

State is dumped to standard output in JSON.

This code is Copyright (c) 2009 by Eric S. Raymond.  New BSD license applies.
For the terms of this license, see the file COPYING included with this
distribution.

Requires Python 2.6.
"""

import sys, os, re, time, calendar
from forgeplucker import *

if __name__ == '__main__':
    import getopt, json
    jdump = lambda x: json.dump(x, sys.stdout, sort_keys=True, indent=4)
    user = passwd = forgetype = None
    verbose = 0
    issue = None
    timeless = permissions = repositories = dump = False
    (options, arguments) = getopt.getopt(sys.argv[1:], "f:d:i:np:PSu:v:h?")
    for (arg, val) in options:
        if arg in ('-h', '-?'):
            print __doc__
            for cls in handler_classes:
                print "-" * 72
                print cls.__doc__
            raise SystemExit, 0
        elif arg == '-u':
            user = val
        elif arg == '-p':
            passwd = val
        elif arg == '-P':	# Not documented
            permissions = True
        elif arg == '-S':	# Not documented
            repositories = True
        elif arg == '-d':   # Not documented
            dump = True     # Dump contents of a specific page to standard output
            page = val
        elif arg == '-n':
            timeless = True
        elif arg == '-v':
            verbose = int(val)
        elif arg == '-i':
            issue = val
        elif arg == '-f':
            for cls in handler_classes:
                if val == cls.__name__:
                    forgetype = cls
                    break
            else:
                print >>sys.stderr, "%s: unknown forge type" % sys.argv[0]
                raise SystemExit, 1
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
    (user, passwd) = get_credentials(user, passwd, host)
    if user is None or passwd is None:
        print >>sys.stderr, "Error fetching authentication details for user %s at %s" % (user,host)
        print >>sys.stderr, "usage: %s [-hnrv?] [-i itemspec] -u username -p password -f forgetype host project" % sys.argv[0]
        raise SystemExit, 1
    try:
        bt = forgetype(host, project)
        bt.verbosity = verbose
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
        elif issue:
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
