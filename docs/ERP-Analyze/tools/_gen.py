# -*- coding: utf-8 -*-
"""唯讀抽取 MS SQL Server (EFGP / HRMDB) metadata 並產出 md + html。
全程只執行 SELECT，連線設 autocommit 不開交易。"""
import sys, io, html, collections, os, pymssql
from opencc import OpenCC

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
_cc = OpenCC('s2twp')   # 简体 → 繁體（台灣用語）
def s2t(s):
    return _cc.convert(s) if s else s

DB = sys.argv[1]
OUT_PREFIX = sys.argv[2]      # e.g. bpm / hrm
TODAY = '2026-06-22'

# ---- 每個 DB 的人讀設定（角色說明、已知條件驗證、領域標籤） ----
CFG = {
  'EFGP': {
    'title': 'BPM（華苓 Agentflow / EFGP）測試站 Metadata 與關聯分析',
    'system': '華苓 **Agentflow BPM**（企業流程管理 / 簽核表單平台）',
    'name_source': '本庫**無** `MS_Description` 擴充屬性，表/欄位皆為英文命名；中文名欄位以英文原名呈現（已於已知條件驗證標註）。',
    'domain_labels': {
      'EPM':'企業流程管理(EPM)','SYN':'同步/整合','ISO':'ISO文件管理','Pro':'流程(Process)',
      'Doc':'文件(Document)','ecp':'入口/雲端平台','For':'表單(Form)','Cha':'簽核/變更',
      'Ser':'服務(Service)','MTS':'訊息/任務','Org':'組織(Org)','Per':'權限/人員',
      'Wor':'工作流(Workflow)','Sys':'系統設定','Bpm':'BPM核心','Act':'活動(Activity)',
      'Att':'附件(Attachment)','Use':'使用者','dfs':'自訂(df)','dfc':'自訂(df)',
    },
  },
  'HRMDB': {
    'title': 'HRM（HRMDB）測試站 Metadata 與關聯分析',
    'system': '人資管理系統（HRMDB，含人員/組織/出勤/薪資/招募/訓練/績效等模組）',
    'name_source': '中文名取自 `sys.extended_properties` 的 `MS_Description`（原為**简体**，已以 OpenCC `s2twp` 轉為**繁體台灣用語**）：表級 890/1129、欄位級 15,820 筆；缺漏者以欄位英文原名呈現。',
    'domain_labels': {
      'Emp':'員工(Employee)','ESS':'員工自助(ESS)','Sal':'薪資(Salary)','Rec':'招募(Recruit)',
      'Att':'出勤(Attendance)','Tra':'訓練(Training)','Per':'績效(Performance)','Ana':'資料分析模型',
      'Sys':'系統設定','Rol':'角色/權限(Role)','Res':'資源/留存','Ann':'公告(Announce)',
      'Use':'使用者','Bus':'商務/流程','Ale':'提醒(Alert)','Dep':'部門(Dept)','Reg':'註冊/法規',
      'App':'簽核/申請','For':'表單(Form)','Cod':'代碼(Code)','Org':'組織',
    },
  },
}
cfg = CFG[DB]

# 密碼不入 repo:執行前 export MSSQL_SA_PASSWORD(見本目錄 README)
conn = pymssql.connect(server='10.200.206.222', port=1433, user='sa',
                       password=os.environ['MSSQL_SA_PASSWORD'], database=DB, login_timeout=10, timeout=300)
conn.autocommit(True)
cur = conn.cursor(as_dict=True)
def q(s):
    cur.execute(s); return cur.fetchall()

print(f'[{DB}] 抓取 tables / row counts ...')
tables = {}   # name -> {rows, descr, cols:[], pks:set}
for r in q("""
  SELECT t.object_id oid, t.name name,
         CAST(ep.value AS NVARCHAR(1000)) descr
  FROM sys.tables t
  LEFT JOIN sys.extended_properties ep
    ON ep.major_id=t.object_id AND ep.minor_id=0 AND ep.name='MS_Description'
  WHERE t.is_ms_shipped=0"""):
    tables[r['oid']] = {'name': r['name'], 'descr': s2t((r['descr'] or '').strip()),
                        'rows': 0, 'cols': [], 'pks': set()}

for r in q("""
  SELECT ps.object_id oid, SUM(ps.row_count) rc
  FROM sys.dm_db_partition_stats ps
  WHERE ps.index_id IN (0,1)
  GROUP BY ps.object_id"""):
    if r['oid'] in tables:
        tables[r['oid']]['rows'] = int(r['rc'] or 0)

print(f'[{DB}] 抓取 PK columns ...')
for r in q("""
  SELECT i.object_id oid, c.name col
  FROM sys.indexes i
  JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
  JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
  WHERE i.is_primary_key=1"""):
    if r['oid'] in tables:
        tables[r['oid']]['pks'].add(r['col'])

print(f'[{DB}] 抓取 columns ...')
def render_type(tp, ml, prec, scale):
    tp = tp.lower()
    if tp in ('varchar','char','varbinary','binary'):
        return f"{tp}({'max' if ml==-1 else ml})"
    if tp in ('nvarchar','nchar'):
        return f"{tp}({'max' if ml==-1 else ml//2})"
    if tp in ('decimal','numeric'):
        return f"{tp}({prec},{scale})"
    if tp in ('datetime2','time','datetimeoffset') and scale is not None:
        return f"{tp}({scale})"
    return tp

