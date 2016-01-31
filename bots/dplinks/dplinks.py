# -*- coding: utf-8  -*-
# $Id$
"""
List articles with links to disambiguation pages.
"""
#
# (C) Erwin (nl.wikipedia.org), 2010
#
# Distributed under the terms of the CC-BY-SA 3.0 licence.
#

from __future__ import generators
import sys, os
# Import pywikipedia and database wrapper
sys.path.append(os.environ['HOME'] + "/trunk")

import re, querier
import wikipedia, config

#DB Info
db = querier.querier(host='nlwiki.labsdb') #same as MySQLdb.connect attributes

def main():
    page = wikipedia.Page(wikipedia.getSite(), 'Wikipedia:Links_naar_doorverwijspagina\'s/Artikelen')
    
    try:
        # Load the page's text from the wiki.
        original_text = page.get()
        if not page.canBeEdited():
            wikipedia.output(u"Page %s is locked; skipping." % page.aslink())
            return
        #No page, so ignore   
    except wikipedia.NoPage:
        wikipedia.output(u"Page %s does not exist; skipping." % page.aslink())
        return
    except wikipedia.IsRedirectPage:
        wikipedia.output(u"Page %s is a redirect; skipping." % page.aslink())
        return

    s1 = re.search(r'\<\!\-\- bof \-\-\>', original_text)
    s2 = re.search(r'\<\!\-\- eof \-\-\>', original_text)
    if s1 and s2:
        i1 = s1.end()
        i2 = s2.start()
    else:
        wikipedia.output(u'Start and end markers not found. Aborting.')
        return

    new_text = original_text[:i1]
    
    # Page id 1841050 is Wikipedia:Links naar doorverwijspagina's/Artikelen/Filter
    wikipedia.output(u'Running query')
    sql = """
            SELECT p.page_title AS title,
                count(1) AS count,
                group_concat(dp.page_title ORDER BY dp.page_title ASC) AS links
            FROM nlwiki_p.page AS p
            JOIN nlwiki_p.pagelinks AS pl
                ON pl.pl_from = p.page_id
            JOIN s51086_dab_p.nlwiki_disambiguations AS dp
                ON dp.page_title = pl.pl_title
            WHERE p.page_namespace = 0
                AND p.page_is_redirect = 0
                AND pl_namespace = 0
                AND dp.date = (
                                SELECT MAX(date)
                                FROM s51086_dab_p.nlwiki_disambiguations
                              )
                AND NOT EXISTS (
                                SELECT *
                                FROM nlwiki_p.pagelinks AS fpl
                                WHERE fpl.pl_from = 1841050
                                AND fpl.pl_title = p.page_title
                                AND fpl.pl_namespace = p.page_namespace
                               )
            GROUP BY p.page_id
            ORDER BY count DESC
            LIMIT 500 /* SLOW_OK */;"""
            
    results = db.do(sql)
    
    new_text += u'\n{| class = "prettytable sortable"\n! #\n! style="width: 300px;" | Artikel\n! Aantal links\n! Links\n! Opmerkingen'
    
    i = 1
    for result in results:
        title = unicode(result['title'], 'utf8').replace('_', ' ')
        count = result['count']

        try:
            links_text = unicode(result['links'], 'utf8')
        # Assume that it is caused by MySQL not returning all bytes of the last unicode character.
        except UnicodeDecodeError:
            wikipedia.output(u'UnicodeDecodeError for %s.' % title)
            
            links_text = result['links']
            if links_text.rfind(','):
                links_text = unicode(links_text[:links_text.rfind(',')], 'utf8')
                links_text += u',…'
            else:
                links_text = u'…'
            
        links = [u'[[%s]]' % l.replace('_', ' ') for l in links_text.split(',')]
        
        # If string length > group_concat_max_len ( = 1024)
        if len(links_text) > 980:
            links.pop()
            links.append(u'…')
            
        links_text = u', '.join(links)
   
        new_text += u'\n|-\n|| %i || [[%s]] || %i || %s || ' % (i, title, count, links_text)
        i += 1
    
    new_text += u'\n|}\n' + original_text[i2:]
    page.put(new_text, 'nlwikibots: Listing query results.')

if __name__ == "__main__":
    try:
        main()
    finally:
        wikipedia.stopme()
