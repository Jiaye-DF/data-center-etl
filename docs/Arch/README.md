# Arch — 長期架構方向

> **本資料夾用途**:跨版本、跨專案的**長期架構決策**與設計取捨記錄。**不**寫實作規範(那屬於 `docs/Design-Base/`),**不**寫單版本任務(那屬於 `docs/Tasks/`)。
>
> **規則優先序**:`docs/Design-Base/* > docs/Arch/* > AGENTS.md / CLAUDE.md > docs/Tasks/*`(見各 `00-overview/` 與 `AGENTS.md`)

---

## 什麼進來、什麼不該進來

### ✅ 進來

- **架構決策紀錄(ADR)**:重大選型 / 取捨 / 拒絕方案的脈絡(例:為什麼選 RTK Query 而非 SWR、為什麼用 SQLAlchemy 2 async 而非 Tortoise)
- **跨服務 / 跨領域圖**:系統 context 圖、資料流、認證流程、佈署拓撲(高層次,不到實作細節)
- **長期演進方向**:下個 6–12 個月想往哪走(例:朝 event-driven、引入 read replica、拆 microservice 評估)
- **跨版本不變的契約**:對外 API 設計哲學、資料模型核心關係

### ❌ 不該進來

- 程式碼風格 / 命名 / 型別規則 → `docs/Design-Base/02-frontend/00-overview.md` 等風格地板
- 單版本要做什麼 → `docs/Tasks/v{X.Y.Z}/propose-v{X.Y.Z}.md`
- bug 根因 → `docs/Tasks/v{X.Y.Z}/fixed.md`
- 套件版本鎖定 → `docs/Design-Base/00-overview/01-versions.md`
- 第三方串接細節 → `docs/Design-Base/90-third-party-service/`

---

## 建議結構

```
docs/Arch/
├── README.md                       # 本檔
├── overview.md                     # 系統 context 圖 + 主要 service / 資料流(可選)
├── adr/
│   ├── 0001-rtk-query-vs-swr.md
│   ├── 0002-sqlalchemy-async-only.md
│   ├── 0003-coolify-vs-k8s.md
│   └── ...
├── diagrams/                       # 圖 bundle(由 `/create-arch-diagram` skill 從內建模板產生,每張架構一個資料夾;主架構 + N 子流程同檔切換)
│   ├── system-arch/                # ← /create-arch-diagram 產生
│   │   ├── README.md
│   │   └── diagram.html
│   └── payment-arch/
│       ├── README.md
│       └── diagram.html
└── roadmap.md                      # 長期方向(可選)
```

`adr/` 為主軸;其餘檔依需要建立。**禁**為了「看起來完整」湊檔。

---

## ADR 格式

採用 [Michael Nygard ADR](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) 簡化版。檔名 `{NNNN}-{kebab-title}.md`(連號,4 位數,不重複):

```markdown
# ADR-{NNNN}: <一句話標題>

- **狀態**:Proposed | Accepted | Deprecated | Superseded by ADR-{MMMM}
- **日期**:2026-05-07
- **決策者**:<人 / 角色>

## 背景(Context)
<為什麼要做這個決定;當時的 constraints>

## 決策(Decision)
<選了什麼;一句話 + 必要細節>

## 拒絕方案(Rejected Alternatives)
- **<方案 A>**:<為什麼不選>
- **<方案 B>**:<為什麼不選>

## 後果(Consequences)
- **正向**:<...>
- **負向 / Trade-off**:<必須清楚寫出代價>
- **後續可能觸發的 ADR**:<...>

## 參照
- 對應規範檔(若有):`docs/Design-Base/.../X.md`
- 對應 task / fixed.md(若有):`docs/Tasks/v{X.Y.Z}/...`
```

## ADR 規則

- **不可變更**:Accepted 後**禁**直接改;改變決策 → 開新 ADR + 把舊 ADR 狀態改 `Superseded by ADR-{NNNN}`
- **棄用** ≠ 刪除:狀態改 `Deprecated`,留檔(歷史脈絡有價值)
- **連號**:跳號要寫明(例如 `0007` 跳號因 `0006` 被討論棄用前已搶占)
- 一個 ADR = 一個決策(別把多個獨立決策塞同檔)

---

## 何時寫 ADR

- 決策影響**多版本** / **多模組** / **多人工作流**
- 走偏離**業界預設**的選擇(例:用 RTK Query 而非 React Query)
- 以**取捨**為核心(不是單純「正確答案」,而是「這條路好處 X 代價 Y」)
- 反過來:小範圍 / 一次性實作選擇 → **不**寫 ADR(寫進 PR description / task 即可)

---

## 與其他資料夾的差異

| | Design-Base | Arch(本檔) | Tasks |
| --- | --- | --- | --- |
| 內容 | 實作規範(do / don't) | 長期方向 + ADR | 版本目標 + 執行單元 + fixed |
| 變動頻率 | 低(reflect 升規) | 低(ADR 不可變) | 高(每版本) |
| 寫法 | 規則條列 + 範例 | 敘述性 + 取捨 | 條列 + checkbox |
| 對象 | agent / 實作者 | 架構師 / 跨團隊 reviewer | agent / orchestrator |
| 規則優先序 | 最高 | 中 | 最低 |

---

## 維護準則

- 採用方專案啟動時:先寫 `overview.md`(可選)+ 第一份 ADR(技術選型) → 補 `adr/0001-*.md`
- 新增 ADR → 連號累積;**禁**改舊 ADR(改決策 → 開新 ADR + Supersede)
- 規範升級(`docs/Design-Base/*` 改動)若源於 ADR → 規範檔開頭加 `> 對應 ADR-{NNNN}`
