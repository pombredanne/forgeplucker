#!/usr/bin/env python
"""\
Regression-test driver for forgeplucker code.  Run the default test mode
before committing code changes.  Use the --build mode after changing the
content of a test project.

Usage:
    regress-driver.py                       # Run all regression tests
    regress-driver.py --run site/project    # Run an individual regression test
    regress-driver.py --build site/project  # Rebuild individual .chk file
    regress-driver.py --rebuild-all         # Rebuild all .chk files
    regress-driver.py --diffs               # Show diffs from last regression
    regress-driver.py --help                # Display this help

The -u option can be used to set a username for access to the remote site.
It may be a ':' seperated list of usernames, if you use different 
ones on different sites

The -v option enables verbose progress messages.
"""
import sys, os, getopt
from forgeplucker import site_to_handler

testroot = "test"
testcmd = "./bugplucker.py"

def ignore(filename):
    "Predicare for ignoring version-=control directories."
    return filename.startswith(".")

def walk_tests():
    for site in os.listdir(testroot):
        if ignore(site):
            continue
        for project in os.listdir(os.path.join(testroot, site)):
            if ignore(project):
                continue
            yield ((site, project), os.path.join(testroot, site, project))

if __name__ == '__main__':
    (options, arguments) = getopt.getopt(sys.argv[1:],
                                         "bdhlru:v?",
                                         ["rebuild-all",
                                          "build",
                                          "diffs",
                                          "help",
                                          "list",
                                          "run"])
    rebuild_all = False
    build = False
    diffs = False
    listall = False
    run = False
    username = os.getenv("LOGNAME")
    verbose = 0
    for (arg, val) in options:
        if arg == '--rebuild-all':
            rebuild_all = True
        elif arg in ("-b", "--build"):
            if arguments:
                build = True
            else:
                print >>sys.stderr, "%s: -b/--build requires argument" \
                      % sys.argv[0]
                raise SystemExit, 1
        elif arg in ("-d", "--diffs"):
            diffs = True
        elif arg == '-u':
            username = val
        elif arg == '-v':
            verbose += 1
        elif arg in ('-h', '-?', '--help'):
            print __doc__
            raise SystemExit, 0
        elif arg in ("-l", "--list"):
            listall = True
        elif arg in ("-r", "--run"):
            if arguments:
                run = True
            else:
                print >>sys.stderr, "%s: -r/--run requires argument" \
                      % sys.argv[0]
                raise SystemExit, 1



    # Compute stem for use in naming files
    if '.' in testcmd:
        (stem, dummy) = os.path.splitext(testcmd)
    else:
        stem = testcmd
    if stem.startswith("./"):
        stem = stem[2:]

    # Argument is always parsed the same way
    if arguments:
        try:
            (site, project) = arguments[0].split("/")
            path = os.path.join(testroot, site, project)
            basecmd = testcmd +" -n -u "+ username +" "+ site +"/"+ project +" >"+ path +"/"+ stem
        except (ValueError, IndexError):
            print >>sys.stderr, "usage: %s [options...] host/project" % sys.argv[0]
            raise SystemExit, 1
        if not os.path.exists(path):
            print >>sys.stderr, "%s: no such test %s/%s" \
                  % (sys.argv[0], site, project)
            raise SystemExit, 1
        if build:
            # Rebuild an individual test
            cmd = basecmd + ".chk"
            if verbose:
                print >>sys.stderr, "%s: running '%s'" % (sys.argv[0], cmd)
            status = os.system(cmd)
        elif run:
            # Run an individual test
            # FIXME remove code duplication with running all tests
            cmd = basecmd + ".out"
            if verbose:
                print >>sys.stderr, "%s: running '%s'" % (sys.argv[0], cmd)
            status = os.system(cmd)
            if status:
                print >>sys.stderr, "%s: '%s' FAILED." % (sys.argv[0], cmd)
                raise SystemExit, 1
            status = os.system("diff -u %s/%s.chk %s/%s.out" \
                               % (path, stem, path, stem))
            if status == 0:
                print >>sys.stderr, "%s: %s regression test on %s/%s succeeded." \
                      % (sys.argv[0], testcmd, site, project)
    # Run operation on all tests
    else:
        if rebuild_all:
            # Rebuild all tests
            for ((site, project), path) in walk_tests():
                print "Building %s/%s test..." % (site, project)
                basecmd = testcmd +" -n -u "+ username +" "+ site +"/"+ project +" >"+ path +"/"+ stem 
                cmd = basecmd + ".chk"
                if verbose:
                    print >>sys.stderr, "%s: running '%s'" % (sys.argv[0], cmd)
                status = os.system(cmd)
                if status:
                    print >>sys.stderr, "%s: '%s' FAILED." % (sys.argv[0], cmd)
                    raise SystemExit, 1
            print "Done"
        elif diffs:
            for ((site, project), path) in walk_tests():
                if verbose:
                    print "%s: diffing %s/%s" % (sys.argv[0], site, project)
                status = os.system("diff -u %s/%s.chk %s/%s.out" \
                                   % (path, stem, path, stem))
        elif listall:
            for ((site, project), path) in walk_tests():
                cls = site_to_handler.get(site, None)
                if cls:
                    cls = cls.__name__.split(".")[-1]
                print "%s/%s -> %s" % (site, project, cls)
        else:
            # Run all regression tests
            # FIXME remove code duplication with running a single test
            for ((site, project), path) in walk_tests():
                print "Running %s/%s test..." % (site, project)
                basecmd = testcmd +" -n -u "+ username +" "+ site +"/"+ project +" >"+ path +"/"+ stem
                cmd = basecmd + ".out"
                if verbose:
                    print >>sys.stderr, "%s: running '%s'" % (sys.argv[0], cmd)
                status = os.system(cmd)
                if status:
                    print >>sys.stderr, "%s: '%s' FAILED." % (sys.argv[0], cmd)
                    raise SystemExit, 1
                status = os.system("diff -u %s/%s.chk %s/%s.out" \
                                   % (path, stem, path, stem))
                if status == 0:
                    print >>sys.stderr, "%s: %s regression test on %s/%s succeeded." \
                          % (sys.argv[0], testcmd, site, project)
            print "Done"
    raise SystemExit, 0

# End
