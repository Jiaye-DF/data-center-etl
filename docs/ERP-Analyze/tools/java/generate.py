# -*- coding: utf-8 -*-
"""Render erp-metadata.md + erp-metadata.html from extracted TSV files."""
import csv, os, html, collections, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "_data")
OUT  = os.path.join(BASE, "docs", "output")
os.makedirs(OUT, exist_ok=True)
GEN_DATE = "2026-06-18"

def read_tsv(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    return rows

owners  = read_tsv("owners.tsv")
tables  = read_tsv("m2201_tables.tsv")
columns = read_tsv("m2201_columns.tsv")

# ---- module legend (TIPTOP conventions; marked as inferred) ----
MODULE_ZH = {
    "AGL":"總帳 General Ledger","GGL":"總帳(共用)","CGL":"總帳(集團)",
    "AAP":"應付帳款 Accounts Payable","APY":"請款/付款",
    "AXR":"應收帳款 Accounts Receivable","CXR":"應收(集團)","GXR":"應收(共用)","ARM":"應收沖帳",
    "AIM":"庫存管理 Inventory","ASM":"庫存異動","AMM":"物料管理","AMD":"物料需求","AMR":"物料","AMS":"物料",
    "APM":"採購管理 Purchasing","AQC":"品檢/品保",
    "AOO":"訂單/銷貨 Order/Sales","AXM":"銷售管理","COO":"訂單(集團)","CXM":"銷售(集團)",
    "AFA":"固定資產 Fixed Assets",
    "ANM":"財務分錄/底稿","CNM":"財務分錄(集團)","GNM":"財務分錄(共用)",
    "AXC":"成本計算 Costing",
    "ASF":"生產/製令 Shop Floor","CSF":"生產(集團)","APJ":"專案管理 Project",
    "ABX":"票據管理","ABG":"票據",
    "ASR":"售後服務/維修","AWS":"工作站/整合站台",
    "AZZ":"系統共用/雜項","GNM2":"共用",
    "GGL2":"共用","": "(字典無模組碼)",
}
def mod_label(code):
    code = (code or "").strip()
    if code == "":
        return "(未分類)"
    return MODULE_ZH.get(code, code + "（推測）")

# ---- build column index per table ----
cols_by_table = collections.defaultdict(list)
for c in columns:
    cols_by_table[c["TABLE_NAME"]].append(c)

def fmt_type(c):
    dt = c["DATA_TYPE"]
    if dt == "NUMBER":
        p, s = c.get("DATA_PRECISION","").strip(), c.get("DATA_SCALE","").strip()
        if p:
            return f"NUMBER({p}{','+s if s and s!='0' else ''})"
        return "NUMBER"
    if dt in ("VARCHAR2","CHAR","NVARCHAR2","NCHAR"):
        return f"{dt}({c['DATA_LENGTH']})"
    return dt

def key_role(c):
    return "PK" if c.get("PK_POS","").strip() else ""

# ---- relationship inference: header/detail families by 2-letter prefix ----
def prefix3(t):
    n = t[:-5] if t.endswith("_FILE") else t
    return n if len(n) == 3 else None

data_table_names = [t["TABLE_NAME"] for t in tables]
fam = collections.defaultdict(list)
for t in data_table_names:
    p = prefix3(t)
    if p:
        fam[p[:2]].append(p)
families = {k: sorted(set(v)) for k, v in fam.items() if len(set(v)) > 1}

table_zh = {t["TABLE_NAME"]: t["ZH_NAME"] for t in tables}
table_rows = {t["TABLE_NAME"]: t["NUM_ROWS"] for t in tables}
table_mod  = {t["TABLE_NAME"]: t["MODULE"] for t in tables}

# relationships list: (header_table, detail_table, family)
rels = []
for fam2, prefs in sorted(families.items()):
    header = prefs[0]  # alphabetically first, usually the master/header (xxA)
    htab = header + "_FILE"
    for p in prefs[1:]:
        dtab = p + "_FILE"
        rels.append((htab, dtab, fam2))

# ======================================================================
#  Markdown
# ======================================================================
def md_escape(s):
    return (s or "").replace("|", "\\|").replace("\n", " ")

md = []
A = md.append
A(f"# 鼎新 ERP（TIPTOP）測試站 Metadata 與關聯分析\n")
A(f"> 產出日期：{GEN_DATE}　|　資料來源：Oracle `toptest`（10.200.206.130:1521）　|　帳號：`RO_M2201`（唯讀）\n")
A("> 本文件由 agent 依 [docs/analyze-erp-metadata.md](../analyze-erp-metadata.md) 指令自動產出，全程僅執行 `SELECT`。\n")

# --- 0. 重要前提與資料來源 ---
A("\n## 0. 重要前提與資料來源\n")
A("""
| 項目 | 說明 |
| --- | --- |
| 資料庫版本 | Oracle Database 11g Release 11.2.0.3.0（thin JDBC 連線，ojdbc8）|
| 字元集 | `AL32UTF8`（中文正確，無亂碼）|
| 系統類型 | 鼎新 **TIPTOP GP** ERP；每家公司/帳套為獨立 schema，表結構幾乎相同 |
| 資料字典 | 全域字典放在 `DS` schema：`DS.GAT_FILE`（表中文名）、`DS.GAQ_FILE`（欄位中文名）|
| **權限限制** | 本帳號可讀取 **所有 schema 的「結構 metadata」**（`ALL_*` 系統檢視），但僅能 `SELECT` **少數被授權的資料表**。因此「資料列數」一律取自 **最佳化程式統計值 `ALL_TABLES.NUM_ROWS`**（非即時 `COUNT(*)`），並以 `LAST_ANALYZED` 標註統計新鮮度。|
| 主要分析對象 | 本帳號對應公司帳套 **`M2201`**（其餘公司 schema 為相同表模型之複本，僅資料量不同）|
""")
A("> ⚠️ 區分事實與推導：標示「**統計值**」者來自 Oracle 統計資訊；標示「**推導/推測**」者為依命名慣例或 TIPTOP 慣例推斷，非實際查得。\n")

# --- 1. 總覽 ---
A("\n## 1. 總覽：各 Schema 角色與資料量\n")
A("下表為本帳號可見的所有 owner，資料列數取自統計值（`NUM_ROWS` 加總）。\n")
A("\n| Schema | 角色（推測） | 表數 | 有資料表數 | 資料列數(統計值) | 統計日期 |")
A("| --- | --- | ---: | ---: | ---: | --- |")
ROLE = {
 "DS":"**資料字典/系統設定**（GAT/GAQ 等字典表）","DS_REPORT":"報表暫存",
 "M2201":"**公司帳套（本帳號對應，主要分析對象）**",
 "SDF":"公司帳套（資料量最大）","GDF":"公司帳套","MDF":"公司帳套","DF":"公司帳套",
 "HW":"公司帳套","HWTAX":"公司帳套(稅)","FT":"公司帳套",
 "F2204":"公司帳套","S2202":"公司帳套","G2203":"公司帳套","TDF":"公司帳套",
 "NODATA":"範本/空帳套(推測)","SKL":"帳套(複本)","SKY":"帳套(複本)","SLE":"帳套(複本)",
 "SLY":"帳套(複本)","XCAR":"帳套(複本)","GLY":"帳套(複本)","SPA":"帳套(複本)",
 "DFTEST":"舊測試帳套(統計過期)","DFTEST2":"舊測試帳套","DFTEST6":"舊測試帳套","ERPMIS":"舊測試帳套",
 "PATCHTEMP":"程式更新暫存","SYS":"Oracle 系統","SYSTEM":"Oracle 系統","WMSYS":"Oracle Workspace Manager",
}
for o in owners:
    A(f"| `{o['OWNER']}` | {ROLE.get(o['OWNER'],'—')} | {o['TABS']} | {o['TABS_WITH_DATA']} | {int(o['TOTAL_ROWS']):,} | {o['LAST_STAT']} |")

# --- 2. 已知條件驗證 ---
A("\n## 2. 已知條件驗證\n")
A("""
| # | 原始已知條件 | 驗證方法 | 結論 |
| --- | --- | --- | --- |
| 1 | 僅 `DS`、`M2201`、`MDF`、`PATCHTEMP`、`SDF` 有資料 | 以 `ALL_TABLES.NUM_ROWS` 統計各 owner 資料量 | **不成立（需修正）**。這 5 個 schema 確實有資料，但**並非只有它們**：`SDF`(5,919萬列)、`GDF`(4,937萬)、`DF`(1,263萬)、`HW`、`F2204`、`FT` 等多個公司帳套同樣有資料。`PATCHTEMP` 僅 1,498 列（程式更新暫存，資料極少）。 |
| 2 | `DS.GAT_FILE.GAT01` 存放其他 schema 的 Table 名稱 | 直接查 `DS.GAT_FILE` 結構與內容 | **成立**。`GAT01`=表名（小寫，如 `aaa_file`）、`GAT02`=語言別（**0=繁體、2=简体**）、`GAT03`=**表中文名**、`GAT06`=模組代碼、`GAT04`=說明。共 4,857 列（繁體 2,430）。 |
| 3 | 是否存在欄位字典表（GAT_ITEM 或類似） | 列舉 `DS` 之 `GA*` 系列並取樣 | **修正**：無 `GAT_ITEM`；欄位字典為 **`DS.GAQ_FILE`**：`GAQ01`=欄位名（小寫，如 `aaa01`）、`GAQ02`=語言別、`GAQ03`=**欄位中文名**、`GAQ04/05`=說明/選項。繁體 54,196 列。本帳號於 `DS` 僅被授權 `GAT_FILE`、`GAQ_FILE`、`PAT_FILE`。 |
| 4 | （延伸）資料表是否有實體外鍵 | 查 `ALL_CONSTRAINTS` | **無任何實體 FK**（`M2201` 中 `R` 類型 = 0；僅 PK 2,145、檢查條件 10,858）。符合 TIPTOP「以共用代碼欄位關聯、不建實體 FK」之慣例 → 關聯需以**命名慣例推導**。 |
""")
A("> 字典中文名對 `M2201` 有資料的 333 張表覆蓋良好：表名 98%＋、欄位中文名約 98%（11,756 / 11,947 欄）。\n")

# --- 3. 關聯模型 ---
A("\n## 3. 關聯模型\n")
A(f"""
- **實體外鍵（FK）**：經 `ALL_CONSTRAINTS` 驗證為 **0 筆**（事實）。
- **單頭/單身關聯（推導，中可信度）**：TIPTOP 以 3 碼前綴命名（表＝`<前綴>_file`，欄位＝`<前綴><序號>`）。同一前 2 碼的表屬同一單據族，字尾較前者（多為 `A`）為單頭/主檔，其餘為單身/明細，透過單據號欄位串接（如 `oeb01`=`oea01`）。
- 以下為 `M2201` 有資料的表中，可辨識的單頭/單身族（共 {len(rels)} 條推導關聯，{len(families)} 個族）。完整 ER 圖見 HTML 版（Mermaid）。
""")
A("\n| 單頭/主檔 | 中文名 | 單身/明細（同族其餘表） |")
A("| --- | --- | --- |")
fam_detail = collections.defaultdict(list)
for h, d, f2 in rels:
    fam_detail[h].append(d)
for h in sorted(fam_detail):
    details = ", ".join(f"`{d}`" for d in fam_detail[h])
    A(f"| `{h}` | {md_escape(table_zh.get(h,'—'))} | {details} |")
A("\n> 註：上表為**命名慣例推導**，非字典或 FK 明示；個別表可能為獨立主檔而非單頭。可信度：中。\n")

# --- 4. Table 清單 ---
A("\n## 4. Table 清單（M2201，有資料者，依資料量排序）\n")
A(f"共 {len(tables)} 張表。資料列數為統計值。\n")
A("\n| # | Schema | 表名 | 中文名/說明 | 模組(推測) | 列數(統計值) | PK |")
A("| ---: | --- | --- | --- | --- | ---: | :-: |")
for i, t in enumerate(tables, 1):
    A(f"| {i} | M2201 | `{t['TABLE_NAME']}` | {md_escape(t['ZH_NAME']) or '—'} | {mod_label(t['MODULE'])} | {int(t['NUM_ROWS']):,} | {'✓' if t['HAS_PK']=='1' else ''} |")

# --- 5. Column 清單 ---
A("\n## 5. Column 清單（依表分組）\n")
A("欄位中文名來源：`DS.GAQ_FILE`（繁體）。鍵別 PK 來源：`ALL_CONSTRAINTS`。\n")
# group tables by module for navigability
by_mod = collections.defaultdict(list)
for t in tables:
    by_mod[t["MODULE"]].append(t)
order_mod = [m["MODULE"] for m in read_tsv("m2201_modules.tsv")]
for m in order_mod:
    A(f"\n### 模組 `{m or '(未分類)'}` — {mod_label(m)}\n")
    for t in by_mod[m]:
        tn = t["TABLE_NAME"]
        A(f"\n#### `{tn}` — {md_escape(t['ZH_NAME']) or '—'}　(列數約 {int(t['NUM_ROWS']):,})\n")
        A("| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |")
        A("| --- | --- | --- | :-: | :-: |")
        for c in cols_by_table.get(tn, []):
            A(f"| `{c['COLUMN_NAME']}` | {md_escape(c['ZH_NAME']) or '—'} | {fmt_type(c)} | {'Y' if c['NULLABLE']=='Y' else 'N'} | {key_role(c)} |")

# --- 6. 完成回報 / 未解析 ---
A("\n## 6. 完成回報與未能解析的部分\n")
A("""
**實際有資料的 schema（統計值，前段）**：`SDF`、`GDF`、`MDF`、`DF`、`DS`、`M2201` 為主；`HW`、`F2204`、`FT`、`HWTAX`、`S2202`、`G2203`、`TDF` 及多個複本帳套有少量資料；`DFTEST*`、`ERPMIS` 為統計過期之舊測試帳套。

**字典表驗證結論**：表字典＝`DS.GAT_FILE`（成立）；欄位字典＝`DS.GAQ_FILE`（修正自原推測的 GAT_ITEM）；兩者皆為語言別分列（0 繁／2 简）。

**未能解析 / 受限部分**：
1. **資料列數無法即時 `COUNT(*)`**：本帳號僅被授權 `SELECT` 極少數實體表（多數公司 schema 僅 1 張），故列數一律採統計值；少數無統計或統計過期者列數可能偏差。
2. **實體 FK 不存在**：表間關聯無法由 `ALL_CONSTRAINTS` 取得，僅能以命名慣例推導（中可信度），跨模組（如料件主檔 `IMA_FILE` 被多單據引用）之關聯未逐一列舉。
3. **模組中文名**為依 TIPTOP 慣例推測（字典未含模組碼對照表），以「（推測）」標註。
4. 其他公司 schema（SDF/GDF/DF…）未逐表展開欄位，因表模型與 M2201 同構，可直接套用本文件之欄位字典。

**產出檔案**：`docs/output/erp-metadata.md`、`docs/output/erp-metadata.html`
""")

with open(os.path.join(OUT, "erp-metadata.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(md))
print("MD written:", os.path.join(OUT, "erp-metadata.md"), len(md), "lines")

# ======================================================================
#  HTML  (Mermaid via CDN)
# ======================================================================
# Mermaid erDiagram for top families (limit entities for readability)
top_tables = tables[:1]  # placeholder
# pick families that contain at least one high-row table; cap entities
fam_score = []
for fam2, prefs in families.items():
    tabs = [p+"_FILE" for p in prefs]
    score = sum(int(table_rows.get(t,"0") or 0) for t in tabs)
    fam_score.append((score, fam2, prefs))
fam_score.sort(reverse=True)

def safe_id(t):
    return t.replace("-", "_")

mer = ["erDiagram"]
ent_count = 0
MAX_ENT = 60
for score, fam2, prefs in fam_score:
    if ent_count >= MAX_ENT:
        break
    tabs = [p+"_FILE" for p in prefs if (p+"_FILE") in table_zh]
    if len(tabs) < 2:
        continue
    header = tabs[0]
    for d in tabs[1:]:
        if ent_count >= MAX_ENT:
            break
        mer.append(f'    {safe_id(header)} ||--o{{ {safe_id(d)} : "單身(推導)"')
        ent_count += 1
# entity labels with zh name
label_lines = []
shown = set()
for line in mer[1:]:
    for tok in line.split():
        if tok.endswith("_FILE") and tok not in shown:
            shown.add(tok)
mermaid_src = "\n".join(mer)

# schema overview graph
g = ["graph LR", '    DS["DS 資料字典<br/>GAT_FILE/GAQ_FILE"]']
for o in owners:
    ow = o["OWNER"]
    if ow in ("DS","SYS","SYSTEM","WMSYS","DS_REPORT","PATCHTEMP"): continue
    if int(o["TOTAL_ROWS"]) < 10000: continue
    g.append(f'    DS -.中文名.-> {ow}["{ow}<br/>{int(o["TOTAL_ROWS"]):,} 列"]')
schema_graph = "\n".join(g)

def h(s): return html.escape(s or "")

parts = []
P = parts.append
P("<!DOCTYPE html><html lang='zh-Hant'><head><meta charset='utf-8'>")
P("<meta name='viewport' content='width=device-width,initial-scale=1'>")
P("<title>鼎新 ERP (TIPTOP) Metadata 與關聯分析</title>")
P("<script src='https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js'></script>")
P("<script>mermaid.initialize({startOnLoad:true, securityLevel:'loose', er:{layoutDirection:'LR'}});</script>")
P("""<style>
body{font-family:-apple-system,'Microsoft JhengHei',sans-serif;margin:0;color:#1a2233;background:#f6f8fb}
header{background:#0f3d61;color:#fff;padding:22px 32px}
header h1{margin:0 0 6px;font-size:22px}
header .meta{opacity:.85;font-size:13px}
nav{position:sticky;top:0;background:#fff;border-bottom:1px solid #dfe5ee;padding:8px 32px;font-size:13px;z-index:10}
nav a{margin-right:14px;color:#0f3d61;text-decoration:none}
main{max-width:1180px;margin:0 auto;padding:24px 32px 80px}
h2{border-bottom:2px solid #0f3d61;padding-bottom:6px;margin-top:38px;color:#0f3d61}
h3{margin-top:26px;color:#1c4e80}
h4{margin:18px 0 6px;color:#23303f}
table{border-collapse:collapse;width:100%;font-size:13px;margin:10px 0;background:#fff}
th,td{border:1px solid #e1e7f0;padding:5px 8px;text-align:left;vertical-align:top}
th{background:#eef3fa;position:sticky}
tr:nth-child(even){background:#fafcff}
code{background:#eef1f6;padding:1px 5px;border-radius:4px;font-size:12px}
.tag{display:inline-block;background:#0f3d61;color:#fff;border-radius:3px;padding:0 6px;font-size:11px}
.warn{background:#fff6e5;border-left:4px solid #e8a800;padding:8px 12px;margin:10px 0;font-size:13px}
.mermaid{background:#fff;border:1px solid #e1e7f0;border-radius:8px;padding:14px;overflow:auto}
details{background:#fff;border:1px solid #e6ebf3;border-radius:6px;margin:6px 0;padding:4px 10px}
summary{cursor:pointer;font-weight:600;color:#1c4e80}
.kpi{display:flex;gap:14px;flex-wrap:wrap;margin:12px 0}
.kpi div{background:#fff;border:1px solid #e1e7f0;border-radius:8px;padding:10px 16px;min-width:120px}
.kpi b{font-size:20px;color:#0f3d61;display:block}
</style></head><body>""")
P("<header><h1>鼎新 ERP（TIPTOP）測試站 — Metadata 與關聯分析</h1>")
P(f"<div class='meta'>產出日期 {GEN_DATE}　|　Oracle toptest @10.200.206.130　|　帳號 RO_M2201（唯讀）　|　全程僅 SELECT</div></header>")
P("<nav><a href='#ov'>總覽</a><a href='#verify'>已知條件驗證</a><a href='#rel'>關聯圖</a><a href='#tabs'>Table 清單</a><a href='#cols'>Column 清單</a><a href='#report'>回報</a></nav>")
P("<main>")

P("<div class='kpi'>")
P(f"<div><b>{len(owners)}</b>可見 Schema</div>")
P(f"<div><b>{len(tables)}</b>M2201 有資料表</div>")
P(f"<div><b>{len(columns):,}</b>欄位</div>")
P(f"<div><b>{len(rels)}</b>推導關聯</div>")
P("<div><b>0</b>實體外鍵</div></div>")

P("<section id='ov'><h2>1. 總覽：各 Schema 角色與資料量</h2>")
P("<div class='warn'>系統為 <b>鼎新 TIPTOP GP</b>，每家公司為獨立 schema、表結構同構；全域中文字典在 <code>DS</code>。資料列數取自 <b>最佳化統計值</b> <code>ALL_TABLES.NUM_ROWS</code>（本帳號無法對多數表即時 COUNT）。</div>")
P("<div class='mermaid'>"+h(schema_graph)+"</div>")
P("<table><tr><th>Schema</th><th>角色(推測)</th><th>表數</th><th>有資料表</th><th>資料列數(統計值)</th><th>統計日期</th></tr>")
for o in owners:
    P(f"<tr><td><code>{o['OWNER']}</code></td><td>{h(ROLE.get(o['OWNER'],'—'))}</td><td>{o['TABS']}</td><td>{o['TABS_WITH_DATA']}</td><td style='text-align:right'>{int(o['TOTAL_ROWS']):,}</td><td>{o['LAST_STAT']}</td></tr>")
P("</table></section>")

P("<section id='verify'><h2>2. 已知條件驗證</h2>")
P("""<table>
<tr><th>#</th><th>原始已知條件</th><th>結論</th></tr>
<tr><td>1</td><td>僅 DS/M2201/MDF/PATCHTEMP/SDF 有資料</td><td><b>不成立（需修正）</b>：這些確有資料，但 SDF(5,919萬)、GDF(4,937萬)、DF(1,263萬)、HW、F2204、FT 等多帳套同樣有資料；PATCHTEMP 僅 1,498 列。</td></tr>
<tr><td>2</td><td>DS.GAT_FILE.GAT01 存放表名</td><td><b>成立</b>：GAT01=表名(小寫)、GAT02=語言(0繁/2简)、GAT03=表中文名、GAT06=模組碼。</td></tr>
<tr><td>3</td><td>是否有欄位字典(GAT_ITEM)</td><td><b>修正</b>：無 GAT_ITEM；欄位字典為 <code>DS.GAQ_FILE</code>(GAQ01=欄位名、GAQ03=欄位中文名)。</td></tr>
<tr><td>4</td><td>(延伸) 實體外鍵</td><td><b>0 筆 FK</b>(ALL_CONSTRAINTS 驗證)；符合 TIPTOP 以共用代碼欄位關聯之慣例。</td></tr>
</table>
<div class='warn'>字典覆蓋：M2201 有資料的欄位中,11,756 / 11,947 (約 98%) 取得繁體中文名。</div></section>""")

P("<section id='rel'><h2>3. 關聯圖（單頭/單身，命名慣例推導）</h2>")
P("<div class='warn'>實體 FK = 0（事實）。下圖為依 TIPTOP 同前綴單據族推導之單頭→單身關聯（<b>中可信度</b>），僅顯示資料量較大的前 ~60 條。</div>")
P("<div class='mermaid'>"+h(mermaid_src)+"</div>")
P("<details><summary>展開：單頭/單身族對照表</summary><table><tr><th>單頭/主檔</th><th>中文名</th><th>單身/明細</th></tr>")
for hd in sorted(fam_detail):
    details = ", ".join(f"<code>{d}</code>" for d in fam_detail[hd])
    P(f"<tr><td><code>{hd}</code></td><td>{h(table_zh.get(hd,'—'))}</td><td>{details}</td></tr>")
P("</table></details></section>")

P("<section id='tabs'><h2>4. Table 清單（M2201 有資料,依列數排序）</h2>")
P("<table><tr><th>#</th><th>表名</th><th>中文名/說明</th><th>模組(推測)</th><th>列數(統計值)</th><th>PK</th></tr>")
for i, t in enumerate(tables, 1):
    P(f"<tr><td>{i}</td><td><code>{t['TABLE_NAME']}</code></td><td>{h(t['ZH_NAME']) or '—'}</td><td>{h(mod_label(t['MODULE']))}</td><td style='text-align:right'>{int(t['NUM_ROWS']):,}</td><td style='text-align:center'>{'✓' if t['HAS_PK']=='1' else ''}</td></tr>")
P("</table></section>")

P("<section id='cols'><h2>5. Column 清單（依模組/表分組,可展開）</h2>")
P("<div class='warn'>欄位中文名來源 <code>DS.GAQ_FILE</code>(繁體);PK 來源 <code>ALL_CONSTRAINTS</code>。</div>")
for m in order_mod:
    P(f"<h3>模組 <code>{h(m) or '(未分類)'}</code> — {h(mod_label(m))}</h3>")
    for t in by_mod[m]:
        tn = t["TABLE_NAME"]
        P(f"<details><summary><code>{tn}</code> — {h(t['ZH_NAME']) or '—'}（約 {int(t['NUM_ROWS']):,} 列,{len(cols_by_table.get(tn,[]))} 欄）</summary>")
        P("<table><tr><th>欄位</th><th>中文名/說明</th><th>型別</th><th>可空</th><th>鍵別</th></tr>")
        for c in cols_by_table.get(tn, []):
            P(f"<tr><td><code>{c['COLUMN_NAME']}</code></td><td>{h(c['ZH_NAME']) or '—'}</td><td>{h(fmt_type(c))}</td><td style='text-align:center'>{'Y' if c['NULLABLE']=='Y' else 'N'}</td><td style='text-align:center'>{key_role(c)}</td></tr>")
        P("</table></details>")
P("</section>")

P("<section id='report'><h2>6. 完成回報與未解析部分</h2>")
P("""<ul>
<li><b>實際有資料 schema</b>：SDF/GDF/MDF/DF/DS/M2201 為主,另多個公司帳套有少量資料;DFTEST*/ERPMIS 為過期舊測試帳套。</li>
<li><b>字典</b>：表字典 DS.GAT_FILE、欄位字典 DS.GAQ_FILE(修正自原推測 GAT_ITEM),皆語言別分列。</li>
<li><b>受限</b>：(1) 列數採統計值,無法即時 COUNT(權限);(2) 無實體 FK,關聯為命名慣例推導;(3) 模組中文名為 TIPTOP 慣例推測;(4) 其他公司 schema 與 M2201 同構,未逐表展開。</li>
</ul></section>""")
P("</main></body></html>")

with open(os.path.join(OUT, "erp-metadata.html"), "w", encoding="utf-8") as f:
    f.write("".join(parts))
print("HTML written:", os.path.join(OUT, "erp-metadata.html"))
print("families:", len(families), "rels:", len(rels), "mermaid entities:", ent_count)
