# -*- coding: utf-8  -*-
# $Id$
"""
This bot can archive any page based on sections, == .* ==, to multiple
archive pages. It uses the most recent date in standard MediaWiki format.

More information, in Dutch, is available at [[:nl:Gebruiker:Erwin/Bot/Archivering]].

You can run the bot with the following commandline parameters:

-always      - Don't prompt you for each replacement
-project     - Just check one project
               Argument can also be given as "-project:family:code".
-test        - Handle pages linking to [[:w:nl:Gebruiker:Erwin85/Bot/Archiveerlinkstest]]

"""
#
# (C) Erwin (nl.wikipedia.org), 2007
#
# Distributed under the terms of the CC-BY-SA 2.5 licence.
#
from __future__ import division
import sys, os
sys.path.append(os.environ['HOME'] + "/trunk")

import re, time, datetime, string
import wikipedia, pagegenerators, config

class ArchivingRobot:
    """
    A bot that does the archiving.
    """
    def __init__(self, generator, t0, site, linkingPageTitle, acceptall = False):
        """
        Arguments:
            * generator         - A generator that yields Page objects.
            * t0                - A time.time() object with the time the bot was started.
            * linkingPageTitle  - The template used in the settings
            * acceptall         - If True, the user won't be prompted before changes
                                  are made.
        """
        self.generator = generator
        self.acceptall = acceptall
        self.linkingPageTitle = linkingPageTitle
        self.site = site
        self.t0 = t0
        
        #Settings
        self.settings = {}
        
        #Regex to split a text in sections.
        self.resection = re.compile('([\n\r]={2}[^\n=]*?={2}[ ]*?[\n\r])')
        
        #Regex to get the dates in a section.
        self.redate = re.compile('(\d{1,2} .{3} \d{4} \d{2}:\d{2} \((CEST|CET)\))')
        
        #Regex to convert a date in plain text to a datetime object.
        self.redatematch = re.compile('(\d{1,2}) (.{3}) (\d{4}) (\d{2}):(\d{2})')
        
        #Regex used to skip a certain section.
        self.renoarchive = re.compile(r'<!-- noarchive -->')

        #Comment to place when there's a syntax error in the settings.
        self.nosettingscomment = '\n== Archivering ==\nBeste, ik heb geprobeerd deze pagina te archiveren, maar er zit een fout in je instellingen. Zie [[Gebruiker:Erwin/Bot/Archivering]] voor een correcte syntax van de instellingen. Als je vragen hebt, kun je deze stellen op [[Overleg project:nlwikibots]]. --~~~~'   

        #Comment to place when there's a syntax error in the magicwords setting.
        self.nomagicwordscomment = '\n== Archivering ==\nBeste, ik heb geprobeerd deze pagina te archiveren, maar er zit een fout in je instelling voor "magicwords". Zie [[Gebruiker:Erwin/Bot/Archivering]] voor een correcte syntax van deze instelling. Als je vragen hebt, kun je deze stellen op [[Overleg project:nlwikibots]]. --~~~~'

        #Summary when placing one of the above comments.
        self.commentsummary = '/* Archivering */ Automatisch bericht van nlwikibots.'

        #Comment to place when the archive page is a redirect
        self.cantedit = '\n== Archiveringspagina ==\nBeste, ik heb geprobeerd deze pagina te archiveren, maar een archiveringsdoel, [[%s]], is een doorverwijzing, beveiligd of mijn bot mag de pagina niet bewerken. Zou je daarom de archiveringscode even willen controleren? Er is niet gearchiveerd. Als je vragen hebt, kun je deze stellen op [[Overleg project:nlwikibots]]. --~~~~'

        #Summary when placing the above comments.
        self.canteditsummary = '/* Archiveringspagina */ Automatisch bericht van nlwikibots.'
        
        #Used to convert a plain text date to a datetime object.
        self.monthn = {
            'jan' : 1,
            'feb' : 2,
            'mrt' : 3,
            'apr' : 4,
            'mei' : 5,
            'jun' : 6,
            'jul' : 7,
            'aug' : 8,
            'sep' : 9,
            'okt' : 10,
            'nov' : 11,
            'dec' : 12
            }

        #Used to convert a datetime object to a plain text date.
        self.month = {
            1 : 'jan',
            2 : 'feb',
            3 : 'mrt',
            4 : 'apr',
            5 : 'mei',
            6 : 'jun',
            7 : 'jul',
            8 : 'aug',
            9 : 'sep',
            10 : 'okt',
            11 : 'nov',
            12 : 'dec'
            }
            
        #Used to convert a datetime object to a plain text date.
        self.trimester = {
            1 : '1',
            2 : '1',
            3 : '1',
            4 : '2',
            5 : '2',
            6 : '2',
            7 : '3',
            8 : '3',
            9 : '3',
            10 : '4',
            11 : '4',
            12 : '4'
            }

    def loadConfig(self, original_text):
        lines = original_text.split('\n')
        mode = 0
        for line in lines:
            if mode == 0 and re.search(r'\{\{%s(?:test|)' % self.linkingPageTitle, line):
                mode = 1
                continue
            if mode == 1 and re.match('}}',line):
                return True
            attRE = re.search(r'^\| *(\w+) *= *(.*?) *$',line)
            if mode == 1 and attRE:
                self.settings[attRE.group(1)] = attRE.group(2).strip()
                continue

        if mode == 0:
            return False
            
    def doDateReplacements(self, original_text):
        """
        Returns the text which is generated by applying all datereplacements to the
        given text.
        """
        datereplacements = [('{{CURRENTDAY2}}', time.strftime("%d")), ('{{CURRENTMONTH}}', time.strftime("%m")), ('{{CURRENTMONTHABBREV}}', self.month[int(time.strftime("%m"))]), ('{{CURRENTWEEK}}',time.strftime("%W")), ('{{CURRENTYEAR}}', time.strftime("%Y")), ('{{CURRENTTRIMESTER}}', self.trimester[int(time.strftime("%m"))])]

        new_text = original_text
        for old, new in datereplacements:
            new_text = new_text.replace(old, new)
        return new_text

    def doTitleReplacements(self, original_text, date):
        """
        Returns the text which is generated by applying all datereplacements based on date
        to the given text.
        """
        titlereplacements = [('{{DAY}}', date.strftime('%d')), ('{{MONTH}}', date.strftime('%m')), ('{{MONTHABBREV}}', self.month[int(date.strftime('%m'))]), ('{{YEAR}}', date.strftime('%Y')), ('{{TRIMESTER}}', self.trimester[int(date.strftime('%m'))])]
        new_text = original_text
        for old, new in titlereplacements:
            new_text = new_text.replace(old, new)
        return new_text
    
    def sort_by_value(self, d):
        """
        Returns the keys of dictionary d sorted by their values.
        """
        items = d.items()
        backitems = [ [v[1],v[0]] for v in items]
        backitems.sort()
        return [ backitems[i][1] for i in range(0,len(backitems))]    

    def plural(self, i, singular, plural):
        """
        Return singular or plural depending on the value of i.
        """
        if i == 1:
            return singular
        else:
            return plural      
        
    def run(self):
        """
        Starts the robot.
        """
        # Run the generator which will yield Pages which might need to be
        # changed.  
        for page in self.generator:
            wikipedia.output(u'\n>>> %s <<<' % page.title())
            #Current time
            sectiont0 = time.time()
            try:
                # Load the page's text from the wiki.
                original_text = page.get()
                if not page.canBeEdited():
                    wikipedia.output(u'Pagina %s wordt overgeslagen, deze pagina is beveiligd.' % page.title())
                    continue
            #No page, so ignore   
            except wikipedia.NoPage:
                wikipedia.output(u'Pagina %s bestaat niet.' % page.title())
                continue
            #Get the archiving settings.
            settings = self.loadConfig(original_text)

            #No settings were found, leave a message on the page.
            if not settings:
                wikipedia.output(u'Er kunnen geen instellingen worden gevonden op %s. Er wordt een bericht achtergelaten.' % page.title())
                page.put(original_text + self.nosettingscomment, self.commentsummary, minorEdit = False)                
                continue

            #Incorrect magicwords settings were found, leave a message on the page.
            if not self.settings['magicwords'] == u'oudste' and not self.settings['magicwords'] == u'recentste':
                wikipedia.output(u'Pagina %s wordt overgeslagen, er zijn geen of foute magicwords instellingen opgegeven, opgegeven was %s. Er wordt een bericht achtergelaten.' % (page.title(), self.settings['magicwords']))
                page.put(original_text + self.nomagicwordscomment, self.commentsummary, minorEdit = False)  
                continue

            #Get the number of days after which a section should be archived.
            self.settings['dagen'] = int(self.settings['dagen'])

            #Get the template for the archive page, some variables still have to be replaced using the section's oldest or most
            #recent date.
            #Make it a subpage of the current page.
            archive_titletemplate = page.title() + '/' + self.doDateReplacements(self.settings['archief'].strip())

            #Get a datetime object for the current date and time to compare other dates.
            todaydt = datetime.datetime.today()

            #Split the text into sections
            sections = self.resection.split(original_text)

            #The text before the first section won't be checked.
            new_text = sections[0]

            #A dictionary containing the archive page as key and the text as item.
            archives_dictionary = {}

            #The archiving target to be used in summaries.
            archive_target = 'n.v.t.'

            #The number of sections that will be archived.
            numberofsections = 0

            #A dictionary containing the archive page as key and the number of sections that will
            #be archived to that page as item.
            nos_dictionary = {}

            #Check all sections
            for i in range(2, len(sections), 2):
                archive_text = ''
                section_text = sections[i]
                #Check if the page shouldn't be archived.
                if self.renoarchive.search(section_text):
                    #Ignore this section.
                    new_text += sections[i-1] + section_text
                    continue
                
                #A list of the dates in wikisyntax.
                dates = self.redate.findall(section_text)
                if dates:
                    #A list of the dates as datetimeobjects.
                    datesdt = []
                    #A list of the difference in seconds between the date and now.
                    differences = {}
                    j = 0

                    #Create datetime objects from all found dates.
                    for date in dates:
                        datematch = self.redatematch.match(date[0])
                        try:
                            datedt = datetime.datetime(int(datematch.group(3)),self.monthn[datematch.group(2)],int(datematch.group(1)),int(datematch.group(4)),int(datematch.group(5)))
                        except:
                            wikipedia.output(u'Could not create a datetime object, skipping date')
                            continue
                        datesdt.append(datedt)
                        differencedt = todaydt - datedt
                        differences[j] = differencedt.days * 86400 + differencedt.seconds
                        j += 1
                        
                    try:					
                        diferences_sortedkeys = self.sort_by_value(differences)
                        difference = todaydt - datesdt[diferences_sortedkeys[0]]      
                    except:
                        wikipedia.output(u'Could not get the difference, probably because of skipping a date.')
                        #Add daylight saving time
                        if time.daylight == 1:
                            dst = 'CEST'
                        else:
                            dst = 'CET'
                            
                        section_text += '\n<!-- %s %s %s (%s) -->' % (time.strftime('%d'), self.month[int(time.strftime('%m'))], time.strftime('%Y %H:%M'), dst)
                        new_text += sections[i-1] + section_text
                        continue
                    #Check if a section should be archived using the most recent date.
                    if difference.days >= self.settings['dagen']:
                        if self.settings['magicwords'] == 'recentste':
                            archive_title = self.doTitleReplacements(archive_titletemplate, datesdt[diferences_sortedkeys[0]])
                        else:
                            archive_title = self.doTitleReplacements(archive_titletemplate, datesdt[diferences_sortedkeys[len(diferences_sortedkeys)-1]])

                        #Add section to archive.
                        numberofsections += 1

                        #Add the text and number of sections to the corresponding dictionaries.
                        if archives_dictionary.has_key(archive_title):
                            archives_dictionary[archive_title] += sections[i-1] + section_text
                            nos_dictionary[archive_title] += 1
                        else:
                            archives_dictionary[archive_title] = sections[i-1] + section_text
                            nos_dictionary[archive_title] = 1

                        #Add archive_title to archive_target
                        archive_target = '[[%s]]' % archive_title
                    else:
                        new_text += sections[i-1] + section_text
                else:
                    #No date was found, add one.
                    #We have to fill in the date ourselves because MediaWiki ignores <!-- ~~~~~ -->.

                    #Add daylight saving time
                    if time.daylight == 1:
                        dst = 'CEST'
                    else:
                        dst = 'CET'
                            
                    section_text += '\n<!-- %s %s %s (%s) -->' % (time.strftime('%d'), self.month[int(time.strftime('%m'))], time.strftime('%Y %H:%M'), dst)
                    new_text += sections[i-1] + section_text        

            #Check if there are multiple archive pages
            if len(archives_dictionary) > 1:
                archive_target = '%i archiefpagina\'s' % len(archives_dictionary)
            
            if not original_text == new_text:
                if page.isRedirectPage() or not page.canBeEdited():
                    wikipedia.output(u'Can not edit %s. Aborting.' % page.title())
                    continue
                abort = False
                for title in archives_dictionary.keys():
                    ap = wikipedia.Page(self.site, title)
                    if ap.isRedirectPage() or not ap.canBeEdited():
                        wikipedia.output(u'Can not edit %s. Aborting.' % ap.title())
                        try:
                            page.put(page.get() + self.cantedit % ap.title(), self.canteditsummary, minorEdit = False)
                        except wikipedia.EditConflict:
                            wikipedia.output(u'Pagina %s wordt overgeslagen vanwege een bewerkingsconflict.' % (page.title()))
                        abort = True
                        break
                
                if abort:
                    continue
                    
            if not original_text == new_text:
                diff = len(original_text) - len(new_text)
                reduction = (diff/len(original_text))*100
                wikipedia.output(u'Er worden %d onderwerpen gearchiveerd ouder dan %d dagen. In totaal worden %d tekens aangepast, een reductie van %d procent.' % (numberofsections, self.settings['dagen'], diff, reduction))
                wikipedia.output(u'Deze onderwerpen worden gearchiveerd naar %d verschillende archiefpagina\'s.' % (len(archives_dictionary)))

                if not self.acceptall:

                    cview = wikipedia.inputChoice(u'Wilt u deze wijzigingen bekijken?',  ['Yes', 'No'], ['y', 'N'], 'N')

                    if cview in ['y', 'Y']:
                        wikipedia.showDiff(original_text, new_text)

                    choice = wikipedia.inputChoice(u'Wilt u deze wijzigingen doorvoeren?',  ['Yes', 'No', 'All'], ['y', 'N', 'a'], 'N')
                    if choice in ['a', 'A']:
                        self.acceptall = True

                #Archive the page.
                if self.acceptall or choice in ['y', 'Y']:
                    if numberofsections:
                        wikipedia.setAction('nlwikibots: [[Gebruiker:Erwin85/Bot/Archivering|Archivering]] van %i %s ouder dan %i dagen naar %s.' % (numberofsections, self.plural(numberofsections, 'onderwerp', 'onderwerpen'), self.settings['dagen'], archive_target))
                    else:
                        wikipedia.setAction('nlwikibots: Datum toegevoegd in verband met [[Gebruiker:Erwin85/Bot/Archivering|archivering]].')

                    try:
                        page.put(new_text)
                    except wikipedia.EditConflict:
                        wikipedia.output(u'Pagina %s wordt overgeslagen vanwege een bewerkingsconflict.' % (page.title()), toStdout = True)
                        continue
                    except wikipedia.LockedPage:
                        wikipedia.output(u'Pagina %s is beveiligd.' % (page.title()), toStdout = True)
                        continue
                                       
                    for archive_title, archivetext in archives_dictionary.items():
                        redirect = False
                        if numberofsections:
                            wikipedia.setAction('nlwikibots: [[Gebruiker:Erwin85/Bot/Archivering|Archivering]] van %i %s ouder dan %i dagen van [[%s]].' % (nos_dictionary[archive_title], self.plural(nos_dictionary[archive_title], 'onderwerp', 'onderwerpen'), self.settings['dagen'], page.title()))
                        try:
                            archivepage = wikipedia.Page(self.site, archive_title)
                            # Load the page's text from the wiki
                            original_archivetext = archivepage.get()
                            if not page.canBeEdited():
                                wikipedia.output(u'Pagina %s wordt overgeslagen, deze pagina is beveiligd.' % archive_title)
                                continue
                        except wikipedia.NoPage:
                            wikipedia.output(u'Pagina %s bestaat niet.' % archive_title)
                            original_archivetext = ''
                        except wikipedia.IsRedirectPage:
                            wikipedia.output(u'Pagina %s is een doorverwijzing.' % archive_title)
                            redirect = True
                        if not redirect:
                            if original_archivetext:
                                archivetext = original_archivetext + '\n' + archivetext
                            else:
                                if self.settings['sjabloon']:
                                    archivetext = '{{subst:%s}}\n' % self.settings['sjabloon'] + archivetext

                            try:
                                archivepage.put(archivetext)
                            except wikipedia.EditConflict:
                                wikipedia.output(u'Pagina %s wordt overgeslagen vanwege een bewerkingsconflict.' % (archive_title))
                            
                        else:
                            wikipedia.output(u'Leaving message informing that archive page is a redirect.')
                            try:
                                page.put(page.get() + self.cantedit % archive_title, self.canteditsummary, minorEdit = False)
                            except wikipedia.EditConflict:
                                wikipedia.output(u'Pagina %s wordt overgeslagen vanwege een bewerkingsconflict.' % (page.title()))
		    
	    else:
                #No need for archiving.
                wikipedia.output(u'Archivering is niet nodig.')

            #Execution time for this section.
            sectiontimediff = time.time() - sectiont0
            wikipedia.output(u'Executiontime: %ss.' % str(sectiontimediff))
       
        #Total execution time.
        timediff = time.time() - self.t0
        wikipedia.output(u'Total executiontime: %ss.' % str(timediff))
        
