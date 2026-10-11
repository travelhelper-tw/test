# 電子組裝產線品質異常分析｜求職作品

> **合成資料（Synthetic Data）作品。** 所有產線、產品、品質紀錄與異常情境均為人工合成，不代表任何公司的實際績效。這是可重建的分析作品，不是已部署的工廠系統。
>
> **驗證限制：** 文件中的操作步驟不等於已執行驗證。Windows、Windows 套件安裝、Excel 桌面程式與 Power BI Desktop 尚未驗證；本交付不含 `.pbix`。實作欄位與封存設計已同步文件，強制斷電回復未驗證，詳見[驗證狀態](docs/驗證狀態.md)。

**agent Linux 實測：** Python 3.12.3 x64、SQLite 3.45.1，`pip check` 無衝突；最新 **49 項 pytest 全通過（8.97 秒）**，含整週空窗的連續日曆週覆蓋。案例 2 日報 590／8／10，展示 28 日報 69,225／818／1,146；再次 run 同檔全跳過、數據不增、輸出相同。兩模式資料庫完整性與外鍵通過，所有封存 SHA／批次相符。ZIP 87 檔，CRC 檢查通過，排除 venv／既有指南／pbix；87 檔逐一秘密掃描未發現秘密。Windows／Power BI、強制斷電與正式審查仍待驗證。

## 作品定位

本作品以電子組裝產線的每日品質日報為起點，呈現「日報匯入 → 資料檢查 → SQLite 整理 → SQL 日／週／缺陷分析 → Excel 分析輸出 → Power BI 建置規格 → 面試展示」的完整流程。重點不是把缺陷數畫成圖，而是回答：

1. 哪個 ISO 週、產線、班別、產品組合需要優先處理？
2. 不良率變化如何隨投入量、日期與生產組合呈現，哪些組合達到調查規則？此規則非統計檢定，不能證明穩定異常或原因。
3. 最主要的缺陷是什麼？缺陷次數與不良板數是否被混淆？
4. 修正版日報如何重匯、追溯與避免重複計算？
5. 換一台 Windows 筆電後，是否能用文件重建成果？

分析只提供調查排序，不宣稱已找到因果或改善成效。若週資料尚未完整，必須說明是截至匯出時點的週內累積，不可當作完整週結果。

## 分析原則

- 欄位採 English `snake_case`；日期採 ISO `YYYY-MM-DD`，匯入 Power BI 後轉成真正日期型別。
- **投入板數**、**不良板數**、**缺陷次數**分開：同一不良板可能同時有多個缺陷，不可用缺陷次數計算板件不良率。
- 不良率＝不良板數 ÷ 投入板數。彙總時使用分子／分母加總後相除，不平均日率。
- 週優先條件：目標組合週率至少為同週全部組合總不良板／總投入的 **2 倍**，且週投入至少 **100**、週不良板數至少 **3**。達倍數但樣本不足為觀察，其他為未觸發；未觸發不等於合格。
- 門檻與路徑由 `config/settings.json` 管理；以 `rule_version` 留下規則版本。週率、基準與命中結果以 SQL 未四捨五入值判定，Power BI 不另算一套週規則。
- `case` 是可手算、可驗收的案例；`demo` 是另一個展示模式。兩種模式的資料、資料庫、封存與輸出必須隔離。

## 核心介面

### 直接跑已附資料（開箱流程）

儲存庫已附 `raw` 日報，首次直接 `run`，**不要先 `generate`**。生成器禁止覆蓋已存在日報。Windows 一律直接呼叫虛擬環境 Python，不啟用環境、不修改執行原則：

```powershell
py -3.12 -m venv venv6
.\venv6\Scripts\python.exe -m pip install -r requirements.txt
.\venv6\Scripts\python.exe -m quality run --mode case
.\venv6\Scripts\python.exe -m quality run --mode demo
```

案例與展示模式皆直接使用已附資料，不需生成。

### 要生成新資料（另設空資料夾）

先備份設定，在獨立工作副本將 `config/settings.json` 的 `modes` 改為新的、不含日報的資料夾：

```json
"modes": {"case": "data/new_case", "demo": "data/new_demo"}
```

此為設定中的欄位片段，其餘設定保留。確認路徑沒有既存日報後才執行：

```powershell
.\venv6\Scripts\python.exe -m quality generate --mode case
.\venv6\Scripts\python.exe -m quality run --mode case
.\venv6\Scripts\python.exe -m quality generate --mode demo
.\venv6\Scripts\python.exe -m quality run --mode demo
.\venv6\Scripts\python.exe -m quality export --mode demo
```

### 修正版與封裝（另行操作）

v2 僅在獨立副本驗收。若仍用原設定，修正版路徑如下；若設定改為 `data/new_case`，須同步改成 `data/new_case/revisions/...`：

```powershell
.\venv6\Scripts\python.exe -m quality import --mode case --file data/case/revisions/品質日報_2026-10-05_v2.xlsx --yes
.\venv6\Scripts\python.exe -m quality export --mode case
.\venv6\Scripts\python.exe -m quality package
```

不要刪除已附日報來繞過生成器保護。Linux 封裝允許清單已實測；ZIP 位於被忽略的 `deliverables`，不提交，但可用 `package` 重產，詳見交付指南。

## 資料與交付結構

