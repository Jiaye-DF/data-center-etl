---
id: task-001
title: ETL framework 核心骨架
status: done
parallel: true
depends_on: []
affected_files:
  - etl/main.py
  - etl/__init__.py
  - etl/common/__init__.py
  - etl/common/config.py
  - etl/common/logger.py
  - etl/common/utils.py
  - etl/jobs/__init__.py
  - etl/transforms/__init__.py
  - etl/transforms/common.py
  - etl/tests/__init__.py
  - etl/config/job_config.yaml
  - etl/config/table_config.yaml
  - etl/requirements.txt
  - etl/README.md
estimated_hours: 4
---

## 目標

建立獨立 `etl/` 專案的 Glue Job framework 骨架:`main.py` 入口以**設定驅動的動態派工**執行 `jobs.<name>_job`,搭配 config 載入器 / logger / utils / 共用 transform 基底。此 task 只建骨架與共用層,**不含**來源 reader、目標 writer、具體 job(見 002–005)。

## 範圍要點(避免與後續 task 互鎖)

- `main.py` 依 `config/job_config.yaml` 的 job 名稱**動態 import** `jobs.<name>_job` 並呼叫其 `run(...)`;新增 job **不得**回頭改 `main.py`。
- `common/config.py`:讀 `config/*.yaml` + `config/mapping/*.yaml`,回傳 dict/dataclass;yaml 解析集中於此。
- `common/logger.py`:標準 logging 包裝(structured,可印 job 名 / 表名 / 筆數)。
- `common/utils.py`:純函式小工具(如時間、命名正規化);時區一律 UTC+8。
- `transforms/common.py`:共用轉換 helper 基底(trim / 型別轉換 / null 正規化),供 004/005 匯入,兩者**不改**本檔。
- `config/mapping/` 目錄需存在(可放 `.gitkeep`)供 004/005 落 yaml。
- `requirements.txt`:鎖定 `pyspark` 版本(附版號)。

## Acceptance

- [ ] `python -m py_compile etl/main.py etl/common/config.py etl/common/logger.py etl/common/utils.py etl/transforms/common.py` 全通過(exit 0)
- [ ] `python -c "import yaml; yaml.safe_load(open('etl/config/job_config.yaml')); yaml.safe_load(open('etl/config/table_config.yaml'))"` 不拋錯
- [ ] `python -c "import etl.common.config as c; print(hasattr(c,'load_config'))"` 印 `True`(config 載入器存在且可 import)
- [ ] `[ -d etl/config/mapping ] && [ -f etl/requirements.txt ] && grep -q 'pyspark' etl/requirements.txt` 成立
- [ ] `main.py` 內無以 if/elif 硬列 job 名稱的派工(以動態 import 實作;人工檢視 + `! grep -qE "elif .*job_name ==" etl/main.py`)

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`(規範優先序 + 輸出語言 = 繁中)
- `docs/Design-Base/00-overview/02-secrets.md`(DB / S3 憑證以 env 注入,禁硬編)
- `docs/Design-Base/00-overview/05-timezone.md`(全棧 UTC+8 / Asia/Taipei)
