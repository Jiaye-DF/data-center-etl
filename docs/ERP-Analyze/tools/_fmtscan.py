# -*- coding: utf-8 -*-
"""唯讀掃描 EFGP 大文字欄位，判斷存的是 XML / HTML / JSON / BASE64。只下 SELECT。"""
import sys, io, json, os, pymssql
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 密碼不入 repo:執行前 export MSSQL_SA_PASSWORD(見本目錄 README)
c = pymssql.connect(server='10.200.206.222', port=1433, user='sa',
                    password=os.environ['MSSQL_SA_PASSWORD'], database='EFGP', login_timeout=10, timeout=300)
c.autocommit(True)
cur = c.cursor(as_dict=True)
def q(s):
    try: cur.execute(s); return cur.fetchall()
    except Exception as e: return [{'ERR': str(e)[:120]}]

rowcnt = {r['o']: int(r['c'] or 0) for r in q(
    "SELECT object_id o, SUM(row_count) c FROM sys.dm_db_partition_stats "
    "WHERE index_id IN (0,1) GROUP BY object_id") if 'o' in r}

cols = q("""SELECT t.object_id oid, t.name tbl, c.name col, ty.name tp
  FROM sys.columns c JOIN sys.tables t ON t.object_id=c.object_id
  JOIN sys.types ty ON ty.user_type_id=c.user_type_id
  WHERE ty.name IN ('xml','ntext','text') OR (ty.name IN ('nvarchar','varchar') AND c.max_length=-1)
  ORDER BY t.name,c.name""")
print('大文字/XML 欄位總數:', len(cols), flush=True)

def classify(s):
    if not s: return None
    s = s.strip()
    if not s: return None
    low = s[:300].lower()
    if s.startswith('data:') and 'base64,' in s[:60]: return 'BASE64'
    if low.startswith('<?xml') or low.startswith('<com.'): return 'XML'
    if '<!doctype html' in low or '<html' in low: return 'HTML'
    if any(tag in low for tag in ('<div', '<table', '<span', '<p>', '<br', '<font', '<img', '<a ', '<tr', '<td')): return 'HTML片段'
    if s[0] == '<' and ('</' in s or '/>' in s): return 'XML'
    if (s[0] == '{' and s.rstrip()[-1:] == '}') or (s[0] == '[' and s.rstrip()[-1:] == ']'): return 'JSON'
    return 'TEXT'

res = []
todo = [cc for cc in cols if 'tbl' in cc and rowcnt.get(cc['oid'], 0) > 0]
total = len(todo)
print(f'有資料表的大文字欄位: {total}，開始抽樣 ...', flush=True)
for i, cc in enumerate(todo, 1):
    tb, col = cc['tbl'], cc['col']
    n = rowcnt.get(cc['oid'], 0)
    # 大表只看前幾筆實體列（免全表掃描）；小表掃非空值
    if n > 200000:
        s = q(f"SELECT TOP 5 CAST([{col}] AS NVARCHAR(MAX)) v FROM [{tb}]")
    else:
        s = q(f"SELECT TOP 1 CAST([{col}] AS NVARCHAR(MAX)) v FROM [{tb}] WHERE [{col}] IS NOT NULL AND DATALENGTH([{col}])>0")
    v = None
    for row in (s or []):
        if 'v' in row and row['v'] and row['v'].strip():
            v = row['v']; break
    f = classify(v)
    if f and f != 'TEXT':
        res.append({'fmt': f, 'tbl': tb, 'col': col, 'tp': cc['tp'], 'rows': n})
    if i % 25 == 0 or i == total:
        print(f'  進度 {i}/{total} ({i*100//total}%)', flush=True)

order = {'HTML': 0, 'HTML片段': 1, 'XML': 2, 'BASE64': 3, 'JSON': 4}
res.sort(key=lambda x: (order.get(x['fmt'], 9), -x['rows']))
cf = None
for r in res:
    if r['fmt'] != cf:
        print(f"\n#### {r['fmt']} ####"); cf = r['fmt']
    print(f"  {r['tbl']}.{r['col']} [{r['tp']}] 表約{r['rows']:,}列")
json.dump(res, open('_fmt_scan.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('\nDONE rows=', len(res), flush=True)
c.close()
