# -*- coding: utf-8 -*-
"""單一公司帳套 schema 版產生器：DS 字典（GAT/GAQ/ZZ/GAZ/ZR/GAE/GAU）↔ <SCHEMA> 表/欄位 ↔ TipTop 畫面(程式)。
用法：python _gen_schema.py S2202（另需先抽出 data/<schema>_tables.tsv、<schema>_columns.tsv）。
由 ../data/*.tsv 產出 ../output/erp-metadata-<schema>.html；HTML 結構沿用 _gen_screen.py（M2201 版）。
資料來源皆為先前以唯讀 SELECT 抽出的 TSV，本腳本不連 DB。"""
import os, html, collections, io, sys, bisect

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if len(sys.argv) < 2:
    print("用法：python _gen_schema.py <SCHEMA>（如 S2202 / G2203 / F2204）")
    sys.exit(1)
SCHEMA = sys.argv[1].upper()
SLC    = SCHEMA.lower()
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "..", "data")
OUT  = os.path.join(BASE, "..", "output")
os.makedirs(OUT, exist_ok=True)
TODAY = "2026-07-20"

def read_tsv(name):
    """單純以 tab 切割（資料含引號字元，避免 csv 引號規則吞行）。"""
    rows = []
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        header = f.readline().rstrip("\r\n").split("\t")
        for line in f:
            vals = line.rstrip("\r\n").split("\t")
            if len(vals) < len(header):
                vals += [""] * (len(header) - len(vals))
            rows.append(dict(zip(header, vals)))
    return rows

owners   = read_tsv("owners.tsv")                # OWNER TABS TABS_WITH_DATA TOTAL_ROWS LAST_STAT
tables   = read_tsv(f"{SLC}_tables.tsv")         # TABLE_NAME NUM_ROWS ZH_NAME MODULE HAS_PK
columns  = read_tsv(f"{SLC}_columns.tsv")        # TABLE_NAME COLUMN_NAME DATA_TYPE ... ZH_NAME PK_POS
programs = read_tsv("ds_programs.tsv")           # PROG MODULE PTYPE ZH_NAME
zr       = read_tsv("ds_zr.tsv")                 # ZR01 ZR02 ZR03
gae      = read_tsv("ds_gae.tsv")                # GAE01 GAE02 GAE04
ds_tabs  = read_tsv("ds_tables.tsv")             # TABLE_NAME NUM_ROWS ZH_NAME MODULE（DS 全部）
gau      = read_tsv("ds_gau.tsv")                # GAU01=PK欄 GAU02=PK表 GAU03=FK欄 GAU04=FK表

# ---- 程式字典（DS.ZZ_FILE + DS.GAZ_FILE）----
prog_zh  = {p["PROG"]: (p["ZH_NAME"] or "").strip() for p in programs}
prog_mod = {p["PROG"]: (p["MODULE"] or "").strip() for p in programs}

KIND_SCORE = {"i": 2, "t": 2, "m": 1}   # 程式代號第4碼：i=建檔 t=交易（TipTop 命名慣例，推導）

def prog_kind(p):
    return p[3].lower() if len(p) > 3 else ""

def rank_prog(prog, acts):
    w = len(acts & {"I", "U", "D"})
    name_score = 1 if "維護" in prog_zh.get(prog, "") else 0
    return (-w, -KIND_SCORE.get(prog_kind(prog), 0), -name_score, prog)

# ---- 表 ↔ 程式（DS.ZR_FILE，全域字典，各帳套共用）----
tbl_progs = collections.defaultdict(lambda: collections.defaultdict(set))
for r in zr:
    tbl_progs[r["ZR02"].strip().lower()][r["ZR01"].strip()].add(r["ZR03"].strip())

# ---- 欄位 ↔ 畫面欄位名稱（DS.GAE_FILE，繁中）----
label_by_form = collections.defaultdict(dict)
label_count   = collections.defaultdict(collections.Counter)
field_forms   = collections.defaultdict(set)
for r in gae:
    form, field, label = r["GAE01"].strip(), r["GAE02"].strip().lower(), (r["GAE04"] or "").strip()
    if not label:
        continue
    label_by_form[form][field] = label
    label_count[field][label] += 1
    field_forms[field].add(form)