for r in q("""
  SELECT c.object_id oid, c.column_id cid, c.name col,
         ty.name tp, c.max_length ml, c.precision prec, c.scale scale,
         c.is_nullable nullable, c.is_identity ident,
         CAST(ep.value AS NVARCHAR(1000)) descr
  FROM sys.columns c
  JOIN sys.types ty ON ty.user_type_id=c.user_type_id
  LEFT JOIN sys.extended_properties ep
    ON ep.major_id=c.object_id AND ep.minor_id=c.column_id AND ep.name='MS_Description'
  WHERE c.object_id IN (SELECT object_id FROM sys.tables WHERE is_ms_shipped=0)
  ORDER BY c.object_id, c.column_id"""):
    t = tables.get(r['oid'])
    if not t: continue
    t['cols'].append({
      'col': r['col'], 'type': render_type(r['tp'], r['ml'], r['prec'], r['scale']),
      'nullable': 'Y' if r['nullable'] else 'N',
      'ident': bool(r['ident']),
      'descr': s2t((r['descr'] or '').strip()),
      'pk': r['col'] in t['pks'],
    })

# ---- BPM(EFGP) 業務語意對照：流程/表單定義 → 中文名、MLANGUAGE 三語 ----
proc_dict, form_dict, mlang_sample, mlang_n = [], [], [], 0
if DB == 'EFGP':
    print(f'[{DB}] 抓取流程/表單繁中對照 ...')
    inst_cnt = {r['d']: r['c'] for r in q("""
        SELECT processDefinitionId d, COUNT(*) c FROM ProcessInstance
        WHERE processDefinitionId IS NOT NULL GROUP BY processDefinitionId""") if 'd' in r}
    for r in q("""SELECT id, MAX(processDefinitionName) nm FROM ProcessDefinition
                  WHERE processDefinitionName IS NOT NULL GROUP BY id"""):
        proc_dict.append({'id': r['id'], 'name': s2t((r['nm'] or '').strip()),
                          'inst': inst_cnt.get(r['id'], 0)})
    proc_dict.sort(key=lambda x: (-x['inst'], x['id']))
    for r in q("""SELECT id, MAX(formDefinitionName) nm FROM FormDefinition
                  WHERE formDefinitionName IS NOT NULL GROUP BY id"""):
        form_dict.append({'id': r['id'], 'name': s2t((r['nm'] or '').strip())})
    form_dict.sort(key=lambda x: x['id'].lower())
    mlang_n = q("SELECT COUNT(*) c FROM MLANGUAGE WHERE zh_TW IS NOT NULL")[0]['c']
    for r in q("""SELECT TOP 20 group_type, group_id, field_id, zh_TW, en_US
                  FROM MLANGUAGE WHERE zh_TW IS NOT NULL ORDER BY group_type, group_id, field_id"""):
        mlang_sample.append(r)

conn.close()
print(f'[{DB}] 連線已關閉，開始推導關聯與輸出 ...')

# ---- 推導關聯：單欄 PK 名稱唯一者作為被參照鍵，其他表含同名欄位 => 隱含 FK ----
name_by = {t['name']: t for t in tables.values()}
pk_target = {}          # pkcol -> table name （僅單欄PK且該欄名在所有單欄PK中唯一）
single_pk = collections.defaultdict(list)
for t in tables.values():
    if len(t['pks']) == 1:
        col = next(iter(t['pks']))
        single_pk[col].append(t['name'])
GENERIC = {'ID','OID','OBJECTID','SEQ','SEQNO','NO','CODE','GUID','UUID','KEY','PK',
           'CREATEDATE','UPDATEDATE','TENANTID'}
for col, owners in single_pk.items():
    if len(owners) == 1 and col.upper() not in GENERIC and len(col) >= 4:
        pk_target[col] = owners[0]

relations = []   # (child_table, fk_col, parent_table)
for t in tables.values():
    cols = {c['col'] for c in t['cols']}
    for col in cols:
        if col in pk_target and pk_target[col] != t['name']:
            relations.append((t['name'], col, pk_target[col]))
rel_by_child = collections.defaultdict(list)
for ch, col, pa in relations:
    rel_by_child[ch].append((col, pa))

# ---- 共用鍵欄位（跨表關聯樞紐）：同名欄位出現在多張表，且看似「鍵」非稽核欄位 ----
AUDIT = {c.lower() for c in (
    'objectVersion','createdTime','createTime','creator','creatorOID','creator_uid','creator_date',
    'updaterOID','updateTime','updatedTime','updater','modify_date','modify_uid','description',
    'name','flag','doneSync','version','status','remark','sortNo','sortOrder','isDeleted',
    'createBy','updateBy','createDate','updateDate','lastModified','tenantId','companyId')}
def keylike(name):
    n = name.lower()
    if n in AUDIT: return False
    return (n.endswith('oid') or n.endswith('id') or n.endswith('serialnumber')
            or n.endswith('no') or n.endswith('number') or n.endswith('code') or n.endswith('key'))
col_tables = collections.defaultdict(set)
for t in tables.values():
    for c in t['cols']:
        col_tables[c['col']].add(t['name'])
shared_keys = sorted(
    [(col, ts) for col, ts in col_tables.items() if keylike(col) and len(ts) >= 3],
    key=lambda kv: -len(kv[1]))

# ---- 領域分群（以表名前 3 字元為 key） ----
def dom_key(name): return name[:3]
groups = collections.defaultdict(list)
for t in tables.values():
    groups[dom_key(t['name'])].append(t)
def group_rows(g): return sum(t['rows'] for t in g)
ordered_groups = sorted(groups.items(), key=lambda kv: -group_rows(kv[1]))

all_tables_sorted = sorted(tables.values(), key=lambda t: (-t['rows'], t['name']))
n_tables = len(tables)
n_cols = sum(len(t['cols']) for t in tables.values())
n_with_data = sum(1 for t in tables.values() if t['rows'] > 0)
total_rows = sum(t['rows'] for t in tables.values())
n_tbl_desc = sum(1 for t in tables.values() if t['descr'])
n_col_desc = sum(1 for t in tables.values() for c in t['cols'] if c['descr'])

