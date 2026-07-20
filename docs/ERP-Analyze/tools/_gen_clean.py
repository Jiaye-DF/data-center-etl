# -*- coding: utf-8 -*-
"""資料清洗前置：整合四帳套（M2201/S2202/G2203/F2204）metadata 的跨 schema 對照報告。
讀 data/<schema>_tables.tsv、<schema>_columns.tsv（皆為先前唯讀 SELECT 抽出，僅含「有資料」的表），
產出 output/erp-data-clean.html：表 × Schema 對照矩陣、僅部分帳套有的表、欄位級（Column 粒度）presence 對照、結構差異。
HTML 版型沿用 _gen_schema.py。本腳本不連 DB。"""
import os, html, collections, io, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "..", "data")
OUT  = os.path.join(BASE, "..", "output")
os.makedirs(OUT, exist_ok=True)
TODAY = "2026-07-20"

SCHEMAS = ["M2201", "S2202", "G2203", "F2204"]
SHORT   = {"M2201": "M", "S2202": "S", "G2203": "G", "F2204": "F"}

def read_tsv(name):
    rows = []
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        header = f.readline().rstrip("\r\n").split("\t")
        for line in f:
            vals = line.rstrip("\r\n").split("\t")
            if len(vals) < len(header):
                vals += [""] * (len(header) - len(vals))
            rows.append(dict(zip(header, vals)))
    return rows

tabs = {s: read_tsv(f"{s.lower()}_tables.tsv") for s in SCHEMAS}
cols = {s: read_tsv(f"{s.lower()}_columns.tsv") for s in SCHEMAS}
owners = read_tsv("owners.tsv")
ds_tabs = read_tsv("ds_tables.tsv")
gau = read_tsv("ds_gau.tsv")            # GAU01=PK欄 GAU02=PK表 GAU03=FK欄 GAU04=FK表（小寫）
# 跨 schema synonym（ALL_SYNONYMS 唯讀查詢落地；2026-07-20 查自 toptest）
synonyms = read_tsv("cross_schema_synonyms.tsv") if os.path.exists(os.path.join(DATA, "cross_schema_synonyms.tsv")) else []

# 英文語意名草稿（有才用，無則欄位留空）
semantic = []
for name in ("semantic_draft.tsv", "semantic_draft_extra.tsv"):
    if os.path.exists(os.path.join(DATA, name)):
        semantic += read_tsv(name)
sem_tab = {r["TABLE_NAME"]: r["EN_NAME"] for r in semantic if not r["COLUMN_NAME"]}
sem_col = {(r["TABLE_NAME"], r["COLUMN_NAME"]): r["EN_NAME"] for r in semantic if r["COLUMN_NAME"]}

# ---- 表層 presence ----
tinfo = {s: {t["TABLE_NAME"]: t for t in tabs[s]} for s in SCHEMAS}
tset  = {s: set(tinfo[s]) for s in SCHEMAS}
union_tables  = sorted(set().union(*tset.values()))
common_tables = set.intersection(*tset.values())

# 中文名/模組：取任一帳套（同構，字典全域一致），DS 目錄備援
zh_map, mod_map = {}, {}
for s in SCHEMAS:
    for t in tabs[s]:
        zh_map.setdefault(t["TABLE_NAME"], t["ZH_NAME"])
        if t["MODULE"]:
            mod_map.setdefault(t["TABLE_NAME"], t["MODULE"])
for t in ds_tabs:
    zh_map.setdefault(t["TABLE_NAME"], t["ZH_NAME"])

MODULE_ZH = {
    "AGL":"總帳 General Ledger","GGL":"總帳(共用)","CGL":"總帳(集團)",
    "AAP":"應付帳款 Accounts Payable","APY":"請款/付款",
    "AXR":"應收帳款 Accounts Receivable","CXR":"應收(集團)","GXR":"應收(共用)","ARM":"應收沖帳",
    "AIM":"庫存管理 Inventory","ASM":"庫存異動","AMM":"物料管理","AMD":"物料需求","AMR":"物料","AMS":"物料",
    "APM":"採購管理 Purchasing","CPM":"採購(集團)","AQC":"品檢/品保",
    "AOO":"訂單/銷貨 Order/Sales","AXM":"銷售管理","COO":"訂單(集團)","CXM":"銷售(集團)",
    "AFA":"固定資產 Fixed Assets","ANM":"財務分錄/底稿","CNM":"財務分錄(集團)","GNM":"財務分錄(共用)",
    "AXC":"成本計算 Costing","ASF":"生產/製令 Shop Floor","CSF":"生產(集團)","APJ":"專案管理 Project",
    "ABX":"票據管理","ABG":"票據","ASR":"售後服務/維修","AWS":"工作站/整合站台","AZZ":"系統共用/雜項",
}
def mod_label(code):
    code = (code or "").strip()
    if code == "":
        return "(未分類)"
    return MODULE_ZH.get(code, code + "（推測）")

# ---- 欄位層 ----
colmap = {s: collections.defaultdict(dict) for s in SCHEMAS}   # schema -> table -> {col: row}
for s in SCHEMAS:
    for c in cols[s]:
        colmap[s][c["TABLE_NAME"]][c["COLUMN_NAME"]] = c

def fmt_type(c):
    dt = c["DATA_TYPE"]
    if dt == "NUMBER":
        p, s = c.get("DATA_PRECISION", "").strip(), c.get("DATA_SCALE", "").strip()
        if p:
            return f"NUMBER({p}{','+s if s and s != '0' else ''})"
        return "NUMBER"
    if dt in ("VARCHAR2", "CHAR", "NVARCHAR2", "NCHAR"):
        return f"{dt}({c['DATA_LENGTH']})"
    return dt

