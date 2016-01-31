# This is based on https://toolserver.org/~bryan/stats/dbquery/dab.sh
# with parameters hard-coded for nlwiki

DBNAME=s51086_dab_p
HOSTNAME=nlwiki.labsdb
SITENAME=nlwiki
DABCAT=Wikipedia:Doorverwijspagina
NRESULTS=250

#1=nlwiki
#2=nl:wikipedia
#3=Wikipedia:Links_naar_doorverwijspagina\'s/data
#4=Wikipedia:Doorverwijspagina
#5=250

BASE=${HOME}/public_html/stats/dbquery/${SITENAME}_dab
SQLFILE=${BASE}.sql
OUTFILE=${BASE}.txt

CMD="mysql -h ${HOSTNAME} --skip-column-names ${DBNAME}"
cat > ${SQLFILE} <<EOF
# ${CMD} < ${SQLFILE} > ${OUTFILE}
CREATE TABLE IF NOT EXISTS ${SITENAME}_disambiguations (page_title VARBINARY(255), page_id INT, page_latest INT, rd_title VARBINARY(255), date DATE, PRIMARY KEY(page_title, date), INDEX(rd_title), INDEX (date));
CREATE TABLE IF NOT EXISTS ${SITENAME}_dablinks (page_title VARBINARY(255), linkcount INT, date DATE, PRIMARY KEY(page_title, date), INDEX(date));

DELETE FROM ${SITENAME}_disambiguations WHERE date = CURDATE();

-- Create list of disambiguations pages
--  All pages in the main namespace that are in the disambiguation category
INSERT IGNORE INTO /* SLOW_OK */ ${SITENAME}_disambiguations SELECT page_title, page_id, page_latest, NULL as rd_title, CURDATE() AS date FROM ${SITENAME}_p.page, ${SITENAME}_p.categorylinks WHERE page_namespace = 0 AND page_id = cl_from AND cl_to = "${DABCAT}";
--  All pages in the main namespace that redirect to a disambiguation page
REPLACE INTO /* SLOW_OK */ ${SITENAME}_disambiguations SELECT p.page_title, p.page_id, p.page_latest, r.rd_title, CURDATE() AS date FROM ${SITENAME}_p.page AS p, ${SITENAME}_p.redirect AS r, ${SITENAME}_disambiguations AS d WHERE p.page_namespace = 0 AND p.page_id = r.rd_from AND r.rd_namespace = 0 AND r.rd_title = d.page_title AND d.date = CURDATE() AND d.rd_title IS NULL;

-- Links to dismabiguation pages
--  Cleanup today's run
DELETE FROM ${SITENAME}_dablinks WHERE date = CURDATE();

--  Links to disambiguations where the link source is in the main namespace
INSERT IGNORE INTO /* SLOW_OK */ ${SITENAME}_dablinks SELECT d.page_title, COUNT(p.page_id) AS linkcount, CURDATE() as date FROM ${SITENAME}_p.page AS p, ${SITENAME}_p.pagelinks, ${SITENAME}_disambiguations AS d WHERE p.page_namespace = 0 AND p.page_id = pl_from AND (pl_namespace, pl_title) = (0, d.page_title) AND d.date = CURDATE() AND NOT p.page_is_redirect AND p.page_title NOT IN (SELECT page_title FROM ${SITENAME}_disambiguations WHERE date = CURDATE()) GROUP BY d.page_title;

-- Get the diffs in linkcount
CREATE TEMPORARY TABLE ${SITENAME}_dablinks_diff (page_title VARBINARY(255), cur_linkcount INT, prev_linkcount INT, PRIMARY KEY(page_title));
INSERT INTO /* SLOW_OK */ ${SITENAME}_dablinks_diff (page_title, cur_linkcount, prev_linkcount) SELECT page_title, linkcount, linkcount FROM ${SITENAME}_dablinks WHERE date = CURDATE() ORDER BY linkcount DESC LIMIT ${NRESULTS};
SELECT DISTINCT @prev_date := date FROM ${SITENAME}_dablinks WHERE date < CURDATE() ORDER BY date DESC LIMIT 1;
UPDATE ${SITENAME}_dablinks_diff, ${SITENAME}_dablinks SET prev_linkcount = linkcount WHERE ${SITENAME}_dablinks_diff.page_title = ${SITENAME}_dablinks.page_title AND date = @prev_date;

-- Output in wiki format
SELECT CONCAT('# [[', REPLACE(page_title, '_', ' '), ']]: ', cur_linkcount, ' (', (cur_linkcount - prev_linkcount), ') [[Special:Whatlinkshere/', page_title, '|Links]]') FROM ${SITENAME}_dablinks_diff ORDER BY cur_linkcount DESC;
EOF

${CMD} < ${SQLFILE} > ${OUTFILE}

#if [ $? -eq 0 ]
#	then python /home/bryan/public_html/stats/dbquery/update.py -w $2 -p $3 -t list -s "Updating disambiguations" `mysql -hsql-s2-user --skip-column-names -e "SELECT CONCAT('count:', COUNT(*)) FROM ${SITENAME}_disambiguations WHERE date = CURDATE(); SELECT CONCAT('linkcount:', SUM(linkcount)) FROM ${SITENAME}_dablinks WHERE date = CURDATE(); SELECT CONCAT('today:', CURDATE()); SELECT CONCAT('last:', date) FROM ${SITENAME}_dablinks WHERE date < CURDATE() ORDER BY date DESC LIMIT 1;" u_bryan_dab_p` </home/bryan/public_html/stats/dbquery/${SITENAME}_dab.txt
#fi
