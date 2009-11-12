# Collect all imports required to do project state fetches.

import netrc

from htmlscrape import *
from generic import *
from handle_sourceforge import *
from handle_berlios import *
from handle_savane import *

# Collect handler classes here, client code will introspect on this set
# so as not to have to know about individual handler classes.
handler_classes = (SourceForge, Berlios, Savane)

# Map well-known hosting sites to forge system types. We'd try using
# pattern-matching on the site main page for this, but forge adnmins
# customize their front pages a lot and unambiguous cues about
# forge type aren't so easy to find.
site_to_handler = {
    "sourceforge.net": SourceForge,
    "sourceforge2.net": SourceForge,
    "developer.berlios.de": Berlios,
    "savannah.gnu.org": Savane,
    "savannah.nongnu.org": Savane,
    "gna.org": Savane,
}

def get_forgetype(host):
    if host in site_to_handler:
        return site_to_handler[host]
    print >>sys.stderr, "Can't determine forge type for host %s" % host
    raise SystemExit, 1

def get_credentials(user, passwd, host):
    "Assemble user's actual credentials."
    if user is None:
        user = os.getenv("LOGNAME")
    if passwd is None:
        passwords = netrc.netrc()
        auth = passwords.authenticators(host)
        if auth and auth[0] == user:
            passwd = auth[2]
    return (user, passwd)

# End