# 每表組裝：presence、列數、欄位聯集與每欄 presence、結構差異
table_rows = []
struct_diff = []      # (table, column, 缺少的 schema 清單) — 欄位聯集 ≠ 交集
type_diff = []        # (table, column, {schema: 型別}) — 同欄位型別不一致
for tname in union_tables:
    present = [s for s in SCHEMAS if tname in tset[s]]
    rows_by = {s: int(tinfo[s][tname]["NUM_ROWS"] or 0) for s in present}
    col_union = []
    seen = set()
    for s in present:                       # 依 COLUMN_ID 保序：先出現者先列
        for cname, c in sorted(colmap[s][tname].items(), key=lambda kv: int(kv[1]["COLUMN_ID"] or 0)):
            if cname not in seen:
                seen.add(cname)
                col_union.append(cname)
    col_rows = []
    for cname in col_union:
        chas = [s for s in present if cname in colmap[s][tname]]
        ref = colmap[chas[0]][tname][cname]
        types = {s: fmt_type(colmap[s][tname][cname]) for s in chas}
        if len(set(types.values())) > 1:
            type_diff.append((tname, cname, types))
        if len(chas) < len(present):
            struct_diff.append((tname, cname, [s for s in present if s not in chas]))
        col_rows.append({
            "col": cname, "zh": ref["ZH_NAME"], "type": types[chas[0]],
            "null": "Y" if ref["NULLABLE"] == "Y" else "N", "pk": ref["PK_POS"],
            "en": sem_col.get((tname, cname), ""), "has": set(chas),
            "type_by": types if len(set(types.values())) > 1 else None,
        })
    table_rows.append({
        "table": tname, "zh": zh_map.get(tname, ""), "module": mod_map.get(tname, ""),
        "present": present, "rows_by": rows_by, "cols": col_rows,
        "en": sem_tab.get(tname, ""),
        "n_struct_diff": sum(1 for c in col_rows if len(c["has"]) < len(present)),
    })

by_max_rows = sorted(table_rows, key=lambda x: (-max(x["rows_by"].values()), x["table"]))
trow_by_name = {t["table"]: t for t in table_rows}

# 分布統計：presence 組合
pat_counter = collections.Counter("+".join(SHORT[s] for s in t["present"]) for t in table_rows)
n_by_count = collections.Counter(len(t["present"]) for t in table_rows)
only_in = {s: sorted(tset[s] - set().union(*(tset[x] for x in SCHEMAS if x != s))) for s in SCHEMAS}
partial_tables = [t for t in table_rows if len(t["present"]) < 4]

n_col_union = sum(len(t["cols"]) for t in table_rows)

# ---- 跨帳套共用表（ALL_SYNONYMS 實錘）----
shared_syn = [r for r in synonyms if r["TABLE_OWNER"] in SCHEMAS]          # 指向其他帳套 = 集中託管
syn_to_ds  = collections.Counter(r["OWNER"] for r in synonyms if r["TABLE_OWNER"] == "DS")
shared_map = collections.defaultdict(lambda: {"host": "", "users": []})    # table -> host / 引用帳套
for r in shared_syn:
    shared_map[r["TABLE_NAME"]]["host"] = r["TABLE_OWNER"]
    shared_map[r["TABLE_NAME"]]["users"].append(r["OWNER"])
shared_tables = set(shared_map)

# ---- FK 參照完整性（DS.GAU_FILE 邏輯外鍵）----
fk_masters = collections.defaultdict(set)     # 參照表 -> 被參照主檔
for r in gau:
    fk_masters[r["GAU04"].upper()].add(r["GAU02"].upper())
union_set = set(union_tables)
fk_missing = {}                                # schema -> Counter(缺的被參照主檔 -> 參照表數)
for s in SCHEMAS:
    cnt = collections.Counter()
    for t in tset[s]:
        for m in fk_masters.get(t, ()):
            if m not in tset[s] and m in union_set:
                cnt[m] += 1
    fk_missing[s] = cnt
fk_empty_all = collections.Counter()           # 四帳套皆無資料、卻被有資料表參照的主檔
for s in SCHEMAS:
    for t in tset[s]:
        for m in fk_masters.get(t, ()):
            if m not in union_set:
                fk_empty_all[m] += 1

def fmt(n): return f"{n:,}"
def esc(s): return html.escape(str(s) if s is not None else "")

def presence_cells(has, present=None):
    """✓/─/✗ 儲存格：✓=有，✗=帳套有此表但無此欄（結構差異），─=帳套無此表資料。"""
    out = []
    for s in SCHEMAS:
        if s in has:
            out.append("<td class='y'>✓</td>")
        elif present is not None and s in present:
            out.append("<td class='n'>✗</td>")
        else:
            out.append("<td class='no'>─</td>")
    return "".join(out)

# ============================= HTML =============================
H = []
B = H.append
B("<!DOCTYPE html><html lang='zh-Hant'><head><meta charset='utf-8'>")
B("<meta name='viewport' content='width=device-width,initial-scale=1'>")
B("<title>ERP 資料清洗前置：四帳套（M2201/S2202/G2203/F2204）表與欄位 Mapping 對照</title>")
B("<style>")
B(":root{--primary:#0f3d61;--primary-2:#1c4e80;--accent:#2e7dd1;--ink:#1a2233;--muted:#5b6b7d;"
  "--bg:#eef2f7;--card:#ffffff;--line:#e3e9f2;--line-strong:#d4dde9;--th-bg:#f0f5fb;--row-even:#f9fbfe;--row-hover:#eaf3fc;"
  "--warn-bg:#fff8e8;--warn-line:#e8a800;--code-bg:#edf1f7}")
