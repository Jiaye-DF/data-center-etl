# 05-precision — 數值精度

> **何時讀**:寫金額 / 計費欄位才讀。

金額 / 計費 / 餘額(`amount` / `price` / `balance` / `total`):**禁** FLOAT / DOUBLE → `Numeric(18, 2)` 或整數最小單位(分)。
