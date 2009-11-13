"""
Helper functions for scraping HTML.
"""

from BeautifulSoup import BeautifulSoup
import re

def select_parse(branch):
    "Parse a BeautfulSoup select object."
    options = branch.findAll("option")
    possibilities = map(lambda x: x.contents[0], options)
    for x in options:
        if 'selected' in `x`:
            return (x.contents[0], possibilities)
    return (None, possibilities)

# This doesn't use Beautiful Soup (yet) because there's a Berlios case
# BS may not be able to cope with. We'll check sometime.

def walk_table(text):
    "Parse out the rows of an HTML table."
    rows = []
    while True:
        oldtext = text
        # First, strip out all attributes for easier parsing
        text = re.sub('<TR[^>]+>', '<TR>', text, re.I)
        text = re.sub('<TD[^>]+>', '<TD>', text, re.I)
        # Case-smash all the relevant HTML tags, we won't be keeping them.
        text = text.replace("</table>", "</TABLE>")
        text = text.replace("<td>", "<TD>").replace("</td>", "</TD>")
        text = text.replace("<tr>", "<TR>").replace("</tr>", "</TR>")
        text = text.replace("<br>", "<BR>")
        # Yes, Berlios generated \r<BR> sequences with no \n
        text = text.replace("\r<BR>", "\r\n")
        # And Berlios generated doubled </TD>s
        # (This sort of thing is why a structural parse will fail)
        text = text.replace("</TD></TD>", "</TD>")
        # Now that the HTML table structure is canonicalized, parse it.
        if text == oldtext:
            break
    end = text.find("</TABLE>")
    if end > -1:
        text = text[:end]
    while True:
        m = re.search(r"<TR>\w*", text)
        if not m:
            break
        start_row = m.end(0)
        end_row = start_row + text[start_row:].find("</TR>")
        rowtxt = text[start_row:end_row]
        rowtxt = rowtxt.strip()
        if rowtxt:
            rowtxt = rowtxt[4:-5]	# Strip off <TD> and </TD>
            rows.append(re.split(r"</TD>\s*<TD>", rowtxt))
        text = text[end_row+5:]
    return rows

def dehtmlize(text):
    "Remove HTMLisms from text."
    # Gna! can sometimes embed input elements with a readonly attribute
    # and a value but no name. These are rendered as though they were
    # wrapped in <pre> or <listing>.  Rescue the value.
    text = re.sub('<input[^>]*readonly="readonly"[^>]*value="([^"]*)"[^>]*>',
                  "\n\\1\n", text, re.I)
    text = re.sub("<[^>]*>", "", text)
    text = text.replace("&quot;", '"')
    text = text.replace("&lt;",   '<')
    text = text.replace("&gt;",   '>')
    text = text.replace("&nbsp;", ' ')
    text = text.replace("&amp;", '&')
    text = text.replace("\r\n",   '\n')
    return text

def blocktext(text):
    "Canonicalize whitespace around the text."
    return text.strip() + "\n"

# This probably belongs in a separate utils module, but for one function?

import time

def timestamp():
    "Timestamp in ISO time."
    return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(time.time()))

# End
