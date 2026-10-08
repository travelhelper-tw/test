# 有聲閱讀教室

Python 3.11+、Django 5.2、MySQL 8.0+（mysqlclient／utf8mb4）、Pillow，
搭配 Django Template、原生 CSS 與少量 JavaScript 的繁體中文課程閱讀網站。
以 Teachable 常見的導覽列、章節側欄及內容區為版面參考，所有介面皆自行撰寫，
沒有複製其原始碼、圖片、音檔或書籍文字。既有 `docs/` 文件保持不變。

## 功能與範圍

- Django 內建登入／POST 登出；只有具有效購買權限的登入者能讀取章節及標記完成。
- 綠界信用卡一次付款，整套課程販售，不提供免費試聽。
- 銷售頁、訂單紀錄與已購課程；驗簽後的付款通知才開通無到期日的課程權限。
- 每門課獨立計算個人進度，固定查詢次數，不依章節數增加查詢。
- 上／下一章、完成並繼續、MP3 播放、書封及 HTML 簡介。
- 深紫色導覽列、345px 章節側欄、狀態圓圈與手機可收合目錄。
- 後台新增課程、上傳素材、直接編輯章節排序。排序相同時，以章節 ID
  決定導覽先後。進度百分比無條件捨去小數；只有完成全部章節才會顯示 100%。

預設金流為**測試環境**。尚未設定售價／金流時不允許結帳，沒有自動替課程定價。
每張訂單固定記錄結帳時的價格及課程名稱，修改售價不影響舊訂單。
章節沒有免費試聽；superuser 可預覽全部章節，一般 staff 不會繞過購買權限。
MP3 存於 `private_media/`，不再提供公開的 `/media/audio/`。
書封仍可公開，課程銷售介紹是獨立的純文字欄位，不會顯示章節 HTML。

此版不含自助註冊、電子發票、自動退款／金流對帳、訂閱或單章販售。
帳號由管理員建立。正式販售前仍須確認商業授權、服務／隱私／退款政策及發票需求，
並完成綠界沙箱與正式商店驗收。購買者仍能保存取得的音檔，這不是 DRM。

## 1. 安裝（Ubuntu）

### Windows 本機：使用 WSL2 Ubuntu

Windows 建議使用 WSL2，在 Ubuntu 內執行 Python、MySQL 與 Django，
避免原生 Windows 編譯 mysqlclient 的工具鏈差異。WSL 是本機環境，
**不是公開 Ubuntu 主機**，不需先購買主機或網域。

1. 在支援 WSL2 的 Windows 10／11，以系統管理員身分開啟 PowerShell：

   ```powershell
   wsl --install -d Ubuntu-24.04
   ```

   依提示重新啟動，開啟 Ubuntu，建立 Linux 使用者與密碼。
   以下所有安裝／Django 指令都在 **Ubuntu 終端機**執行，不是 PowerShell。
   若已裝 WSL，可先在 PowerShell 用 `wsl -l -v` 確認 Ubuntu 使用 VERSION 2。

2. 將 repo 放在 WSL 的 Linux 家目錄（例如 `~/projects/test`），
   不要沿用 Windows 的虛擬環境。可先在 Windows 檔案總管以
   `\\wsl.localhost\Ubuntu-24.04\home\<Linux使用者>\projects` 存取目錄；
   發行版名稱以 `wsl -l -v` 結果為準。若複製既有 repo，
   排除 `.venv`、`.env` 和資料庫／素材備份，重新建立環境。
3. 接續下方 Ubuntu 安裝步驟，把 `cd /你的路徑/test` 換成 repo 的實際路徑。
   Ubuntu 24.04 的 Python 3.12 符合需求。若 WSL 未啟用 systemd，
   以 `sudo service mysql start` 啟動 MySQL；不需安裝 Nginx 或 Gunicorn 服務。
4. 初始化後執行 `python manage.py runserver`，在 Windows 瀏覽器開啟
   `http://localhost:8000/`。素材可從 Windows 瀏覽器選檔上傳，
   音檔會存入 WSL 的私有目錄，不必複製到 Git。
5. WSL 關閉後，下次先開啟 Ubuntu、啟動 MySQL，再進入 repo：

   ```bash
   source .venv/bin/activate
   set -a
   source .env
   set +a
   python manage.py runserver
   ```

