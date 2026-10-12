# Power BI 建置規格

既有 Linux 管線驗證為 56 項通過（9.63 秒）；匯出使用共用鎖與一致性快照。此紀錄不表示 Power BI Desktop 的 M、DAX 或視覺已驗證；第 13 節為使用者待執行的建立與保存步驟。

## 1. 範圍與驗證限制

此規格依目前實作欄位描述手動重建方式；**不建立、不交付 `.pbix`**。Windows、Excel 桌面、Power BI Desktop 的 M／DAX／視覺與互動尚未實測。檢視實作不是執行驗證，不可標記通過。

agent Linux 已實測完整 CLI；`case` 2 日報為 590／8／10，`demo` 28 日報為 69,225／818／1,146。**這些結果不代表下面任何 Power BI 步驟已通過**；M、模型、DAX、排序、互動、下鑽、手動刷新與元資料呈現仍須逐步實測。

2026-10-11 Linux 既有實測為 **56 項全通過（9.63 秒）**，含完整連續日曆週、文字型別及一致性快照。再次 run 同檔跳過、指標不變（匯出時間更新）；資料庫完整性／外鍵／封存 SHA 通過，package 87 檔 CRC 通過且排除 venv／既有指南／pbix。87 檔逐一秘密掃描未發現秘密；**Power BI 各步驟仍待使用者實機驗證**，本次補文件未執行 Desktop。

CodeQL Python 既有實測 0 警示。自動 code review 模型不可用，不算通過；補充唯讀審查發現的型別與快照問題已修正，最終複查未發現新的高信心問題。來源所有識別碼及文字欄須為 Excel 文字型別，不接受數值；先設文字再輸入，既存數值重新輸入為文字。M 的 `type text` 不能替代來源驗證，也不能修復已合併的序號。

所有資料為合成資料（Synthetic Data），不代表真實工廠經驗、品質改善或根因證明。每頁標示模式、資料截止日、匯出時間與週暫定狀態。實作已輸出「說明」工作表，匯出時間為 UTC，但 Power BI 時間型別與卡片呈現尚未驗證；尚未接妥前留「資料匯出時間：待驗證」，不得以本機刷新時間冒充。

## 2. 實際資料契約

來源為 `data/<mode>/output/品質分析.xlsx`，**3 張事實表＋6 張維度＝9 張分析表，再加 1 張「說明」，共 10 張工作表**，首列為標題。完整命名與欄位契約如下，沒有待新增的分析表。

| 表 | 欄位／粒度 |
|---|---|
| `dim_date` | `prod_date`、`week_key`；連續日期，一日一列 |
| `dim_week` | `week_key`、`week_start`、`week_end`；一 ISO 週一列 |
| `dim_line` | `line`；一產線一列 |
| `dim_shift` | `shift`；一班別一列 |
| `dim_product` | `product`；一產品一列 |
| `dim_defect` | `defect_code`、`defect_name`、`defect_category`；一缺陷代碼一列 |
| `fact_production` | `prod_date,line,shift,product,input_boards,batch_id,source_sheet,source_row,bad_boards,defect_count`；一日／產線／班別／產品一列 |
| `fact_defect` | `defect_id,prod_date,line,shift,product,board_sn,defect_code,position,inspection_station,batch_id,source_sheet,source_row`；一缺陷事件一列 |
| `weekly_priority` | 以下完整週欄位；一 ISO 週／產線／班別／產品一列，含命中與未命中組合 |
| `說明` | `項目`、`內容`；不同項目的內容有文字、日期與日期時間 |

`weekly_priority` 完整欄位：

```text
week_key,line,shift,product,input_boards,bad_boards,defect_count,
bad_rate,baseline_rate,rate_multiple,sample_status,priority,
main_defect,reason,rule_version,provisional_status,
main_defect_count,main_defect_share,main_defect_tied
```

- `bad_boards` 由每個生產組合的不同 `board_sn` 計算；`fact_defect` 每列就是一次缺陷，**沒有 `defect_qty` 欄位**。
- `bad_rate`＝週不良板／週投入；`baseline_rate`＝同週**全部產線／班別／產品**的總不良板／總投入，SQL 固定計算。
- `rate_multiple`＝週率／基準，零基準為空白；不自行填無限大。
- `sample_status`：「樣本足夠」或「樣本不足」。
- `priority`：「優先調查」、「觀察（樣本不足）」或「未觸發規則」，不是布林欄位。
- `main_defect` 並列時列出所有並列缺陷名稱；`main_defect_count`、`main_defect_share` 是**每個並列代碼**的筆數／該組合總缺陷，不是並列合計；`main_defect_tied` 是布林。零缺陷占比為 0。
- `provisional_status`：「七日日報完整」或「截至資料截止日的暫定評估」。同週七個完整日報皆存在才標完整。
- ISO 週使用 `2026-W41`；ISO 週年不一定等於日期的日曆年。

