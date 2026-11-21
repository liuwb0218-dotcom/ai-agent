import re
from pathlib import Path
for name in ['.env','.env.example']:
    p=Path(r'D:\AIAPP\ai-agent')/name
    print('===',name,'===')
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
        if re.match(r'\s*(DATABASE_URL|DB_|MYSQL)', line, re.I):
            if '=' in line:
                k,v=line.split('=',1)
                if '://' in v:
                    v=re.sub(r'://([^:/]+):([^@]+)@', r'://\1:***@', v)
                print(k+'='+v)
            else:
                print(line)
