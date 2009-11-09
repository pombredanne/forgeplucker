#!/usr/bin/env python
"""
Regression-test driver for forgeplucker code.

Usage:
    regress-driver.py                       # Run all regression tests
    regress-driver.py --build site/project  # Rebuild individual .chk file
    regress-driver.py --build-all           # Rebuild all .chk files
    regress-deiver.py --diffs               # Show diffs from last regression

The -v option enables verbose progress messages.
"""
import sys, os, getopt

testroot = "test"
testcmd = "bugplucker.py"

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
    (options, arguments) = getopt.getopt(sys.argv[1:], "bdv", ["build-all", "build", "diffs"])
    rebuild_all = False
    build = False
    diffs = False
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
        elif arg == '-v':
            verbose += 1

    # Compute stem for use in naming files
    if '.' in testcmd:
        (stem, dummy) = os.path.splitext(testcmd)
    else:
        stem = testcmd

    # Argument is always parsed the same way
    if arguments:
        try:
            (site, project) = arguments[0].split("/")
            path = os.path.join(testroot, site, project)
            basecmd = testcmd +" -n "+ site +"/"+ project +" >"+ path +"/"+ stem
        except (ValueError, IndexError):
            print >>sys.stderr, "usage: %s [options...] host/project" % sys.argv[0]
            raise SystemExit, 1
        if build:
            # Rebuild an individual test
            if not os.path.exists(path):
                print >>sys.stderr, "%s: no such test %s/%s" \
                      % (sys.argv[0], site, project)
                raise SystemExit, 1
            else:
                cmd = basecmd + ".chk"
                if verbose:
                    print >>sys.stderr, "%s: running '%s'" % (sys.argv[0], cmd)
                status = os.system(cmd)
    # Run operation on all tests
    else:
        if rebuild_all:
            # Rebuild all tests
            for ((site, project), path) in walk_tests():
                print "Building %s/%s test..." % (site, project)
                basecmd = testcmd +" -n "+ site +"/"+ project +" >"+ path
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
        else:
            # Run all regression tests
            for ((site, project), path) in walk_tests():
                print "Running %s/%s test..." % (site, project)
                basecmd = testcmd +" -n "+ site +"/"+ project +" >"+ path +"/"+ stem
                cmd = basecmd + ".out"
                if verbose:
                    print >>sys.stderr, "%s: running '%s'" % (sys.argv[0], cmd)
                status = os.system(cmd)
                if status:
                    print >>sys.stderr, "'%s' FAILED." % (sys.argv[0], cmd)
                    raise SystemExit, 1
                status = os.system("diff -u %s/%s.chk %s/%s.out" \
                                   % (path, stem, path, stem))
                if status == 0:
                    print >>sys.stderr, "%s: %s regression test on %s/%s succeeded." \
                          % (sys.argv[0], testcmd, site, project)
            print "Done"
    raise SystemExit, 0

# End