## 3. Power Query：參數、函數與每表 M

### 3.1 `ProjectFolder` 參數

「轉換資料 → 管理參數」新增必要的文字參數 `ProjectFolder`，值例如：

```text
C:\作品\品質分析\data\case
```

它指向**模式目錄**，不是專案根目錄或 `output`。切換展示模式改為 `...\data\demo`。

建立空白查詢 `AnalysisWorkbook`，關閉啟用載入：

```powerquery
let
    Folder = Text.TrimEnd(ProjectFolder, {"\", "/"}),
    Source = Excel.Workbook(
        File.Contents(Folder & "\output\品質分析.xlsx"),
        null,
        true
    )
in
    Source
```

建立函數 `ReadSheet`，也關閉載入：

```powerquery
(sheet_name as text, column_types as list) as table =>
let
    Sheet = AnalysisWorkbook{[Item = sheet_name, Kind = "Sheet"]}[Data],
    Headers = Table.PromoteHeaders(Sheet, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, column_types, "en-US")
in
    Typed
```

實作輸出的是工作表，使用 `Kind = "Sheet"` 並提升首列標題。日期輸出已為 Excel 日期物件；明確轉型，不能只改顯示格式。

### 3.2 完整十表查詢

以下各段各建一個同名查詢並啟用載入。

`dim_date`：

```powerquery
let
    Source = ReadSheet("dim_date", {
        {"prod_date", type date}, {"week_key", type text}
    })
in
    Source
```

`dim_week`：

```powerquery
let
    Source = ReadSheet("dim_week", {
        {"week_key", type text},
        {"week_start", type date}, {"week_end", type date}
    })
in
    Source
```

`dim_line`：

```powerquery
let
    Source = ReadSheet("dim_line", {{"line", type text}})
in
    Source
```

`dim_shift`：

```powerquery
let
    Source = ReadSheet("dim_shift", {{"shift", type text}})
in
    Source
```

`dim_product`：

```powerquery
let
    Source = ReadSheet("dim_product", {{"product", type text}})
in
    Source
```

`dim_defect`：

```powerquery
let
    Source = ReadSheet("dim_defect", {
        {"defect_code", type text}, {"defect_name", type text},
        {"defect_category", type text}
    })
in
    Source
```

`fact_production`：

```powerquery
let
    Source = ReadSheet("fact_production", {
        {"prod_date", type date}, {"line", type text},
        {"shift", type text}, {"product", type text},
        {"input_boards", Int64.Type}, {"batch_id", type text},
        {"source_sheet", type text}, {"source_row", Int64.Type},
        {"bad_boards", Int64.Type}, {"defect_count", Int64.Type}
    })
in
    Source
```

`fact_defect`：

```powerquery
let
    Source = ReadSheet("fact_defect", {
        {"defect_id", type text}, {"prod_date", type date},
        {"line", type text}, {"shift", type text}, {"product", type text},
        {"board_sn", type text}, {"defect_code", type text},
        {"position", type text}, {"inspection_station", type text},
        {"batch_id", type text}, {"source_sheet", type text},
        {"source_row", Int64.Type}
    })
in
    Source
```

`weekly_priority`：

```powerquery
let
    Source = ReadSheet("weekly_priority", {
        {"week_key", type text}, {"line", type text},
        {"shift", type text}, {"product", type text},
        {"input_boards", Int64.Type}, {"bad_boards", Int64.Type},
        {"defect_count", Int64.Type}, {"bad_rate", type number},
        {"baseline_rate", type number}, {"rate_multiple", type number},
        {"sample_status", type text}, {"priority", type text},
        {"main_defect", type text}, {"reason", type text},
        {"rule_version", type text}, {"provisional_status", type text},
        {"main_defect_count", Int64.Type}, {"main_defect_share", type number},
        {"main_defect_tied", type logical}
    })
in
    Source
```

`說明`：先保持混合的 `內容` 為 `Any`，依 `項目` 明確格式化成文字，避免在同一欄把日期與聲明硬轉成同一日期型別。