```text
README.md
requirements.txt
quality/
  __main__.py
  core.py
  generate.py
  analysis.py
sql/
  schema.sql
  daily_summary.sql
  weekly_summary.sql
  defect_analysis.sql
tests/
  test_quality.py
config/
  settings.json
data/
  case/
    raw/
    archive/
    revisions/
    quality.sqlite3
    output/
      品質分析.xlsx
      檢查報告.xlsx
  demo/
    raw/
    archive/
    revisions/
    quality.sqlite3
    output/
      品質分析.xlsx
      檢查報告.xlsx
deliverables/
  作品交付.zip
docs/
  操作手冊.md
  PowerBI建置規格.md
  四週安排.md
  展示腳本.md
  交付指南.md
  驗證狀態.md
```

`raw` 保留輸入、`revisions` 放修正版。封存先複製來源驗 SHA，再以 SQLite backup 建交易前備份，整日交易提交後改名正式封存；改名失敗回復資料庫。排他鎖與 pending 殘留阻擋後續匯入，不能直接刪備份解除；這不是跨系統分散式原子交易，強制斷電未驗證。`quality.sqlite3` 是分析資料庫；兩份 Excel 分別承載分析資料與檢查結果。ZIP 不含 `venv6` 或 `.pbix`。

## 文件索引

| 文件 | 用途 |
|---|---|
| [操作手冊](docs/操作手冊.md) | 環境、雙模式、修正版、設定、SQL 與故障處理 |
| [Power BI 建置規格](docs/PowerBI建置規格.md) | Power Query、模型、DAX、四頁視覺配置與驗收 |
| [四週安排](docs/四週安排.md) | 每週成果、驗收與求職練習 |
| [展示腳本](docs/展示腳本.md) | 三分鐘講解與追問準備 |
| [交付指南](docs/交付指南.md) | 打包、USB、另一台筆電重建 |
| [驗證狀態](docs/驗證狀態.md) | 區分規格、實際驗證、待驗事項 |

## 可手算基準

`case` 的 ISO `2026-W41`：

| 篩選 | 投入 | 不良板 | 缺陷次數 | 生產組合數 | 板件不良率 |
|---|---:|---:|---:|---:|---:|
| W41 全部 | 590 | 8 | 10 | 4 | 8 ÷ 590 ≈ 1.36% |
| W41、L1 | 250 | 4 | 5 | 2 | 4 ÷ 250＝1.60% |
| W41、L1、早班 | 100 | 3 | 4 | 1 | 3 ÷ 100＝3.00% |

「組合數」是目前篩選下的產線／班別／產品組合，不是優先命中數。實際資料與 Power BI 需逐項驗收後才可把以上預期值標記為通過。

原始交付 `case` 保留 v1。v2 僅在獨立重建副本測試：全週 610／8／10，L1 270／4／5，L1 早班 120／3／4、2.50%，低於 `2×8/610` 約 2.62295%，因此未觸發；L2 早班仍為觀察。v1 缺陷為 SHORT 4、INSUF 3、SHIFT 2、MISSING 1；v2 為 SHORT 3、INSUF 3、SHIFT 2、MISSING 2，v2 的 P1 SHORT 2／4＝50%。兩版缺陷總數同為 10，但分布不同，不能說只有投入改變或當成改善證明。

## 技術環境

目標 Python：Linux **3.12.3 x64**；Windows 使用 Python 3.12 建立 `venv6`，實際版本與相容性待驗證。套件鎖定清單見操作手冊。Power BI Desktop 採手動建置與刷新，無排程刷新保證。報表與匯出時間必須標示為合成資料，匯出時間欄位／實際刷新時間的串接尚待驗證，不能使用固定文字冒充即時時間。

### 實測環境與套件版本

agent Linux 實測 Python 3.12.3 x64、SQLite 3.45.1，`pip check` 無衝突與最新 49 項測試通過（8.97 秒）。

案例週分類為 2 未觸發／1 優先／1 觀察；展示週分類為 64 未觸發／4 優先／4 觀察。

| 套件 | 版本 | 狀態 |
|---|---|---|
| pandas | 2.2.3 | Linux 實測環境 |
| numpy | 2.1.3 | Linux 實測環境 |
| openpyxl | 3.1.5 | Linux 實測環境 |
| et-xmlfile | 2.0.0 | Linux 實測環境 |
| python-dateutil | 2.9.0.post0 | Linux 實測環境 |
| pytz | 2024.2 | Linux 實測環境 |
| tzdata | 2024.2 | Linux 實測環境 |
| six | 1.17.0 | Linux 實測環境 |
| pytest | 8.3.5 | Linux 實測環境 |
| pluggy | 1.5.0 | Linux 實測環境 |
| iniconfig | 2.0.0 | Linux 實測環境 |
| packaging | 24.2 | Linux 實測環境 |
| colorama | 0.4.6 | 僅 Windows；Linux 未裝、Windows 未測 |

### Windows／Power BI 驗證填寫欄

實際執行後填寫，不先標通過：

| 項目 | 版本／環境 | 日期時間（含時區） | 實際結果／證據 |
|---|---|---|---|
| Windows 版本／架構 | 待填 | 待填 | 未驗證 |
| Python／依賴／colorama | 待填 | 待填 | 未驗證 |
| Power BI Desktop 版本 | 待填 | 待填 | 未驗證 |
| M／日期型別／模型 | 待填 | 待填 | 未驗證 |
| KPI／優先清單／柏拉圖 | 待填 | 待填 | 未驗證 |
| 互動／下鑽／換路徑刷新 | 待填 | 待填 | 未驗證 |
| 匯出 UTC 時點／資料截止日 | 待填 | 待填 | 未驗證 |