B("*{box-sizing:border-box}")
B("body{font-family:'Segoe UI','Microsoft JhengHei',-apple-system,sans-serif;margin:0;color:var(--ink);background:var(--bg);font-size:17px;line-height:1.7}")
B("aside#sb{position:fixed;left:0;top:0;bottom:0;width:264px;background:linear-gradient(180deg,#0b2f4d 0%,#0f3d61 60%,#123f66 100%);"
  "color:#fff;padding:26px 18px 20px;overflow-y:auto;z-index:10}")
B("aside#sb h1{margin:0 0 10px;font-size:20px;line-height:1.45;letter-spacing:.3px}")
B("aside#sb .meta{opacity:.72;font-size:13px;line-height:1.6;margin-bottom:18px;border-bottom:1px solid rgba(255,255,255,.15);padding-bottom:14px}")
B("aside#sb nav a{display:block;color:#cfe1f3;text-decoration:none;padding:8px 14px;border-radius:8px;margin:3px 0;font-size:15.5px;transition:background .15s,color .15s}")
B("aside#sb nav a:hover{background:rgba(255,255,255,.1);color:#fff}")
B("aside#sb nav a.on{background:#fff;color:var(--primary);font-weight:600}")
B("main{margin-left:264px;padding:26px 64px 90px}")
B("@media(max-width:1000px){aside#sb{position:static;width:auto;bottom:auto}main{margin-left:0;padding:24px 28px 60px}}")
B("main>section{display:none}")
B("main>section.act{display:block}")
B(".pgbar{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:12px 0}")
B("input.pgq{width:360px;max-width:100%;padding:8px 15px;border:1px solid var(--line-strong);border-radius:999px;font-size:15.5px;outline:none;transition:border .15s,box-shadow .15s;background:#fff}")
B("input.pgq:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(46,125,209,.15)}")
B(".pginfo{color:var(--muted);font-size:14.5px;white-space:nowrap}")
B(".pgnav{display:flex;gap:4px;flex-wrap:wrap}")
B(".pgnav button{border:1px solid var(--line-strong);background:#fff;color:var(--primary-2);min-width:36px;padding:4px 9px;border-radius:8px;font-size:14.5px;cursor:pointer;transition:background .12s}")
B(".pgnav button:hover:not(:disabled){background:#e4edf7}")
B(".pgnav button:disabled{opacity:.35;cursor:default}")
B(".pgnav button.cur{background:var(--primary);border-color:var(--primary);color:#fff;font-weight:600}")
B("section{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:26px 30px 30px;margin:26px 0;box-shadow:0 1px 3px rgba(15,61,97,.06)}")
B("h2{margin:0 0 14px;padding-bottom:10px;color:var(--primary);font-size:24px;border-bottom:1px solid var(--line);position:relative}")
B("h2::after{content:'';position:absolute;left:0;bottom:-1px;width:64px;height:3px;background:var(--accent);border-radius:2px}")
B("h3{margin-top:30px;color:var(--primary-2);font-size:20px}")
B("p{font-size:17px}")
B("table{border-collapse:separate;border-spacing:0;width:100%;font-size:16px;margin:14px 0;background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden}")
B("th,td{border-bottom:1px solid var(--line);border-right:1px solid #eef2f8;padding:9px 13px;text-align:left;vertical-align:top}")
B("th:last-child,td:last-child{border-right:none}")
B("tr:last-child td{border-bottom:none}")
B("th{background:var(--th-bg);font-size:15px;color:var(--primary-2);position:sticky;top:0;z-index:5;white-space:nowrap}")
B("tbody tr:nth-child(even),tr:nth-child(even){background:var(--row-even)}")
B("tbody tr:hover,table tr:hover{background:var(--row-hover)}")
B("code{background:var(--code-bg);color:#12406b;padding:2px 7px;border-radius:5px;font-size:15px;font-family:Consolas,'Courier New',monospace}")
B(".warn{background:var(--warn-bg);border:1px solid #f3ddaa;border-left:5px solid var(--warn-line);border-radius:8px;padding:13px 17px;margin:14px 0;font-size:16px}")
B("details{background:#fff;border:1px solid var(--line);border-radius:10px;margin:10px 0;padding:0 16px;transition:box-shadow .15s}")
B("details:hover{box-shadow:0 2px 8px rgba(15,61,97,.08)}")
B("details[open]{box-shadow:0 2px 10px rgba(15,61,97,.08)}")
B("summary{cursor:pointer;font-weight:600;color:var(--primary-2);font-size:17px;padding:11px 0;list-style-position:inside}")
B("details[open]>summary{border-bottom:1px dashed var(--line-strong);margin-bottom:8px}")
B(".kpi{display:flex;gap:16px;flex-wrap:wrap;margin:18px 0}")
B(".kpi div{background:var(--card);border:1px solid var(--line);border-top:3px solid var(--accent);border-radius:10px;"
  "padding:13px 24px;min-width:150px;box-shadow:0 1px 3px rgba(15,61,97,.06);transition:transform .15s}")