```powerquery
let
    Source = ReadSheet("說明", {{"項目", type text}}),
    Display = Table.AddColumn(Source, "display_value", each
        if [項目] = "匯出時間" then
            DateTime.ToText(
                DateTime.From([內容]),
                [Format = "yyyy-MM-dd HH:mm:ss", Culture = "en-US"]
            ) & " UTC"
        else if [項目] = "資料截止日" then
            Date.ToText(
                Date.From([內容]),
                [Format = "yyyy-MM-dd", Culture = "en-US"]
            )
        else Text.From([內容], "zh-TW"),
        type text
    ),
    Result = Table.SelectColumns(Display, {"項目", "display_value"})
in
    Result
```

輸入「說明」契約仍是 `項目/內容`；模型查詢用 `display_value` 作呈現欄。這是格式化元資料，不取代 `dim_date` 等真正日期型別。實作將 UTC 時間移除時區後存 Excel，文字中必須保留「UTC」。

### 3.3 載入檢查

1. `prod_date`、`week_start`、`week_end` 圖示為日期，顯示格式 `yyyy-MM-dd`；不使用文字或自動日期階層。
2. 將 `dim_date` 標記為日期資料表，日期欄選 `prod_date`。
3. 所有維度鍵唯一、不空白且覆蓋事實；不能靠「移除重複」掩蓋輸出錯誤。
4. 「選項 → 目前檔案 → 資料載入」關閉自動日期／時間、自動偵測／建立關聯，刪除意外關聯。版本 UI 名稱待實測。
5. 欄位或型別錯誤立即回查 Excel／檢查報告，不補零、不忽略。

## 4. 模型：全部一對多、單向

所有下列關聯使用中，篩選皆由一端維度到多端：

| 一端 | 多端 |
|---|---|
| `dim_week[week_key]` | `dim_date[week_key]` |
| `dim_week[week_key]` | `weekly_priority[week_key]` |
| `dim_date[prod_date]` | `fact_production[prod_date]` |
| `dim_date[prod_date]` | `fact_defect[prod_date]` |
| `dim_line[line]` | `fact_production[line]` |
| `dim_line[line]` | `fact_defect[line]` |
| `dim_line[line]` | `weekly_priority[line]` |
| `dim_shift[shift]` | `fact_production[shift]` |
| `dim_shift[shift]` | `fact_defect[shift]` |
| `dim_shift[shift]` | `weekly_priority[shift]` |
| `dim_product[product]` | `fact_production[product]` |
| `dim_product[product]` | `fact_defect[product]` |
| `dim_product[product]` | `weekly_priority[product]` |
| `dim_defect[defect_code]` | `fact_defect[defect_code]` |

「說明」無關聯。禁止事實彼此、雙向、多對多、`dim_defect` 連到生產／週表、`dim_week` 再直接連日事實、`dim_date` 再連週表。不得建立第二條週路徑。

週切片器用 **`dim_week[week_key]`**，不是 `dim_date[week_key]`。單向日期篩選不會逆向到週維度；任意日期篩選不能把 SQL 整週結果變成部分週結果。週優先頁不放任意日期切片器。

## 5. 基礎 KPI 與元資料 DAX

```dax
投入板數 =
CALCULATE (
    SUM ( fact_production[input_boards] ),
    REMOVEFILTERS ( dim_defect )
)

不良板數 =
CALCULATE (
    SUM ( fact_production[bad_boards] ),
    REMOVEFILTERS ( dim_defect )
)

板件不良率 =
DIVIDE ( [不良板數], [投入板數] )

缺陷次數 =
COUNTROWS ( fact_defect )

生產組合數 =
CALCULATE (
    COUNTROWS (
        SUMMARIZE (
            fact_production,
            fact_production[line],
            fact_production[shift],
            fact_production[product]
        )
    ),
    REMOVEFILTERS ( dim_defect )
)

目前ISO週 =
SELECTEDVALUE ( dim_week[week_key], "請單選ISO週" )

匯出時間文字 =
CALCULATE (
    SELECTEDVALUE ( '說明'[display_value], "待驗證" ),
    '說明'[項目] = "匯出時間"
)

資料截止日文字 =
CALCULATE (
    SELECTEDVALUE ( '說明'[display_value], "待驗證" ),
    '說明'[項目] = "資料截止日"
)

資料說明 =
"合成資料（Synthetic Data）｜匯出時間：" & [匯出時間文字]
    & "｜資料截止日：" & [資料截止日文字]
```

模式來源需另以頁面文字／參數確認顯示 `case` 或 `demo`，不可沿用舊標題。此元資料接法仍需 Power BI 實測，未接妥前保留「待驗證」提示。

投入、不良板、缺陷、組合顯示整數且顯示單位「無」；率為百分比兩位。率按分子／分母加總後相除，空分母留空白，不平均日率。`REMOVEFILTERS` 是語意防護，不是錯誤關聯的補救。

## 6. 週優先清單 DAX

