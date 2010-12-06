# Collect all imports required to do project state fetches.

import netrc

from htmlscrape import *
from generic import *
from handle_sourceforge import *
from handle_berlios import *
from handle_savane import *
from handle_trac import *
from handle_fusionforge import *
from handle_gcode import *

from output_oslccmv2json import *

# Collect handler classes here, client code will introspect on this set
# so as not to have to know about individual handler classes.
handler_classes = (SourceForge, Berlios, Savane, Trac, Sf_Trac, GCode, FusionForge)

# Map well-known hosting sites to forge system types. We'd try using
# pattern-matching on the site main page for this, but forge admins
# customize their front pages a lot and unambiguous cues about
# forge type aren't so easy to find.
site_to_handler = {
    "sourceforge.net": SourceForge,
    "sourceforge.net/apps/trac": Sf_Trac,
    "developer.berlios.de": Berlios,
    "savannah.gnu.org": Savane,
    "savannah.nongnu.org": Savane,
    "gna.org": Savane,
    "code.google.com": GCode,
    "fusionforge.org": FusionForge,
    "gforge.inria.fr": FusionForge,
}

def get_forgetype(host):
    "Deduce forge type from hostname."
    if host in site_to_handler:
        return site_to_handler[host]
    # FIXME: Someday, we'll do more checks by parsing the site entry page 
    print >>sys.stderr, "Can't determine forge type for host %s" % host
    raise SystemExit, 1

def get_credentials(user, passwd, host):
    """Assemble user's actual credentials.
       user can be a ':' seperated list of usernames"""
    #usernames is list of usernames to try
    if user is None:
        usernames = [os.getenv("LOGNAME")]
        user = os.getenv("LOGNAME")
    else:
        usernames = user.split(':')
    host = host.split('/')[0] #If the host is a not a domain use just the domain
    if passwd is None:
        passwords = netrc.netrc()
        auth = passwords.authenticators(host)
        if auth and auth[0] in usernames:
            user = auth[0]
            passwd = auth[2]
    return (user, passwd)

# End
