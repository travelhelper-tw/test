# 用自己的複製聲音製作中文有聲書：Windows 本機新手手冊（草案 v0.2）

查閱日期：2026-09-29（v0.2 於 2026-10-06 對照固定 commit 原始碼修訂）。這份是給你審閱的草案，現在不用安裝或執行任何東西。

## v0.2 修訂摘要

- 更正清單 P 項：語者嵌入用整段參考音；前 6 秒只用於 T3 條件 token；前 10 秒只用於 S3Gen 參考。
- 3.2 同步修改：整段參考音都要乾淨。
- 10.2 批次程式：加入 `ATTEMPT` 參數（重做時換種子）、處理 BOM、收尾引號不被切開、超長句再切、超長警告。
- 10.4 重做流程：重跑時需加上 `ATTEMPT` 參數。
- 10.5 接合：改為重新編碼並統一格式，不再用 `-c copy`。
- 第 2 章：註明腳本只執行一次，並加入自動比對雜湊。
- 補充：種子可重現性的前提、Perth 實際 commit 的記錄方式、清單 M 的說明。

## 先看結論

- **選定的模型路線**：Resemble AI 的 **Chatterbox Multilingual V3**。程式碼用 GitHub 固定 commit，模型用 Hugging Face 一般多語模型 `ResembleAI/chatterbox`。
- **不使用的路線**：中文專門模型 `ResembleAI/Chatterbox-Multilingual-zh-cmn`。它的程式碼、權重和授權是另一套，我沒查它，所以整份手冊都不會引用它的授權。
- **私人測試**：可以照這份手冊做。
- **商業上架：目前暫停**。模型權重的授權、平台的 AI 語音政策、揭露義務，這次都還沒查到原文（見第 11 章）。

---

## 0. 查核清單