forms_sorted = sorted(label_by_form.keys())
_prog_forms_cache = {}

def prog_forms(prog):
    """該程式的主畫面＋子畫面（gae01 以程式代號開頭），排序表 + bisect 取前綴區間。"""
    if prog not in _prog_forms_cache:
        lo = bisect.bisect_left(forms_sorted, prog)
        hi = bisect.bisect_right(forms_sorted, prog + "￿")
        _prog_forms_cache[prog] = forms_sorted[lo:hi]
    return _prog_forms_cache[prog]

def prog_label(prog, field):
    d = label_by_form.get(prog)
    if d and field in d:
        return d[field]
    for f in prog_forms(prog):
        if field in label_by_form[f]:
            return label_by_form[f][field]
    return ""

def all_labels(field):
    """該欄位在全系統畫面上的所有相異名稱：[(名稱, 出現畫面數)]，依畫面數排序。"""
    c = label_count.get(field)
    if not c:
        return []
    return c.most_common()

# ---- <SCHEMA> 欄位 ----
cols_by_table = collections.defaultdict(list)
for c in columns:
    cols_by_table[c["TABLE_NAME"]].append(c)

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

ROLE = {
 "DS":"**資料字典/系統設定**（GAT/GAQ/ZZ/GAZ/ZR/GAE 等字典表）","DS_REPORT":"報表暫存",
 "M2201":"公司帳套（erp-metadata.html 主要分析對象）",
 "SDF":"公司帳套（資料量最大）","GDF":"公司帳套","MDF":"公司帳套","DF":"公司帳套",
 "HW":"公司帳套","HWTAX":"公司帳套(稅)","FT":"公司帳套",
 "F2204":"公司帳套","S2202":"公司帳套","G2203":"公司帳套","TDF":"公司帳套",
 "NODATA":"範本/空帳套(推測)","SKL":"帳套(複本)","SKY":"帳套(複本)","SLE":"帳套(複本)",
 "SLY":"帳套(複本)","XCAR":"帳套(複本)","GLY":"帳套(複本)","SPA":"帳套(複本)",
 "DFTEST":"舊測試帳套(統計過期)","DFTEST2":"舊測試帳套","DFTEST6":"舊測試帳套","ERPMIS":"舊測試帳套",
 "PATCHTEMP":"程式更新暫存","SYS":"Oracle 系統","SYSTEM":"Oracle 系統","WMSYS":"Oracle Workspace Manager",
}
ROLE[SCHEMA] = f"**公司帳套（本文件主要分析對象）**"

# ---- 單頭/單身族（命名慣例推導，沿用 erp-metadata 邏輯）----
def prefix3(t):
    n = t[:-5] if t.endswith("_FILE") else t
    return n if len(n) == 3 else None

fam = collections.defaultdict(list)
for t in tables:
    p = prefix3(t["TABLE_NAME"])
    if p:
        fam[p[:2]].append(p)
families = {k: sorted(set(v)) for k, v in fam.items() if len(set(v)) > 1}
table_zh_map = {t["TABLE_NAME"]: t["ZH_NAME"] for t in tables}
rels = []
for fam2, prefs in sorted(families.items()):
    htab = prefs[0] + "_FILE"
    for p in prefs[1:]:
        rels.append((htab, p + "_FILE", fam2))
fam_detail = collections.defaultdict(list)
for h_, d_, f2 in rels:
    fam_detail[h_].append(d_)

