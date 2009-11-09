#!/usr/bin/env python
"""
Regression-test driver for forgeplucker code.
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
    (options, arguments) = getopt.getopt(sys.argv[1:], "b")
    build = False
    for (arg, val) in options:
        if arg == '-b':
            build = True

    # Compute stem for use in naming files
    if '.' in testcmd:
        (stem, dummy) = os.path.splitext(testcmd)
    else:
        stem = testcmd

    if build:
        for ((site, project), path) in walk_tests():
            print "Building %s/%s test..." % (site, project)
            cmd = testcmd +" "+ site +"/"+ project +" >"+ path +"/"+ stem +".chk"
            status = os.system(cmd)
            if status:
                print >>sys.stderr, "'%s' FAILED." % cmd
                raise SystemExit, 1
        print "Done"

    raise SystemExit, 0

# End