| # | 項目 | 內容 | 狀態 | 來源 |
|---|---|---|---|---|
| A | GitHub repo | `resemble-ai/chatterbox` | 已確認 | https://github.com/resemble-ai/chatterbox |
| B | 程式碼版本 | commit `5de7a54aa4e5e2baadb0182dde554908b48b85c2`；`pyproject.toml` 寫 `version = "0.1.7"` | 已確認 | [pyproject.toml](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/pyproject.toml) |
| C | PyPI 上的 `chatterbox-tts==0.1.7` 是否和上面那個 commit 內容相同 | 無法確認，所以**不從 PyPI 安裝**，改直接安裝那個 commit | 未確認 | https://pypi.org/project/chatterbox-tts/ |
| D | 程式碼授權 | MIT，Copyright (c) 2025 Resemble AI | 已確認（只限程式碼） | [LICENSE](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/LICENSE) |
| E | 主要依賴版本 | Python ≥3.10（官方在 3.11 上測試）；torch==2.6.0、torchaudio==2.6.0、transformers==5.2.0、librosa==0.11.0、numpy<2、spacy-pkuseg | 已確認 | 同 B |
| F | 浮水印套件 | `resemble-perth`，從 GitHub **master 分支**安裝（pyproject.toml 第 24 行），沒有固定版本 | 已確認（版本會隨時間變動） | 同 B |
| G | 程式實際下載的模型 repo | `ResembleAI/chatterbox`，程式裡寫死 `revision="main"` | 已確認 | [mtl_tts.py 第 21、242–251 行](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/src/chatterbox/mtl_tts.py#L21-L251) |
| H | 下載的權重檔 | `ve.pt`、`t3_mtl23ls_v3.safetensors`（用 `t3_model="v3"` 時）、`s3gen.pt`、`grapheme_mtl_merged_expanded_v1.json`、`conds.pt`、`Cangjie5_TC.json` | 已確認 | 同 G |
| I | 預設模型是 V2 | 沒指定 `t3_model` 時會用 `t3_mtl23ls_v2.safetensors`，所以本手冊一律明確寫 `t3_model="v3"` | 已確認 | 同 G，第 22 行 |
| J | 模型卡與**權重授權** | https://huggingface.co/ResembleAI/chatterbox 。搜尋摘要說是 MIT，但我沒讀到模型卡原文，不能當授權依據 | **未確認** | 模型卡 |
| K | 權重版本（Hugging Face commit） | 程式預設抓 `main`，內容可能變動。本手冊改成手動固定版本（第 4.6 節） | 需要你操作時記錄 | — |
| L | 支援中文 | `language_id="zh"` | 已確認 | mtl_tts.py 第 54 行 |
| M | 中文講得像台灣口音、正確讀出繁體字 | 有下載 `Cangjie5_TC.json` 這個檔案，但 `mtl_tts.py` 本身沒有直接引用它（使用方式未確認），官方也沒說明對台灣口音的效果 | 推測／未確認 | — |
| N | 每個生成檔都加浮水印 | `generate()` 最後一定會呼叫 `apply_watermark`，沒有關閉的參數 | 已確認 | mtl_tts.py 第 354 行；README |
| O | 單次生成長度上限 | `max_new_tokens=1000`。換算成秒數取決於 `S3_TOKEN_RATE`（未查），約 40 秒是推測，所以本手冊每段文字控制在 120 字以內 | 程式碼已確認；秒數為推測 | 第 328 行 |
| P | 參考音實際用到的長度 | 語者嵌入（voice encoder）用**整段**參考音，沒有截斷；T3 條件 token 只取前 6 秒；S3Gen 參考只取前 10 秒 | 已確認 | 第 156–157、257、259、266、270 行 |
| Q | Windows 支援 | 官方只說在 Debian 11 上測試過，Windows 沒有官方保證 | 已確認 | README 第 64 行 |
| R | `prepare_conditionals` 後直接 `generate` | 沒傳 `audio_prompt_path` 時會使用已準備好的 `self.conds`；`exaggeration` 相同就不重建 | 已確認 | 第 300–312 行 |

**日後重新查核版本的方法**（半年後環境可能不同）：
1. 打開 `https://github.com/resemble-ai/chatterbox/commits/master`，看有沒有新 commit。
2. 比對新版的 `pyproject.toml` 和 `src/chatterbox/mtl_tts.py`，特別注意 `generate()` 的參數、`REPO_ID`、`allow_patterns` 這幾處。
3. 打開 `https://huggingface.co/ResembleAI/chatterbox/commits/main`，看權重有沒有更新。
4. 換版本前，先在新的資料夾重跑第 4～6 章，不要動舊環境。

---

## 1. 硬體與 Windows 版本檢查

**操作位置**：開始功能表 → 輸入 PowerShell → 開啟「Windows PowerShell」（不需要系統管理員權限）。

```powershell
# 只讀取系統資訊，不改動任何檔案
Get-ComputerInfo -Property OsName, OsVersion, OsArchitecture, CsTotalPhysicalMemory
Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion
Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{n='FreeGB';e={[math]::Round($_.Free/1GB,1)}}
nvidia-smi
```

**預期結果**：看到 Windows 10 或 11 的 64 位元版本、記憶體大小、顯示卡名稱，以及各磁碟剩餘空間。

**依結果分成三條路**：

| 情況 | 走哪條路 |
|---|---|
| `nvidia-smi` 能列出 NVIDIA 顯卡，顯示記憶體（VRAM）8 GB 以上 | **CUDA 路線**（使用顯示卡加速） |
| 沒有 NVIDIA 顯卡，或 `nvidia-smi` 顯示找不到指令 | **CPU 路線**（能用但很慢，長篇書可能要花好幾天） |
| 系統記憶體（RAM）少於 16 GB，或工作磁碟剩餘少於 30 GB | **先停下**，升級硬體或清出空間後再繼續 |

- 上表的 8 GB 和 16 GB 是推測的建議值，官方沒有公布硬體需求。
- `AdapterRAM` 這個欄位對 4 GB 以上的顯示卡常常顯示錯誤，顯示記憶體請以 `nvidia-smi` 為準。

**這一步改動的檔案**：無。

---

## 2. 保護原始檔、建立工作資料夾

原則：**原始檔只讀不改**。所有處理都在副本上做，也不使用任何會移動或刪除原始檔的指令。

**2.1 先備份文字稿**（目前尚未確認已備份）：在檔案總管把文字稿資料夾複製到 USB，然後打開 USB 上的其中一個檔案，確認內容正常。

**2.2 建立工作資料夾並複製素材**

需要替換的路徑：`C:\Users\你\原始錄音`（原始 MP3 所在位置）、`C:\Users\你\原始文字稿`（文字稿所在位置）。

> **這支腳本只執行一次。** 副本會被設成唯讀，再執行一次 `Copy-Item` 會因無法覆蓋而報錯。若路徑含中文字元，部分工具可能出問題，工作資料夾（`$Work`）請只用英文路徑。

```powershell
$Work = "D:\VoiceBook"                      # 可改成其他磁碟；路徑請只用英文
$SrcAudio = "C:\Users\你\原始錄音"
$SrcText  = "C:\Users\你\原始文字稿"

New-Item -ItemType Directory -Force -Path "$Work\00_originals_copy\audio","$Work\00_originals_copy\text","$Work\01_ref","$Work\02_scripts","$Work\03_book_text","$Work\04_out","$Work\05_final","$Work\models","$Work\logs" | Out-Null
Copy-Item "$SrcAudio\*.mp3" "$Work\00_originals_copy\audio\"
Copy-Item "$SrcText\*"      "$Work\00_originals_copy\text\"

# 把副本設成唯讀，避免誤改
Get-ChildItem "$Work\00_originals_copy" -Recurse -File | ForEach-Object { $_.IsReadOnly = $true }

# 記錄雜湊值，之後可比對副本是否和原檔一致
Get-FileHash "$SrcAudio\*.mp3" -Algorithm SHA256 | Export-Csv "$Work\logs\original_hashes.csv" -NoTypeInformation

# 自動比對原檔與副本的雜湊值
$a = Get-FileHash "$SrcAudio\*.mp3" -Algorithm SHA256 | Sort-Object { Split-Path $_.Path -Leaf }
$b = Get-FileHash "$Work\00_originals_copy\audio\*.mp3" -Algorithm SHA256 | Sort-Object { Split-Path $_.Path -Leaf }
if (-not (Compare-Object $a.Hash $b.Hash)) { "全部一致" } else { "有不一致，請停下" }
```

**預期結果**：顯示「全部一致」。

**失敗排查**：
- 找不到路徑：檢查路徑有沒有打錯。
- 「存取被拒」：換一個你有權限寫入的資料夾，例如「文件」底下。
- 顯示「有不一致」：不要繼續，重新複製（需先在檔案總管手動處理副本）。

**改動的檔案**：只在 `D:\VoiceBook` 裡新增檔案。原始位置不會被改動。

---

## 3. 選取並只處理一段參考音副本

**3.1 安裝 ffmpeg（處理音檔的工具）**

```powershell
winget install --id Gyan.FFmpeg -e
# 安裝完請關閉 PowerShell 再重新開一個，然後確認：
ffmpeg -version
```

- 這個 winget 套件 ID 是推測的。如果安裝失敗，請先用 `winget search ffmpeg` 查正確的 ID。
- 這一步只會安裝程式，不會改動你的素材。

**3.2 選段**：先聽 10 個 MP3，挑出語氣最平穩、最接近你想要的旁白風格的一段，記下大約 10～12 秒的起訖時間。語者嵌入會用到**整���**參考音，T3 條件 token 取前 6 秒，S3Gen 參考取前 10 秒（見清單 P 項），所以**整段都要是乾淨、連續的說話聲**，不能只有開頭幾秒乾淨。

**3.3 從副本剪出參考音，轉成 WAV**

需要替換：`clip03.mp3`（你選的檔名）、`00:00:05`（起點）、`-t 11`（長度 11 秒）。

```powershell
$Work = "D:\VoiceBook"
ffmpeg -n -ss 00:00:05 -t 11 -i "$Work\00_originals_copy\audio\clip03.mp3" -ac 1 -ar 24000 "$Work\01_ref\ref_v1.wav"
```

- `-n` 代表如果目標檔已存在就不覆蓋（ffmpeg 會顯示 "already exists. Exiting." 並結束），所以不會蓋掉之前的成果。
- 取樣率設 24000 是推測值，模型讀檔時本來就會自動重新取樣（程式用 librosa 載入並重新取樣），這個值不影響結果。

**預期結果**：產生 `ref_v1.wav`。請播放確認開頭和結尾沒有把字剪斷。

**失敗排查**：
- 顯示「already exists」：把輸出檔名改成 `ref_v2.wav`。
- 找不到 `ffmpeg`：重新開啟 PowerShell 再試。

---

## 4. 安裝工具與隔離環境

「隔離環境」指專門為這個專案建立的 Python 環境，不會影響電腦上其他程式。

**4.1 安裝 Python 3.11 和 Git**

```powershell
winget install --id Python.Python.3.11 -e
winget install --id Git.Git -e
# 重新開啟 PowerShell 後確認：
py -3.11 --version
git --version
```

**4.2 建立隔離環境**

```powershell
cd D:\VoiceBook
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

如果出現「因為這個系統上已停用指令碼執行」的錯誤，先執行下面這行，它只改你個人帳號的設定，然後再啟用一次：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**4.3 安裝 PyTorch（只選一條路線）**

```powershell
# CUDA 路線（使用 NVIDIA 顯示卡）：
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
# CPU 路線（沒有 NVIDIA 顯示卡）：
# pip install torch==2.6.0 torchaudio==2.6.0
```

`cu124` 這個版本組合是推測。請先到 https://pytorch.org/get-started/previous-versions/ 查 2.6.0 對應的指令。

**4.4 安裝固定 commit 的 Chatterbox**

```powershell
pip install "chatterbox-tts @ git+https://github.com/resemble-ai/chatterbox.git@5de7a54aa4e5e2baadb0182dde554908b48b85c2"
pip freeze > logs\pip_freeze_install.txt
pip show resemble-perth
```

`pip freeze` 會把實際裝到的所有套件版本存成紀錄檔，之後出問題時可以對照。

**記錄 Perth 實際版本**：`resemble-perth` 是從 GitHub master 分支安裝（清單 F 項），`pip freeze` 對這類套件不一定留下 commit。請另外把 `pip show resemble-perth` 的輸出存起來，並到 `.venv\Lib\site-packages\resemble_perth-*.dist-info\direct_url.json` 查看實際的 commit hash，一併記到 `logs\` 裡。

**失敗排查**：
- `spacy-pkuseg` 編譯失敗：可能需要安裝「Visual Studio Build Tools」的 C++ 工具（推測）。
- 下載 `Perth` 失敗：確認 Git 已安裝。
- torch 被換成 CPU 版：重跑 4.3 的 CUDA 指令，並加上 `--force-reinstall`。

**4.5 改動的檔案**：`D:\VoiceBook\.venv` 和 `logs\`。另外 winget 會在系統層安裝 Python、Git 和 ffmpeg。

**4.6 下載並固定模型權重版本**

1. 到 https://huggingface.co/ResembleAI/chatterbox/commits/main 複製最新的 commit hash。
2. **打開模型卡確認授權（第 11 章 J 項）**。
3. 把 hash 填進下面程式的 `REVISION`。

```python
# 02_scripts/download_model.py
from huggingface_hub import snapshot_download

REVISION = "填入HF_commit_hash"
path = snapshot_download(
    repo_id="ResembleAI/chatterbox",
    repo_type="model",
    revision=REVISION,
    allow_patterns=["ve.pt", "t3_mtl23ls_v3.safetensors", "s3gen.pt",
                    "grapheme_mtl_merged_expanded_v1.json", "conds.pt", "Cangjie5_TC.json"],
    local_dir=r"D:\VoiceBook\models\chatterbox_" + REVISION[:8],
)
print("下載到：", path)
```

執行方式：`python 02_scripts\download_model.py`

- 權重會下載到 `models\` 底下的專屬資料夾，所以之後可以只清理這個資料夾，不會動到其他程式共用的模型快取。
- 這個版本有 `local_dir` 參數，這點是推測。如果執行時說不認得這個參數，把該行拿掉，然後照印出的路徑手動記錄位置。

---

## 5. 驗證實際安裝的版本與 CPU／CUDA

```python
# 02_scripts/check_env.py
import importlib.metadata as md, torch, sys
print("Python", sys.version)
for p in ["chatterbox-tts", "torch", "torchaudio", "transformers", "librosa", "resemble-perth", "numpy"]:
    try: print(p, md.version(p))
    except Exception as e: print(p, "未安裝", e)
print("CUDA 可用：", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU：", torch.cuda.get_device_name(0),
          round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1), "GB")