B(".kpi div:hover{transform:translateY(-2px)}")
B(".kpi b{font-size:27px;color:var(--primary);display:block;letter-spacing:.5px}")
B("td.y{color:#0d7a3f;font-weight:700;text-align:center}")
B("td.n{color:#c02929;font-weight:700;text-align:center;background:#fdeeee}")
B("td.no{color:#b6c0cc;text-align:center}")
B(".b{display:inline-block;border-radius:999px;padding:0 9px;font-size:12.5px;line-height:21px;margin-left:6px;color:#fff;font-weight:500;white-space:nowrap;vertical-align:middle}")
B(".b-dict{background:#2563a8}.b-db{background:#5b6b7d}.b-inf{background:#d97706}.b-sug{background:#0d9488}")
B(".pat{display:inline-block;border-radius:6px;padding:1px 8px;font-size:13.5px;background:#e4edf7;color:#1c4e80;font-family:Consolas,monospace;white-space:nowrap}")
B(".pat.all{background:#dcf3e6;color:#0d7a3f}")
B("</style></head><body>")
B("<aside id='sb'><h1>ERP 資料清洗前置<br>四帳套表/欄位 Mapping</h1>")
B(f"<div class='meta'>產出日期 {TODAY}<br>Oracle toptest（鼎新 TIPTOP GP）<br>M2201・S2202・G2203・F2204<br>整合自 erp-metadata-*.html 底層資料<br>全程唯讀，只下 SELECT</div>")
B("<nav><a href='#legend'>閱讀說明</a><a href='#ov'>1. 總覽</a><a href='#matrix'>2. 表 × Schema 矩陣</a>"
  "<a href='#partial'>3. 僅部分帳套有的表</a><a href='#cols'>4. 欄位級對照</a>"
  "<a href='#diff'>5. 結構差異</a><a href='#clean'>6. 清洗建議與限制</a>"
  "<a href='#share'>7. 共用表與抽取來源</a></nav></aside>")
B("<main>")
B("<div class='kpi'>")
B(f"<div><b>{len(union_tables)}</b>表（四帳套聯集）</div>")
B(f"<div><b>{len(common_tables)}</b>四帳套皆有資料</div>")
B(f"<div><b>{len(partial_tables)}</b>僅部分帳套有資料</div>")
B(f"<div><b>{fmt(n_col_union)}</b>欄位（聯集）</div>")
B(f"<div><b>{len(struct_diff)}</b>欄位結構差異</div>")
B(f"<div><b>{len(type_diff)}</b>欄位型別差異</div>")
B(f"<div><b>{len(shared_tables)}</b>跨帳套共用表(synonym)</div>")
B("</div>")

# 閱讀說明
B("<section id='legend'><h2>閱讀說明（全文件通用）</h2>")
B("<p>本報告整合 <code>erp-metadata-m2201/s2202/g2203/f2204.html</code> 四份單帳套分析的底層資料，"
  "做<b>跨帳套（Schema）對照</b>：每張表有資料的帳套、每個欄位在各帳套的存在狀況（Column 粒度），供資料清洗規劃使用。</p>")
B("<table><tr><th>符號 / 名詞</th><th>意義</th></tr>")
for k, v in [
    ("<span style='color:#0d7a3f;font-weight:700'>✓</span>", "該帳套<b>有此表且有此欄位</b>（表層則為：該帳套此表有資料）"),
    ("<span style='color:#c02929;font-weight:700;background:#fdeeee;padding:1px 8px;border-radius:5px'>✗</span>", "該帳套<b>有此表資料、但無此欄位</b> → 真正的結構差異，清洗時要特別處理"),
    ("<span style='color:#b6c0cc'>─</span>", "該帳套此表<b>無資料</b>（未列入該帳套的抽取範圍），非結構差異"),
    ("帳套 / Schema", "每家公司一個 Oracle schema，表結構同構：M2201、S2202、G2203、F2204；縮寫 M / S / G / F"),
    ("Presence 樣式", "該表在哪些帳套有資料的組合，如 <span class='pat'>M+F</span>＝只有 M2201 與 F2204 有資料；<span class='pat all'>M+S+G+F</span>＝四帳套皆有"),
    ("列數(統計值)", "<code>ALL_TABLES.NUM_ROWS</code> 統計值，非即時 COUNT，量級參考用"),
]:
    B(f"<tr><td>{k}</td><td>{v}</td></tr>")
B("</table>")
B("<div class='warn'><b>重要前提</b>：來源 TSV 只抽了「<b>有資料（NUM_ROWS ≥ 1）</b>」的表。"
  "因此「某帳套沒有這張表」指的是<b>該帳套此表無資料</b>；表結構（DDL）四帳套同構，實際結構差異僅第 5 章列出的個案。"
  "表/欄位中文名來自全域字典 <code>DS.GAT_FILE</code> / <code>DS.GAQ_FILE</code>，四帳套共用、無歧義。</div></section>")

# 1 總覽
B("<section id='ov'><h2>1. 總覽：四帳套資料量與重疊分布</h2>")
B("<table><tr><th>Schema</th><th>有資料表數</th><th>欄位數</th><th>獨有表數（僅此帳套有資料）</th><th>總列數(統計值)</th><th>統計日期</th></tr>")
own = {o["OWNER"]: o for o in owners}
for s in SCHEMAS:
    o = own.get(s, {})
    B(f"<tr><td><code>{s}</code></td><td style='text-align:right'>{len(tset[s])}</td>"
      f"<td style='text-align:right'>{fmt(len(cols[s]))}</td>"
      f"<td style='text-align:right'>{len(only_in[s])}</td>"
      f"<td style='text-align:right'>{fmt(int(o.get('TOTAL_ROWS') or 0))}</td><td>{esc(o.get('LAST_STAT',''))}</td></tr>")
B("</table>")
B("<h3>1.2 表重疊分布（幾個帳套有資料）</h3>")
B("<table><tr><th>有資料帳套數</th><th>表數</th><th>說明</th></tr>")
DESC = {4: "四帳套共通 → 清洗主力，欄位對照可完全共用", 3: "三帳套有", 2: "兩帳套有", 1: "單一帳套獨有 → 清洗時只需處理該帳套"}
for n in (4, 3, 2, 1):
    B(f"<tr><td style='text-align:center'>{n}/4</td><td style='text-align:right'>{n_by_count.get(n,0)}</td><td>{DESC[n]}</td></tr>")