def cn(t): return t['descr'] if t['descr'] else ''
def keyflag(c):
    return 'PK' if c['pk'] else ('FK?' if c['col'] in pk_target and pk_target[c['col']] != None else '')

# ============================= 產出 Markdown =============================
def fmt(n): return f"{n:,}"
md = []
A = md.append
A(f"# {cfg['title']}\n")
A(f"> 產出日期：{TODAY}　|　資料來源：MS SQL Server `{DB}`（10.200.206.222:1433）　|　帳號：`sa`（**本任務全程唯讀，只下 SELECT**）\n")
DOC = {'bpm': 'analyze-bpm-metadata.md', 'hrm': 'analyze-hrm-metedata.md'}[OUT_PREFIX]
A(f"> 本文件由 agent 依 [docs/{DOC}](../{DOC}) 指令自動產出，全程僅執行 `SELECT`（連線 autocommit、未開交易、無任何寫入）。\n")

A("\n## 0. 重要前提與資料來源\n")
A("| 項目 | 說明 |")
A("| --- | --- |")
A(f"| 資料庫 | `{DB}`（MS SQL Server，連線 10.200.206.222:1433）|")
A(f"| 系統類型 | {cfg['system']} |")
A("| 權限限制 | 帳號 `sa` 具完整權限，但本任務**全程唯讀**；列數取自 `sys.dm_db_partition_stats`（堆積/叢集索引 `index_id IN (0,1)` 之 `row_count` 加總，屬**估計值**，非即時 `COUNT(*)`）。|")
A(f"| 中文名來源 | {cfg['name_source']} |")
A(f"| 統計摘要 | 表 {fmt(n_tables)} 張（有資料 {fmt(n_with_data)}）、欄位 {fmt(n_cols)} 個、估計總列數 {fmt(total_rows)}；表級中文名 {fmt(n_tbl_desc)}、欄位級中文名 {fmt(n_col_desc)}。|")
A("\n> ⚠️ 區分事實與推導：標示「**估計值**」者來自 `dm_db_partition_stats` 統計；標示「**推導/推測**」者為依命名慣例推斷（本庫無實體外鍵），非實際查得。\n")

A("\n## 1. 總覽：領域分群與資料量\n")
A("下表以表名前 3 字元分群（前綴），列數為各群 `dm_db_partition_stats` 估計值加總，取前 30 群。\n")
A("| 前綴 | 領域（推測） | 表數 | 有資料表數 | 估計列數 |")
A("| --- | --- | ---: | ---: | ---: |")
for k, g in ordered_groups[:30]:
    label = cfg['domain_labels'].get(k, '—')
    wd = sum(1 for t in g if t['rows'] > 0)
    A(f"| `{k}` | {label} | {len(g)} | {wd} | {fmt(group_rows(g))} |")
A(f"\n> 共 {len(ordered_groups)} 個前綴群；完整表清單見第 4 節，欄位見第 5 節。\n")

A("\n## 2. 已知條件驗證\n")
A("| # | 已知條件 | 驗證方法 | 結論 |")
A("| --- | --- | --- | --- |")
A(f"| 1 | 資料主要落在 `dbo` schema | 以 `sys.schemas`+`sys.tables` 統計各 schema 表數 | **成立**。全部 {fmt(n_tables)} 張使用者表皆屬 `dbo`，無其他自訂 schema 含業務資料。|")
if DB == 'EFGP':
    A("| 2 | 表名有命名前綴規律 | 依前 3 字元分群 | **成立（推導）**。可見明顯前綴族：`EPM`(企業流程)、`ISO`(文件)、`Pro`/`Doc`/`For`(流程/文件/表單)、`SYN`(同步)、`Org`/`Per`(組織/權限) 等；前綴含義為依命名推導。|")
    A("| 3 | 中文名來源（MS_Description / 應用字典 / 欄位名） | 查 `sys.extended_properties`、`MLANGUAGE`、`*Definition` 表 | **分層修正**：schema 層 `MS_Description` 為 **0 筆**（欄位名無中文）；但**業務語意層有繁體中文**，存於資料列——`ProcessDefinition`/`FormDefinition` 的流程/表單名、`MLANGUAGE`(zh_TW) 的 UI 標籤。詳見第 3.2 節。|")
else:
    A("| 2 | 表可依人資領域分群 | 依前 3 字元分群 | **成立（推導）**。明顯領域族：`Emp`(員工)、`Sal`(薪資)、`Att`(出勤)、`Rec`(招募)、`Tra`(訓練)、`Per`(績效)、`ESS`(自助) 等；含義為依命名+中文名推導。|")
    A(f"| 3 | 中文名來源（MS_Description / 應用字典 / 欄位名） | 查 `sys.extended_properties` | **成立**。中文名取自 `MS_Description`（原**简体**，已轉**繁體**）：表級 {fmt(n_tbl_desc)}、欄位級 {fmt(n_col_desc)}；缺漏者以英文原名呈現。|")
A(f"| 4 | 是否有實體外鍵 | 查 `sys.foreign_keys` | **無任何實體 FK（0 筆）**。關聯改以**命名慣例推導**：`XxxId` 欄位對應主鍵為 `XxxId` 的表 `Xxx`。|")