先保持 `DEBUG=True`、`ECPAY_ENVIRONMENT=test`、
`USE_X_ACCEL_REDIRECT=False`；沒有綠界資料時保留相關金鑰及 `SITE_URL` 空白。
不要為了讓結帳成功而填入虛構金鑰。不要將本機 runserver 對外公開。

需 MySQL 8.0+，不要用 SQLite 替代實際的 MySQL 環境。

```bash
sudo apt update
sudo apt install python3 python3-venv python3-dev build-essential pkg-config \
  default-libmysqlclient-dev mysql-server
sudo systemctl enable --now mysql
cd /你的路徑/test
python3 --version                 # 確認為 3.11 以上
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

將最後生成的值填入 `.env` 的 `SECRET_KEY`，以**單引號**包住。
自行設定資料庫密碼（同樣以單引號包住，避免 shell 解讀特殊符號），
不得將真實密碼、金鑰或素材提交到 Git。`.env.example` 故意不提供密碼與金鑰。

設定全部透過環境變數讀取，**Django 不會自動讀取 `.env`**。
每次開啟新的 shell、執行管理指令或本機伺服器前，先載入：

```bash
set -a
source .env
set +a
```

| 環境變數 | 說明 |
| --- | --- |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | 資料庫名稱、帳號、密碼 |
| `DB_HOST` / `DB_PORT` | 本機預設 `127.0.0.1` / `3306` |
| `SECRET_KEY` | 必填，未設定即拒絕啟動；正式環境使用獨立隨機金鑰 |
| `DEBUG` | 本機 `True`，正式環境必須 `False`（預設） |
| `ALLOWED_HOSTS` | 逗號分隔，不含協定或連接埠，如 `localhost,127.0.0.1` |
| `ECPAY_ENVIRONMENT` | `test`（預設）或 `production`；決定綠界固定 gateway |
| `ECPAY_MERCHANT_ID` / `ECPAY_HASH_KEY` / `ECPAY_HASH_IV` | 對應環境的商店代號與驗簽資料，僅放環境變數 |
| `SITE_URL` | 公開的 HTTPS 網站 origin，如 `https://courses.example.com`，不要有路徑／query |
| `PRIVATE_MEDIA_ROOT` | 私有音檔絕對路徑，留空用專案的 `private_media/`，不得放在 `media/` 內 |
| `USE_X_ACCEL_REDIRECT` | 本機 `False`；部署且設定 Nginx internal 後改為 `True` |

## 2. 建立 MySQL 資料庫

```bash
sudo mysql
```

在 MySQL 互動命令列執行以下 SQL，**將密碼佔位文字替換成自己的強密碼**。
密碼須與 `.env` 一致；請勿將填好的 SQL 儲存或提交到 repo。

```sql
CREATE DATABASE course_reader CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'course_reader'@'127.0.0.1' IDENTIFIED BY '<自行設定強密碼>';
GRANT ALL PRIVILEGES ON course_reader.* TO 'course_reader'@'127.0.0.1';
EXIT;
```

設定使用 `charset=utf8mb4` 與嚴格 SQL 模式，支援繁體中文及 emoji。

## 3. 初始化與本機執行

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver
```

開啟 `http://127.0.0.1:8000/`，首頁顯示課程列表與公開銷售頁；
章節頁會要求先登入，未購買者會返回銷售頁，不會取得章節內容。
示範資料只有原創佔位文字，不含素材；重複執行不會新增重複章節或覆寫管理員修改。
**新建**示範課程售價為已確認的 **NT$ 3,680／整套課程**，
不會自動開通權限。已存在的示範課程價格（包括留空）不會被覆寫，
請在後台手動改為 `3680`；其他課程仍需管理員自行設定售價。
示範資料不是您實際的有聲書，請自行建立正式課程並上傳授權素材。

### 尚無主機／網域／綠界資料時的本機驗證

1. 用 superuser 登入 `/admin/`，確認課程價格為 `3680`，上傳 MP3 與書封，
   進入章節檢查播放器、圖片及內容。請勿將素材提交至 repo。
2. 建立一般讀者帳號，用另一個瀏覽器或無痕視窗登入：
   未購買者只能看到銷售介紹，進入章節應返回銷售頁。