```dax
週組合數 =
COUNTROWS ( weekly_priority )

優先組合數 =
CALCULATE (
    COUNTROWS ( weekly_priority ),
    KEEPFILTERS ( weekly_priority[priority] = "優先調查" )
)

觀察組合數 =
CALCULATE (
    COUNTROWS ( weekly_priority ),
    KEEPFILTERS ( weekly_priority[priority] = "觀察（樣本不足）" )
)

週投入板數 =
SUM ( weekly_priority[input_boards] )

週不良板數 =
SUM ( weekly_priority[bad_boards] )

週缺陷次數 =
SUM ( weekly_priority[defect_count] )

週組合不良率 =
IF (
    COUNTROWS ( weekly_priority ) = 1,
    SELECTEDVALUE ( weekly_priority[bad_rate] )
)

同週固定基準 =
SELECTEDVALUE ( weekly_priority[baseline_rate] )

週率倍數 =
IF (
    COUNTROWS ( weekly_priority ) = 1,
    SELECTEDVALUE ( weekly_priority[rate_multiple] )
)

週優先標示 =
IF (
    COUNTROWS ( weekly_priority ) = 1,
    SELECTEDVALUE ( weekly_priority[priority] )
)

樣本狀態 =
IF (
    COUNTROWS ( weekly_priority ) = 1,
    SELECTEDVALUE ( weekly_priority[sample_status] )
)

主要缺陷 =
IF (
    COUNTROWS ( weekly_priority ) = 1,
    SELECTEDVALUE ( weekly_priority[main_defect] )
)

主要缺陷筆數 =
IF (
    COUNTROWS ( weekly_priority ) = 1,
    SELECTEDVALUE ( weekly_priority[main_defect_count] )
)

主要缺陷占比 =
IF (
    COUNTROWS ( weekly_priority ) = 1,
    SELECTEDVALUE ( weekly_priority[main_defect_share] )
)

主要缺陷並列 =
IF (
    COUNTROWS ( weekly_priority ) = 1,
    IF (
        SELECTEDVALUE ( weekly_priority[main_defect_tied] ),
        "並列（筆數與占比為每一代碼）",
        "無並列"
    )
)

調查理由 =
IF (
    COUNTROWS ( weekly_priority ) = 1,
    SELECTEDVALUE ( weekly_priority[reason] )
)

規則版本 =
SELECTEDVALUE ( weekly_priority[rule_version], "多版本／無資料" )

週評估狀態 =
SELECTEDVALUE ( weekly_priority[provisional_status], "混合狀態／無資料" )
```

表格需用 ISO 週＋產線＋班別＋產品形成一列；單組合量值在總計留空白。基準是 SQL 原值，切片縮到 L1 仍保留整週母體 `8/590`，不能改為 `4/250`。DAX 不重算 2 倍／100／3 命中；率的顯示四捨五入也不影響 SQL。全週零不良時未觸發，倍數空白；「未觸發」不等於合格。

## 7. 穩定並列柏拉圖

建立唯一顯示類別：

```dax
defect_label =
dim_defect[defect_code] & "｜" & dim_defect[defect_name]
```

以下保留目前週／產線／班別／產品與外部缺陷選擇，移除軸上當前缺陷列後逐代碼計數。排序為次數降冪，同次數則唯一代碼升冪，不用密集排名一起累加並列項目。