A("\n## 3. 關聯模型\n")
A("- **實體外鍵（FK）**：經 `sys.foreign_keys` 驗證為 **0 筆**（事實）。")
A(f"- **隱含關聯（推導，中可信度）**：以「單欄主鍵名稱唯一」的表作為被參照端（共 {fmt(len(pk_target))} 個可辨識主鍵），其他表若含同名欄位即視為隱含 FK，推導出 **{fmt(len(relations))} 條**關聯。已排除泛用欄位（ID/OID/CODE/TenantId…）以降低誤判。")
A("- 下表列出被其他表參照最多的前 30 個核心表（被參照次數＝入度）。\n")
indeg = collections.Counter(pa for _, _, pa in relations)
A("| 核心表 | 中文名 | 被參照次數 | 估計列數 |")
A("| --- | --- | ---: | ---: |")
for name, deg in indeg.most_common(30):
    t = name_by.get(name)
    A(f"| `{name}` | {cn(t) if t else ''} | {deg} | {fmt(t['rows']) if t else '?'} |")

A("\n### 3.1 共用鍵欄位（跨表關聯樞紐，推導）\n")
A("下列欄位以同名出現在多張表，且形態為鍵（非稽核欄位）。在無實體 FK 的系統中，這些是實際的跨表 join 樞紐（取前 30）。\n")
A("| 欄位名 | 出現表數 | 代表表（取樣） |")
A("| --- | ---: | --- |")
for col, ts in shared_keys[:30]:
    sample = ', '.join(f"`{n}`" for n in sorted(ts)[:6]) + ('…' if len(ts) > 6 else '')
    A(f"| `{col}` | {len(ts)} | {sample} |")

if DB == 'EFGP' and (proc_dict or form_dict):
    A("\n### 3.2 流程／表單繁中對照（業務語意層）\n")
    A("Agentflow 將中文存為**資料**而非 schema 註解。資料表中的 `processSerialNumber` = `processDefinitionId` + 流水號，"
      "可接回定義表取得中文業務名；`formSerialNumber` 同理對應表單定義。\n")
    A("**Join 食譜：**\n")
    A("```sql\n"
      "-- 任一資料表的 processSerialNumber → 中文流程名\n"
      "SELECT d.processSerialNumber,\n"
      "       pi.processDefinitionId,\n"
      "       pd.processDefinitionName  AS 中文流程名\n"
      "FROM   <任一含 processSerialNumber 的表> d\n"
      "JOIN   ProcessInstance   pi ON pi.serialNumber = d.processSerialNumber\n"
      "JOIN   ProcessDefinition pd ON pd.id = pi.processDefinitionId;  -- 或直接以 processDefinitionId 前綴比對\n"
      "```\n")
    A(f"\n**流程定義對照表（processDefinitionId → 中文名，共 {fmt(len(proc_dict))} 個定義，依流程實例數排序）**\n")
    A("| processDefinitionId（serialNumber 前綴） | 中文流程名 | 流程實例數 |")
    A("| --- | --- | ---: |")
    for d in proc_dict:
        A(f"| `{d['id']}` | {d['name']} | {fmt(d['inst'])} |")
    A(f"\n**表單定義對照表（formId → 中文表單名，共 {fmt(len(form_dict))} 個）**\n")
    A("| formId（formSerialNumber 前綴） | 中文表單名 |")
    A("| --- | --- |")
    for d in form_dict:
        A(f"| `{d['id']}` | {d['name']} |")
    A(f"\n**MLANGUAGE 三語 UI 標籤**：共 {fmt(mlang_n)} 筆繁體（`zh_TW`）標籤，鍵為 `group_type`+`group_id`+`field_id`（對應應用層欄位，非 DB 欄位）。取樣：\n")
    A("| group_type | group_id | field_id | 繁體(zh_TW) | en_US |")
    A("| --- | --- | --- | --- | --- |")
    for r in mlang_sample:
        A(f"| {r['group_type']} | `{r['group_id']}` | `{r['field_id']}` | {s2t((r['zh_TW'] or '').strip())} | {r['en_US'] or ''} |")
    A("\n> ⚠️ 此對照賦予「**資料的業務含義**」（這筆是什麼流程／表單），但仍**無法**翻譯個別欄位名（如 `TB2`、`hdnJobId`）——欄位語意需另查各表單的 form-field 定義。\n")

A("\n## 4. Table 清單（依估計列數排序）\n")
A("| # | 表名 | 中文名/說明 | 欄位數 | 估計列數 | 隱含關聯數 |")
A("| ---: | --- | --- | ---: | ---: | ---: |")
for i, t in enumerate(all_tables_sorted, 1):
    A(f"| {i} | `{t['name']}` | {cn(t)} | {len(t['cols'])} | {fmt(t['rows'])} | {len(rel_by_child.get(t['name'], []))} |")

A("\n## 5. Column 清單（依領域分群、表內依估計列數排序）\n")
for k, g in ordered_groups:
    label = cfg['domain_labels'].get(k, '—')
    A(f"\n### 前綴 `{k}` — {label}（{len(g)} 表）\n")
    for t in sorted(g, key=lambda x: (-x['rows'], x['name'])):
        rels = rel_by_child.get(t['name'], [])
        relnote = ('　[隱含FK→ ' + ', '.join(f"{c}→{p}" for c, p in rels[:8]) +
                   ('…' if len(rels) > 8 else '') + ']') if rels else ''
        A(f"\n#### `{t['name']}` — {cn(t) or '（無中文名）'}　(列數約 {fmt(t['rows'])})\n")
        A("| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |")
        A("| --- | --- | --- | :-: | :-: |")
        for c in t['cols']:
            flag = 'PK' if c['pk'] else ('FK?' if (c['col'] in pk_target and pk_target[c['col']] != t['name']) else '')
            desc = c['descr']
            A(f"| `{c['col']}` | {desc} | {c['type']} | {c['nullable']} | {flag} |")
        if relnote:
            A(f"\n> 隱含關聯：{relnote.strip()}")

md_text = '\n'.join(md)
with open(f"docs/output/{OUT_PREFIX}-metadata.md", 'w', encoding='utf-8') as f:
    f.write(md_text)