# ---- 每表組裝（程式對應 + 欄位標籤）----
table_rows = []
n_col_total = n_col_dict = n_col_screen = 0
for t in tables:
    tname = t["TABLE_NAME"]
    progs = tbl_progs.get(tname.lower(), {})
    tbl_fields = [c["COLUMN_NAME"].lower() for c in cols_by_table.get(tname, [])]

    def screen_coverage(prog):
        forms = prog_forms(prog)
        if not forms:
            return 0
        return sum(1 for fld in tbl_fields if any(fld in label_by_form[f] for f in forms))

    coverage = {p: screen_coverage(p) for p in progs}
    ordered = sorted(progs.items(), key=lambda kv: (-coverage[kv[0]],) + rank_prog(kv[0], kv[1]))
    writers = [(p, a) for p, a in ordered if a & {"I", "U", "D"}]
    main_prog = writers[0][0] if writers else (ordered[0][0] if ordered else "")

    cols = []
    for c in cols_by_table.get(tname, []):
        field = c["COLUMN_NAME"].lower()
        main_lab = prog_label(main_prog, field) if main_prog else ""
        labs = all_labels(field)
        n_col_total += 1
        if c["ZH_NAME"]:
            n_col_dict += 1
        if main_lab or labs:
            n_col_screen += 1
        cols.append({
            "col": c["COLUMN_NAME"], "dict_zh": c["ZH_NAME"], "type": fmt_type(c),
            "null": "Y" if c["NULLABLE"] == "Y" else "N",
            "pk": c["PK_POS"], "main_lab": main_lab, "labs": labs,
            "nforms": len(field_forms.get(field, ())),
        })
    table_rows.append({
        "table": tname, "zh": t["ZH_NAME"], "module": t["MODULE"], "rows": int(t["NUM_ROWS"] or 0),
        "has_pk": t["HAS_PK"] == "1",
        "main_prog": main_prog, "main_prog_zh": prog_zh.get(main_prog, ""),
        "progs": ordered, "n_writers": len(writers), "cols": cols,
    })

by_rows   = sorted(table_rows, key=lambda x: (-x["rows"], x["table"]))
n_tbl = len(table_rows)
n_tbl_prog = sum(1 for t in table_rows if t["progs"])
n_tbl_writer = sum(1 for t in table_rows if t["n_writers"])

def fmt(n): return f"{n:,}"
def acts_str(a): return "/".join(x for x in "IUDS" if x in a)

# ---- 反查：主要程式 → 影響的資料表（來源 ZR_FILE，僅涵蓋本 schema 有資料的表）----
tbl_cols_l = {t["TABLE_NAME"]: [c["COLUMN_NAME"].lower() for c in cols_by_table.get(t["TABLE_NAME"], [])]
              for t in tables}
_prog_fields_cache = {}
def prog_fields(prog):
    """該程式（含子畫面）畫面上出現過的所有欄位代碼集合。"""
    if prog not in _prog_fields_cache:
        s = set()
        for f in prog_forms(prog):
            s.update(label_by_form[f].keys())
        _prog_fields_cache[prog] = s
    return _prog_fields_cache[prog]

prog_tbls = collections.defaultdict(list)
for t in table_rows:
    for p, a in t["progs"]:
        prog_tbls[p].append((t["table"], t["zh"], a, p == t["main_prog"]))
writer_progs = {p: lst for p, lst in prog_tbls.items() if any(x[2] & {"I", "U", "D"} for x in lst)}
def prog_sort_key(p):
    lst = writer_progs[p]
    n_main = sum(1 for x in lst if x[3])
    n_write = sum(1 for x in lst if x[2] & {"I", "U", "D"})
    return (-n_main, -n_write, p)
writer_order = sorted(writer_progs, key=prog_sort_key)

# ---- GAU_FILE（鼎新字典層 PK/FK）品質統計（對本 schema 表）----
colset_l = {(c["TABLE_NAME"].lower(), c["COLUMN_NAME"].lower()) for c in columns}
tabset_l = {t["TABLE_NAME"].lower() for t in tables}
zh_any = {t["TABLE_NAME"].lower(): t["ZH_NAME"] for t in tables}
for t in ds_tabs:
    zh_any.setdefault(t["TABLE_NAME"].lower(), t["ZH_NAME"])
gau_pk_tabs = {r["GAU02"] for r in gau}
gau_fk_tabs = {r["GAU04"] for r in gau}
gau_both = [r for r in gau if r["GAU02"] in tabset_l and r["GAU04"] in tabset_l]
gau_ok = sum(1 for r in gau_both
             if (r["GAU02"], r["GAU01"]) in colset_l and (r["GAU04"], r["GAU03"]) in colset_l)
gau_cover = sum(1 for t in tabset_l if t in gau_pk_tabs or t in gau_fk_tabs)
gau_pairs = {(r["GAU02"], r["GAU04"]) for r in gau}
derived_pairs = {(h.lower(), d.lower()) for h, d, _ in rels}
gau_hit_derived = sum(1 for pr in derived_pairs if pr in gau_pairs)

