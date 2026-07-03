#!/usr/bin/env bash
# deploy_s3.sh — 將 etl/ 上傳到 S3,供 AWS Glue Job 從上傳後的 main.py 讀取執行。
#
# 安全規則(對齊 CLAUDE.md 毀滅性操作禁止 / 00-overview/02-secrets.md):
#   - bucket / prefix 一律走 env(ETL_BUCKET / ETL_PREFIX),禁硬編。
#   - 缺 ETL_BUCKET 立即 fail-fast(在呼叫任何 aws 指令之前)。
#   - 僅以 `aws s3 sync` 上傳,不加 --delete(不刪 S3 既有物件),不使用 rm -rf。
#
# 用法(於 repo 根目錄或任意路徑,Git Bash):
#   ETL_BUCKET=my-etl-bucket ETL_PREFIX=etl/ bash etl/scripts/deploy_s3.sh
#   (ETL_PREFIX 可省略,預設為 etl/)

set -euo pipefail

# --- 1) env 檢查(必須在任何 aws 呼叫之前)---------------------------------
if [[ -z "${ETL_BUCKET:-}" ]]; then
  echo "錯誤:缺少必要環境變數 ETL_BUCKET(目標 S3 bucket 名)。" >&2
  echo "      範例:ETL_BUCKET=my-etl-bucket bash etl/scripts/deploy_s3.sh" >&2
  exit 1
fi

# ETL_PREFIX 預設 etl/;去掉開頭斜線並確保結尾為單一斜線,避免 s3 路徑重複斜線。
ETL_PREFIX="${ETL_PREFIX:-etl/}"
ETL_PREFIX="${ETL_PREFIX#/}"
ETL_PREFIX="${ETL_PREFIX%/}/"

# --- 2) 定位 etl/ 來源目錄(以本腳本所在位置回推,執行路徑無關)-----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ETL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"   # etl/scripts/.. = etl/

DEST="s3://${ETL_BUCKET}/${ETL_PREFIX}"

echo "來源:${ETL_DIR}"
echo "目標:${DEST}"
echo "開始上傳(aws s3 sync,排除 tests/ 與 __pycache__ 與 *.pyc)..."

# --- 3) 上傳(排除測試與快取;config yaml 不含機密,照上傳)-----------------
aws s3 sync "${ETL_DIR}" "${DEST}" \
  --exclude "tests/*" \
  --exclude "**/__pycache__/*" \
  --exclude "*.pyc" \
  --exclude ".pytest_cache/*" \
  --exclude "etl_pkg.zip"

# --- 4) 打包子套件 zip(Glue --extra-py-files 只吃檔案,不吃目錄)-------------
#     zip 根層即 common/ jobs/ transforms/,Glue 加進 sys.path 後 import common 可解析。
#     用 python stdlib zipfile,不依賴系統 zip 指令(Windows Git Bash 常缺)。
PY_BIN="$(command -v python || command -v python3)"
PKG_ZIP="${ETL_DIR}/etl_pkg.zip"
rm -f "${PKG_ZIP}"
(
  cd "${ETL_DIR}"
  "${PY_BIN}" - <<'EOF'
import zipfile
from pathlib import Path

with zipfile.ZipFile("etl_pkg.zip", "w", zipfile.ZIP_DEFLATED) as zf:
    for pkg in ("common", "jobs", "transforms"):
        for path in sorted(Path(pkg).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            zf.write(path, path.as_posix())
print("etl_pkg.zip 打包完成")
EOF
)
aws s3 cp "${PKG_ZIP}" "${DEST}etl_pkg.zip"
rm -f "${PKG_ZIP}"

echo "上傳完成。"
echo "提示:Glue Job 設定對應值 —"
echo "  Script location : ${DEST}main.py"
echo "  --extra-py-files: ${DEST}etl_pkg.zip"
echo "  --config-s3-uri : ${DEST}config/   (job argument;改 S3 上 yaml 下次 run 生效)"
