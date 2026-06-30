# &lt;System&gt; — 架構 Breakdown

> **定位**:&lt;一句話描述本系統做什麼;對應的業務目標&gt;。
> **目標讀者**:&lt;標出哪些角色該讀;對應第四節矩陣&gt;。
> **互補文件**:
> - 視覺層:[`diagram.html`](diagram.html)(Demo 簡報式 — N 張 slide,← / → 翻頁)
> - 規範地板:`docs/Design-Base/`
> - 版本任務:`docs/Tasks/v*/`

---

## 一、為什麼有這份 Breakdown

&lt;描述當前痛點 / 為什麼一張圖不夠 / Breakdown 解決什麼問題。3–5 點。&gt;

例:
- 新人看不懂單張架構圖,訊息密度過高
- PM / Backend / DevOps 各看不同層級的關注點
- Coolify 部署前一刻才發現缺項(audit / log / healthcheck)

本 Breakdown 解法:
- **依「層級」切**:Edge / Application(Presentation + Business + Cross-cutting)/ Data
- **依「角色」三色標分布**:🟢 業務 / 🔵 IT / 🟣 共同 / 🔴 ★ Critical
- **依「合規」反推產出**:每個 Critical 標記對應上線前必須過的合規條目

---

## 二、視覺索引(diagram.html)

互動式 Demo 簡報網頁:[`diagram.html`](diagram.html)(雙擊瀏覽器即開,無需 server)。

**操作:**
- **翻頁**:`← / →` / `空白鍵` / `Home / End` / 右上 picker
- **放大縮小**:`+ / -` / `0` 重設 / `F` 符合視窗 / `Ctrl + 滾輪`
- **拖曳平移**:左鍵拖曳(Mermaid SVG slide)
- **匯出**:複製 SVG、下載 SVG / PNG(2× 解析度)

### slide 線性順序

模板預設提供 6 種 slide 類型範例,使用者依專案自行增減 / 改順序。**`data-order` 控排序**,可塞小數(0.5 / 1.1 / 4.5)插隊。

| 序 | 工具列標籤 | 類型(`data-kind`)| 格式(`data-format`)| 重點 |
| --- | --- | --- | --- | --- |
| 0 | 0. 封面 | cover | html | 系統定位 + 三色角色表 + Demo 導覽 |
| 0.1 | 0.1 為什麼需要(Before vs After) | compare | html | 4 對痛點 ↔ 解法卡片對比 |
| 1 | 1. 系統架構主圖 | architecture | mermaid | 主架構圖 + 跨切關注點 |
| 1.1 | 1.1 RACI 三角色責任分布 | architecture | html | 每個層級對應的 🟢 / 🔵 / 🟣 / 🔴 責任 |
| 2 | 2. &lt;元件 / 模組總覽&gt; | architecture | html | 卡片 grid(cols-2/3/4)逐元件並列 |
| 3 | 3. Auth 流程(JWT 登入) | flow | mermaid | 登入流程節點 → 對應主架構 |
| 4 | 4. Deploy 流程(Coolify CD) | flow | mermaid | 部署流程節點 → 對應外部依賴 |

> 新增 slide → 複製任一 `<script type="text/plain">` 區塊,改 `id` / `data-label` / `data-order` / `data-kind` / `data-format` 即可,picker 與翻頁自動套用。

---

## 三、三色角色對照

`diagram.html` 內所有節點都依下表染色,工具列下方 legend 永遠顯示:

| 色 | 角色 | &lt;公司內對應&gt; | 在架構中的位置 |
| --- | --- | --- | --- |
| 🟢 **使用者** | &lt;業務 / PM / 終端使用者&gt; | &lt;說明&gt; | &lt;例:UI / 需求 / Audit 可審計人物&gt; |
| 🔵 **IT** | &lt;Backend / DevOps / Tech Lead&gt; | &lt;說明&gt; | &lt;例:平台底座、CI / CD、Cross-cutting&gt; |
| 🟣 **共同** | &lt;QA / SME / 跨部門共同維護&gt; | &lt;說明&gt; | &lt;例:品質、SOP、主檔資料&gt; |
| 🔴 ★ **Critical** | (附加標記,不是第四種角色)| 合規 / 安全關鍵點 | &lt;例:Sandbox、Audit、隱私邊界&gt; |

> 「★ Critical」是**附加標記**,不是第四種角色 — 它表達「即使你是 IT,這個節點也必須**特別小心**」。

---

## 四、架構層級總覽

對應 [`diagram.html`](diagram.html) `1. 系統架構主圖`。

| 層級 | 內容 | Owner | 部署 / 合規要點 |
| --- | --- | --- | --- |
| **Edge** | Caddy / Coolify Proxy / TLS / Domain | DevOps | TLS 自動續簽 / domain whitelist |
| **Application — Presentation** | React UI / RTK Query / i18n | Frontend Team | bundle size / CSP / 不洩漏內部 ID |
| **Application — Business** | FastAPI Routers / Domain Services | Backend Team | OpenAPI / Pydantic / 分層不互調 |
| **Application — Cross-cutting** | Auth / Logging / Audit | Backend + Security | JWT httpOnly / 結構化 log / 不洩 PII |
| **Data** | PostgreSQL(asyncpg) | DBA + Backend | 連線池 / 軟刪除 / 備份 |
| **外部信任邊界** | Sentry / Loki(可觀測性) | 各服務 owner | webhook 簽章 / PII 過濾 |

> Redis / SSO / Payment 等屬選用三方服務(`docs/Design-Base/90-third-party-service/`);若採用,需在本表追加列並擴充 `diagram.html` 主架構圖。

