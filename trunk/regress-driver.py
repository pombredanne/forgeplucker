#!/usr/bin/env python
"""\
Regression-test driver for forgeplucker code.  Run the default test mode
before committing code changes.  Use the --build mode after changing the
content of a test project.

Usage: regress-driver [action-option] [options] [site/project ...]
The actions are -r/--run     # Run the tests (default)
                -b/--build   # Build the tests
                --diffs      # Get the diffs from the last regression for each test
                --list       # List the tests and their handlers
If the -e/--exclude option is provided, run on all the tests not listed.
If no site/project arguments are provided do the action on all tests.

The -u option can be used to set a username for access to the remote site.
It may be a ':' separated list of usernames, if you use different 
ones on different sites

The -v option enables verbose progress messages
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

def runtest(test,output):
    cmd = testcmd + ' -v ' + str(verbose) + ' '
    if username != None:
        cmd += '-u ' + username + ' '
    cmd += test + '>' + output
    if verbose >= 1:
        print >>sys.stderr, "%s: running '%s'" % (sys.argv[0],cmd)
    if system(cmd) == 0:
        return
    else:
        print >>sys.stderr, "Command ('"+cmd+"') failed!"
        raise SystemExit, 1

def difftest(test):
    if verbose >= 1:
        print >>sys.stderr, "%s: diffing %s" % (sys.argv[0], test)
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
                                         "bdhlru:ev?",
                                         ["build",
                                          "diffs",
                                          "help",
                                          "list",
                                          "run",
                                          "exclude"])
    username = None
    action = None
    exclude = False
    verbose = 0
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
            runtest(test,output=testtoname(test)+'.out')
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
