#!/usr/bin/env python

"""
bugplucker.py -- extract bugtracker state from hosting sites.

usage: bugplucker.py [-hrv?] [-f type] [-u user] [-p password] site/project

State is dumped to standard output in JSON or XML.

This code is Copyright (c) 2009 by Eric S. Raymond.  New BSD license applies.
For the terms of this license, see the file COPYING included with this
distribution.

Requires Python 2.6.
"""

import sys, os, re, time, calendar
from forgeplucker import *

def canonicalize(issues):
    "Canonicalize issue data."
    name_mappings = {
        "bug_group_id": "group",
        "artifact_group_id": "group", #SourceForge
        "category_id": "category",
        "category_version_id": "category_version",	# Savane
        #'comment_type_id', 'comment_type',		# Savane
        "fix_release_id": "fix_release_version",	# Savane
        "feature_status_id": "status",			# Berlios
        "feature_category_id": "category",		# Berlios
        "patch_status_id": "status",			# Berlios
        "patch_category_id": "category",		# Berlios
        "plan_release_id": "plan_release_version",	# Savane
        "platform_version_id": "platform_version",	# Savane
        "reproducibility_id": "reproducibility",	# Savane
        "resolution_id": "resolution",
        "size_id": "size",				# Savane
        "status_id": "status",
        }
    for tracker in issues['trackers']:
        # Delete range info for assigned_to field, it's not actually useful
        # to treat it as a vocablary.
        if 'assigned_to' in tracker['vocabularies']:
            del tracker['vocabularies']['assigned_to']
        # Perform name smoothing so we have a semi-standard set of attributes
        # across all forges and tracker types.
        for (rough, smooth) in name_mappings.items():
            if rough in tracker['vocabularies']:
                tracker['vocabularies'][smooth] = tracker['vocabularies'][rough]
                del tracker['vocabularies'][rough]
            for artifact in tracker['artifacts']:
                if rough in artifact:
                    if smooth in artifact:
                        raise ForgePluckerException(sys.argv[0] + ": name collision on %s" % smooth)
                    artifact[smooth] = artifact[rough]
                    del artifact[rough]
                    for change in artifact['history']:
                        if change['field'] == rough:
                            change['field'] = smooth
    return issues