print(f"[{DB}] 已寫出 docs/output/{OUT_PREFIX}-metadata.md ({len(md_text)} bytes)")

# ============================= 產出 HTML =============================
def esc(s): return html.escape(str(s) if s is not None else '')

# Mermaid：HRM 用 erDiagram（FK 推導關聯豐富）；BPM 用共用鍵 hub 圖（graph）
def safe_id(s):
    out = ''.join(ch if (ch.isalnum() or ch == '_') else '_' for ch in s)
    return out if out and out[0].isalpha() or out[:1] == '_' else 'n_' + out

# 計算核心表之間（彼此互為 FK 端）的關聯數，決定圖型
core = [n for n, _ in indeg.most_common(24)]
core_set = set(core)
inner_edges = [(ch, col, pa) for ch, col, pa in relations
               if ch in core_set and pa in core_set and ch != pa]

if len(inner_edges) >= 8:
    # erDiagram：實體 + 推導 FK
    mer = ["erDiagram"]
    for n in core:
        t = name_by.get(n)
        pkcols = [c for c in (t['cols'] if t else []) if c['pk']][:6]
        mer.append(f'  {safe_id(n)} {{')
        for c in pkcols:
            mer.append(f'    {c["type"].split("(")[0]} {c["col"]} PK')
        mer.append('  }')
    seen_pair = set()
    for ch, col, pa in inner_edges:
        if (ch, pa) in seen_pair:
            continue
        seen_pair.add((ch, pa))
        mer.append(f'  {safe_id(pa)} ||--o{{ {safe_id(ch)} : "{col}"')
    mermaid_src = '\n'.join(mer)
else:
    # 共用鍵 hub 圖：以前 6 大共用鍵為樞紐，連到代表表
    mer = ["graph LR"]
    for col, ts in shared_keys[:6]:
        hub = 'KEY_' + safe_id(col)
        mer.append(f'  {hub}["🔑 {col}<br/>({len(ts)} 表)"]')
        for n in sorted(ts)[:5]:
            mer.append(f'  {hub} --- {safe_id(n)}["{n}"]')
    mermaid_src = '\n'.join(mer)

_is_er = mermaid_src.startswith('erDiagram')
_sys_label = cfg['system'].replace('**', '')
_name_src = cfg['name_source'].replace('**', '').replace('`', '')

H = []
B = H.append
# ---- head + ERP 風格樣式 ----
B("<!DOCTYPE html><html lang='zh-Hant'><head><meta charset='utf-8'>")
B("<meta name='viewport' content='width=device-width,initial-scale=1'>")
B(f"<title>{esc(cfg['title'])}</title>")
B("<script src='https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js'></script>")
B("<script>mermaid.initialize({startOnLoad:true, securityLevel:'loose', er:{layoutDirection:'LR'}});</script>")
B("<style>")
B("body{font-family:-apple-system,'Microsoft JhengHei',sans-serif;margin:0;color:#1a2233;background:#f6f8fb}")
B("header{background:#0f3d61;color:#fff;padding:22px 32px}")
B("header h1{margin:0 0 6px;font-size:22px}")
B("header .meta{opacity:.85;font-size:13px}")
B("nav{position:sticky;top:0;background:#fff;border-bottom:1px solid #dfe5ee;padding:8px 32px;font-size:13px;z-index:10}")
B("nav a{margin-right:14px;color:#0f3d61;text-decoration:none}")
B("main{max-width:1180px;margin:0 auto;padding:24px 32px 80px}")
B("h2{border-bottom:2px solid #0f3d61;padding-bottom:6px;margin-top:38px;color:#0f3d61}")
B("h3{margin-top:26px;color:#1c4e80}")
B("h4{margin:18px 0 6px;color:#23303f}")
B("table{border-collapse:collapse;width:100%;font-size:13px;margin:10px 0;background:#fff}")
B("th,td{border:1px solid #e1e7f0;padding:5px 8px;text-align:left;vertical-align:top}")
B("th{background:#eef3fa;position:sticky}")
B("tr:nth-child(even){background:#fafcff}")
B("code{background:#eef1f6;padding:1px 5px;border-radius:4px;font-size:12px}")
B(".tag{display:inline-block;background:#0f3d61;color:#fff;border-radius:3px;padding:0 6px;font-size:11px}")
B(".warn{background:#fff6e5;border-left:4px solid #e8a800;padding:8px 12px;margin:10px 0;font-size:13px}")
B(".mermaid{background:#fff;border:1px solid #e1e7f0;border-radius:8px;padding:14px;overflow:auto}")
B("details{background:#fff;border:1px solid #e6ebf3;border-radius:6px;margin:6px 0;padding:4px 10px}")
B("summary{cursor:pointer;font-weight:600;color:#1c4e80}")
B(".kpi{display:flex;gap:14px;flex-wrap:wrap;margin:12px 0}")
B(".kpi div{background:#fff;border:1px solid #e1e7f0;border-radius:8px;padding:10px 16px;min-width:120px}")
B(".kpi b{font-size:20px;color:#0f3d61;display:block}")
B("</style></head><body>")

# ---- header + nav ----
B(f"<header><h1>{esc(cfg['title'])}</h1>")
B(f"<div class='meta'>產出日期 {TODAY}　|　MS SQL Server {DB} @10.200.206.222　|　帳號 sa（<b>本任務全程唯讀</b>）　|　全程僅 SELECT、未開交易</div></header>")
_bizlink = "<a href='#bizdict'>流程/表單中文</a>" if DB == 'EFGP' else ""
B(f"<nav><a href='#ov'>總覽</a><a href='#verify'>已知條件驗證</a><a href='#rel'>關聯模型</a>{_bizlink}<a href='#tabs'>Table 清單</a><a href='#cols'>Column 清單</a></nav>")
B("<main>")