from chatterbox.mtl_tts import ChatterboxMultilingualTTS, MULTILINGUAL_T3_MODELS
print("v3 可用：", "v3" in MULTILINGUAL_T3_MODELS)
```

**預期結果**：chatterbox-tts 0.1.7、torch 2.6.0（CUDA 版會顯示 `2.6.0+cu124`）、`v3 可用： True`。

**停止條件**：
- 走 CUDA 路線卻顯示 `CUDA 可用： False` → 回 4.3 重裝 CUDA 版 torch。
- 版本和上面不同 → 先停下，對照 `logs\pip_freeze_install.txt` 找原因。

---

## 6. 零樣本生成（第一句試聽）

「零樣本」是指不另外訓練模型，只靠一段參考音就模仿你的聲音。

```python
# 02_scripts/gen_one.py
import torch, torchaudio as ta
from pathlib import Path
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

CKPT = r"D:\VoiceBook\models\chatterbox_填前8碼"
REF  = r"D:\VoiceBook\01_ref\ref_v1.wav"
OUT  = Path(r"D:\VoiceBook\04_out\test")
OUT.mkdir(parents=True, exist_ok=True)
device = "cuda" if torch.cuda.is_available() else "cpu"

model = ChatterboxMultilingualTTS.from_local(CKPT, device, t3_model="v3")
torch.manual_seed(42)
text = "你好，這是我用自己的聲音做的第一段測試。"
wav = model.generate(text, language_id="zh", audio_prompt_path=REF,
                     exaggeration=0.5, cfg_weight=0.5, temperature=0.8)
