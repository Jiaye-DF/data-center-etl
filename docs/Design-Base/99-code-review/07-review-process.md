# 07-review-process — Review 流程

> **何時讀**:設定 / 執行 PR review 流程時讀。

## 基本流程

- 主分支 `main`,功能分支從 `main` 切出
- PR 必經至少 1 reviewer 同意 + 全部 CI green 才能 merge
- 衝突仲裁:衝突依 `00-overview/00-overview.md § 規範優先順序` 機械式判定
- 規範被推翻 → commit / task doc 註明 + `fixed.md` 補根因(見 `01-fixed-md.md`)

## hook 失敗

hook 失敗去**修 hook 或修 code**,**禁** `--no-verify`。