```dax
柏拉圖分母 =
VAR VisibleCodes =
    SELECTCOLUMNS (
        ALLSELECTED ( dim_defect ),
        "__code", dim_defect[defect_code]
    )
RETURN
    SUMX (
        VisibleCodes,
        VAR CodeValue = [__code]
        RETURN
            CALCULATE (
                [缺陷次數],
                REMOVEFILTERS ( dim_defect ),
                TREATAS ( { CodeValue }, dim_defect[defect_code] )
            )
    )

缺陷穩定序 =
VAR CurrentCode = SELECTEDVALUE ( dim_defect[defect_code] )
VAR CurrentQty = [缺陷次數]
VAR VisibleCodes =
    SELECTCOLUMNS (
        ALLSELECTED ( dim_defect ),
        "__code", dim_defect[defect_code]
    )
VAR Scored =
    ADDCOLUMNS (
        VisibleCodes,
        "__qty",
            VAR CodeValue = [__code]
            RETURN
                CALCULATE (
                    [缺陷次數],
                    REMOVEFILTERS ( dim_defect ),
                    TREATAS ( { CodeValue }, dim_defect[defect_code] )
                )
    )
RETURN
    IF (
        NOT ISBLANK ( CurrentCode ) && CurrentQty > 0,
        1 + COUNTROWS (
            FILTER (
                Scored,
                [__qty] > 0
                    && (
                        [__qty] > CurrentQty
                            || (
                                [__qty] = CurrentQty
                                    && [__code] < CurrentCode
                            )
                    )
            )
        )
    )

柏拉圖累計次數 =
VAR CurrentCode = SELECTEDVALUE ( dim_defect[defect_code] )
VAR CurrentQty = [缺陷次數]
VAR VisibleCodes =
    SELECTCOLUMNS (
        ALLSELECTED ( dim_defect ),
        "__code", dim_defect[defect_code]
    )
VAR Scored =
    ADDCOLUMNS (
        VisibleCodes,
        "__qty",
            VAR CodeValue = [__code]
            RETURN
                CALCULATE (
                    [缺陷次數],
                    REMOVEFILTERS ( dim_defect ),
                    TREATAS ( { CodeValue }, dim_defect[defect_code] )
                )
    )
RETURN
    IF (
        NOT ISBLANK ( CurrentCode ) && CurrentQty > 0,
        SUMX (
            FILTER (
                Scored,
                [__qty] > 0
                    && (
                        [__qty] > CurrentQty
                            || (
                                [__qty] = CurrentQty
                                    && [__code] <= CurrentCode
                            )
                    )
            ),
            [__qty]
        )
    )

柏拉圖累計占比 =
DIVIDE ( [柏拉圖累計次數], [柏拉圖分母] )

柏拉圖80%參考 =
0.8
```

視覺為折線及群組直條圖：

- X 軸：`dim_defect[defect_label]`。
- 直條 Y 軸：`[缺陷次數]`。
- 折線次軸：`[柏拉圖累計占比]`，固定 0–1、百分比；80% 用常數線或第二條 `[柏拉圖80%參考]`。
- 工具提示：`[缺陷穩定序]`、`[柏拉圖累計次數]`、`[柏拉圖分母]`。
- 視覺排序選 `[缺陷穩定序]` **升冪**；若版本無法依工具提示量值排序，先用明細表驗證，另確認可用視覺，不宣稱並列已穩定。
- 篩選 `[缺陷次數] > 0`，不開無資料項目、不使用 Top N。外部缺陷選擇會改分母，圖上單項的軸過濾不改分母。
- 不以醒目提示後的局部柱狀解讀完整分母；缺陷視覺對柏拉圖可選「無」避免誤讀。

### 案例核對

W41 v1 排序：`SHORT 4`、`INSUF 3`、`SHIFT 2`、`MISSING 1`；累計為 40%、70%、90%、100%。v2 排序：`INSUF 3`、`SHORT 3`、`MISSING 2`、`SHIFT 2`；累計為 30%、60%、80%、100%。只有 v2 有此並列情境，不能將兩版分布混用。名稱與字母順序可能不同，必須按代碼穩定排序。

v2 只選 P1 時共 4 次缺陷，SHORT 2 次占 50%；分母不能仍用全週 10。零資料時率空白，不捏造 100%。週表主要缺陷並列的占比是每代碼份額，不能把兩個 3 次合稱某單一缺陷 60%。

## 8. 共用切片器與編輯互動

四頁同步 `dim_week[week_key]`、`dim_line[line]`、`dim_shift[shift]`、`dim_product[product]`；ISO 週開啟單選、關閉全選，預設 `2026-W41`。頁首合成資料與模式，頁尾匯出時間、資料截止日、`[週評估狀態]`，並註明排序非因果。

班別資料值為「早」與「晚」；本文「早班」是說明名稱，實際切片器選 `dim_shift[shift] = "早"`，不要尋找不存在的「早班」值。

「格式 → 編輯互動」逐一設定：

| 來源 | 投入／不良板／率／組合 KPI | 缺陷分析 | 週清單 |
|---|---|---|---|
| 週／產線／班別／產品切片器 | 篩選 | 篩選 | 篩選 |
| 缺陷切片器／缺陷柱／柏拉圖 | **無** | 可篩選；對柏拉圖預設無 | **無** |
| 日點選／日期切片器 | 可在日頁限日 | 可限日 | **無** |
| 週表列點選 | 預設無，改用維度切片器／鑽研 | 預設無 | 不重新算 SQL |

單向模型仍需實測視覺互動；不能只看 DAX 就宣稱缺陷不改 KPI。週頁不放日期切片器，日頁限日也不代表週評估重新計算。

## 9. 四頁每視覺欄位配置

### 第 1 頁：品質總覽