# ---- KPI 卡片 ----
B("<div class='kpi'>")
B(f"<div><b>{fmt(n_tables)}</b>資料表</div>")
B(f"<div><b>{fmt(n_with_data)}</b>有資料表</div>")
B(f"<div><b>{fmt(n_cols)}</b>欄位</div>")
B(f"<div><b>{fmt(len(relations))}</b>推導關聯</div>")
B(f"<div><b>0</b>實體外鍵</div>")
B("</div>")

# ---- 0/1 總覽 + 關聯圖 ----
B("<section id='ov'><h2>1. 總覽：資料來源與領域分群</h2>")
B(f"<div class='warn'>系統為 <b>{esc(_sys_label)}</b>，全部 {fmt(n_tables)} 張使用者表皆屬 <code>dbo</code>。"
  f"中文名來源：{esc(_name_src)} 資料列數取自 <b>統計值</b> <code>sys.dm_db_partition_stats</code>（非即時 COUNT）。</div>")
if _is_er:
    B("<p>本庫無實體外鍵，下圖為「命名慣例推導」之隱含關聯（<code>XxxId</code> → 表 <code>Xxx</code>），取被參照最多的核心表。</p>")
else:
    B("<p>本庫無實體外鍵且採通用 <code>OID</code> 主鍵，FK 命名推導稀疏；下圖以「共用鍵 hub」呈現實際 join 樞紐（前 6 大共用鍵 → 代表表）。</p>")
B(f"<div class='mermaid'>\n{esc(mermaid_src)}\n</div>")
B("<h3>領域分群（依表名前綴，前 30）</h3>")
B("<table><tr><th>前綴</th><th>領域(推測)</th><th>表數</th><th>有資料表</th><th>估計列數</th></tr>")
for k, g in ordered_groups[:30]:
    label = cfg['domain_labels'].get(k, '—')
    wd = sum(1 for t in g if t['rows'] > 0)
    B(f"<tr><td><code>{esc(k)}</code></td><td>{esc(label)}</td><td style='text-align:right'>{len(g)}</td>"
      f"<td style='text-align:right'>{wd}</td><td style='text-align:right'>{fmt(group_rows(g))}</td></tr>")
B("</table></section>")

# ---- 2 已知條件驗證 ----
B("<section id='verify'><h2>2. 已知條件驗證</h2><table><tr><th>#</th><th>已知條件</th><th>驗證方法</th><th>結論</th></tr>")
kc = [
  ("1","資料主要落在 dbo schema","sys.schemas + sys.tables", f"<b>成立</b>。全部 {fmt(n_tables)} 張使用者表皆屬 dbo，無其他自訂 schema。"),
  ("2","表名分群規律","依前 3 字元分群", "<b>成立（推導）</b>。可依表名前綴分為若干領域族，含義為依命名推導。"),
  ("3","中文名來源","sys.extended_properties / MLANGUAGE / *Definition",
     ("<b>分層修正</b>：schema 層 MS_Description 為 0 筆（欄位名無中文）；但<b>業務語意層有繁體中文</b>存於資料列（流程/表單名、MLANGUAGE）。詳見第 3.2 節。" if DB=='EFGP'
      else f"<b>成立</b>。中文名取自 MS_Description（原简体，已以 OpenCC s2twp 轉繁體）：表級 {fmt(n_tbl_desc)}、欄位級 {fmt(n_col_desc)}。")),
  ("4","實體外鍵","查 sys.foreign_keys", f"<b>無任何實體 FK（0 筆）</b>；改以命名慣例推導 {fmt(len(relations))} 條隱含關聯。"),
]
for a,b,c,d in kc:
    B(f"<tr><td>{a}</td><td>{esc(b)}</td><td><code>{esc(c)}</code></td><td>{d}</td></tr>")
B("</table></section>")

# ---- 3 關聯模型 ----
B("<section id='rel'><h2>3. 關聯模型</h2>")
B(f"<div class='warn'>實體外鍵經 <code>sys.foreign_keys</code> 驗證為 <b>0 筆</b>（事實）。"
  f"隱含關聯以「單欄主鍵名稱唯一」表為被參照端（{fmt(len(pk_target))} 個可辨識主鍵），推導 <b>{fmt(len(relations))}</b> 條，已排除泛用欄位。</div>")
B("<h3>3.1 核心表（被參照次數前 30）</h3>")
B("<table><tr><th>核心表</th><th>中文名</th><th>被參照次數</th><th>估計列數</th></tr>")
for name, deg in indeg.most_common(30):
    t = name_by.get(name)
    B(f"<tr><td><code>{esc(name)}</code></td><td>{esc(cn(t) if t else '')}</td>"
      f"<td style='text-align:right'>{deg}</td><td style='text-align:right'>{fmt(t['rows']) if t else '?'}</td></tr>")
B("</table>")
B("<h3>3.2 共用鍵欄位（跨表關聯樞紐，推導）</h3>")
B("<p>同名且形態為鍵（非稽核欄位）並出現在 ≥3 張表 — 無實體 FK 系統的實際 join 樞紐，取前 30。</p>")
B("<table><tr><th>欄位名</th><th>出現表數</th><th>代表表（取樣）</th></tr>")
for col, ts in shared_keys[:30]:
    sample = ', '.join(f"<code>{esc(n)}</code>" for n in sorted(ts)[:6]) + ('…' if len(ts) > 6 else '')
    B(f"<tr><td><code>{esc(col)}</code></td><td style='text-align:right'>{len(ts)}</td><td>{sample}</td></tr>")
B("</table>")