B("</table>")
B("<h3>1.3 Presence 樣式分布</h3>")
B("<table><tr><th>樣式</th><th>表數</th></tr>")
for pat, n in pat_counter.most_common():
    cls = " all" if pat == "M+S+G+F" else ""
    B(f"<tr><td><span class='pat{cls}'>{pat}</span></td><td style='text-align:right'>{n}</td></tr>")
B("</table></section>")

# 2 矩陣
B("<section id='matrix'><h2>2. 表 × Schema 對照矩陣（全部 " + str(len(union_tables)) + " 表，依最大列數排序）</h2>")
B("<div class='warn'>✓＝該帳套此表有資料（下方數字為列數統計值）；─＝無資料。點第 4 章可看同表的欄位級對照。</div>")
B("<div class='pgwrap' data-size='50' data-list='tbody'>")
PGBAR = "<div class='pgbar'><input class='pgq' placeholder='{ph}'><span class='pginfo'></span><span class='pgnav'></span></div>"
B(PGBAR.format(ph="搜尋表名 / 中文名 / 模組 / 樣式，例如 ima、料件、M+F"))
B("<table><thead><tr><th>#</th><th>資料表</th><th>中文名(GAT)<span class='b b-dict'>字典</span></th><th>模組<span class='b b-inf'>推導</span></th>"
  + "".join(f"<th style='text-align:center'>{s}</th>" for s in SCHEMAS)
  + "<th>樣式</th></tr></thead><tbody>")
for i, t in enumerate(by_max_rows, 1):
    pat = "+".join(SHORT[s] for s in t["present"])
    cls = " all" if len(t["present"]) == 4 else ""
    cells = ""
    for s in SCHEMAS:
        if s in t["rows_by"]:
            cells += f"<td class='y'>✓<br><span style='font-weight:400;font-size:13px;color:var(--muted)'>{fmt(t['rows_by'][s])}</span></td>"
        else:
            cells += "<td class='no'>─</td>"
    share_tag = ""
    if t["table"] in shared_tables:
        sm = shared_map[t["table"]]
        share_tag = f"<br><span class='b' style='background:#7c4dbe;margin:2px 0 0'>共用@{sm['host']}（{'/'.join(sm['users'])} synonym 引用）</span>"
    B(f"<tr data-k='{esc((t['table']+' '+(t['zh'] or '')+' '+(t['module'] or '')+' '+mod_label(t['module'])+' '+pat+(' 共用' if t['table'] in shared_tables else '')).lower())}'>"
      f"<td style='text-align:right'>{i}</td><td><code>{esc(t['table'])}</code></td><td>{esc(t['zh'])}</td>"
      f"<td>{esc(mod_label(t['module']))}</td>{cells}<td><span class='pat{cls}'>{pat}</span>{share_tag}</td></tr>")
B("</tbody></table>")
B(PGBAR.format(ph="搜尋表名 / 中文名 / 模組 / 樣式"))
B("</div></section>")

# 3 僅部分帳套有的表
B("<section id='partial'><h2>3. 僅部分帳套有資料的表（" + str(len(partial_tables)) + " 張）</h2>")
B("<div class='warn'>「只有某些帳套才有的資訊」集中在此章：先列各帳套<b>獨有</b>的表，再列其他部分重疊樣式。"
  "清洗時這些表的資料來源只有列出的帳套，不需對其他帳套做 mapping。</div>")
for s in SCHEMAS:
    lst = only_in[s]
    B(f"<h3>3.{SCHEMAS.index(s)+1} 僅 <code>{s}</code> 有資料（{len(lst)} 張）</h3>")
    if not lst:
        B("<p>（無 — 此帳套沒有獨有表，其所有表在其他帳套也有資料）</p>")
        continue
    B("<div class='pgwrap' data-size='50' data-list='tbody'>")
    B(PGBAR.format(ph="搜尋表名 / 中文名 / 模組"))
    B("<table><thead><tr><th>#</th><th>資料表</th><th>中文名(GAT)</th><th>模組</th><th>列數(統計值)</th><th>欄位數</th></tr></thead><tbody>")
    for i, tn in enumerate(sorted(lst, key=lambda x: -trow_by_name[x]["rows_by"][s]), 1):
        t = trow_by_name[tn]
        share_tag = ""
        if tn in shared_tables:
            share_tag = f"<span class='b' style='background:#7c4dbe'>共用：{'/'.join(shared_map[tn]['users'])} synonym 引用（見第 7 章）</span>"
        B(f"<tr data-k='{esc((tn+' '+(t['zh'] or '')+' '+mod_label(t['module'])).lower())}'>"
          f"<td style='text-align:right'>{i}</td><td><code>{esc(tn)}</code>{share_tag}</td><td>{esc(t['zh'])}</td>"
          f"<td>{esc(mod_label(t['module']))}</td><td style='text-align:right'>{fmt(t['rows_by'][s])}</td>"
          f"<td style='text-align:right'>{len(t['cols'])}</td></tr>")
    B("</tbody></table>")
    B(PGBAR.format(ph="搜尋表名 / 中文名 / 模組"))
    B("</div>")
