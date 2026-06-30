---
name: create-arch-diagram
description: 在任何專案內建立一份「Demo 簡報式架構圖 bundle」(N 張 slide:cover / compare / architecture / flow / cards / RACI)到 docs/Arch/diagrams/<name>/。預設會**掃描專案結構**(技術棧 / 服務 / 外部依賴 / CI / 部署)自動填 Mermaid 主架構 + 1-2 條子流程,使用者可改改即用;HTML 類 slide(封面 / 卡片 / RACI / Before-After)留 placeholder 由使用者手填;也可選擇只 cp 模板手動填。當使用者說「掃描專案建架構圖 / 新架構圖 / 建 diagram bundle / create arch diagram」時觸發。
---

# create-arch-diagram

從本 skill 內建的 `_template/` cp 出一份新的架構圖 bundle 到 `<cwd>/docs/Arch/diagrams/<name>/`,並依模式可選擇:

- **scan 模式(預設推薦)**:掃描專案 → 偵測技術棧 / 服務 / 外部依賴 → LLM 寫入 Mermaid 主架構 + 1-2 條子流程,HTML 類 slide(cover / compare / cards / RACI)**留 placeholder**(因為需要業務脈絡);使用者後續微調 + 補 HTML slide 的內容
- **raw cp 模式**:純 cp 模板 + 改 title,使用者完全手填

本 skill **不限定 Harness-Engineering 套用過的專案**,任何有實質結構的專案目錄都可跑。

## 模板格式(對齊 Architecture/diagram.html 的簡報式)

模板採 **Demo 簡報式 HTML**,單檔可放 N 張 slide,左右翻頁 + zoom + 拖曳。slide 規約:

| 屬性 | 用途 | 取值 |
| --- | --- | --- |
| `id` | 全域唯一 | 英數 + 連字號 |
| `data-label` | 工具列下拉與 slide 標題 | 顯示文字 |
| `data-order` | 排序鍵 | 數字,可塞小數(0.5 / 1.1 / 4.5)插隊 |
| `data-kind` | 語意類別 | `cover` / `architecture` / `flow` / `compare` |
| `data-format` | 渲染模式 | `mermaid`(預設)/ `html`(內容直接當 HTML 渲染)|
| `data-desc` | 講者註記 | HTML 字串(目前未渲染為獨立面板,保留作維護備忘)|

模板預設 6 張 skeleton slide(全套 6 種類型範例):

| 序 | id | kind | format | 說明 |
| --- | --- | --- | --- | --- |
| 0 | `cover` | cover | html | 封面:系統定位 + 三色角色表 + Demo 導覽 |
| 0.1 | `arch-why` | compare | html | Before vs After:4 對痛點 ↔ 解法卡片對比 |
| 1 | `arch` | architecture | mermaid | 系統架構主圖(Edge / App / Data) |
| 1.1 | `arch-raci` | architecture | html | RACI 三角色責任分布 grid |
| 2 | `arch-cards` | architecture | html | 元件 / 模組總覽 cards grid |
| 3 | `flow-auth` | flow | mermaid | Auth 流程範例 |
| 4 | `flow-deploy` | flow | mermaid | Deploy 流程範例 |

**三色約定**(全檔通用,Mermaid `classDef` 與 HTML `class` 同名):

| Class | 用途 | 色票 |
| --- | --- | --- |
| `user` | 🟢 業務 / 終端使用者 | `#dcfce7` / `#16a34a` |
| `it` | 🔵 工程 / 平台 | `#dbeafe` / `#2563eb` |
| `shared` | 🟣 業務 + 工程共同 | `#f3e8ff` / `#9333ea` |
| `critical` | 🔴 ★ 合規 / 安全關鍵點 | `#fee2e2` / `#dc2626` |

## 心法