| 視覺 | 配置 |
|---|---|
| 共用切片器 | 第 8 節四個維度，ISO 週單選 |
| 五張卡片 | 投入板數、不良板數、板件不良率、缺陷次數、生產組合數 |
| 日率折線 | X：`dim_date[prod_date]` 真日期；Y：板件不良率；提示：投入、不良板 |
| 產線長條 | Y：`dim_line[line]`；X：板件不良率；提示：投入、不良板；率降冪 |
| 班別／產品矩陣 | 列：`dim_shift[shift]` → `dim_product[product]`；值：投入、不良板、率 |
| 資料文字 | 資料說明、目前 ISO 週、週評估狀態；模式文字 |

v1 全週 590／8／10／4，約 1.36%；L1 250／4／5／2，1.60%。所有總計率以總分子／總分母相除。

### 第 2 頁：週異常優先清單

| 視覺 | 配置 |
|---|---|
| 共用切片器 | 第 8 節；不放任意日期／缺陷切片器 |
| 卡片 | 週組合數、優先組合數、觀察組合數、規則版本、週評估狀態 |
| 優先表格 | 維度欄：週、產線、班別、產品；值：週投入、週不良板、週缺陷、週組合率、固定基準、倍數、樣本狀態、優先標示、主要缺陷、主要缺陷筆數／占比／並列、調查理由 |
| 觀察表格 | 同上；視覺篩選 `weekly_priority[priority] = "觀察（樣本不足）"` |
| 全組合矩陣 | 列：產線 → 班別 → 產品；值：週投入、不良板、率、優先標示；不限制命中 |
| 規則文字 | 「SQL 固定同週整體基準；2 倍／100 投入／3 不良板；未四捨五入判定」 |

優先表格視覺篩選 `weekly_priority[priority] = "優先調查"`。卡片不套用表格的視覺篩選。兩表倍數降冪，同倍數再以產線／班別／產品穩定排序；總計關閉。無命中時表示「無優先調查組合」，但觀察表仍可有資料。

### 第 3 頁：缺陷與柏拉圖

| 視覺 | 配置 |
|---|---|
| 共用切片器 | 四個維度 |
| 生產卡片 | 投入、不良板、率；缺陷來源互動「無」 |
| 缺陷卡片 | 缺陷次數、柏拉圖分母 |
| 柏拉圖 | 第 7 節欄位、穩定序、次軸與工具提示 |
| 缺陷明細表 | `dim_defect[defect_label]`；缺陷次數、穩定序、累計次數／占比；穩定序升冪 |
| 產線／缺陷矩陣 | 列：`dim_line[line]`；欄：`dim_defect[defect_label]`；值：缺陷次數 |
| 說明文字 | 一板多缺陷；目前選擇分母；並列是每代碼占比 |

若加缺陷切片器，明示分母變成所選缺陷集合；不影響生產 KPI。v2 P1 的 SHORT 2／4＝50% 是單項占比，不是全週占比。

### 第 4 頁：組合下鑽與來源追溯

| 視覺 | 配置 |
|---|---|
| 共用切片器 | 四個維度，ISO 週單選 |
| 下鑽矩陣 | 列：`dim_line[line]` → `dim_shift[shift]` → `dim_product[product]` → `dim_date[prod_date]`；值：投入、不良板、率 |
| 日生產表 | 維度日期／產線／班別／產品；投入、不良板、率；不放缺陷碼 |
| 缺陷事件表 | `fact_defect` 的 `defect_id,prod_date,line,shift,product,board_sn,defect_code,position,inspection_station,batch_id,source_sheet,source_row` |
| 生產追溯表 | `fact_production` 的 `prod_date,line,shift,product,input_boards,bad_boards,defect_count,batch_id,source_sheet,source_row` |
| 日量率圖 | X：`dim_date[prod_date]`；直條：投入；折線次軸：率；提示：不良板 |
| 驗收說明 | v1 L1 早班 100／3／4，3%；v2 120／3／4，2.5% |

下鑽用維度階層「移至下一層／展開」。如另設鑽研跳頁，鑽研欄位用 `dim_week[week_key]`、`dim_line[line]`、`dim_shift[shift]`、`dim_product[product]`，保留全部篩選並加返回按鈕。來源表需包含**同一維度欄位**；不是看似相同的事實欄位。事實列點選不逆向傳到另一事實，跨表比對用維度篩選或鑽研。

## 10. v1／v2 分開驗收

原始交付 `case` 保留 v1 基準；v2 只在專案內獨立重建副本驗收，不覆寫交付原檔。