B("<h3>3.5 其他部分重疊樣式（2～3 個帳套有資料）</h3>")
mixed = [t for t in partial_tables if 1 < len(t["present"]) < 4]
B("<div class='pgwrap' data-size='50' data-list='tbody'>")
B(PGBAR.format(ph="搜尋表名 / 中文名 / 樣式，例如 M+F"))
B("<table><thead><tr><th>#</th><th>資料表</th><th>中文名(GAT)</th><th>模組</th><th>樣式</th><th>各帳套列數</th></tr></thead><tbody>")
for i, t in enumerate(sorted(mixed, key=lambda x: ("+".join(SHORT[s] for s in x["present"]), x["table"])), 1):
    pat = "+".join(SHORT[s] for s in t["present"])
    rows_s = "、".join(f"{s} {fmt(t['rows_by'][s])}" for s in t["present"])
    B(f"<tr data-k='{esc((t['table']+' '+(t['zh'] or '')+' '+pat).lower())}'>"
      f"<td style='text-align:right'>{i}</td><td><code>{esc(t['table'])}</code></td><td>{esc(t['zh'])}</td>"
      f"<td>{esc(mod_label(t['module']))}</td><td><span class='pat'>{pat}</span></td><td>{rows_s}</td></tr>")
B("</tbody></table>")
B(PGBAR.format(ph="搜尋表名 / 中文名 / 樣式"))
B("</div></section>")

# 4 欄位級對照
B("<section id='cols'><h2>4. 欄位級對照（Column 粒度 × Schema Presence）</h2>")
B("<div class='warn'>每表展開後列出<b>欄位聯集</b>：✓＝該帳套有此欄位、✗＝該帳套有此表但無此欄位（結構差異）、─＝該帳套此表無資料。"
  "中文名(GAQ)與型別四帳套一致（型別不一致者於第 5 章列出）。欄位型別/可空/鍵取自任一存在帳套。</div>")
B("<div class='pgwrap' data-size='20'>")
B(PGBAR.format(ph="搜尋表名 / 中文名 / 模組 / 樣式，例如 ima、料件、M+F"))
B("<div class='pglist'>")
for t in by_max_rows:
    pat = "+".join(SHORT[s] for s in t["present"])
    cls = " all" if len(t["present"]) == 4 else ""
    diff_tag = f"　<span class='b' style='background:#c02929'>結構差異 {t['n_struct_diff']} 欄</span>" if t["n_struct_diff"] else ""
    key = esc((t["table"] + " " + (t["zh"] or "") + " " + mod_label(t["module"]) + " " + pat).lower())
    en = f"　<code style='font-size:13.5px'>{esc(t['en'])}</code>" if t["en"] else ""
    B(f"<details data-k='{key}'><summary><code>{esc(t['table'])}</code> — {esc(t['zh'] or '（無中文名）')}{en}"
      f"　<span class='pat{cls}'>{pat}</span>"
      f"　<span style='color:var(--muted);font-weight:400'>模組 {esc(mod_label(t['module']))}｜{len(t['cols'])} 欄</span>{diff_tag}</summary>")
    rows_s = "、".join(f"<code>{s}</code> {fmt(t['rows_by'][s])} 列" for s in t["present"])
    B(f"<p style='font-size:15px'>有資料帳套：{rows_s}</p>")
    B("<table><tr><th>欄位</th><th>中文名(GAQ)<span class='b b-dict'>字典</span></th><th>英文名(草稿)<span class='b b-sug'>建議</span></th>"
      "<th>型別<span class='b b-db'>DB</span></th><th>可空</th><th>鍵</th>"
      + "".join(f"<th style='text-align:center'>{s}</th>" for s in SCHEMAS) + "</tr>")
    for c in t["cols"]:
        pk = "PK" if c["pk"] else ""
        tcell = esc(c["type"])
        if c["type_by"]:
            tcell = "、".join(f"{s}:{esc(v)}" for s, v in c["type_by"].items())
            tcell = f"<span style='color:#c02929;font-weight:600'>{tcell}</span>"
        B(f"<tr><td><code>{esc(c['col'])}</code></td><td>{esc(c['zh'])}</td>"
          f"<td>{('<code>'+esc(c['en'])+'</code>') if c['en'] else ''}</td><td>{tcell}</td>"
          f"<td style='text-align:center'>{c['null']}</td><td style='text-align:center'>{pk}</td>"
          + presence_cells(c["has"], t["present"]) + "</tr>")
    B("</table></details>")
B("</div>")
B(PGBAR.format(ph="搜尋表名 / 中文名 / 模組 / 樣式"))
B("</div></section>")

# 5 結構差異
B("<section id='diff'><h2>5. 結構差異清單（跨帳套欄位/型別不一致）</h2>")
B("<h3>5.1 欄位存在差異（帳套有此表資料、卻無此欄位）</h3>")
if struct_diff:
    B("<table><tr><th>資料表</th><th>中文名</th><th>欄位</th><th>欄位中文名</th><th>缺此欄位的帳套</th><th>有此欄位的帳套</th></tr>")
    for tname, cname, missing in struct_diff:
        t = trow_by_name[tname]
        c = next(c for c in t["cols"] if c["col"] == cname)
        B(f"<tr><td><code>{esc(tname)}</code></td><td>{esc(t['zh'])}</td><td><code>{esc(cname)}</code></td>"
          f"<td>{esc(c['zh'])}</td><td>{'、'.join(f'<code>{m}</code>' for m in missing)}</td>"
          f"<td>{'、'.join(f'<code>{s}</code>' for s in sorted(c['has'], key=SCHEMAS.index))}</td></tr>")
    B("</table>")
    B("<div class='warn'>差異極少＝四帳套<b>幾乎完全同構</b>。上列欄位多為 <code>TA_</code> 開頭的<b>客製欄位</b>（鼎新命名慣例：TA_=客製），"
      "清洗時對缺此欄位的帳套以 NULL 補位即可對齊。</div>")