1. **填寫模式分明**:scan 模式下,LLM 可寫 Mermaid + 主架構 + 子流程的 Breakdown,但**必須先給使用者看偵測結果**讓他確認;raw cp 模式下,LLM **禁**寫圖表內容
2. **HTML slide 不由 LLM 偽造**:cover / compare / cards / RACI 四種 HTML slide 需要業務脈絡(痛點 / 角色責任分配 / 元件分類邏輯)— scan 模式下**永遠留 placeholder**,由使用者手填,**禁**從 README 推測偽造
3. **冪等不可逆**:cp 是不可逆動作(會落實體檔)— target 已存在時,**必須**用 `AskUserQuestion` 詢問處理,**禁**直接覆寫
4. **單一動作**:本 skill 只做「建一份 bundle」一件事,不跑 server / 不開瀏覽器 / 不 commit / 不裝套件
5. **掃描範圍受限**:只讀 manifest / config / 結構 / 公開 README,**禁**讀 `.env*`(非 example)/ 任何含密碼 hash / token 的檔
6. **輸出語言**:繁體中文(回應 / 註解 / commit message)
7. **AskUserQuestion 必有「推薦」選項**:對齊 init-project § 7,**首項標 `(Recommended)`**,且 Recommended 必須:
   - **(a) 命中典型意圖**:多數使用者觸發 skill 想要的結果
   - **(b) 不會造成不可逆 / 高破壞性後果**:若典型意圖含覆寫既存檔,Recommended **退一階**到「中止」或「改名」

## 執行步驟

### 1. cwd 健全性檢查(寬鬆)

確認當前目錄看起來是個專案(任一存在即可):

- `<cwd>/.git/`
- `<cwd>/package.json`
- `<cwd>/pyproject.toml`
- `<cwd>/pom.xml` / `<cwd>/build.gradle`
- `<cwd>/Cargo.toml` / `<cwd>/go.mod`
- `<cwd>/composer.json` / `<cwd>/Gemfile`
- `<cwd>/README.md`(任何含 README 的有結構目錄)

**完全空目錄**(沒有上述任何信號) → **中止**,告知:「當前目錄看起來不是專案。請 `cd` 到實際專案根目錄。」

> **不限定 Harness-Engineering 套用過的專案**。即使沒有 CLAUDE.md / docs/Design-Base/ 也可跑(scan 模式仍能掃結構)。

### 2. 收集圖表名稱

用 plain text 詢問(不用 AskUserQuestion,因為是自由輸入):

```
請輸入圖表名稱(kebab-case,例如 system-arch / payment-arch / billing-arch):
```

**校驗**:`/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/`(同 init-project § 2a 的 `project_name` 規則)

不合法 → 重新詢問,告知:「需小寫字母開頭,只能含 `a-z` / `0-9` / `-`,連續 `-` 不可。」

合法 → target = `<cwd>/docs/Arch/diagrams/<name>/`

### 3. 衝突偵測

#### 3a. 確認 `<cwd>/docs/Arch/diagrams/` 是否存在

不存在 → 用 `mkdir -p <cwd>/docs/Arch/diagrams` 建立(可逆,無風險,直接做)

#### 3b. 確認 `<cwd>/docs/Arch/diagrams/<name>/` 是否存在

存在 → 用 `AskUserQuestion`(對齊心法 § 7,Recommended = 中止):

- **中止 (Recommended)** — 不動既存內容
- **改用其他名稱** — LLM 回到 § 2 重新詢問
- **覆寫(刪掉舊 `<name>/` 再 cp)** — ✱ 不可逆,需獨立再確認一次

### 4. cp 模板(永遠先放 baseline)

不管 § 6 模式選什麼,先 cp 模板做 baseline,確保 target 至少有完整 6 張 skeleton slide。

skill 安裝後路徑通常為 `~/.claude/skills/create-arch-diagram/`。

#### Windows / PowerShell

```powershell
Copy-Item -Recurse "<skill-root>\_template" "<cwd>\docs\Arch\diagrams\<name>"
```

#### macOS / Linux / bash

```bash
cp -r "<skill-root>/_template" "<cwd>/docs/Arch/diagrams/<name>"
```

cp 完後 `ls <target>` 確認 `README.md` + `diagram.html` 都在。

### 5. 改顯示文字

**三處**改成新名稱(對應新模板的位置):

