"""容器內 ETL 執行核心(v1.1.0):純 Python、DB 設定驅動,不依賴 Glue / Spark。

轉換與 Comment 規則移植 v1.0.0 `etl/transforms/*` 與 `etl/config/mapping/*.yaml` 行為;
v1.0.0 `etl/` 目錄凍結,僅唯讀參考。
"""

from app.etl.comments import build_column_comments, quote_ident, quote_literal
from app.etl.engine import (
    DbRunStore,
    EtlRunResult,
    EtlTableConfig,
    RunStore,
    SourceReader,
    TargetWriter,
)
from app.etl.reader import PostgresSourceReader
from app.etl.transforms import (
    ColumnMapping,
    convert_value,
    infer_ds_transform_type,
    map_row,
)
from app.etl.writer import PostgresTargetWriter

# now_tw 正典位置已搬 app/utils/datetime.py(fixed.md §5);此處保留 re-export 相容舊 import
from app.utils.datetime import now_tw

__all__ = [
    "ColumnMapping",
    "DbRunStore",
    "EtlRunResult",
    "EtlTableConfig",
    "PostgresSourceReader",
    "PostgresTargetWriter",
    "RunStore",
    "SourceReader",
    "TargetWriter",
    "build_column_comments",
    "convert_value",
    "infer_ds_transform_type",
    "map_row",
    "now_tw",
    "quote_ident",
    "quote_literal",
]