3. 未設定綠界資料時，購買操作應顯示付款服務尚未設定的訊息，
   不會建立付款成功紀錄或開通課程。這不是實際 sandbox 付款驗收。
4. 管理員在後台為讀者新增「僅限測試環境的權限」，確認可閱讀／播放，
   然後撤銷有效權限，確認後續章節及音檔請求遭到阻擋。
   手動測試權限不代表已付款，不能當作正式購買。
5. 主機、HTTPS 網域及綠界測試資料取得後，再依下方部署與綠界驗收章節操作；
   驗收前保持測試環境，不切換正式金流。

### 後台與素材

1. 用 superuser 登入 `/admin/`，新增課程，填寫公開銷售介紹與整套售價（新臺幣整數元）。
2. 新增章節，填寫課程、章節標籤（例如「第九十五章」）、標題與排序。
3. 上傳有權使用的 MP3、JPG／PNG／WebP 書封並儲存。
4. 在章節列表直接修改 `order`（「排序」），或進入章節編輯。
5. 在「使用者」建立讀者帳號。一般讀者不需要 staff 或 superuser 權限。
6. 在「購買權限」以 superuser 手動建立使用者／課程權限，或撤銷 `active`。
   「僅限測試環境的權限」勾選者不能在正式金流環境閱讀。
   管理員開通／撤銷操作由 Django admin 記錄；保留停用紀錄，不直接刪除。
7. 「訂單」與「已驗簽付款通知」在後台唯讀，不能靠手改「已付款」開通權限。
   **撤銷權限不等於退款**；退款須在綠界商店處理後手動撤銷。

**HTML 信任界線：**`lecture.content` 以 `|safe` 呈現，不做 HTML 消毒，
因此**僅允許受信任的 superuser 在後台新增／編輯章節**；一般 staff 即使取得
章節變更權限也不能編輯。不要讓讀者、外部 API 或未審核的匯入資料寫入此欄位，
不要貼上來源不明的 HTML／JavaScript。若未來開放其他人編輯，必須先加上
嚴格的 HTML allowlist 消毒。上傳檔案的副檔名驗證不能取代安全掃描。
開發時 `DEBUG=True` 僅提供 `/media/covers/`，正式環境也只公開書封。
MP3 透過受保護的 `/audio/<音檔名稱>/`，每次請求都檢查有效購買權限。
本機 Django 直接傳送檔案；正式 Nginx internal 傳送支援音訊 Range／跳播，
不快取私有音檔。撤銷會阻擋後續請求，無法收回已下載或已開始傳送的檔案。

### 綠界測試與正式切換

1. 向綠界取得 AIO **信用卡一次付款**測試資料，填入環境變數並重啟服務。
   不要將 HashKey／HashIV 貼到對話、Git、日誌或 HTML。網站結帳表單只傳
   MerchantID、訂單資訊與計算後的 CheckMacValue。
2. 綠界伺服器必須可從外網 HTTPS 443 到達
   `SITE_URL/payments/ecpay/notify/`。只用 localhost 無法完成付款通知。
   本機可以測試頁面和權限，但實際 sandbox 交易請用可公開存取的測試部署。
3. 用一般讀者帳號選取課程，按「購買整套課程」，確認訂單後前往綠界測試 gateway。
   使用綠界官方的測試信用卡資料，**不要填真實卡號**。
4. 返回訂單頁只是查看狀態，不會開通。收到有效通知後顯示已付款及已購課程。
   付款通知核對 SHA256 CheckMacValue（常數時間比較）、商店、訂單、TradeAmt、
   交易編號及付款方式，以資料庫交易／訂單列鎖防止並行重複開通。
   成功處理／有效重複通知回覆純文字 `1|OK`；驗簽失敗不更新資料。
5. `SimulatePaid=1` 為綠界後台模擬通知，**即使在測試環境也不開通**。
   Stage 信用卡交易的正常成功通知（`SimulatePaid=0`）只授予測試權限，
   切換 `production` 後無效；建議測試與正式使用獨立資料庫及金鑰。
6. 測試成功／失敗、重送、金額篡改、未購買者、退款後權限撤銷等流程。
   舊付款成功通知重送不會恢復已撤銷的權限。新的付款訂單成功則可重新開通。