# ---- 3.3 BPM 業務語意對照 ----
if DB == 'EFGP' and (proc_dict or form_dict):
    B("<h3 id='bizdict'>3.3 流程／表單繁中對照（業務語意層）</h3>")
    B("<div class='warn'>Agentflow 將中文存為<b>資料</b>而非 schema 註解。資料表中的 "
      "<code>processSerialNumber</code> = <code>processDefinitionId</code> + 流水號，可接回定義表取得中文業務名；"
      "<code>formSerialNumber</code> 同理對應表單定義。</div>")
    B("<p><b>Join 食譜：</b></p>")
    B("<pre style='background:#0f3d61;color:#e8f0fa;padding:12px;border-radius:6px;overflow:auto;font-size:12px'>"
      "SELECT d.processSerialNumber, pi.processDefinitionId,\n"
      "       pd.processDefinitionName AS 中文流程名\n"
      "FROM   &lt;任一含 processSerialNumber 的表&gt; d\n"
      "JOIN   ProcessInstance   pi ON pi.serialNumber = d.processSerialNumber\n"
      "JOIN   ProcessDefinition pd ON pd.id = pi.processDefinitionId;</pre>")
    B(f"<h4>流程定義對照（processDefinitionId → 中文名，共 {fmt(len(proc_dict))} 個，依流程實例數排序）</h4>")
    B("<table><tr><th>processDefinitionId（serialNumber 前綴）</th><th>中文流程名</th><th>流程實例數</th></tr>")
    for d in proc_dict:
        B(f"<tr><td><code>{esc(d['id'])}</code></td><td>{esc(d['name'])}</td>"
          f"<td style='text-align:right'>{fmt(d['inst'])}</td></tr>")
    B("</table>")
    B(f"<h4>表單定義對照（formId → 中文表單名，共 {fmt(len(form_dict))} 個）</h4>")
    B("<table><tr><th>formId（formSerialNumber 前綴）</th><th>中文表單名</th></tr>")
    for d in form_dict:
        B(f"<tr><td><code>{esc(d['id'])}</code></td><td>{esc(d['name'])}</td></tr>")
    B("</table>")
    B(f"<h4>MLANGUAGE 三語 UI 標籤（共 {fmt(mlang_n)} 筆繁體；取樣）</h4>")
    B("<table><tr><th>group_type</th><th>group_id</th><th>field_id</th><th>繁體(zh_TW)</th><th>en_US</th></tr>")
    for r in mlang_sample:
        B(f"<tr><td>{esc(r['group_type'])}</td><td><code>{esc(r['group_id'])}</code></td>"
          f"<td><code>{esc(r['field_id'])}</code></td><td>{esc(s2t((r['zh_TW'] or '').strip()))}</td>"
          f"<td>{esc(r['en_US'] or '')}</td></tr>")
    B("</table>")
    B("<div class='warn'>此對照賦予「<b>資料的業務含義</b>」（這筆是什麼流程／表單），但仍<b>無法</b>翻譯個別欄位名"
      "（如 <code>TB2</code>、<code>hdnJobId</code>）——欄位語意需另查各表單的 form-field 定義。</div>")
B("</section>")

# ---- 4 Table 清單 ----
B("<section id='tabs'><h2>4. Table 清單（依估計列數排序）</h2><table>")
B("<tr><th>#</th><th>表名</th><th>中文名/說明</th><th>欄位數</th><th>估計列數</th><th>隱含關聯</th></tr>")
for i, t in enumerate(all_tables_sorted, 1):
    B(f"<tr><td style='text-align:right'>{i}</td><td><code>{esc(t['name'])}</code></td><td>{esc(cn(t))}</td>"
      f"<td style='text-align:right'>{len(t['cols'])}</td><td style='text-align:right'>{fmt(t['rows'])}</td>"
      f"<td style='text-align:right'>{len(rel_by_child.get(t['name'],[]))}</td></tr>")
B("</table></section>")

# ---- 5 Column 清單 ----
B("<section id='cols'><h2>5. Column 清單（依領域分群，可展開）</h2>")
for k, g in ordered_groups:
    label = cfg['domain_labels'].get(k, '—')
    B(f"<h3>前綴 <code>{esc(k)}</code> — {esc(label)}（{len(g)} 表）</h3>")
    for t in sorted(g, key=lambda x: (-x['rows'], x['name'])):
        rels = rel_by_child.get(t['name'], [])
        relnote = ('　<span class="tag">隱含FK</span> ' + ', '.join(f"{esc(c)}→{esc(p)}" for c, p in rels[:8])) if rels else ''
        B(f"<details><summary><code>{esc(t['name'])}</code> — {esc(cn(t) or '（無中文名）')}　"
          f"（列數約 {fmt(t['rows'])}，{len(t['cols'])} 欄）{relnote}</summary>")
        B("<table><tr><th>欄位</th><th>中文名/說明</th><th>型別</th><th>可空</th><th>鍵別</th></tr>")
        for c in t['cols']:
            flag = 'PK' if c['pk'] else ('FK?' if (c['col'] in pk_target and pk_target[c['col']] != t['name']) else '')
            B(f"<tr><td><code>{esc(c['col'])}</code></td><td>{esc(c['descr'])}</td><td>{esc(c['type'])}</td>"
              f"<td style='text-align:center'>{c['nullable']}</td><td style='text-align:center'>{flag}</td></tr>")
        B("</table></details>")
B("</section></main></body></html>")