# ============================= HTML =============================
def esc(s): return html.escape(str(s) if s is not None else "")

H = []
B = H.append
B("<!DOCTYPE html><html lang='zh-Hant'><head><meta charset='utf-8'>")
B("<meta name='viewport' content='width=device-width,initial-scale=1'>")
B(f"<title>TIPTOP GP Metadata：DS 字典 ↔ {SCHEMA} ↔ 畫面(程式) 整合分析</title>")
B("<style>")
# ---- 調色盤（CSS 變數，與 erp-metadata.html 相同）----
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
B("details.cols{border:none;background:transparent;margin:0;padding:0;box-shadow:none}")
B("details.cols:hover,details.cols[open]{box-shadow:none}")
B("details.cols>summary{font-size:14.5px;font-weight:500;color:var(--accent);padding:0;border:none;margin:0}")
B("details.cols[open]>summary{border:none;margin-bottom:4px}")
B("details.cols{font-size:14px;color:var(--muted);line-height:1.6;font-family:Consolas,'Courier New',monospace}")
B(".kpi{display:flex;gap:16px;flex-wrap:wrap;margin:18px 0}")
B(".kpi div{background:var(--card);border:1px solid var(--line);border-top:3px solid var(--accent);border-radius:10px;"
  "padding:13px 24px;min-width:150px;box-shadow:0 1px 3px rgba(15,61,97,.06);transition:transform .15s}")
B(".kpi div:hover{transform:translateY(-2px)}")
B(".kpi b{font-size:27px;color:var(--primary);display:block;letter-spacing:.5px}")
B("pre{background:#0b2f4d;color:#dcebfa;padding:16px 18px;border-radius:10px;overflow:auto;font-size:15px;line-height:1.6;font-family:Consolas,'Courier New',monospace}")
B("input[id^='flt']{width:420px;max-width:100%;padding:9px 15px;border:1px solid var(--line-strong);border-radius:999px;font-size:16px;outline:none;transition:border .15s,box-shadow .15s;background:#fff}")
B("input[id^='flt']:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(46,125,209,.15)}")
B(".b{display:inline-block;border-radius:999px;padding:0 9px;font-size:12.5px;line-height:21px;margin-left:6px;color:#fff;font-weight:500;white-space:nowrap;vertical-align:middle}")
B(".b-dict{background:#2563a8}.b-db{background:#5b6b7d}.b-prog{background:#2e8b57}.b-scr{background:#7c4dbe}.b-inf{background:#d97706}.b-sug{background:#0d9488}")
B("</style></head><body>")
B(f"<aside id='sb'><h1>鼎新 TIPTOP GP Metadata<br>DS 字典 ↔ {SCHEMA} ↔ 畫面(程式)</h1>")
B(f"<div class='meta'>產出日期 {TODAY}<br>Oracle toptest @10.200.206.130<br>全程唯讀，只下 SELECT<br>（帳套 metadata 與 DS 字典以 sys 唯讀查詢）</div>")
B("<nav><a href='#legend'>資訊來源標示</a><a href='#ov'>1. 總覽</a><a href='#rel'>2. 關聯模型</a>"
  "<a href='#tp'>3. 表↔程式</a><a href='#cols'>4. 欄位對照</a><a href='#limit'>5. 限制</a></nav></aside>")
B("<main>")
B("<div class='kpi'>")
B(f"<div><b>{n_tbl}</b>{SCHEMA} 有資料表</div>")
B(f"<div><b>{fmt(n_col_total)}</b>欄位</div>")
B(f"<div><b>{fmt(n_col_dict)}</b>欄位有字典中文名</div>")
B(f"<div><b>{fmt(n_col_screen)}</b>欄位有畫面標籤</div>")
B(f"<div><b>{n_tbl_prog}</b>表可對應到程式</div>")
B(f"<div><b>{len(rels)}</b>推導關聯</div>")
B("</div>")