| 檔 | 位置 | 改為 |
| --- | --- | --- |
| `diagram.html` | `<title>...</title>`(`<head>` 內) | `<title><name> — 架構圖</title>` |
| `diagram.html` | `<header class="toolbar">` 內的 `<h1 id="title">` | `<h1 id="title"><name></h1>` |
| `README.md` | 第一行 `# <System> — 架構 Breakdown` | `# <name> — 架構 Breakdown` |

> 其他 `<系統名稱>` / `<...>` placeholder 此時**先保留**:
> - 若 § 6 走 scan 模式,§ 8 會由偵測結果改寫 mermaid slide(arch / flow-*),HTML slide 維持 placeholder 給使用者手填
> - 若走 raw cp,則保留全部 placeholder 給使用者手填

### 6. 模式選擇(AskUserQuestion)

對齊心法 § 7,Recommended = scan-and-fill(典型意圖、又是寫到新檔案不會毀既有東西):

| 選項 | 行為 |
| --- | --- |
| **掃描專案 + 自動填 mermaid 主架構 (Recommended)** | 進 § 7 掃描 → § 7c 給使用者確認 → § 8 寫入 mermaid slide;HTML slide 維持 placeholder。最後再次微調仍由使用者操作 |
| **只 cp 模板(我自己填)** | 跳過 § 7 / § 8,直接 § 9 報告 |
| **中止** | baseline 已 cp(§ 4),不繼續寫入;使用者可後續自行編輯或刪掉 |

### 7. 掃描專案(scan 模式)

#### 7a. 必讀檔(若存在)

- **語言 / 框架**:`package.json`(deps)、`pyproject.toml`、`pom.xml` / `build.gradle`、`Cargo.toml`、`go.mod`、`composer.json`、`Gemfile`
- **資料庫**:`alembic/` / `prisma/` / `migrations/` / `*.sql` / `docker-compose.yml`(找 `image: postgres|mysql|mongo|redis`)
- **外部 client**:`src/clients/` / `src/integrations/` / `app/clients/`
- **環境變數線索**:`.env.example` / `.env.development.example`(**只讀 example 檔**,**禁**讀真 `.env*`)
- **CI/CD**:`.github/workflows/*.yml` / `.gitlab-ci.yml` / `Jenkinsfile`
- **部署**:`Dockerfile` / `docker-compose.yml` / `.coolify/` / `Caddyfile` / `nginx.conf`
- **架構文件**:`README.md` / `docs/Arch/` / `docs/Architecture/`(若已有舊文,參考但不照抄)

#### 7b. 偵測產出表

整理成這張表(scan 結果)給使用者看:

```
| 層級 | 偵測結果 | 來源 |
| --- | --- | --- |
| Frontend | React 19 + Vite | frontend/package.json |
| Backend | FastAPI + SQLAlchemy async | backend/pyproject.toml |
| Database | PostgreSQL (asyncpg) | backend/alembic/env.py + docker-compose.yml |
| Cache | (未偵測) | — |
| 外部依賴 | Stripe / Sentry | backend/app/clients/, .env.example |
| Edge / Deploy | Coolify + Docker Compose | docker-compose.yml + .coolify/ |
| CI | GitHub Actions(lint / typecheck / build) | .github/workflows/ci.yml |
```

**禁**偽造偵測結果 — 沒看到的寫「未偵測」,不要憑空寫「應該有 Redis」之類。

#### 7c. 使用者確認(AskUserQuestion)

對齊心法 § 7,Recommended = 直接寫入(偵測結果可審,使用者已看過,寫入新檔案不毀東西):

| 選項 | 行為 |
| --- | --- |
| **照這個結果寫入 (Recommended)** | 進 § 8 |
| **我先補充 / 修正後再寫** | 使用者用 plain text 列補充項(例:「加 Redis」「外部還有 Slack webhook」),LLM 整合後重出 § 7b 表再次確認 |
| **不寫了,保留 baseline** | 跳到 § 9 報告 |

### 8. 寫入(scan 模式)