| 範圍 | v1 | v2 |
|---|---|---|
| W41 | 590／8／10／4，8/590 ≈ 1.36% | 610／8／10／4，8/610 ≈ 1.31% |
| W41＋L1 | 250／4／5／2，1.60% | 270／4／5／2，約 1.48% |
| W41＋L1＋早班 | 100／3／4／1，3.00% | 120／3／4／1，2.50% |
| 兩倍整週率門檻 | 2×8/590 ≈ 2.71186% | 2×8/610 ≈ 2.62295% |
| L1 早班分類 | 優先調查 | 未觸發規則，2.5% 小於門檻 |
| L2 早班分類 | 觀察（樣本不足） | 觀察（樣本不足） |

兩版缺陷總數同為 10，但 v1 為 SHORT 4、INSUF 3、SHIFT 2、MISSING 1，v2 為 SHORT 3、INSUF 3、SHIFT 2、MISSING 2；v2 P1 SHORT 2／4＝50%。v2 同時修正投入與缺陷分布，不是只有分母改變，更不是品質改善證據。以上為提供的預期值，文件代理未另行執行驗證。

最新驗證：上述 v1 全週／L1／早班與 v2 數值、規則結果已在 Linux pytest 通過；v2 不算獨立 CLI 驗證。本文 Power BI 呈現／互動驗收仍未執行。

展示模式 Linux CLI 基準：完整 4 週、28 日報、69,225 投入／818 不良板／1,146 缺陷，週表 72 個組合列；三類優先狀態均存在。低樣本情境每日 10 投入、每週 70 投入／21 不良板，應能在觀察類別解釋「率高但樣本不足」。Power BI 對這些基準的呈現仍未驗證。

agent Linux 實測週表分類：case 2 未觸發／1 優先／1 觀察；demo 64 未觸發／4 優先／4 觀察。這是 Linux 輸出基準，不表示 Desktop 卡片已驗收。

## 11. 手動換路徑與刷新

1. 先 Python 匯出正確模式的 Excel、檢查報告；關閉占用的 Excel。
2. Power BI 管理參數修改 `ProjectFolder`。
3. 核對來源 9 張分析表＋1 張說明共 10 張工作表與型別，套用、手動重新整理。
4. 清除舊篩選，選 W41；確認模式標題與資料時點。
5. 逐項核對 v1 或 v2，不能混用答案。
6. 完成缺陷互動、並列排序、P1 分母、週固定基準與下鑽驗收。
7. 「說明」時間接妥並實測後才取代暫定時間標示；Power BI 刷新時間不是匯出時間。

不承諾 Service、排程或閘道。Desktop 版本、環境、實際時間與操作結果記到驗證狀態。

## 12. 最低驗收清單（目前未驗證）

- [ ] 9 張分析表＋說明共 10 表，M 型別一致，真正日期與維度唯一鍵正確。
- [ ] 全部一對多單向，無雙向、事實彼此或第二條週路徑。
- [ ] ISO 週單選同步四頁；日期限日不改 SQL 週表。
- [ ] v1 全週／L1／早班手算相符。
- [ ] 副本 v2 全週 610／8／10、早班 120／3／4、2.5%，分類未觸發。
- [ ] SQL 固定基準、未四捨五入門檻、規則版本與三類優先狀態一致。
- [ ] 缺陷點選不改投入、不良板、率。
- [ ] v1 累計 40／70／90／100%；v2 並列穩定序與累計 30／60／80／100%，v2 P1 SHORT 50%。
- [ ] 零分母／無命中／零缺陷／部分週不誤導。
- [ ] 換路徑、手動刷新、匯出 UTC 時點與資料截止日顯示正確。

只可在實際操作後勾選，不把檢視程式當成通過。

## 13. 使用者建立與保存 .pbix：一次一個核對點

**狀態：全部待使用者在 Power BI Desktop 建立／驗證。** agent 沒有建立 `.pbix`，Linux 測試不覆蓋 M／DAX／視覺。此節在操作手冊第 1～8 步核對通過後才開始；教練每次只引導一個核對點，收到實際結果與「核對通過」才繼續。

**目的／應用程式：** 在 Windows Power BI Desktop 建立可保存、重開與手動刷新的作品，來源僅為 `品質分析.xlsx`。從「關於」畫面記錄 Desktop 完整版本；選單名稱如因版本不同，回報實際名稱並同步更正本節，不預先聲稱已驗證。