### 跨切關注點(Cross-cutting)為什麼獨立一層

- **Auth**:不可重複實作於每個 router;集中管理 token / RBAC
- **Logging**:結構化 stdout → Loki / Sentry,避免散落
- **Audit**:legal / 合規要求,單一進入點才能保證完整性

---

## 五、角色 × 必修矩陣

> ✅深 = 必須能講出細節並設計;✅淺 = 知道存在、知道找誰負責;— = 可不修。

| 角色 | Edge | Pres | Biz | Cross-cutting | Data | 外部 |
| --- | :-: | :-: | :-: | :-: | :-: | :-: |
| 高層 / 業務主管 | — | — | ✅淺 | — | — | ✅淺 |
| PM / 產品 | — | ✅淺 | ✅深 | ✅淺 | ✅淺 | ✅淺 |
| **Tech Lead** | ✅深 | ✅深 | ✅深 | ✅深 | ✅深 | ✅深 |
| Frontend | — | ✅深 | ✅淺 | ✅淺 | — | ✅淺 |
| Backend | ✅淺 | ✅淺 | ✅深 | ✅深 | ✅深 | ✅深 |
| DevOps | ✅深 | — | ✅淺 | ✅淺 | ✅淺 | ✅淺 |
| QA / NPI | ✅淺 | ✅深 | ✅深 | ✅深 | ✅淺 | ✅淺 |
| 新人 | ✅淺 | ✅淺 | ✅淺 | — | ✅淺 | — |

口訣:**「上看流程,下看合規。」** PM 讀流程圖即可;DevOps 必過 Edge + Cross-cutting + 外部。

---

## 六、子流程清單

對應 [`diagram.html`](diagram.html) 中所有 `data-kind="flow"` 的 slide。每條流程都標出「**對應架構節點**」與「**為什麼存在**」。

| # | 流程 | 對應架構節點 | 為什麼 | Owner |
| --- | --- | --- | --- | --- |
| 3 | Auth(JWT 登入) | User → Proxy → UI → API → Auth → DB | JWT httpOnly cookie 防 XSS;bcrypt 比對密碼 | Backend + Security |
| 4 | Deploy(Coolify CD) | External(GitHub)→ Proxy → 服務重啟 | main push 即部署 + 健康檢查自動回滾 | DevOps |
| &lt;...&gt; | &lt;新增流程時加列&gt; | | | |

### 新增子流程的步驟

1. 開啟 [`diagram.html`](diagram.html),找到任一 `<script type="text/plain" id="flow-XXX">` 區塊
2. 複製整段 → 改 `id` / `data-label` / `data-order` / `data-desc`
3. 把 `data-desc` 寫清楚「對應架構節點」+「為什麼存在」
4. 修改下方 Mermaid 內容,記得用三色 `classDef`(user / it / shared / critical)
5. 存檔 → 重新整理瀏覽器 → picker / 翻頁自動列出新流程
6. 把該流程加進本檔第六節表格

### 新增 HTML slide(Cards / RACI / Compare / Cover)

1. 找對應類型的範例 slide(`arch-cards` / `arch-raci` / `arch-why` / `cover`)
2. 複製整段,改 `id` / `data-label` / `data-order` 與內部 HTML
3. **`data-format="html"` 不可漏** — 否則會被當 Mermaid 解析失敗
4. CSS class 已內建在 `diagram.html` `<style>`(card / raci-cell / compare-section / slide-cover),直接套用

---

## 七、學習路徑建議

### 7.1 高層 / PM(30 分鐘)
打開 [`diagram.html`](diagram.html) → 0. 封面 → 1. 系統架構主圖 → 1.1 RACI 責任分布 → 跳讀本檔第五節矩陣。

### 7.2 Tech Lead(1 小時)
全本依序翻 → 對照 `docs/Design-Base/` 各層規範 → 完成本檔第五節矩陣的 Critical 自我檢核。

### 7.3 Frontend / Backend(30 分鐘)
讀第四節該層級欄位 → 翻 [`diagram.html`](diagram.html) 看自己負責的 flow slide。

### 7.4 DevOps(40 分鐘)
讀第四節 Edge / Cross-cutting / Data → 翻 Deploy 流程 → 對照 `docs/Design-Base/06-Coolify-CD/` 與所有 🔴 Critical 卡片。

### 7.5 新人(20 分鐘)
依 picker 順序把每張 slide 翻過一遍 → 重點停在封面與架構主圖。

---

## 八、與其他資料夾的關係

| | 本 bundle | `docs/Arch/adr/` | `docs/Design-Base/` | `docs/Tasks/` |
| --- | --- | --- | --- | --- |
| 內容 | 主架構 + 子流程視覺 + Breakdown | 決策紀錄 | 實作規範 | 單版本任務 |
| 變動 | 低(架構變才動) | 不可變 | 低 | 高 |
| 形式 | 1 HTML(N slide)+ 1 README | N 份 ADR md | N 份規範 md | 版本資料夾 |

規則優先序:`docs/Design-Base/* > docs/Arch/* > AGENTS.md / CLAUDE.md > docs/Tasks/*`

---

## 九、版本與維護

- **v1.0(YYYY-MM-DD)** — 首版,N 張 slide(cover / compare / architecture × M / flow × N)
- 架構變動 → 主圖 + 對應流程 + 卡片同步更新,本檔表格同步
- 修正規則:任何架構節點 rename / 移動 → 子流程的 `data-desc` 必須同步,**禁**留 dangling reference
- 三色染色變動 → 同步更新本檔第三節對照表與 `diagram.html` 內所有 `classDef` / `card.*` / `raci-item.*`
