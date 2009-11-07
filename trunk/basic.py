"""Basic test code that demostrates handle_sourceforge.py"""

from forgeplucker import ForgePluckerException
import forgeplucker.handle_sourceforge


try:
  sfhandle = forgeplucker.handle_sourceforge.SourceForge("sourceforge.net","forgepluckertes")

  #sfhandle.login("ultratwo",password)
    #login is not neccesary for current functionality
  bugtracker = sfhandle.getbugTracker()
  print bugtracker.getbugids()
  
except ForgePluckerException, e:
  print >>sys.stderr, e.msg
  raise SystemExit, 1