def xml_dump(issues, fp=sys.stdout):
    "XML dump of bugtracker state.  NOT YET fully implemented."
    def xmlize(txt):
        txt = txt.replace('<', '&#60;')
        txt = txt.replace('>', '&#62;')
        txt = txt.replace('&', '&#38;')
        txt = txt.replace('"', '&#34;')
        return txt
    def identity_dump(identity, indent=0):
        if type(identity) != type({}) or 'class' not in identity or identity['class'] != 'IDENTITY':
            raise ValueError
            #raise ForgePluckerException(sys.argv[0] + ': illegal identity specification "%s"\n' % identity)
        # FIXME: Needs to be replaced with some sort of FOAF thing
        idump = (' ' * indent) + "<identity"
        for (key, val) in identity.items():
            if key != "class":
                idump += ' "%s"="%s"' % (key, val)
        idump += "/>"
        return idump
    fp.write('<trackers>\n')
    for tracker in issues['trackers']:
        fp.write('  <tracker id="%s">\n' % tracker['type'])
        fp.write('    <capture-begins>%s</capture-begins>\n' \
                 % tracker['interval'][0])
        fp.write('    <artifacts>\n')
        for artifact in tracker['artifacts']:
            fields = artifact.keys()
            fields.remove("class")	# Always 'ARTIFACT'
            fp.write('    <artifact id="%s">\n' % artifact['id'])
            fields.remove("id")
            # List in case we get more attributes we want to move up front 
            for field in ('summary', "assigned_to"):
                fp.write('      <%s>%s</%s>\n' % (field,artifact[field],field))
                fields.remove(field)
            selects = tracker['vocabularies'].keys()
            selects.sort()
            for field in selects:
                fp.write('      <attribute name="%s" value="%s"/>\n' % (field,artifact[field]))
                fields.remove(field)
            if 'comments' in artifact:
                if artifact['comments']:
                    fp.write('      <comments>\n')
                for (i, comment) in enumerate(artifact['comments']):
                    fp.write('        <comment number="%d">\n' % i)
                    fp.write('          <submitter>\n')
                    fp.write(identity_dump(comment['submitter'], indent=12))
                    fp.write('          </submitter>\n')
                    fp.write('          <date>%s</date>\n' % comment['date'])
                    fp.write('          <text>\n')
                    fp.write(xmlize(comment['comment']))
                    fp.write('          </text>\n')
                    fp.write('        </comment>\n')
                if artifact['comments']:
                    fp.write('      </comments>\n')
                fields.remove("comments")
            if 'attachments' in artifact:
                if artifact['attachments']:
                    fp.write('      <attachments>\n')
                for (i, attachment) in enumerate(artifact['attachments']):
                    fp.write('        <attachment number="%d">\n' % i)
                    for (field, value) in attachment.items():
                        if field != 'class':
                            continue
                        elif field == 'attacher':
                            fp.write(identity_dump(comment['attacher'], indent=10))
                        else:
                            fp.write('          <%s>%s<%s>\n' \
                                     % (field, xmlize(value), field))
                    fp.write('        </attachment>\n')
                fp.write('      </attachments>\n')
                if artifact['attachments']:
                    fields.remove("attachments")
            if 'history' in artifact:
                if artifact['history']:
                    fp.write('      <history>\n')
                for (i, fieldchange) in enumerate(artifact['history']):
                    fp.write('        <change number="%d">\n' % i)
                    for (field, value) in fieldchange.items():
                        if field != 'class':
                            fp.write('          <%s>%s<%s>\n' \
                                     % (field, xmlize(value), field))
                    fp.write('        </change>\n')
                if artifact['history']:
                    fp.write('      </history>\n')
                fields.remove("history")
            if 'dependents' in artifact:
                if artifact['dependents']:
                    fp.write('      <dependents>\n')
                for issueid in artifact['dependents']:
                    fp.write('        <dependent>%d</dependent>\n' % issueid)
                if artifact['dependents']:
                    fp.write('      </dependents>\n')
                fields.remove("dependents")
            if 'subscribers' in artifact:
                if artifact['subscribers']:
                    fp.write('      <subscribers>\n')
                for person in artifact['subscribers']:
                    fp.write('        <subscriber>\n')
                    fp.write('          <identity>\n')
                    fp.write(identity_dump(person['subscriber'], indent=12))
                    fp.write('          </identity>\n')
                    fp.write('          <reason>\n')
                    fp.write('          <reason>\n')
                    fp.write(person['reason'])
                    fp.write('        <subscriber>\n')
                if artifact['subscribers']:
                    fp.write('      </subscribers>\n')
                fields.remove("subscribers")
            if fields:
                raise ForgePluckerException(sys.argv[0] + ": no dump logic for fields %s in %s\n" % (fields, artifact))
            fp.write('    <artifact>\n')
        fp.write('    </artifacts>\n')
        fp.write('    <vocabularies>\n')
        for (field, vocabulary) in tracker['vocabularies'].items(): 
            fp.write('      <select attribute="%s">\n' % field)
            for value in vocabulary:
                fp.write('        </value>%s</value>\n' % value)
            fp.write('      <select>\n')
        fp.write('    </vocabularies>\n')
        fp.write('    <capture-ends>%s</capture-ends>\n' \
                 % tracker['interval'][1])
        fp.write('  </tracker>\n')
    fp.write('</trackers>\n')

if __name__ == '__main__':
    import getopt, pprint
    pp = pprint.PrettyPrinter(indent=4)
    user = passwd = forgetype = None
    verbose = 0
    issue = None
    xml = timeless = permissions = repositories = dump = False
    (options, arguments) = getopt.getopt(sys.argv[1:], "f:d:i:np:PSru:v:h?")
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
        elif arg == '-r':
            xml = True
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
            pp.pprint(perms)
        elif repositories:
            perms = bt.pluck_repository_urls()
            pp.pprint(perms)
        elif dump:
            page = bt.fetch(page,"Page to dump")
            print page
        elif issue:
            (tracker, issueid) = issue.split(":")
            issue = bt.pluck_artifact(tracker, issueid)
            pp.pprint(issue)
        else:
            bugs = bt.pluck_trackers(timeless=timeless)
            bugs = canonicalize(bugs)
            if xml:
                xml_dump(bugs)
            else:
                pp.pprint(bugs)
    except ForgePluckerException, e:
        print >>sys.stderr, e.msg
        raise SystemExit, 1
    except urllib2.HTTPError, e:
        print >>sys.stderr, "%s: %d - %s" % (e.url, e.code, e.msg)
        raise SystemExit, 1
    except KeyboardInterrupt:
        pass

# End