out = OUT / "test_001.wav"
if out.exists(): raise SystemExit("檔案已存在，請改檔名")
ta.save(str(out), wav, model.sr)
print("完成：", out, "取樣率", model.sr)
```

- 所有參數名稱都照 `mtl_tts.py` 第 280–291 行，已確認。
- 程式會先檢查輸出檔是否已存在，存在就停止，不會覆蓋。
- `torch.manual_seed(42)` 固定隨機種子，讓**同一台電腦、同一環境下**同樣設定能產生可重現的結果。換顯示卡、CPU 或套件版本後，不保證結果相同。
- 請記下印出的 `model.sr`，第 10.5 節會用到。

**失敗排查**：
- `CUDA out of memory`（顯示記憶體不足）→ 改用 CPU 路線。
- `FileNotFoundError` → 檢查 `CKPT` 資料夾裡是否有 6 個模型檔。

---

## 7. 找到、播放及檢查音檔

```powershell
explorer D:\VoiceBook\04_out\test
```

用內建的「媒體播放器」播放，檢查以下幾點：

- 聲音像不像你
- 有沒有漏字、多字、重複
- 破音字和專有名詞念得對不對
- 結尾有沒有雜音

浮水印檢查可以用 README 裡的程式碼（[README 第 182–198 行](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/README.md#L182-L198)），預期結果是 `1.0`，代表有浮水印。

---

## 8. 效果不佳時的調整

每次只改一項，並用新檔名輸出，方便比較。

| 問題 | 調整方式 |
|---|---|
| 語速太快 | `cfg_weight` 降到 0.3（官方 README 的建議） |
| 太平淡、沒有感情 | `exaggeration` 調到 0.6～0.7，同時 `cfg_weight` 降到 0.3 |
| 不穩定、亂念、重複 | `temperature` 降到 0.6，並縮短句子 |
| 聲音不像你 | 回第 3 章換一段參考音（輸出成 `ref_v2.wav`） |
| 讀錯字 | 改寫那一句文字：用同音字、加標點、把阿拉伯數字寫成國字 |

如果以上都試過仍然不滿意 → **停下來評估**：可以考慮中文專門模型，但那需要重做第 0 章和第 11 章的全部查核，不能沿用本手冊的結論。

---

## 9. 保留成果與安全清理

**要保留的東西**：
- `01_ref\` 參考音
- `logs\` 所有紀錄
- `02_scripts\` 所有程式
- 滿意的輸出檔，以及當時用的參數

建議把整個 `D:\VoiceBook`（`.venv` 除外）另外複製一份到 USB。

**清理方式**：
- 不提供刪除指令。
- 不需要的測試檔，請在檔案總管手動刪除，讓它進資源回收筒，還能救回。
- 如果要重建環境，可以在檔案總管刪掉 `D:\VoiceBook\.venv` 或 `models\chatterbox_xxxxxxxx`。這兩個只屬於本專案。
- **不要**去刪使用者資料夾底下的 `.cache\huggingface`，那是其他程式也可能在用的共用模型快取。

---

## 10. 長篇有聲書製作流程

**10.1 準備書稿**：每章存成一個 UTF-8 編碼的純文字檔，例如 `03_book_text\ch01.txt`。段落之間空一行。書中的數字、英文、罕見字，請先改寫成你希望的念法。（程式以 `utf-8-sig` 讀取，所以記事本存出的 BOM 不會造成問題。）

**10.2 分段、批次生成、記錄**

```python
# 02_scripts/batch_chapter.py
import csv, re, sys, torch, torchaudio as ta
from pathlib import Path
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