依 § 7c 確認的偵測結果,改寫 **僅 mermaid slide**(`arch` / `flow-auth` / `flow-deploy`),HTML slide 維持 placeholder。

#### 8a. `diagram.html` — Mermaid slide

- **`<script id="arch">`**:重畫主架構,**禁**保留模板裡 React/FastAPI/PG 的範例節點(那是 Harness-Engineering 預設,跟現在偵測結果不一定相同)。用偵測到的真實層級 / 元件 / 邊界 / Owner。**保留三色 `classDef`(user / it / shared / critical)**,新節點記得 `class X it` 之類正確染色
- **`<script id="flow-auth">`** 與 **`<script id="flow-deploy">`**:
  - 若偵測到 auth 機制 → 改寫 auth 流程(例:JWT cookie / SSO / API key)
  - 若偵測到 CI/CD → 改寫部署流程
  - 偵測不到 → **刪掉該整段 `<script>` 區塊**(別留 Harness-Engineering 預設範例混進來),picker 自動不會列
- 其他 `<script type="text/plain">` 區塊保持規約:`id` / `data-label` / `data-order` / `data-kind` / `data-format` / `data-desc`

#### 8b. `diagram.html` — HTML slide(cover / arch-why / arch-raci / arch-cards)

**全部維持 placeholder,不寫**。理由(對齊心法 § 2):
- **cover**:系統定位 / 用途 / 目標讀者 / 互補文件路徑 — 需業務脈絡
- **arch-why(Before vs After)**:痛點 ↔ 解法的對應 — 需業務 / 組織痛點脈絡
- **arch-raci**:每層級的角色責任分配 — 需組織分工脈絡
- **arch-cards**:元件分類邏輯 / 重要度標記 — 需領域知識

LLM **可選擇性地**:
- 把 cover slide 的 `<title>` / `<subtitle>` / `<tag>` 改成偵測到的專案名稱(例:`<系統名稱>` → `bookstore-api`)
- 把 cover slide `<meta>` 區的 `<日期>` 改成今天日期(透過 currentDate)
- **其他內容(role-table 文字 / key-msg / role 對應 / 卡片內容)一律不動,留 placeholder**

#### 8c. `README.md`

- **「四、架構層級總覽」表**:用偵測結果填(Edge / Pres / Biz / Cross-cutting / Data / 外部),Coolify 合規欄若非 Coolify 專案改為「部署合規要點」或留空
- **「六、子流程清單」表**:對齊 § 8a 寫進 diagram.html 的 mermaid 流程
- **「二、視覺索引」slide 表**:依實際 slide 數量更新(刪除 § 8a 中刪掉的 flow 列)
- **「一、為什麼有這份 Breakdown」**:**留 placeholder**(`<為什麼>` / 例舉痛點)— 這需要業務脈絡,LLM 不該猜
- **「三、三色角色對照」**:**留模板預設值**(角色配置因組織而異,使用者自己改)
- **「五、角色 × 必修矩陣」**:**留模板預設值**(高層 / PM / Tech Lead / Frontend / Backend / DevOps / QA / 新人)
- **「七、學習路徑建議」**:**留模板預設值**

> 規則:**有客觀依據的(技術棧 / 流程)由 scan 結果寫;有主觀脈絡的(為什麼 / 角色 / RACI / 卡片)留 placeholder**。

#### 8d. 預覽

寫入後,簡述「改了哪幾段、改成什麼樣子」給使用者看,並**明確列出哪些 HTML slide 是 placeholder 待填**,不必貼完整 diff(過長)。

### 9. 報告

不管走哪個模式,最後告知:

```
✓ 已建立 docs/Arch/diagrams/<name>/
  ├── README.md      ← <若 scan:已填層級總覽 + 子流程清單;若 raw cp:placeholder 待填>
  └── diagram.html   ← <若 scan:已填 mermaid 主架構 + 子流程;HTML slide(cover / compare / cards / RACI)維持 placeholder>
                     ← <若 raw cp:全部 placeholder>

下一步:
1. 用瀏覽器開啟 docs/Arch/diagrams/<name>/diagram.html(雙擊即可)
2. ← / → 翻頁,Ctrl + 滾輪 zoom
3. 用 VSCode 編輯 <script type="text/plain"> 區塊微調內容:
   - mermaid slide(arch / flow-*):改 Mermaid DSL
   - html slide(cover / arch-why / arch-raci / arch-cards):改 HTML 內容
4. 同步補 README.md 的「為什麼」「三色角色」「角色矩陣」(這三段 skill 不代填)
5. 完成後 commit 整個 docs/Arch/diagrams/<name>/ 資料夾
```

