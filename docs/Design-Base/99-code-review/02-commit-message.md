# 02-commit-message — Commit Message

> **何時讀**:任何 commit 前都應遵守。

格式:`(AI?) <類型>: <描述>`(繁中)

類型:`Add` / `Modify` / `Fix` / `Refactor` / `Docs`

AI 產生**必**前綴 `(AI)`,例 `(AI) Fix: 修正 bcrypt 阻塞 event loop`。

**禁**:`--force` / `reset --hard` / `--no-verify` 未授權;skip hooks(hook 失敗去修 hook);偽造作者。