CKPT = r"D:\VoiceBook\models\chatterbox_填前8碼"
REF  = r"D:\VoiceBook\01_ref\ref_v1.wav"
CH   = sys.argv[1]                                        # 例：ch01
ATTEMPT = int(sys.argv[2]) if len(sys.argv) > 2 else 0    # 重做時傳 1、2…
SRC  = Path(rf"D:\VoiceBook\03_book_text\{CH}.txt")
OUT  = Path(rf"D:\VoiceBook\04_out\{CH}"); OUT.mkdir(parents=True, exist_ok=True)
MAXLEN = 120
P = dict(exaggeration=0.5, cfg_weight=0.5, temperature=0.8)

def split_sentences(para):
    # 句末標點後面若跟著收尾引號／括號，一起留在同一句
    return re.findall(r".+?(?:[。！？；][」』”）)]*|$)", para)

def split(text):
    segs = []
    for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
        buf = ""
        for s in split_sentences(para):
            # 單句超長時，改在逗號處再切
            parts = [s] if len(s) <= MAXLEN else re.findall(r".+?(?:[，、][」』”）)]*|$)", s)
            for part in parts:
                if len(buf) + len(part) > MAXLEN and buf:
                    segs.append(buf); buf = ""
                buf += part
        if buf: segs.append(buf)
    return segs

