import os
from pathlib import Path
from urllib.parse import urlparse, unquote
import pymysql
from dotenv import load_dotenv
load_dotenv(r'D:\AIAPP\ai-agent\.env')
url=os.getenv('DATABASE_URL')
u=urlparse(url)
conn=pymysql.connect(host=u.hostname,port=u.port or 3306,user=unquote(u.username),password=unquote(u.password),database=u.path.lstrip('/'),charset='utf8mb4')
with conn.cursor() as cur:
    cur.execute('SELECT DATABASE(), VERSION()')
    print('db_version', cur.fetchone())
    cur.execute('SHOW TABLES')
    tables=[r[0] for r in cur.fetchall()]
    print('tables', tables)
    for t in tables:
        cur.execute(f'SELECT COUNT(*) FROM `{t}`')
        print(t, cur.fetchone()[0])
conn.close()
