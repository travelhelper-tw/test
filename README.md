# 有聲閱讀教室

Python 3.11+、Django 5.2、MySQL 8.0+（mysqlclient／utf8mb4）、Pillow，
搭配 Django Template、原生 CSS 與少量 JavaScript 的繁體中文課程閱讀網站。
以 Teachable 常見的導覽列、章節側欄及內容區為版面參考，所有介面皆自行撰寫，
沒有複製其原始碼、圖片、音檔或書籍文字。既有 `docs/` 文件保持不變。

## 功能與範圍

- Django 內建登入／POST 登出；只有登入者能讀取章節及標記完成。
- 每門課獨立計算個人進度，固定查詢次數，不依章節數增加查詢。
- 上／下一章、完成並繼續、MP3 播放、書封及 HTML 簡介。
- 深紫色導覽列、345px 章節側欄、狀態圓圈與手機可收合目錄。
- 後台新增課程、上傳素材、直接編輯章節排序。排序相同時，以章節 ID
  決定導覽先後。進度百分比無條件捨去小數；只有完成全部章節才會顯示 100%。

**本版不含金流、商品訂單、購買權限或付費音檔保護。**
所有登入者目前都能閱讀所有課程。`media/` 在開發及 Nginx 範例中為公開 URL，
知道連結的人不必登入也可下載；登入保護不能替代素材授權或付費存取控制。
正式販售前須加入購買權限、金流 webhook 驗簽及私有音檔傳送
（例如通過權限檢查後使用 Nginx internal＋X-Accel-Redirect），並確認商業授權、
隱私、服務條款及退款政策。現在僅適合使用允許公開的素材進行開發／展示。

## 1. 安裝（Ubuntu）

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

開啟 `http://127.0.0.1:8000/`，首頁會導向第一門課的第一章；
尚無課程或第一門課尚無章節時顯示課程列表。章節頁會要求先登入。
示範資料只有原創佔位文字，不含素材；重複執行不會新增重複章節或覆寫管理員修改。

### 後台與素材

1. 用 superuser 登入 `/admin/`，新增課程。
2. 新增章節，填寫課程、章節標籤（例如「第九十五章」）、標題與排序。
3. 上傳有權使用的 MP3、JPG／PNG／WebP 書封並儲存。
4. 在章節列表直接修改 `order`（「排序」），或進入章節編輯。
5. 在「使用者」建立讀者帳號。一般讀者不需要 staff 或 superuser 權限。

**HTML 信任界線：**`lecture.content` 以 `|safe` 呈現，不做 HTML 消毒，
因此**僅允許受信任的 superuser 在後台新增／編輯章節**；一般 staff 即使取得
章節變更權限也不能編輯。不要讓讀者、外部 API 或未審核的匯入資料寫入此欄位，
不要貼上來源不明的 HTML／JavaScript。若未來開放其他人編輯，必須先加上
嚴格的 HTML allowlist 消毒。上傳檔案的副檔名驗證不能取代安全掃描。
開發時 `DEBUG=True` 由 Django 提供 `/media/`，正式環境則由 Nginx 提供。

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
可選素材、HTML 後台權限及示範資料重複執行。

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
   sudo mkdir -p /srv/course-reader/media /srv/course-reader/staticfiles
   sudo chown -R course-reader:www-data /srv/course-reader
   sudo chmod 750 /srv/course-reader /srv/course-reader/media /srv/course-reader/staticfiles
   sudo -u course-reader python3 -m venv /srv/course-reader/.venv
   sudo -u course-reader /srv/course-reader/.venv/bin/pip install \
     -r /srv/course-reader/requirements.txt
   ```

2. 建立 `/etc/course-reader.env`，參照 `.env.example` 填入正式設定。
   使用 `DEBUG=False`、`ALLOWED_HOSTS=courses.你的網域`、獨立金鑰及密碼。
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

5. 用 `https://你的網域/` 檢查登入、播放、書封、進度及手機目錄。
   檢查日誌及更新後重新啟動：

   ```bash
   sudo journalctl -u course-reader -n 100 --no-pager
   sudo systemctl restart course-reader
   ```

定期備份 MySQL 與 `media/`，限制管理員權限，定期更新安全修補版本。
不要對外開啟 DEBUG、使用示範密碼或直接上架需要付費保護的素材。
