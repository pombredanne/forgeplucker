# -*- coding: utf-8 -*-
"""
Container implementation to store all plucked data/meta-data in a .zip archive conforming to OpenDocument Package 1.2 specs

Contributed in the frame of the COCLICO project.

(C) 2011 Olivier Berger - Institut Telecom

Note that we based ourself on the "Open Document Format for Office Applications (OpenDocument) Version 1.2 - Part 3: Packages" draft version 03

@author: Olivier Berger

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.

    * Redistributions in binary form must reproduce the above
      copyright notice, this list of conditions and the following
      disclaimer in the documentation and/or other materials provided
      with the distribution.

    * Neither the name of ForgePlucker nor the names of its
      contributors may be used to endorse or promote products derived
      from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""

# Reuse odfpy v. 0.9.3 available from http://pypi.python.org/pypi/odfpy

from odf.opendocument import OpenDocument, OpenDocumentText, OpaqueObject
from odf.element import Element
from odf.namespaces import OFFICENS

class OpenDocumentPackage(OpenDocument):
    '''
    Poor man's OpenDocument Package implementation (1.2 draft, part 3) 
    
    Extends odf.opendocument to create "empty" zip
    '''


    def __init__(self, mimetype, add_generator=True):
        '''
        Constructor
        '''
        OpenDocument.__init__(self, mimetype, add_generator)
        
    def addExtra(self, opaqueobject):
        """
        Adds an extra document, as an OpaqueObject into the package
        """
        doc._extra.append(opaqueobject)


class PlanetForgeExportContainer(OpenDocumentPackage):
    '''
    Container for PlanetForge compatible forge export documents
    '''
    MIMETYPE = 'application/x-planetforge-forge-export'
    
    def __init__(self, mimetype=MIMETYPE, add_generator=True):
        OpenDocumentPackage.__init__(self, mimetype, add_generator)

if __name__ == '__main__':

    doc = PlanetForgeExportContainer()    
    
    jsondoc = OpaqueObject('dump.plk', 'application/x-forgeplucker-oslc-rdf+json', "plop plop\n")
    doc.addExtra(jsondoc)
    
    doc.save("test.zip")