segs = split(SRC.read_text(encoding="utf-8-sig"))         # 吃掉 BOM
too_long = [i for i, t in enumerate(segs, 1) if len(t) > MAXLEN]
if too_long: print("警告：以下段落超過", MAXLEN, "字，請手動拆句：", too_long)

device = "cuda" if torch.cuda.is_available() else "cpu"
model = ChatterboxMultilingualTTS.from_local(CKPT, device, t3_model="v3")
model.prepare_conditionals(REF, exaggeration=P["exaggeration"])

log = OUT / "segments.csv"
new = not log.exists()
with open(log, "a", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    if new: w.writerow(["file", "seed", "params", "text", "status"])
    for i, t in enumerate(segs, 1):
        fn = OUT / f"{CH}_{i:04d}.wav"
        if fn.exists(): continue                          # 可續跑，不覆蓋
        seed = 1000 + i + ATTEMPT * 100000                # 重做時換種子
        torch.manual_seed(seed)
        wav = model.generate(t, language_id="zh", **P)
        ta.save(str(fn), wav, model.sr)
        w.writerow([fn.name, seed, P, t, "待核對"]); f.flush()
        print(i, "/", len(segs), fn.name)
```

執行方式：`python 02_scripts\batch_chapter.py ch01`（第一次）；重做時 `python 02_scripts\batch_chapter.py ch01 1`。

- 程式以句號、驚嘆號、問號、分號切句，每段盡量不超過 120 字；句末的收尾引號會留在同一句。
- 已存在的段落會跳過，所以中斷後重跑會接著做，不會覆蓋。
- 每段的檔名、隨機種子、參數、原文都記在 `segments.csv`。
- 種子只在同一台電腦、同一環境下可重現。
- 先用 `generate()` 傳入與 `prepare_conditionals` 相同的 `exaggeration`（本程式即如此），就不會重建條件（清單 R 項）。

**10.3 逐段核對文字**：用 Excel 打開 `segments.csv`，一邊聽一邊對照文字，把 `status` 欄改成「OK」或「重做」。自動語音辨識可以輔助比對，但本手冊沒有查核相關工具，這裡只寫人工核對。

**10.4 修正錯音**：
1. 在檔案總管把錯的那段 wav 移到 `04_out\ch01\_rejected\`（不要刪除）。
2. 視情況修改 `ch01.txt` 裡的那句文字，或調整參數。
3. 重跑 10.2，並**加上重做參數**：`python 02_scripts\batch_chapter.py ch01 1`。程式只會補生成缺少的那一段，且用新的種子。若同一段再失敗，改用 `2`、`3`……。

為什麼要換種子：種子原本由段落編號決定，同樣文字加同樣種子會重現同樣的錯誤。注意 `ATTEMPT` 只影響這次重跑中新生成的段落。

注意：如果修改文字後分段位置改變，後面所有段落的編號都會錯開。所以**請盡量只在同一段內改字**，不要增減句子。

**10.5 接合**：每段之間插入 0.4 秒靜音，接成一整章。

生成檔的格式（位元深度）和靜音檔可能不同，用 `-c copy` 容易失敗或產生雜音，所以這裡統一重新編碼成 16-bit PCM。靜音檔的取樣率必須和生成音檔一致，請以第 6 章印出的 `model.sr` 為準（下面的 24000 要換成實際值）。

```powershell
$Work = "D:\VoiceBook"; $CH = "ch01"; $SR = 24000   # 請改成 model.sr 的實際值
cd "$Work\04_out\$CH"
ffmpeg -n -f lavfi -i anullsrc=r=${SR}:cl=mono -t 0.4 -c:a pcm_s16le silence.wav
$list = Get-ChildItem "${CH}_*.wav" | Sort-Object Name | ForEach-Object { "file '$($_.Name)'"; "file 'silence.wav'" }
$list | Set-Content -Encoding ascii concat.txt
ffmpeg -n -f concat -safe 0 -i concat.txt -c:a pcm_s16le "$Work\05_final\${CH}_raw.wav"
```

- `silence.wav` 和 `concat.txt` 不是 `${CH}_*.wav` 的符合項目，不會被列入清單。
- 若重跑時顯示 already exists，先在檔案總管把舊的 `silence.wav`、`concat.txt` 或 `_raw.wav` 改名或移走。

**10.6 品質檢查與匯出**：調整整體音量（響度），再轉成 MP3。

```powershell
$F = "D:\VoiceBook\05_final"; $CH = "ch01"
ffmpeg -n -i "$F\${CH}_raw.wav" -af "loudnorm=I=-20:TP=-3:LRA=11" -ar 44100 -ac 1 -b:a 192k "$F\${CH}.mp3"
```

- `I=-20`、`TP=-3`、192k 這些是**暫定值**。各平台的響度、峰值、檔案格式規格不同，請以你要上架平台的官方規格為準。
- 匯出後請完整聽一遍，確認沒有段落接錯、重複或缺漏。

---

## 11. 商業化關卡：目前狀態為「暫停商業上架」

| 項目 | 狀態 | 正式販售前要做的事 |
|---|---|---|
| 程式碼授權 | 已確認 MIT（第 0 章 D 項） | 保留授權聲明 |
| 模型權重授權（`ResembleAI/chatterbox` 模型卡） | **未確認** | 讀模型卡原文，截圖並記下日期和 HF commit |
| 生成音檔的商用條件 | **未確認**。MIT 授權的是軟體本身，生成的音檔能否商用要另外確認 | 查模型卡和 Resemble 官方條款；必要時直接詢問 Resemble |
| 浮水印 | 已確認一律嵌入 | 不要嘗試移除。上架時是否必須或建議揭露，要確認 |
| 書稿權利 | 待你確認 | 自己寫的書，或已取得有聲書改編權的書，並保留書面授權 |
| 聲音權利 | 用你自己的聲音 | 確認原始錄音沒有其他人的聲音、背景音樂或第三方素材 |
| 上架平台的 AI 語音政策 | **未確認**（這次沒有查任何平台） | 確定平台後，逐一查該平台官方的上架規範原文 |
| 揭露要求（法規＋平台） | **未確認** | 查所在地法規與平台規定；必要時諮詢律師 |

**解除暫停的條件**：「未確認」各項全部變成「已確認」，而且每一項都有官方原文連結、查閱日期和截圖存檔。

再次提醒：**模型標示 MIT，不等於有聲書一定能上架販售。**

---

## 日後實際開始操作的第一步

**先把文字稿備份到 USB**（第 2.1 節）：用檔案總管複製，然後在 USB 上打開其中一個檔案，確認內容正常。這一步不用安裝任何東西。