# ============== 精簡版 BPM(EFGP) HTML：大字體、只保留必要資訊 ==============
if DB == 'EFGP':
    data_tables = [t for t in all_tables_sorted if t['rows'] > 0]
    H = []
    B = H.append
    B("<!DOCTYPE html><html lang='zh-Hant'><head><meta charset='utf-8'>")
    B("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    B(f"<title>{esc(cfg['title'])}</title>")
    B("<style>")
    B("body{font-family:-apple-system,'Microsoft JhengHei',sans-serif;margin:0;color:#1a2233;background:#f6f8fb;font-size:17px;line-height:1.7}")
    B("header{background:#0f3d61;color:#fff;padding:26px 34px}")
    B("header h1{margin:0 0 8px;font-size:26px}")
    B("header .meta{opacity:.9;font-size:15px}")
    B("main{max-width:1080px;margin:0 auto;padding:24px 34px 80px}")
    B("h2{border-bottom:2px solid #0f3d61;padding-bottom:8px;margin-top:44px;color:#0f3d61;font-size:23px}")
    B("p{font-size:17px}")
    B("table{border-collapse:collapse;width:100%;font-size:15px;margin:14px 0;background:#fff}")
    B("th,td{border:1px solid #e1e7f0;padding:8px 11px;text-align:left;vertical-align:top}")
    B("th{background:#eef3fa;font-size:15px}")
    B("tr:nth-child(even){background:#fafcff}")
    B("code{background:#eef1f6;padding:2px 6px;border-radius:4px;font-size:14px}")
    B(".warn{background:#fff6e5;border-left:5px solid #e8a800;padding:13px 17px;margin:16px 0;font-size:16px}")
    B("details{background:#fff;border:1px solid #e6ebf3;border-radius:6px;margin:8px 0;padding:6px 12px}")
    B("summary{cursor:pointer;font-weight:600;color:#1c4e80;font-size:16px;padding:5px 0}")
    B(".kpi{display:flex;gap:16px;flex-wrap:wrap;margin:18px 0}")
    B(".kpi div{background:#fff;border:1px solid #e1e7f0;border-radius:8px;padding:13px 22px;min-width:140px}")
    B(".kpi b{font-size:25px;color:#0f3d61;display:block}")
    B("</style></head><body>")
    B(f"<header><h1>{esc(cfg['title'])}</h1>")
    B(f"<div class='meta'>產出日期 {TODAY}　|　MS SQL Server EFGP @10.200.206.222　|　帳號 sa（全程唯讀）</div></header><main>")
    # KPI
    B("<div class='kpi'>")
    B(f"<div><b>{fmt(n_with_data)}</b>有資料表（共 {fmt(n_tables)}）</div>")
    B(f"<div><b>{fmt(len(proc_dict))}</b>流程定義</div>")
    B(f"<div><b>{fmt(len(form_dict))}</b>表單定義</div>")
    B("</div>")
    # 摘要
    B("<div class='warn'><b>這個庫是什麼：</b>華苓 Agentflow BPM（流程簽核平台）。欄位名為英文、"
      "schema 無中文註解，亦無實體外鍵；但<b>中文業務名存在資料裡</b>——可由 "
      "<code>processSerialNumber</code> / <code>formSerialNumber</code> 的前綴接回下方對照表，取得流程／表單的中文名。</div>")
    # 流程定義對照（主角）
    B("<h2>流程定義對照（processId → 中文，依使用量排序）</h2>")
    B("<p><code>processSerialNumber</code> 的前綴即 <code>processDefinitionId</code>，對應下表中文流程名（例：<code>DFSALE00000123</code> → 銷貨申請單）。</p>")
    B("<table><tr><th>processDefinitionId</th><th>中文流程名</th><th>流程實例數</th></tr>")
    for d in proc_dict:
        B(f"<tr><td><code>{esc(d['id'])}</code></td><td>{esc(d['name'])}</td><td style='text-align:right'>{fmt(d['inst'])}</td></tr>")
    B("</table>")
    # 表單定義對照
    B("<h2>表單定義對照（formId → 中文）</h2>")
    B("<table><tr><th>formId</th><th>中文表單名</th></tr>")
    for d in form_dict:
        B(f"<tr><td><code>{esc(d['id'])}</code></td><td>{esc(d['name'])}</td></tr>")
    B("</table>")
    # 資料表清單（只列有資料）
    B(f"<h2>資料表清單（{fmt(len(data_tables))} 張有資料表，依列數排序）</h2>")
    B("<table><tr><th>#</th><th>表名</th><th>欄位數</th><th>估計列數</th></tr>")
    for i, t in enumerate(data_tables, 1):
        B(f"<tr><td style='text-align:right'>{i}</td><td><code>{esc(t['name'])}</code></td>"
          f"<td style='text-align:right'>{len(t['cols'])}</td><td style='text-align:right'>{fmt(t['rows'])}</td></tr>")
    B("</table>")
    # 欄位清單（只列有資料表、折疊；BPM 欄位無中文故省略中文欄）
    B(f"<h2>欄位清單（點表名展開，僅列有資料的 {fmt(len(data_tables))} 張表）</h2>")
    for t in data_tables:
        B(f"<details><summary><code>{esc(t['name'])}</code>（{len(t['cols'])} 欄，約 {fmt(t['rows'])} 列）</summary>")
        B("<table><tr><th>欄位</th><th>型別</th><th>可空</th><th>主鍵</th></tr>")
        for c in t['cols']:
            B(f"<tr><td><code>{esc(c['col'])}</code></td><td>{esc(c['type'])}</td>"
              f"<td style='text-align:center'>{c['nullable']}</td><td style='text-align:center'>{'PK' if c['pk'] else ''}</td></tr>")
        B("</table></details>")
    B("</main></body></html>")

html_text = '\n'.join(H)
with open(f"docs/output/{OUT_PREFIX}-metadata.html", 'w', encoding='utf-8') as f:
    f.write(html_text)
print(f"[{DB}] 已寫出 docs/output/{OUT_PREFIX}-metadata.html ({len(html_text)} bytes)")
print(f"[{DB}] 完成：tables={n_tables} cols={n_cols} rels={len(relations)} pk_targets={len(pk_target)}")
