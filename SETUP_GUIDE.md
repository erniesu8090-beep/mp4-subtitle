# 字幕嵌入大師 - 環境部署指南 (適用於無 GitHub 權限或離線電腦)

本專案是一個本地端運行的網頁程式，當您將整個專案資料夾複製到限制網域（無法連線 GitHub）或完全無網路的電腦後，請依照本指南安裝所需的 Python 環境與 FFmpeg 依賴。

---

## 步驟一：安裝 Python 3

本程式需要 Python 3.8 或以上版本。

1. **下載安裝檔**：
   * 請在該電腦的瀏覽器中前往 [Python 官方下載頁面](https://www.python.org/downloads/windows/)（通常官方網站不受 GitHub 網域限制影響）。
   * 選擇 **Windows Installer (64-bit)** 下載。
2. **進行安裝**：
   * 執行下載的 `.exe` 安裝程式。
   * **⚠️ 務必勾選最下方的：「Add Python to PATH」**。
   * 點擊 **Install Now** 完成安裝。
3. **驗證安裝**：
   * 開啟命令提示字元（CMD）或 PowerShell，輸入以下指令：
     ```cmd
     python --version
     ```
   * 若正確顯示 `Python 3.x.x`，即代表安裝成功。

---

## 步驟二：安裝並配置 FFmpeg

FFmpeg 是處理視訊與字幕的核心引擎，必須安裝並加入系統環境變數中。

1. **下載 FFmpeg**：
   * 請前往 FFmpeg 官方推薦的 Windows 編譯下載點：[Gyan.dev FFmpeg 下載頁](https://www.gyan.dev/ffmpeg/builds/)。
   * 在 **git full builds** 區塊下，下載 **ffmpeg-git-full.7z** 或是 **ffmpeg-release-full.7z**。
2. **解壓縮並放置**：
   * 將下載的壓縮檔解壓縮。
   * 將解壓縮後的資料夾重新命名為 `ffmpeg`，並將其移動至您方便管理的位置（例如 `C:\ffmpeg`）。
3. **將 FFmpeg 加入系統環境變數 (PATH)**：
   * 在 Windows 搜尋列輸入「**環境變數**」，點選「**編輯系統環境變數**」。
   * 點擊右下角的「**環境變數**」按鈕。
   * 在下方的「**系統變數**」清單中找到 **Path**，選取後點擊「**編輯**」。
   * 點擊右側的「**新增**」，並輸入您剛剛放置 FFmpeg 的 `bin` 資料夾路徑（例如：`C:\ffmpeg\bin`）。
   * 依序點擊「**確定**」關閉所有視窗。
4. **驗證安裝**：
   * 重新開啟一個新的 CMD 視窗，輸入以下指令：
     ```cmd
     ffmpeg -version
     ```
   * 若顯示 FFmpeg 的版本資訊，即代表設定成功。

---

## 步驟三：安裝 Flask 網頁套件

視該電腦的網路連線狀態，請選擇以下其中一種方法安裝：

### 方法 A：該電腦可以連線上網（僅封鎖 GitHub）
只要電腦能連線至 Python 官方套件庫 (PyPI)，您不需要做任何事情：
1. **直接執行專案中的 [run.bat](file:///c:/Users/305651/Documents/MP4影片嵌入字幕/run.bat)**。
2. 批次檔會自動偵測並透過 `pip` 自動下載並安裝 Flask，隨後啟動程式。
3. 或者，您也可以手動開啟 CMD 輸入以下指令安裝：
   ```cmd
   pip install flask
   ```

---

### 方法 B：該電腦為「完全斷網 / 離線」狀態
如果該電腦完全無法連接外網，您需要使用另一台可以上網的電腦協助下載套件包：

1. **在「可上網」的電腦上下載套件包**：
   * 新建一個空白資料夾，並在該資料夾路徑下開啟 CMD。
   * 輸入以下指令下載 Flask 及其所有依賴套件的 `.whl` 檔案：
     ```cmd
     pip download flask -d ./flask_packages
     ```
   * 這會在 `flask_packages` 資料夾中生成數個 `.whl` 離線安裝檔。
2. **轉移檔案**：
   * 將這整個 `flask_packages` 資料夾使用隨身碟複製到「離線電腦」上，放在本專案的根目錄下。
3. **在「離線電腦」上安裝**：
   * 在離線電腦上開啟 CMD，進入本專案資料夾。
   * 執行以下指令進行離線安裝：
     ```cmd
     pip install --no-index --find-links=./flask_packages flask
     ```
   * 安裝完成後，直接按兩下執行 [run.bat](file:///c:/Users/305651/Documents/MP4影片嵌入字幕/run.bat) 即可順利啟動程式！
