下載並安裝美顏相機 KOC 評估工具，完成後自動啟動。

執行以下步驟：

1. 在使用者的下載資料夾建立 `koc-tool` 目錄並進入：
   ```
   mkdir -p ~/Downloads/koc-tool && cd ~/Downloads/koc-tool
   ```

2. 從 GitHub 下載所有檔案：
   ```
   curl -L https://raw.githubusercontent.com/peggy1020322-arch/beautycam-dashboard/main/app.py -o app.py
   curl -L https://raw.githubusercontent.com/peggy1020322-arch/beautycam-dashboard/main/threads_worker.py -o threads_worker.py
   curl -L https://raw.githubusercontent.com/peggy1020322-arch/beautycam-dashboard/main/requirements.txt -o requirements.txt
   mkdir -p templates
   curl -L https://raw.githubusercontent.com/peggy1020322-arch/beautycam-dashboard/main/templates/index.html -o templates/index.html
   ```

3. 安裝 Python 套件：
   ```
   pip3 install -r requirements.txt
   ```

4. 安裝 Playwright 瀏覽器：
   ```
   python3 -m playwright install chromium
   ```

5. 啟動工具：
   ```
   python3 app.py
   ```

6. 告訴使用者：工具已啟動，開啟瀏覽器前往 http://127.0.0.1:5001 即可使用。第一次使用需要在工具內完成 Threads 和 Instagram 登入。