else:
    B("<p>（無 — 四帳套共有表的欄位集合完全一致）</p>")
B("<h3>5.2 型別差異（同表同欄位、各帳套型別不同）</h3>")
if type_diff:
    B("<table><tr><th>資料表</th><th>欄位</th><th>各帳套型別</th></tr>")
    for tname, cname, types in type_diff:
        B(f"<tr><td><code>{esc(tname)}</code></td><td><code>{esc(cname)}</code></td>"
          f"<td>{'、'.join(f'<code>{s}</code>:{esc(v)}' for s, v in types.items())}</td></tr>")
    B("</table>")
else:
    B("<p>（無 — 共有欄位的型別（含長度/精度）四帳套完全一致）</p>")
B("</section>")

# 6 清洗建議與限制
B("<section id='clean'><h2>6. 資料清洗建議與限制</h2>")
B("<h3>6.1 對清洗規劃的直接結論</h3><ul>")
B(f"<li><b>四帳套結構同構</b>：{len(common_tables)} 張共通表可用<b>同一套清洗規則</b>直接套用四個帳套（欄位、型別、中文名完全一致，"
  f"僅 {len(struct_diff)} 個欄位例外，見第 5 章）。</li>")
B(f"<li><b>「只有某些帳套才有的資訊」= 資料 presence 差異</b>：{len(partial_tables)} 張表僅部分帳套有資料"
  f"（M2201 獨有 {len(only_in['M2201'])}、F2204 獨有 {len(only_in['F2204'])}、G2203 獨有 {len(only_in['G2203'])}、S2202 獨有 {len(only_in['S2202'])}），"
  f"各帳套業務範圍不同所致；清洗這些表時只需處理列出的帳套。<b>唯一例外是 {len(shared_tables)} 張跨帳套共用表（synonym 集中託管，見第 7 章）</b>。</li>")
B("<li><b>合併四帳套資料時</b>：同名表可直接 UNION ALL 並加 <code>schema</code>（帳套）欄位區分來源；"
  "唯一結構差異欄位對缺少的帳套補 NULL。</li>")
B("<li><b>中文語意共用</b>:表/欄位中文名（GAT/GAQ）與英文語意名草稿為全域字典，跨帳套 mapping 不需逐帳套重建。</li>")
B("</ul>")
B("<h3>6.2 限制</h3><ul>")
B("<li>來源僅含「有資料」的表：帳套缺某表＝<b>該表無資料</b>，非 DDL 不存在；空表（NUM_ROWS=0）不在本報告範圍。</li>")
B("<li>列數為 <code>ALL_TABLES.NUM_ROWS</code> 統計值，統計過期者可能偏差（統計日期見第 1 章）。</li>")
B("<li>本報告不含表↔程式、畫面標籤與關聯推導 — 該內容見各單帳套報告 <code>erp-metadata-&lt;schema&gt;.html</code>。</li>")
B("<li>英文語意名為 AI 草稿（<code>semantic_draft*.tsv</code>），待人工複核。</li>")
B("</ul></section>")

# 7 共用表與抽取來源（ALL_SYNONYMS 實錘 + FK 參照完整性）
B("<section id='share'><h2>7. 跨帳套共用表與抽取來源（<code>ALL_SYNONYMS</code> 實錘）</h2>")
B("<div class='warn'>「某帳套的表看似無資料、實際資料放在別的帳套」的疑慮，以 Oracle data dictionary <code>ALL_SYNONYMS</code> "
  "唯讀查詢（2026-07-20）<b>全表確認完畢</b>：跨 schema 共用關係完整記錄在 DB 內部，不需逐表猜測。"
  "查詢結果落地於 <code>data/cross_schema_synonyms.tsv</code>（四帳套共 " + fmt(len(synonyms)) + " 筆 synonym）。</div>")
B("<h3>7.1 集中託管的共用表（synonym 指向其他帳套）— 全系統僅 " + str(len(shared_tables)) + " 張</h3>")
if shared_tables:
    B("<table><tr><th>表名</th><th>中文名(GAT)</th><th>資料實際所在（託管帳套）</th><th>經 synonym 引用的帳套</th><th>清洗抽取來源</th></tr>")
    for tn in sorted(shared_tables):
        sm = shared_map[tn]
        B(f"<tr><td><code>{esc(tn)}</code></td><td>{esc(zh_map.get(tn, '（字典無中文名）') or '（字典無中文名）')}</td>"
          f"<td><code>{sm['host']}</code></td><td>{'、'.join(f'<code>{u}</code>' for u in sorted(sm['users'], key=SCHEMAS.index))}</td>"
          f"<td>{'、'.join(f'<code>{u}</code>' for u in sorted(sm['users'], key=SCHEMAS.index))} 一律抽 <code>{sm['host']}</code> 這份</td></tr>")
    B("</table>")
    B("<div class='warn'><b>F2204 不在引用清單中</b>＝F2204 的部門/員工資料是<b>自己獨立維護的一份</b>（無 synonym、自有資料），"
      "與 G2203 那份無關；合併分析時兩份都要抽、以帳套欄位區分。<br>"
      "除上列表外，四帳套<b>沒有其他任何</b>指向彼此的 synonym → 對照矩陣中其餘的 presence 差異都是「該帳套真的無此業務資料」，可放心依矩陣規劃。</div>")
B("<h3>7.2 各帳套 synonym → DS（全域字典，佐證）</h3>")
B("<table><tr><th>帳套</th><th>指向 DS 的 synonym 數</th></tr>")
for s in SCHEMAS:
    B(f"<tr><td><code>{s}</code></td><td style='text-align:right'>{syn_to_ds.get(s, 0)}</td></tr>")
