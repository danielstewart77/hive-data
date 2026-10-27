import sqlite3, subprocess, os, csv, sys
db='/home/daniel/Storage/Dev/hive_mind/nervous-system/data/lucent.db'
c=sqlite3.connect(f'file:{db}?mode=ro',uri=True)
rows=c.execute('select id, content from memories').fetchall()
with open('/tmp/tsrank-check/mem.tsv','w',newline='') as f:
    w=csv.writer(f,delimiter='\t',quoting=csv.QUOTE_NONE,escapechar='\\')
    for i,ct in rows:
        w.writerow([i,(ct or '').replace('\\','\\\\').replace('\t',' ').replace('\n','\\n').replace('\r',' ')])
print('rows',len(rows))
