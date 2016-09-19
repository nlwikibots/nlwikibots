# encoding: utf-8
# $Id: wispagina.py 11 2007-06-10 15:35:37Z valhallasw $

import sys

import os
os.environ['TZ'] = 'Europe/Amsterdam'

import time, datetime
if time.localtime()[3] == 0 or (len(sys.argv) == 2 and sys.argv[1] == "-force"):
  import pywikibot as wikipedia
  import socket 
  wikipedia.setAction(u'Beoordelingslijstupdater van [[Project:nlwikibots]] @ %s' % socket.getfqdn())
  
  now = datetime.datetime(*time.localtime()[0:5])
  intwoweeks = now + datetime.timedelta(weeks=2)
  
  pagename = now.strftime("Wikipedia:Te beoordelen pagina's/Toegevoegd %Y%m%d")
  inhoud = now.strftime("{{subst:Te beoordelen pagina's nieuwe dag|dag=%Y%m%d}}") 
 
  P = wikipedia.Page(wikipedia.getSite(u'nl'), pagename)
  if not P.exists():          # als 'ie bestaat doe ik lekker niks ;)
    P.put(inhoud)
    
  mainpage = wikipedia.Page(wikipedia.getSite(u'nl'), "Wikipedia:Te beoordelen pagina's")
  mpInhoud = mainpage.get()
  
  if not P in mainpage.templates():
    mpInhoud = "".join(mpInhoud.split("<!-- {{"+pagename+"}} -->\n"))
    delen = mpInhoud.split("<!-- HIERVOOR -->")
    mpInhoud = delen[0] + "{{"+pagename+"}}\n<!-- HIERVOOR -->"+ delen[1]
    

  #nu nog de pagina voor over een week toevoegen
  dan = now + datetime.timedelta(days=7)
  intwoweeks = dan + datetime.timedelta(weeks=2)
  
  pagename = dan.strftime("Wikipedia:Te beoordelen pagina's/Toegevoegd %Y%m%d")
  inhoud = dan.strftime("{{subst:Te beoordelen pagina's nieuwe dag|dag=%Y%m%d}}") 

  P = wikipedia.Page(wikipedia.getSite(u'nl'), pagename)
  if not P.exists():          # als 'ie bestaat doe ik lekker niks ;)
    P.put(inhoud)

  if P.title() not in mpInhoud:
    delen = mpInhoud.split("<!-- EINDE QUEUE -->")
    mpInhoud = delen[0] + "<!-- {{"+pagename+"}} -->\n<!-- EINDE QUEUE -->" + delen[1]
  
  mainpage.put(mpInhoud, botflag=False)



#else:
  #print time.strftime("--not 00:00 yet. current time: %H:%M:%S") 