# 資訊來源圖例
B("<section id='legend'><h2>資訊來源標示（全文件通用）</h2>")
B("<table><tr><th>標示</th><th>意義</th><th>來源</th><th>本文件中的欄位</th></tr>")
LEGEND = [
 ("<span class='b b-dict'>字典</span>","資料表/欄位層的字典<b>事實</b>","<code>GAT_FILE</code>／<code>GAQ_FILE</code>（直接查表）","表中文名(GAT)、字典中文名(GAQ)"),
 ("<span class='b b-db'>DB</span>","Oracle 資料庫本身的<b>事實</b>","<code>ALL_CONSTRAINTS</code>／<code>ALL_TAB_COLUMNS</code>／<code>NUM_ROWS</code>","型別、可空、鍵(PK)、列數(統計值)"),
 ("<span class='b b-prog'>作業</span>","作業(程式)層的<b>事實</b>","<code>ZZ_FILE</code>／<code>GAZ_FILE</code>／<code>ZR_FILE</code>（直接查表）","程式代號、程式名稱(GAZ)、相關程式與異動別(I/U/D/S)"),
 ("<span class='b b-scr'>畫面</span>","畫面層的<b>事實</b>：某畫面上某欄位的顯示名稱","<code>GAE_FILE</code>（依「畫面＋欄位」設定）","全部畫面標籤、主要程式畫面標籤的「名稱」本身"),
 ("<span class='b b-inf'>推導</span>","依規則推斷的<b>選擇/判斷</b>，可能個別出錯","演算法（非字典欄位）","主要維護程式（挑哪支）、單頭/單身關聯、模組中文名"),
]
for r in LEGEND:
    B(f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td></tr>")
B("</table>")
B("<div class='warn'>「主要程式畫面標籤」是複合的：<b>名稱本身</b>是<span class='b b-scr'>畫面</span>事實（GAE_FILE 查得），"
  "但<b>以哪支程式為準</b>是<span class='b b-inf'>推導</span>。不想吃這個推導，請看「全部畫面標籤」欄。<br>"
  "DS 字典為<b>全域</b>（各帳套共用），本文件僅資料範圍換成 <b>" + SCHEMA + "</b>；"
  "DS 字典詳解、已知條件驗證與權限模型見主檔 <code>erp-metadata.html</code>（M2201 版）。</div></section>")

# 1 總覽
B(f"<section id='ov'><h2>1. 總覽：各 Schema 角色與資料量（本文件分析 <code>{SCHEMA}</code>）</h2>")
B("<div class='warn'>系統為 <b>鼎新 TIPTOP GP</b>（Oracle 11g）。全域字典在 <code>DS</code> schema；"
  "每家公司/帳套一個 schema、表結構同構。資料列數為 <b>統計值</b>（<code>ALL_TABLES.NUM_ROWS</code>），非即時 COUNT。</div>")
B("<table><tr><th>Schema</th><th>角色（推測）</th><th>表數</th><th>有資料表數</th><th>資料列數(統計值)</th><th>統計日期</th></tr>")
for o in owners:
    hl = " style='background:#fff8e8'" if o["OWNER"] == SCHEMA else ""
    B(f"<tr{hl}><td><code>{esc(o['OWNER'])}</code></td><td>{ROLE.get(o['OWNER'],'—').replace('**','')}</td>"
      f"<td style='text-align:right'>{o['TABS']}</td><td style='text-align:right'>{o['TABS_WITH_DATA']}</td>"
      f"<td style='text-align:right'>{int(o['TOTAL_ROWS']):,}</td><td>{esc(o['LAST_STAT'])}</td></tr>")
B("</table>")
B(f"<div class='warn'>字典覆蓋率（{SCHEMA} 有資料 {n_tbl} 張表）：欄位 {fmt(n_col_total)} 個，GAQ 中文名覆蓋 <b>{fmt(n_col_dict)}</b>、"
  f"GAE 畫面標籤覆蓋 <b>{fmt(n_col_screen)}</b>；{n_tbl_prog} 張表可對應到程式（{n_tbl_writer} 張有明確維護程式）。</div></section>")

# 2 關聯
B("<section id='rel'><h2>2. 關聯模型（單頭/單身，命名慣例推導）</h2>")
B(f"<div class='warn'>實體外鍵 <b>0 筆</b>（各帳套同構，經 M2201 之 ALL_CONSTRAINTS 驗證）。單頭/單身以 3 碼前綴推導：同前 2 碼為同一單據族，"
  f"字尾 A 多為單頭/主檔，透過單據號欄位串接（如 <code>oeb01</code>=<code>oea01</code>）。{SCHEMA} 有資料表中共 {len(rels)} 條、{len(families)} 個族。</div>")
B("<table><tr><th>單頭/主檔</th><th>中文名</th><th>單身/明細（同族其餘表）</th></tr>")
for h_ in sorted(fam_detail):
    B(f"<tr><td><code>{h_}</code></td><td>{esc(table_zh_map.get(h_,'—'))}</td><td>{', '.join(f'<code>{d}</code>' for d in fam_detail[h_])}</td></tr>")
B("</table>")
B("<h3>2.2 GAU_FILE：鼎新字典層 PK/FK<span class='b b-dict'>字典</span>（與 2.1 互補）</h3>")
B(f"<div class='warn'><code>DS.GAU_FILE</code> 登錄 <b>{len(gau):,} 條</b>邏輯外鍵（全域字典）。對 {SCHEMA} 的品質驗證："
  f"雙方皆為 {SCHEMA} 有資料表者 {len(gau_both)} 條、欄位皆實際存在 <b>{gau_ok}</b> 條"
  f"（{gau_ok*100//max(1,len(gau_both))}%）；{n_tbl} 張有資料表中 {gau_cover} 張出現在其中。"
  f"性質是<b>「欄位→主檔」參照型 FK</b>（料號→ima、科目→aag…）；<b>單頭/單身關聯幾乎沒登錄</b>"
  f"（2.1 推導 {len(rels)} 條僅 {gau_hit_derived} 條在 GAU）→ 與命名推導互補，不能互相取代。</div>")
B("<div class='pgwrap' data-size='50' data-list='tbody'>")
PGBAR = "<div class='pgbar'><input class='pgq' placeholder='{ph}'><span class='pginfo'></span><span class='pgnav'></span></div>"
B(PGBAR.format(ph="搜尋表名 / 欄位 / 中文名，例如 ima_file 或 客戶"))
B("<table><thead><tr><th>參照表(FK)</th><th>中文名</th><th>FK 欄位</th><th>→</th><th>被參照主檔(PK)</th><th>中文名</th><th>PK 欄位</th></tr></thead><tbody>")
gau_schema = sorted((r for r in gau if r["GAU02"] in tabset_l or r["GAU04"] in tabset_l),
                    key=lambda x: (x["GAU02"], x["GAU04"], x["GAU03"]))
for r in gau_schema:
    B(f"<tr><td><code>{esc(r['GAU04'])}</code></td><td>{esc(zh_any.get(r['GAU04'], ''))}</td><td><code>{esc(r['GAU03'])}</code></td>"
      f"<td>→</td><td><code>{esc(r['GAU02'])}</code></td><td>{esc(zh_any.get(r['GAU02'], ''))}</td><td><code>{esc(r['GAU01'])}</code></td></tr>")
B("</tbody></table>")
B(PGBAR.format(ph="搜尋表名 / 欄位 / 中文名"))
B("</div></section>")

# 3 表↔程式
B("<section id='tp'><h2>3. 資料表 ↔ 主要程式(畫面) 一覽（依列數排序）</h2>")
B("<div class='warn'>「主要維護程式」= 對該表有 I/U/D 動作、且畫面（GAE_FILE）實際顯示本表欄位最多者（<b>推導</b>，非鼎新官方欄位）。"
  "程式↔表關連（ZR_FILE）為全域字典，各帳套共用。</div>")
B("<div class='pgwrap' data-size='50' data-list='tbody'>")
B(PGBAR.format(ph="搜尋表名 / 中文名 / 模組 / 程式代號，例如 oea、訂單、axmt410"))
B("<table><thead><tr><th>#</th><th>資料表</th><th>表中文名(GAT)<span class='b b-dict'>字典</span></th><th>模組<span class='b b-inf'>推導</span></th>"
  "<th>列數(統計值)<span class='b b-db'>DB</span></th><th>主要維護程式<span class='b b-inf'>推導</span></th>"
  "<th>程式名稱(GAZ)<span class='b b-prog'>作業</span></th><th>相關程式數<span class='b b-prog'>作業</span></th></tr></thead><tbody>")
for i, t in enumerate(by_rows, 1):
    B(f"<tr><td style='text-align:right'>{i}</td><td><code>{esc(t['table'])}</code></td><td>{esc(t['zh'])}</td>"
      f"<td>{esc(mod_label(t['module']))}</td><td style='text-align:right'>{fmt(t['rows'])}</td>"
      f"<td><code>{esc(t['main_prog'])}</code></td><td>{esc(t['main_prog_zh'])}</td>"
      f"<td style='text-align:right'>{len(t['progs'])}</td></tr>")
B("</tbody></table>")
B(PGBAR.format(ph="搜尋表名 / 中文名 / 模組 / 程式代號"))
B("</div>")
B("<h3 id='pt'>3.2 反查：程式(畫面) → 影響哪些資料表、做哪些操作<span class='b b-prog'>作業</span></h3>")
B(f"<div class='warn'>來源 <code>ZR_FILE</code>（事實）。共 <b>{len(writer_progs)}</b> 支程式對 {SCHEMA} 有資料表有寫入動作（I/U/D）。"
  "★ = 該程式是這張表的主要維護程式（<span class='b b-inf'>推導</span>）。<br>"
  "有寫入的表另附「<b>推導欄位</b>」<span class='b b-inf'>推導</span>＝該表欄位 ∩ 該程式畫面(GAE_FILE)顯示的欄位，即這支程式實際操作的欄位集合。"
  "邊界：畫面顯示 ≠ 必定寫入（可能唯讀帶出）；程式在背景自動寫的欄位（審計欄、狀態碼）不會顯示在畫面上，故此清單是<b>下限</b>。欄位級的確切寫入仍需 4GL 原始碼。</div>")
B("<div class='pgwrap' data-size='30'>")
B(PGBAR.format(ph="搜尋程式代號 / 名稱 / 表名，例如 axmt410、訂單、oea"))
B("<div class='pglist'>")
for p in writer_order:
    lst = writer_progs[p]
    mains = [x[0] for x in lst if x[3]]
    n_w = sum(1 for x in lst if x[2] & {"I", "U", "D"})
    n_s = sum(1 for x in lst if "S" in x[2])
    key = esc((p + " " + prog_zh.get(p, "") + " " + " ".join(x[0].lower() for x in lst)).lower())
    star = f"　主要維護 {len(mains)} 表" if mains else ""
    B(f"<details data-k='{key}'><summary><code>{esc(p)}</code> — {esc(prog_zh.get(p, '（字典無名稱）'))}"
      f"　<span style='color:var(--muted);font-weight:400'>模組 {esc(prog_mod.get(p, '—'))}｜寫入 {n_w} 表｜查詢 {n_s} 表{star}</span></summary>")
    B("<table><thead><tr><th>資料表</th><th>中文名(GAT)</th><th>新增 I</th><th>更新 U</th><th>刪除 D</th><th>查詢 S</th><th>主要程式</th><th>推導欄位（畫面∩表）</th></tr></thead><tbody>")
    pf = prog_fields(p)
    for tbl, zh_, acts, is_main in sorted(lst, key=lambda x: (not x[3], not (x[2] & {"I","U","D"}), x[0])):
        def ck(flag): return "✓" if flag in acts else ""
        colcell = ""
        if acts & {"I", "U", "D"}:
            hit = [c for c in tbl_cols_l.get(tbl, []) if c in pf]
            if hit:
                colcell = (f"<details class='cols'><summary>{len(hit)}/{len(tbl_cols_l.get(tbl, []))} 欄</summary>"
                           + "、".join(hit) + "</details>")
        B(f"<tr><td><code>{esc(tbl)}</code></td><td>{esc(zh_)}</td>"
          f"<td style='text-align:center'>{ck('I')}</td><td style='text-align:center'>{ck('U')}</td>"
          f"<td style='text-align:center'>{ck('D')}</td><td style='text-align:center'>{ck('S')}</td>"
          f"<td style='text-align:center'>{'★' if is_main else ''}</td><td>{colcell}</td></tr>")
    B("</tbody></table></details>")
B("</div>")
B(PGBAR.format(ph="搜尋程式代號 / 名稱 / 表名"))
B("</div></section>")

# 4 欄位對照
B("<section id='cols'><h2>4. Column 清單：原始欄位 ↔ 字典中文名(GAQ) ↔ 畫面欄位名稱(GAE)</h2>")
B("<div class='pgwrap' data-size='20'>")
B(PGBAR.format(ph="搜尋表名 / 中文名 / 模組 / 程式代號，例如 oea、訂單、axmt410"))
B("<div class='pglist'>")
for t in by_rows:
    key = esc((t["table"] + " " + (t["zh"] or "") + " " + (t["module"] or "") + " " + mod_label(t["module"])
               + " " + t["main_prog"] + " " + t["main_prog_zh"]).lower())
    prog_list = "、".join(f"<code>{esc(p)}</code>({acts_str(a)})" for p, a in t["progs"][:8]) + ("…" if len(t["progs"]) > 8 else "")
    B(f"<details data-k='{key}'><summary><code>{esc(t['table'])}</code> — {esc(t['zh'] or '（無中文名）')}　"
      f"<span style='color:var(--muted);font-weight:400'>模組 {esc(t['module'] or '—')}</span>"
      f"｜主要程式<span class='b b-inf'>推導</span> <code>{esc(t['main_prog'])}</code> {esc(t['main_prog_zh'])}（約 {fmt(t['rows'])} 列）</summary>")
    if prog_list:
        B(f"<p>相關程式（前 8）<span class='b b-prog'>作業</span>：{prog_list}</p>")
    B("<table><tr><th>原始欄位</th><th>字典中文名(GAQ)<span class='b b-dict'>字典</span></th><th>型別<span class='b b-db'>DB</span></th>"
      "<th>可空<span class='b b-db'>DB</span></th><th>鍵<span class='b b-db'>DB</span></th>"
      "<th>主要程式畫面標籤<span class='b b-scr'>畫面</span><span class='b b-inf'>推導</span></th>"
      "<th>全部畫面標籤（畫面數）<span class='b b-scr'>畫面</span></th></tr>")
    for c in t["cols"]:
        pk = "PK" if c["pk"] else ""
        labs = "、".join(f"{esc(lab)}({n})" for lab, n in c["labs"])
        B(f"<tr><td><code>{esc(c['col'])}</code></td><td>{esc(c['dict_zh'])}</td><td>{esc(c['type'])}</td>"
          f"<td style='text-align:center'>{c['null']}</td><td style='text-align:center'>{pk}</td>"
          f"<td>{esc(c['main_lab'])}</td><td>{labs}</td></tr>")
    B("</table></details>")
B("</div>")
B(PGBAR.format(ph="搜尋表名 / 中文名 / 模組 / 程式代號"))
B("</div></section>")

# 5 限制
B("<section id='limit'><h2>5. 完成回報與限制</h2><ul>")
B("<li>資料列數採<b>統計值</b>（<code>ALL_TABLES.NUM_ROWS</code>），統計過期者可能偏差。</li>")
B("<li>實體 FK 不存在，關聯以命名慣例推導（中可信度）；<code>DS.GAU_FILE</code> 可作補充來源。</li>")
B("<li>「主要維護程式」為推導；同表可能被多支程式維護。</li>")
B(f"<li>畫面標籤覆蓋 {fmt(n_col_screen)}/{fmt(n_col_total)} 欄位；未覆蓋者多為純後端欄位（畫面本來不顯示）。</li>")
B(f"<li>DS 字典（GAT/GAQ/ZZ/GAZ/ZR/GAE/GAU）為全域，{SCHEMA} 與 M2201 同構、直接套用；"
  "DS 字典詳解、已知條件驗證與權限模型見 <code>erp-metadata.html</code>（M2201 版）。</li>")
B("</ul></section></main>")
# 章節換頁路由（sidebar = 分頁器，一次只顯示一章）+ 清單分頁元件
B("""<script>
(function(){
  // ---- 章節分頁 ----
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

  // ---- 清單分頁元件（搜尋跨全部項目，分頁只顯示當頁）----
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
out_path = os.path.join(OUT, f"erp-metadata-{SLC}.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html_text)
print(f"已寫出 {out_path}", len(html_text), "bytes")
print(f"schema={SCHEMA} tables={n_tbl} with_prog={n_tbl_prog} with_writer={n_tbl_writer} "
      f"cols={n_col_total} col_dict={n_col_dict} col_screen={n_col_screen} rels={len(rels)}")