7. 綠界商店正式核准後，換為正式商店資料和 `ECPAY_ENVIRONMENT=production`，
   確認 SITE_URL／Nginx／HTTPS 與金鑰對應，不得混用測試金鑰或權限。

採用官方 AIO V5 gateway：
`https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5`（測試）、
`https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5`（正式）。
付款結果是綠界伺服器 form POST，金額欄位是 `TradeAmt`，不是 `TotalAmount`。
唯一免 CSRF 的端點是已驗簽的付款通知；站內結帳／完成／登出仍有 CSRF 保護。
不儲存卡號或完整通知內容，只記錄核對所需欄位與結果；不紀錄金鑰。

參考：[綠界官方 SDK 驗簽規則](https://github.com/ECPay/ECPay-API-Skill/blob/master/guides/13-checkmacvalue.md)、
[AIO 協定](https://github.com/ECPay/ECPay-API-Skill/blob/master/guides/01-payment-aio.md)、
[官方通知文件](https://developers.ecpay.com.tw/2878/)。
開發驗證對照官方 SDK／測試向量；正式上線前請再次核對最新商店文件與設定。

### 既有公開音檔升級（先備份、停止服務）

**部署新版前先阻擋舊 `/media/audio/` URL，並停用舊版應用／CDN 或物件儲存分享。**
資料遷移只變更儲存設定，不會自動搬移檔案。使用既有 DB 與素材目錄執行：

```bash
python manage.py migrate
python manage.py migrate_private_audio --dry-run
python manage.py migrate_private_audio
```

指令會依 Lecture.audio 原檔名複製到 PRIVATE_MEDIA_ROOT、比對 SHA256，
確認一致後刪除公開副本。可重複執行；遇到缺檔／不同內容／不安全路徑會停止，
不覆寫不同檔案。備份也須存於不公開的路徑；檢查並清除 media/audio 中
不再被章節引用的殘留檔案、舊 CDN 快取及舊公開連結。完成後再啟動新版服務。
既有 Progress 不會自動授予購買權限，請由管理員核對既有買家並手動開通。

## 4. 測試與檢查

Django 測試框架使用 MySQL 建立獨立 `test_course_reader` 資料庫。
僅在**開發／測試主機**給測試帳號以下權限，不要擴大正式資料庫帳號權限：

```sql
GRANT ALL PRIVILEGES ON test_course_reader.* TO 'course_reader'@'127.0.0.1';
```

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test courses
```

涵蓋登入要求、登入／登出、課程／使用者隔離、百分比、固定查詢數、
POST／CSRF、完成後跳轉、最後一章、相同排序、跨課程 404、空站點、
可選素材、HTML 後台權限及示範資料重複執行。另涵蓋 MAC 編碼、
結帳金額快照、成功／失敗／偽造／模擬／重複／並行付款通知、
交易編號綁定、資料庫失敗回滾、撤銷後重送、測試／正式隔離、
訂單隱私、私有音檔與舊 URL 封鎖，以及舊素材搬移核對。
測試不連線綠界或產生真實交易；實際 sandbox 付款需自行完成上述驗收。

## 5. Linux＋Nginx＋Gunicorn 部署

以下範例固定安裝於 `/srv/course-reader`，服務帳號 `course-reader`，
群組 `www-data`。替換網域、路徑與憑證；勿以 `runserver` 對外部署。

1. 完成前述系統依賴與 MySQL 設定，另安裝 Nginx：

   ```bash
   sudo apt install nginx
   sudo useradd --system --create-home --home-dir /srv/course-reader \
     --gid www-data --shell /usr/sbin/nologin course-reader
   ```

   將此 repo 的程式檔案放到 `/srv/course-reader`，勿複製本機 `.env` 或虛擬環境。
   建立服務所需的虛擬環境及素材目錄：

   ```bash
   sudo mkdir -p /srv/course-reader/media /srv/course-reader/private_media /srv/course-reader/staticfiles
   sudo chown -R course-reader:www-data /srv/course-reader
   sudo chmod 750 /srv/course-reader /srv/course-reader/media /srv/course-reader/private_media /srv/course-reader/staticfiles
   sudo -u course-reader python3 -m venv /srv/course-reader/.venv
   sudo -u course-reader /srv/course-reader/.venv/bin/pip install \
     -r /srv/course-reader/requirements.txt
   ```

2. 建立 `/etc/course-reader.env`，參照 `.env.example` 填入正式設定。
   使用 `DEBUG=False`、`ALLOWED_HOSTS=courses.你的網域`、獨立金鑰及密碼。
   另設定 `PRIVATE_MEDIA_ROOT=/srv/course-reader/private_media`、
   `USE_X_ACCEL_REDIRECT=True`、公開 HTTPS `SITE_URL` 及對應綠界設定。
   每行 `KEY=value`，不要用 `export`；有特殊字元的值以單引號包住。

   ```bash
   sudo install -m 640 -o root -g www-data /dev/null /etc/course-reader.env
   sudoedit /etc/course-reader.env
   ```

   使用服務帳號載入設定並初始化（更新時也須執行 migrate／collectstatic）：

   ```bash
   sudo -u course-reader bash -c 'cd /srv/course-reader; set -a; source /etc/course-reader.env; set +a; .venv/bin/python manage.py migrate'
   sudo -u course-reader bash -c 'cd /srv/course-reader; set -a; source /etc/course-reader.env; set +a; .venv/bin/python manage.py createsuperuser'
   sudo -u course-reader bash -c 'cd /srv/course-reader; set -a; source /etc/course-reader.env; set +a; .venv/bin/python manage.py collectstatic --noinput'
   sudo -u course-reader bash -c 'cd /srv/course-reader; set -a; source /etc/course-reader.env; set +a; .venv/bin/python manage.py check --deploy'
   ```

3. 安裝 Gunicorn systemd 範例：

   ```bash
   sudo cp /srv/course-reader/deploy/gunicorn.service /etc/systemd/system/course-reader.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now course-reader
   sudo systemctl status course-reader
   ```

   Gunicorn 僅監聽 `127.0.0.1:8000`。Django 信任 Nginx 寫入的
   `X-Forwarded-Proto`，不可將此連接埠暴露給外部或使用未受信任的反向代理。
   服務採 `UMask=0027`，讓 Nginx 所屬 `www-data` 可以讀取上傳檔。

4. 將網域 DNS 指向主機，取得有效的 TLS 憑證（例如 Let's Encrypt）。
   `deploy/nginx.conf` **假設憑證已存在**；尚未取得時，先用臨時 HTTP
   ACME 設定取得憑證，再安裝此 HTTPS 範例。修改範例中的網域與憑證路徑：

   ```bash
   sudo cp /srv/course-reader/deploy/nginx.conf /etc/nginx/sites-available/course-reader
   sudoedit /etc/nginx/sites-available/course-reader
   sudo ln -s /etc/nginx/sites-available/course-reader /etc/nginx/sites-enabled/course-reader
   sudo nginx -t
   sudo systemctl reload nginx
   ```

   只開放 SSH、HTTP、HTTPS；MySQL 不對外開放。正式設定強制 HTTPS，
   使用 secure session／CSRF cookies 與 HSTS，需先確保憑證和代理設定正確。
   `check --deploy` 的 W005／W021 提醒是因為本範例未啟用
   HSTS includeSubDomains／preload；只有確認所有子網域都永久使用 HTTPS、
   並了解 preload 的長期影響後，才應啟用這兩項設定。
   Nginx 的 200MB 上傳限制可依素材大小調整；大檔建議另行規劃上傳流程。
   私有音檔目錄不可另設公開 alias／symlink；`/_private_audio/` 必須保留
   `internal`，alias 必須與 PRIVATE_MEDIA_ROOT 一致。
   Django 和 Nginx 都必須能讀檔，但不得允許網站使用者列出或直接下載私有目錄。

5. 用 `https://你的網域/` 檢查登入、播放、書封、進度及手機目錄。
   檢查日誌及更新後重新啟動：

   ```bash
   sudo journalctl -u course-reader -n 100 --no-pager
   sudo systemctl restart course-reader
   ```

定期私下備份 MySQL、`media/covers/` 與 `private_media/`，限制管理員權限，
定期更新安全修補版本。不要對外開啟 DEBUG、使用示範密碼或公開私有素材。