| 核對點 | 開啟位置與操作 | 意思與預期結果（不是已通過） | 實機核對／常見錯誤處理 |
|---|---|---|---|
| 9-A：建立空白檔 | Windows 檔案總管在自己的專案根目錄建立 `reports` 資料夾。開 Power BI Desktop，選空白報表；「檔案 → 另存新檔」至 `reports\電子組裝產線品質異常分析.pbix`。 | 這是你建立的本機報表，不是 agent 交付成品。預期檔名副檔名為 `.pbix`，可在檔案總管找到。 | 核對實際保存位置、Desktop 版本；若提示檔案已存在先另取名稱，不覆蓋唯一副本。保存被限制先回報權限／版本訊息。 |
| 9-B：關閉自動功能 | 「檔案 → 選項與設定 → 選項」在目前檔案的資料載入設定關閉自動日期／時間與自動偵測關係；參閱第 4 節。 | 模型由自己明確建置，不讓隱藏日期表或自動關係製造重複路徑。 | 記錄兩個設定實際位置與關閉狀態；若選項不在該位置，回報版本畫面，先確認再繼續。 |
| 9-C：設定 Excel 來源 | 新空白報表先「首頁 → 取得資料 → 空白查詢」開 Power Query；已有查詢可用「轉換資料」。依第 3.1 節建立 `ProjectFolder`，指向自己的 `data\case`；逐一建立 `AnalysisWorkbook`、`ReadSheet`，關閉兩者載入。 | 參數控制模式路徑，不寫死他人電腦路徑；Excel.Workbook 讀工作表。預期來源可列出十張工作表，函數無錯誤。 | 若空白查詢未在快捷清單，用「取得資料 → 更多」搜尋；確認指向模式資料夾而不是專案根目錄或 output。找不到檔案先查 `output\品質分析.xlsx` 是否存在；不要連 SQLite、不要用其他資料格式取代 Excel。 |
| 9-D：逐表匯入與型別 | 依第 3.2 節每次建一個同名查詢、貼對應完整 M；每表確認後才建下一表，最後「關閉並套用」。 | 9 分析表＋說明共10表載入；兩個輔助查詢不載入。型別轉換是資料契約，不只是顯示格式。 | 日期／週起訖為日期，數量為整數，率為小數，識別碼為文字，並列為布林；檢查說明的 display_value。任何轉換錯誤先停，不移除錯誤列或補零；零缺陷表只有標題也須能載入。 |
| 9-E：逐條建立關係 | 在模型檢視依第 4 節關係表，一次建立並核對一條；刪除非規格的自動關係。 | 共14條使用中的一對多單向關係，篩選由維度到事實；說明無關係。 | 看一端 `1`、多端 `*`、箭頭方向及實際鍵。不得連事實彼此或將主要缺陷連 dim_defect；重複鍵／空鍵先回查來源，不改多對多繞過。 |
| 9-F：逐個建立量值 | 報表檢視「新增量值」，依第 5～7 節一次貼一個完整 DAX；`defect_label` 依規格建計算欄而非量值。 | KPI 分開投入、不良板、缺陷；週等級使用 SQL 固定結果；柏拉圖目前範圍分母與並列順序明確。 | 每個量值無語法錯誤、數量整數、率百分比。名稱引用須與匯入欄一致；錯誤先貼該量值與訊息，不一次重寫全部。 |
| 9-G：四頁與互動 | 依第 8～9 節每次建一個視覺及其欄位配置。ISO週用 dim_week 單選，同步頁面；設定「編輯互動」及下鑽。每頁放合成資料、模式、匯出時間與暫定標示。 | 報表可顯示優先清單與缺陷原因線索，不推論根因。 | 依第 10 節逐項選 W41、L1、早班核對590／8／10→250／4／5→100／3／4與清單4→2→1。缺陷點選不改生產 KPI；並列柏拉圖排序與最後100%、帶入週／產線／班別／產品下鑽均須實測。 |
| 9-H：保存與重新開啟 | 清除額外篩選、恢復案例W41，`Ctrl+S` 保存；關閉 Desktop，再從檔案總管開同一 `.pbix`，手動重新整理。 | 檔案存在不代表完成；保存／重開／刷新才驗證報表可用。 | 再核對來源參數、10載入表、關係、四頁、手算、合成／暫定／匯出時間。失敗保留錯誤及上次已保存副本；不把快取結果當刷新通過。 |

完成每個核對點，填[使用者逐步實機驗收紀錄](驗證狀態.md#使用者逐步實機驗收紀錄)的實際日期、版本、結果與證據；每個量值／視覺可追加一列，不能僅用「報表看起來正常」代替互動與數據核對。

換電腦、切換 demo、v2 副本均依第 11 節重新驗收，不沿用案例 v1 的通過紀錄。實機建立的 `reports` **不在目前 Python 打包允許清單**，所以需另外保存與交付已驗收 `.pbix`；在你完成之前仍寫「待使用者在 Power BI Desktop 建立／驗證」。