## 自我約束

- **scan 模式下**:LLM 可寫 mermaid slide(arch / flow-*)的內容,但 § 7c 必須先給使用者確認偵測結果;**禁**未確認直接寫入。HTML slide(cover / arch-why / arch-raci / arch-cards)**留 placeholder**,只可改 cover 的 title / subtitle / tag / 日期,其他不動
- **raw cp 模式下**:LLM **禁**寫 Mermaid 或 HTML slide 內容,只能 cp + § 5 改顯示文字
- **禁讀**任何真 `.env*`(非 `.env.example`)/ 任何含 token / password / private key 的檔
- **禁**自動 commit / git add
- **禁**啟動 HTTP server / 自動開瀏覽器
- **禁**修改 `<cwd>` 既有檔案(除了 § 4 cp 的新 `<name>/` 內容)
- **禁**碰 `docs/Arch/diagrams/_template/`(若該目錄存在於使用者專案)— 那是使用者自己的 reference,不是 skill 的 source。skill 的 source 永遠在 `<skill-root>/_template/`
- **禁**覆寫 target 已存在的 `<name>/` 而不問使用者(§ 3b 擋住)
- **禁**偽造 scan 結果 — 沒讀到的寫「未偵測」,不憑空想像
- **禁**偽造 HTML slide 內容(痛點 / RACI / 卡片元件 / 封面文案)— 這些需要業務脈絡,沒問清楚就寫等於猜

## 不做的事

- 不跑 `/scan-project`(那是另一個 skill,負責偵測**問題清單**;本 skill 只關心**架構結構**)
- 不裝套件 / 不跑 build(模板靠 CDN 載 mermaid.js)
- 不跑 acceptance test
- 不檢查 git 狀態
- 不更新 `docs/Arch/README.md` 或其他索引檔
- 不修改 Harness-Engineering 自己的 `Skills/create-arch-diagram/_template/`(那是分發源)

## 與其他 skill 的關係

| Skill | 何時用 |
| --- | --- |
| `/init-project` | 一次性 — 從 Harness-Engineering 落地專案骨架。**會把本 skill cp 到 `~/.claude/skills/`**,但本 skill **不需要** init-project 跑過才能用 |
| `/scan-project` | 偵測**問題清單**(env / security / 規範違反),產 fixed.md 候選清單 |
| `/create-arch-diagram`(本檔)| 偵測**架構結構** + 建一份可瀏覽的 Demo 簡報式 bundle。問題 vs 結構,各司其職 |
| `/start-dev` / `/stop-dev` | 開發階段啟停 dev server,與架構圖無關 |

## 內建模板維護

本 skill 內建的 `_template/` 是**單一分發源**(自包含,不依賴 bundle 任何外部目錄);格式對齊 `Architecture/<日期>-<...>-v*/diagram.html`(公司架構參考實作)。

維護規則:

- **更新模板**:直接改 `Harness-Engineering/Skills/create-arch-diagram/_template/`(本 skill 內就是唯一一份,無同步成本)
- **變更不影響既存使用者圖表**:既存 `<name>/` 不會自動跟進升級(那是使用者已客製的內容);新模板只影響「之後新建」的 bundle
- **格式變動需對齊參考實作**:slide 規約(`data-order` / `data-format` / 三色 class / cards / raci / compare / cover CSS)以 `Architecture/` 下最新版本為準
- **使用者專案中沒有 `docs/Arch/diagrams/_template/` 也沒關係**:本 skill cp source 永遠來自 `<skill-root>/_template/`,不依賴使用者專案
