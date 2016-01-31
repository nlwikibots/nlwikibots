#!/usr/bin/python
# -*- coding: utf-8  -*-
"""
This bot notifies the first and major author(s) of articles
nominated for deletion at the Dutch Wikipedia.

The following parameters are supported:

    -debug         Don't edit pages. Only show proposed edits.
    -date          The date for which new AfD's should be treated.

"""
#
# (C) Erwin (meta.wikimedia.org), 2009
#
# Distributed under the terms of the CC-BY-SA 3.0 licence.
#
__version__ = '$Id$'

import sys
import time
import re
import locale
import os

# Import pywikipedia and database wrapper
sys.path.append(os.environ['HOME'] + "/trunk")

import wikipedia
import query
import pagegenerators
import querier

class AfDBot:
    # Edit summary message that should be used.
    msg = {
        'en': u'New section: /* [[Wikipedia:Articles for deletion|AfD]] nomination */ Notification',
    }

    def __init__(self, AfDlog, always, debug = False):
        """
        Constructor. Parameters:
            * AfDlog        - The AfD log to be treated.
            * always        - If True, the user won't be prompted before changes
                             are made.
            * debug         - If True, don't edit pages. Only show proposed
                             edits.
        """
        self.AfDlog = AfDlog
        self.always = always
        self.debug = debug
        self.site = AfDlog.site()
        self.db = None
        self.replag = None
        
	locale.setlocale(locale.LC_ALL, 'nl_NL.UTF-8')
        os.environ['TZ'] = 'Europe/Amsterdam'

    def run(self):
        # Set up database access
        try:
            self.db = querier.querier(host="nlwiki.labsdb")
        except Exception, error:
            wikipedia.output(u'Could not connect to database: %s.' % error, toStdout = False)
       
        # Dictionaries of users with page_title and AfD_title tuple.
        self.contributors = {}
        
        if self.db:
            # Get replag
            sql =   """
                    SELECT time_to_sec(timediff(now()+0,CAST(rev_timestamp AS int))) AS replag
                    FROM nlwiki_p.revision
                    ORDER BY rev_timestamp DESC
                    LIMIT 1;"""
            result = self.db.do(sql)
            
            if not result:
                wikipedia.output(u'Could not get replag. Assuming it\'s infinite (= 1 month).')
                self.replag = 30 * 25 * 3600
            else:
                self.replag = int(result[0]['replag'])
                wikipedia.output(u'Replag: %is.' % self.replag)
                
        wikipedia.setAction(wikipedia.translate(wikipedia.getSite(), self.msg))
        try:
            # Load the page
            text = self.AfDlog.get()
        except wikipedia.NoPage:
            wikipedia.output(u"Page %s does not exist; skipping." % self.AfDlog.aslink())
            return
        except wikipedia.IsRedirectPage:
            wikipedia.output(u"Page %s is a redirect; skipping." % self.AfDlog.aslink())
            return

        # Find AfD's
        pageR = re.compile(r'^\*[ ]*?\[\[(?P<page>.*?)(?:\|.*?\]\]|\]\])')
        timestampR = re.compile('(\d{1,2}) (.{3}) (\d{4}) (\d{2}):(\d{2})')
        userR = re.compile(r'\[\[(?:[Uu]ser|[Gg]ebruiker):(?P<user>.*?)(?:\|.*?\]\]|\]\])')
        strictTemplateR = re.compile(r'\{\{(?:[Uu]ser|[Gg]ebruiker):(?P<user>.*?)\/[Hh]andtekening\}\}')
        templateR = re.compile(r'\{\{(?:[Uu]ser|[Gg]ebruiker):(?P<user>.*?)\/.*?\}\}')
        pages = []
        lines = text.splitlines()
        for line in lines:
            mPage = pageR.search(line)
            mTimestamp = timestampR.search(line)
            if mTimestamp:
                t = time.strftime('%Y%m%d%H%M%S', time.gmtime(time.mktime(time.strptime(mTimestamp.group(), '%d %b %Y %H:%M'))))
            else:
                t = None
            if mPage and userR.search(line):
                pages.append((mPage.group('page'), userR.search(line).group('user'), t))
                continue
            elif mPage and strictTemplateR.search(line):
                pages.append((mPage.group('page'), strictTemplateR.search(line).group('user'), t))
                continue
            elif mPage and templateR.search(line):
                pages.append((mPage.group('page'), templateR.search(line).group('user'), t))
                continue
            elif mPage:
                pages.append((mPage.group('page'), None, t))
                continue
        wikipedia.output(u'Found %i AfD\'s.' % len(pages))

        # Treat AfD's       
        for p in pages:
            page = wikipedia.Page(self.site, p[0])
            nominator = p[1]
            timestamp = p[2]
            page_contributors = self.getcontributors(page, timestamp)
            
            for contributor in page_contributors:
                if not self.contributors.has_key(contributor):
                    self.contributors[contributor] = [(page.title(), nominator)]
                else:
                    self.contributors[contributor].append((page.title(), nominator))

        # Treat users
        wikipedia.output(u'\n\nFound %i unique users.' % len(self.contributors))
        pages = [] # User talk pages
        for user in self.contributors.keys():
            pages.append(u'%s:%s' % (self.site.namespace(3), user))
            
        gen = pagegenerators.PagesFromTitlesGenerator(pages, site = self.site)
        gen = pagegenerators.PreloadingGenerator(gen)
        
        for page in gen:
            self.treatUser(page)
                
    def getcontributors(self, page, timestamp):
        """
        Return a page's major contributors.
        """
        wikipedia.output(u'\n>>> %s <<<' % (page.title()))
        if page.isRedirectPage():
            wikipedia.output(u'Page is a redirect.')
            
            if self.db:
                sql =   """
                        SELECT 1
                        FROM nlwiki_p.logging
                        WHERE log_namespace = %s
                        AND log_title = %s
                        AND log_timestamp > %s
                        AND log_type = 'move'
                        ORDER BY log_timestamp ASC
                        LIMIT 1;"""                
                args = (page.namespace(), self.sqltitle(page.titleWithoutNamespace()), timestamp)
                result = self.db.do(sql, args)
                
                if result:
                    page = page.getRedirectTarget()
                    wikipedia.output(u'Page was moved after the nomination. Checking target: %s.' % page.aslink())

        # Get first author of article
        if self.site.versionnumber() >= 12:
            #API Mode
            params = {
            'action': 'query',
            'titles': self.sqltitle(page.title()),
            'prop': 'revisions',
            'rvdir' : 'newer',
            'rvlimit' : 1,
            'rvprop' : 'timestamp|user',
            }
            
            datas = query.GetData(params, self.site)
            try:
                users = [datas['query']['pages'][page_id]['revisions'][0]['user'] for page_id in datas['query']['pages'].keys()]
                creator = users[0]
            except:
                wikipedia.output(u'Could not get first author from api for %s. The page has probably been deleted. Ignoring.' % page.title(), toStdout = True)
                return set()
        elif self.db:
            wikipedia.output(u'Can not use api for version history. Trying database.')
            sql =   """
                    SELECT *
                    FROM nlwiki_p.revision
                    LEFT JOIN nlwiki_p.page
                    ON page_id = rev_page
                    WHERE page_namespace = %s
                    AND page_title = %s
                    ORDER BY rev_timestamp ASC
                    LIMIT 1;"""
            args = (page.namespace(), self.sqltitle(page.title()))
            result = self.db.do(sql, args)
            
            if result:
                creator = result[0]['rev_user_text']
            else:
                creator = None
        else:
            wikipedia.output(u'Both api and database are unavailable. Aborting.', toStdout = False)
            
        # Get authors with more than 5 major edits.
        # FIXME: It's actually faster to select * than rev_user_text. Don't know why.
        if self.db:
            sql =   """
                    SELECT *
                    FROM nlwiki_p.revision
                    LEFT JOIN nlwiki_p.page
                    ON page_id = rev_page
                    WHERE page_namespace = %s
                    AND page_title = %s
                    AND rev_timestamp < %s
                    AND rev_minor_edit = 0
                    GROUP BY rev_user_text
                    HAVING COUNT(1) > 5;"""
            args = (page.namespace(), self.sqltitle(page.title()), timestamp)
            results = self.db.do(sql, args)
            
            try:
                contributors = set([unicode(result['rev_user_text'], 'utf8') for result in results])
            except Exception, error:
                wikipedia.output(u'Could not get contributors.')
                print error
        else:
            contributors = set()

        if creator:
            contributors.add(creator)

        wikipedia.output(u'Found %i contributors: %s.' % (len(contributors), u', '.join(contributors)))                                                       
        return contributors
        
    def sqltitle(self, page_title):
        """
        Return a MySQL style title.
        """
        return page_title.replace(' ', '_').encode('utf8')
        
    def treatUser(self, page):
        """
        Leave a message for the user.
        """
        wikipedia.output(u'\n>>> %s <<<' % (page.title()))
        user = page.titleWithoutNamespace()
        welcomeUser = False
        afds = []
        
        try:
            # Load the page
            original_text = page.get()
        except wikipedia.NoPage:
            wikipedia.output(u"Page %s does not exist." % page.aslink())
            original_text = ''
            welcomeUser = True
        except wikipedia.IsRedirectPage:
            wikipedia.output(u"Page %s is a redirect. Skipping." % page.aslink())
            return

        if not user in self.contributors.keys():
            wikipedia.output(u'Could not find AfD information for this user. Skipping.')
            return
        else:
            for page_title, nominator in self.contributors[user]:
                if nominator == page.title():
                    # Pagina is gestart en genomineerd door dezelfde gebruiker.
                    wikipedia.output(u'* [[%s]]: Article has been nominated for deletion by its author.' % page_title)
                    continue
                # Try to find links to the page using the replicated database.
                if self.db and self.replag < 600:
                    # FIXME: pl_namespace should not be fixed at 0.
                    sql =   """
                             SELECT 1
                             FROM nlwiki_p.page
                             LEFT JOIN nlwiki_p.pagelinks
                             ON pl_from = page_id
                             WHERE page_namespace = 3
                             AND page_title = %s
                             AND pl_namespace = 0
                             AND pl_title = %s
                             LIMIT 1;"""   
                    args = (self.sqltitle(user), self.sqltitle(page_title))
                    result = self.db.do(sql, args)
                    if result:
                        wikipedia.output(u'* [[%s]]: Found link in database.' % page_title)
                        continue
                else:
                    if re.search(r'\[\[\:{0,1}%s(?:.*?|)\]\]' % re.escape(page_title).replace('\\ ', '[_ ]'), original_text):
                        wikipedia.output(u'* [[%s]]: Found a link in text. Ignoring.' % page_title)
                        continue
                    elif re.search(r'\{\{vvn\|%s.*?\}\}' % re.escape(page_title).replace('\\ ', '[_ ]'), original_text):
                        wikipedia.output(u'* [[%s]]: {{vvn}} found.' % page_title)
                        continue

                wikipedia.output(u'* [[%s]]: Leaving message.' % page_title)
                afds.append((page_title, nominator))

            if len(afds) == 0:
                wikipedia.output(u'User has been notified of all AfD\'s.')
                return

            if len(afds) == 1:
                header = u'Beoordelingsnominatie [[%s]]' % afds[0][0]
                if afds[0][1]:
                    titles = u'Het gaat om [[%s]] dat is genomineerd door [[Gebruiker:%s|%s]].' % (afds[0][0], afds[0][1], afds[0][1])
                else:
                    titles = u'Het gaat om [[%s]].' % (afds[0][0])
            elif len(afds) > 1:
                header = u'Beoordelingsnominatie van o.a. [[%s]]' % afds[0][0]
                titles = u'De genomineerde artikelen zijn: '
                for page_title, nominator in afds:
                    if nominator:
                        titles += u'[[%s]] door [[Gebruiker:%s|%s]], ' % (page_title, nominator, nominator)
                    else:
                        titles += u'[[%s]] door een onbekende gebruiker, ' % (page_title)
                
                titles = u'%s.' % titles[:-2]
            
            comment = u'Nieuw onderwerp: /* %s */ Automatische melding van beoordelingsnominatie' % header
            AfDMessage = u'{{subst:Gebruiker:Erwin/Bot/Verwijderbericht/SPagina|%s|%s|%s}} --~~~~' % (header, titles, self.AfDlog.title())
            if welcomeUser:
                comment = u'Welkom op Wikipedia!; %s' % comment
                text = u'{{welkomstbericht}}' + u'\n\n' + AfDMessage
            else:
                text = original_text + u'\n\n' + AfDMessage
            text = text.strip()

        # only save if something was changed
        if text != original_text:
            # show what was changed
            if not self.always or self.debug:
                wikipedia.showDiff(original_text, text)
            if not self.debug:
                if not self.always:
                    choice = wikipedia.inputChoice(u'Do you want to accept these changes?', ['Yes', 'No'], ['y', 'N'], 'N')
                else:
                    choice = 'y'
                if choice == 'y':
                    try:
                        # Save the page
                        page.put(text, comment = comment, minorEdit = False)
                    except wikipedia.LockedPage:
                        wikipedia.output(u"Page %s is locked; skipping." % page.aslink())
                    except wikipedia.EditConflict:
                        wikipedia.output(u'Skipping %s because of edit conflict' % (page.title()))
                    except wikipedia.SpamfilterError, error:
                        wikipedia.output(u'Cannot change %s because of spam blacklist entry %s' % (page.title(), error.url))
                    except wikipedia.PageNotSaved:
                        wikipedia.output(u'Page %s could not be saved; skipping.' % page.aslink())
                        
def main():  
    # If debug is True, don't edit pages, but only show what would have been
    # changed.
    debug = False
    # The AfD log that should be treated.
    date = None
    # Whether to confirm edits.
    always = False

    # Parse command line arguments
    for arg in wikipedia.handleArgs():
        if arg.startswith('-debug'):
            wikipedia.output(u'Debug mode.')
            debug = True
        elif arg.startswith('-date'):        
            if len(arg) == 5:
                date = wikipedia.input(u'Please enter the date of the log that should be treated (yyyymmdd):')
            else:
                date = arg[6:]
        elif arg.startswith('-always'):
            always = True
  
    if date:
        page_title = u'Wikipedia:Te beoordelen pagina\'s/Toegevoegd %s' % date
    else:
        page_title = u'Wikipedia:Te beoordelen pagina\'s/Toegevoegd %s' % time.strftime("%Y%m%d", time.localtime(time.time()-60*60*24))

    wikipedia.output(u'Checking: %s.' % page_title)
    page = wikipedia.Page(wikipedia.getSite(code = 'nl', fam = 'wikipedia'), page_title)
    bot = AfDBot(page, always, debug)
    bot.run()

if __name__ == "__main__":
    try:
        main()
    finally:
        wikipedia.stopme()