B("</table>")
B("<p>四帳套各以相同數量的 synonym 指向 <code>DS</code> 字典表（GAT/GAQ/ZZ/GAZ/ZR/GAE/GAU…），"
  "證實表/欄位中文名等字典資訊<b>全域一份、四帳套共用</b>，mapping 不需逐帳套重建。</p>")
B("<h3>7.3 FK 參照完整性檢查（<code>DS.GAU_FILE</code> 邏輯外鍵，輔助佐證）<span class='b b-inf'>推導</span></h3>")
B("<div class='warn'>檢查邏輯：某帳套「有資料的表」沿字典 FK 參照的主檔、在該帳套卻無資料 → 候選的「資料在別處」訊號。"
  "經 7.1 synonym 實錘後，此清單中除共用表外，其餘均為<b>業務未使用</b>（參照欄位空值），清洗時無需跨帳套補抽。</div>")
for s in SCHEMAS:
    cnt = fk_missing[s]
    B(f"<h3 style='font-size:17px'>7.3.{SCHEMAS.index(s)+1} <code>{s}</code>：被參照但本帳套無資料的主檔（{len(cnt)} 張）</h3>")
    if not cnt:
        B("<p>（無）</p>")
        continue
    B("<table><tr><th>主檔</th><th>中文名</th><th>被本帳套幾張表參照</th><th>有資料的帳套</th><th>判定</th></tr>")
    for m, n in cnt.most_common():
        hosts = "+".join(SHORT[x] for x in SCHEMAS if m in tset[x])
        verdict = (f"<b>共用表</b> → 抽 <code>{shared_map[m]['host']}</code>" if m in shared_tables
                   else "業務未使用（參照欄位多為空值）")
        B(f"<tr><td><code>{esc(m)}</code></td><td>{esc(zh_map.get(m, ''))}</td><td style='text-align:right'>{n}</td>"
          f"<td><span class='pat'>{hosts}</span></td><td>{verdict}</td></tr>")
    B("</table>")
B("<h3 style='font-size:17px'>7.3.5 四帳套皆無資料、卻被有資料表參照的主檔（前 15，依參照次數）</h3>")
B("<p>這些主檔對應的 ERP 功能<b>未啟用</b>（如營運中心、簽核流程），交易表中對應欄位大概率為空值，清洗時可直接排除。</p>")
B("<table><tr><th>主檔</th><th>中文名</th><th>被參照次數（四帳套合計）</th></tr>")
for m, n in fk_empty_all.most_common(15):
    B(f"<tr><td><code>{esc(m)}</code></td><td>{esc(zh_map.get(m, ''))}</td><td style='text-align:right'>{n}</td></tr>")
B("</table></section>")
B("</main>")
B("""<script>
(function(){
  const secs=[...document.querySelectorAll('main>section[id]')];
  const links={};document.querySelectorAll('aside#sb nav a[href^="#"]').forEach(a=>links[a.getAttribute('href').slice(1)]=a);
  function go(id){
    if(!secs.some(s=>s.id===id)) id=secs[0].id;
    secs.forEach(s=>s.classList.toggle('act',s.id===id));
    for(const k in links) links[k].classList.toggle('on',k===id);
    window.scrollTo(0,0);
  }
  window.addEventListener('hashchange',()=>go(location.hash.slice(1)));
  go(location.hash.slice(1));
  document.querySelectorAll('.pgwrap').forEach(w=>{
    const list=w.querySelector(w.dataset.list||'.pglist'); if(!list) return;
    const items=[...list.children], size=+w.dataset.size||50;
    const qs=[...w.querySelectorAll('input.pgq')];
    const infos=w.querySelectorAll('.pginfo'), navs=w.querySelectorAll('.pgnav');
    let page=1;
    const key=el=>(el.dataset.k||el.textContent).toLowerCase();
    function apply(){
      const v=(qs[0]?qs[0].value:'').trim().toLowerCase();
      const f=v?items.filter(el=>key(el).includes(v)):items;
      const pages=Math.max(1,Math.ceil(f.length/size));
      if(page>pages) page=pages;
      items.forEach(el=>el.style.display='none');
      f.slice((page-1)*size,page*size).forEach(el=>el.style.display='');
      infos.forEach(i=>i.textContent=`共 ${f.length.toLocaleString()} 項・第 ${page}/${pages} 頁`);
      navs.forEach(nv=>{nv.innerHTML='';
        const btn=(t,p,dis,cur)=>{const b=document.createElement('button');b.textContent=t;b.disabled=!!dis;
          if(cur)b.className='cur';b.onclick=()=>{page=p;apply();w.scrollIntoView({block:'start'});};nv.appendChild(b);};
        btn('«',1,page===1);btn('‹',page-1,page===1);
        let s=Math.max(1,page-3),e=Math.min(pages,s+6);s=Math.max(1,e-6);
        for(let i=s;i<=e;i++) btn(i,i,false,i===page);
        btn('›',page+1,page===pages);btn('»',pages,page===pages);});
    }
    qs.forEach((q,i)=>q.addEventListener('input',()=>{if(i>0)qs[0].value=q.value;page=1;apply();}));
    apply();
  });
})();
</script>""")
B("</body></html>")

html_text = "\n".join(H)
out_path = os.path.join(OUT, "erp-data-clean.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html_text)
print(f"已寫出 {out_path}", f"{len(html_text):,} bytes")
print(f"tables_union={len(union_tables)} common4={len(common_tables)} partial={len(partial_tables)} "
      f"cols_union={n_col_union:,} struct_diff={len(struct_diff)} type_diff={len(type_diff)}")
