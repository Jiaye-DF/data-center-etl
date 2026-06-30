# 04-fixed-format — fixed.md 條目格式

> **何時讀**:寫 / 改 fixed.md 才讀。

`docs/Tasks/v{X.Y.Z}/fixed.md`(3-digit semver,例 `v1.0.0` / `v1.1.0`):當版本內**所有**規範違反 / bug 根因的累積。Agent 寫,user **不**主動寫。

---

## 寫入時機

- 違反 `docs/Design-Base/*` 任何規則(自己 / 他人 PR)
- 規範被推翻(該規則不適用本情境)
- 重大 bug(影響線上 / 跨版本累積)
- 無聊 typo / 空白格式 → **不寫**(屬於 lint 範疇)

## 條目格式

```markdown
## §{N} — <一句話標題>

- **時間**:2026-05-07T14:23+08:00
- **commit / PR**:`<hash>` / `#<num>`
- **影響檔案**:`<path>` / `<path>`
- **問題**:<發生什麼;使用者 / agent 觀察到的現象>
- **根因**:<為什麼發生;系統性原因。**禁**只寫「typo」「忘了」「漏掉」>
- **修正**:<怎麼改;鏈到 commit hash>
- **規範參照**:`<docs/Design-Base/.../X.md § Y>`(若違反規範,必填)
- **後續**:<是否需 reflect 升規 / 是否補測試 / 是否棄用該規則>
```

---

## 範例

```markdown
## §3 — JWT_SECRET development 預設值上 staging

- **時間**:2026-05-07T14:23+08:00
- **commit / PR**:`a93b8a2` / `#42`
- **影響檔案**:`backend/app/config.py`、`.env.staging`
- **問題**:staging 部署成功啟動,但所有 token 都用 development 預設 secret 簽,可被本機偽造
- **根因**:`Settings._fail_fast_in_prod` validator 漏列 `JWT_SECRET_KEY`,fail-fast 沒觸發;新增 secret 欄位時未同步加進 validator 清單
- **修正**:加 `JWT_SECRET_KEY` 進 validator,並補單元測試掃所有 `*_SECRET_*` 欄位都在清單內(`commit b9...`)
- **規範參照**:`03-backend/04-config.md § 啟動 fail-fast` / `00-overview/02-secrets.md § .env*.example 規則`
- **後續**:reflect 候選 — fail-fast validator 是否該自動掃 `*_SECRET_*` 而非手動列
```

---

## 規則

- **§{N}** 編號連號(全版本內,跨 task)
- 一條 fixed = 一個根因(別把多個獨立問題塞同條;若連動,各寫一條 + cross-ref `見 §M`)
- **根因欄是核心**:寫到「為什麼」而非「改了什麼」
  - ❌ 「JWT_SECRET 上錯」
  - ✅ 「fail-fast validator 漏列 `JWT_SECRET_KEY`,新增欄位時未同步」
- 同類條目跨版本 ≥ 3 → reflect 候選升規(見 `07-rule-evolution.md`)
- **禁**刪除舊條目(歷史不可竄改);過時條目加 `> 後續:已棄用,見 vX.Y.Z §M`

## 跨版本

- `fixed.md` 屬**當版本**;不複製到下版本
- reflect 跑時讀**全部**版本的 `fixed.md`(`docs/Tasks/v*/fixed.md`)做 pattern 分析