def main():
    gen = None
    acceptall = False
    test = False
    linkingPageTitle = 'Gebruiker:Erwin/Bot/Archiveerlinks'
    #What projects should be checked?
    projects = {'wikipedia' : ['nl']}
    
    linkingPageTitles = {
                        'wikipedia' : {'nl' : 'Gebruiker:Erwin/Bot/Archiveerlinks'},
                        'wikisource' : {'nl' : 'Gebruiker:Erwin85/Bot/Archiveerlinks'}
                        }
    for arg in wikipedia.handleArgs():
        if arg == '-always':
            acceptall = True

        #Override defined projects
        #Use: -project:family:code
        elif arg.startswith('-project'):
            if len(arg) == 8:
                project = [wikipedia.input(u'Family?'), wikipedia.input(u'Code?')]
            else:
                project = re.split(r'\:', arg[9:])
            projects = {project[0] : [project[1]]}
        elif arg == '-test':
            test = True
            wikipedia.output(u'Using test settings.')
            projects = {'wikipedia' : ['nl']}

    for family, langs in projects.iteritems():
        for lang in langs:
            if not test:
                linkingPageTitle = linkingPageTitles[family][lang]
            else:
                linkingPageTitle = 'Gebruiker:Erwin/Bot/Archiveerlinkstest'

            wikipedia.output(u'\n>> %s:%s<<\n' % (family, lang))
            referredPage = wikipedia.Page(wikipedia.getSite(code = lang, fam = family), linkingPageTitle)
            gen = pagegenerators.ReferringPageGenerator(referredPage)
            preloadingGen = pagegenerators.PreloadingGenerator(gen, pageNumber = 40)
            bot = ArchivingRobot(preloadingGen, time.time(), wikipedia.getSite(code = lang, fam = family), linkingPageTitle, acceptall)
            bot.run()
    
if __name__ == "__main__":
    try:
        main()
    finally:
        wikipedia.stopme()
