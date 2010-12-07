#!/usr/bin/env python
"""\
Regression-test driver for forgeplucker code.  

Recommended practice is to run the default test mode before committing code changes.

To initialize a reference version of the output that will serve for
later runs (for non-regression), use the --build mode after changing
the content of a test project.

Usage: regress-driver [action-option] [options] [site/project ...]
The actions are -r/--run     # Run the tests (default)
                -b/--build   # Build the tests
                --diffs      # Get the diffs from the last regression for each test
                --list       # List the tests and their handlers
                -e/--exclude # Reverse role of args (see below)
                --skip       # Skip failing tests
                -u           # Username(s)
                -v           # Verbose

If the -e/--exclude option is provided, run on all the tests not listed.
If no site/project arguments are provided do the action on all tests.

The -u option can be used to set a username for access to the remote site.
It may be a ':' separated list of usernames, if you use different 
ones on different sites

"""
import os, sys, getopt
from os import system

from forgeplucker import site_to_handler

testdir = 'test'
testcmd = '../bugplucker.py -n'

os.chdir(testdir)

def nametotest(name):
    return name.replace(':','/')

def testtoname(test):
    return test.replace('/',':')

def msg(msg):
    print >>sys.stderr, "%s: %s" % (sys.argv[0],msg)

def runtest(test, output, skip_failing = False):
    cmd = testcmd + ' -v ' + str(verbose) + ' '
    if username != None:
        cmd += '-u ' + username + ' '
    cmd += test + '>' + output
    if verbose >= 1:
        msg("running '%s'" % cmd)
    ret = system(cmd)
    if ret != 0:
        print >>sys.stderr, "Command ('"+cmd+"') failed!"
        if not skip_failing:
            raise SystemExit, 1
    return ret

def difftest(test):
    if verbose >= 1:
        msg("diffing %s" % test)
    return system("diff -u %s.chk %s.out" % (testtoname(test),testtoname(test)))

def keep(name):
    "Does this file/directory corespond to a test?"
    return not name.startswith('.') and name.endswith('.chk')

def getalltests():
    tests = []
    for _file in os.listdir('.'):
        if keep(_file):
            tests.append(nametotest(_file)[:-4])
    return tests

def setaction(setto):
    global action
    if action != None:
        print >>sys.stderr, "Error more than one action specified:", setto ,"and", action
        raise SystemExit, 1
    action = setto

if __name__ == '__main__':
    (options, arguments) = getopt.getopt(sys.argv[1:],
                                         "bdhlru:esv?",
                                         ["build",
                                          "diffs",
                                          "help",
                                          "list",
                                          "run",
                                          "exclude",
                                          "skip"])
    username = None
    action = None
    exclude = False
    verbose = 0
    skip_failing = None
    for (arg,val) in options:
        if arg == '-u':
            username = val
        elif arg in ('-r','--run'): #Option unnecesary, run is the default action
            setaction('run')
        elif arg in ('-b','--build'):
            setaction('build')
        elif arg in ('-d','--diffs'):
            setaction('diffs')
        elif arg in ('-l','--list'):
            setaction('list')
        elif arg in ('-h', '-?', '--help'):
            print __doc__
            raise SystemExit, 0
        elif arg in ('-e','--exclude'):
            exclude = True
        elif arg in ('-s','--skip'):
            skip_failing = True
        elif arg == '-v':
            verbose += 1
        else:
            print >>sys.stderr, "Unknown argument", arg
            raise SystemExit, 1
    if action == None:
        action = 'run'
    if exclude:
        tests = getalltests()
        for test in arguments:
            tests.remove(test)
    elif arguments == []:
        tests = getalltests()
    else:
        tests = arguments

    if action == 'run':
        for test in tests:            
            print >>sys.stderr, "Running", test
            if runtest(test, output=testtoname(test)+'.out', skip_failing=skip_failing) == 0:
                if difftest(test) == 0:
                    print >>sys.stderr, test, "succeeded"
    elif action == 'build':
        for test in tests:
            print >>sys.stderr, "Building", test
            runtest(test,output=testtoname(test)+'.chk')
    elif action == 'diffs':
        for test in tests:
            difftest(test)
    elif action == 'list':
        for test in tests:
            site = '/'.join(test.split('/')[:-1])
            cls = site_to_handler.get(site, None)
            if cls:
               cls = cls.__name__.split(".")[-1]
            print "%s -> %s" % (test,cls)

# End
