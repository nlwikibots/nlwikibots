# -*- coding: utf-8  -*-
# $Id$
"""
This bot tags uncategorized pages with a template."""
#
# (C) Erwin (nl.wikipedia.org), 2007
#
# Distributed under the terms of the CC-BY-SA 2.5 licence.
#

from __future__ import generators
import sys
sys.path.append("/home/erwin85/libs/python")
sys.path.append("/home/erwin85/libs/pywikipedia")

import re, querier
import wikipedia, erwin85bot, pagegenerators

db = querier.querier(host="sql-s2")

def main():
    wikipedia.handleArgs()
    wikipedia.setAction('Erwin85Bot: [[Sjabloon:nocat|nocat]] toegevoegd ([[:Categorie:Wikipedia:Nog te categoriseren]]).')
    noCatR = re.compile(r'\{\{([Xx]n|[Nn])ocat(\|[^\}]*?|)\}\}')
    excludeR = re.compile(r'\{\{(x{0,1}wiu|x{0,1}weg|nuweg|artikelweg|auteur|ne|reclame|wb|wiu2)(|\|[^\}]*?)\}\}', re.IGNORECASE)
    
    #List of page_titles which are treated
    titlelist = []

    wikipedia.output(u'Getting a list of uncategorized articles.')
    sql = """
            SELECT page_title
            FROM nlwiki_p.page
            LEFT JOIN nlwiki_p.categorylinks AS c1
            ON c1.cl_from = page_id
            WHERE page_is_redirect = 0
            AND page_namespace = 0
            AND page_len > 0
            AND (   cl_to IS NULL
                    OR
                    NOT EXISTS (SELECT *
                               FROM nlwiki_p.categorylinks AS c2
                               WHERE c2.cl_from = page_id
                               AND ( c2.cl_to NOT REGEXP '(Wikipedia:|Portaal:|Gebruiker:)'
                                        OR c2.cl_to LIKE 'Wikipedia:Nog_te_categoriseren%'
                                        OR c2.cl_to LIKE 'Wikipedia:Verwijderbaar/%'
                                   ))
                 )
            AND NOT EXISTS (SELECT *
                            FROM nlwiki_p.templatelinks
                            WHERE tl_from = page_id
                            AND tl_title = 'Dp'
                            AND tl_namespace = 10)
            GROUP BY page_id;
            """
    results = db.do(sql)
    if not results:
        wikipedia.output('No uncategorized mainspace articles')
              
    titles = [unicode(result['page_title'], 'utf8') for result in results]

    gen = pagegenerators.PagesFromTitlesGenerator(titles)
    gen = pagegenerators.PreloadingGenerator(gen)

    for page in gen:
        wikipedia.output(u'\n>>> %s <<<' % page.title())
        try:
            # Load the page's text from the wiki.
            original_text = page.get()
    
        #Redirect, so ignore
        except wikipedia.IsRedirectPage:
            wikipedia.output(u'Pagina is een doorverwijzing.')
            continue

        #No page, so ignore
        except wikipedia.NoPage:
            wikipedia.output(u'Pagina bestaat niet.')
            continue
        
        new_text = original_text
        if page.categories():
            wikipedia.output(u'Pagina zit in een categorie.')
            continue
            
        if noCatR.search(original_text) or excludeR.search(original_text):
            wikipedia.output(u'Pagina is al getagged met nocat of een ander sjabloon.')
        else:
            new_text = erwin85bot.addTemplate(original_text, 'nocat', '||{{subst:LOCALYEAR}}|{{subst:LOCALMONTH}}|{{subst:LOCALDAY2}}')
    
        if not new_text == original_text:
            try:
                page.put(new_text)
            except:
                continue

if __name__ == "__main__":
    try:
        main()
    finally:
        wikipedia.stopme()
