# 我的設定整理方式

我將公開程式與環境設定分開保存。`__CFG_0001__` 形式的字串代表外部參數；我在 [參數目錄](../config/parameters.json) 記錄每個參數的用途、類別與使用檔案，目錄不包含實際值。

我使用 Python 3.10 以上與根目錄的 [依賴清單](../requirements.txt) 執行本機檔案工具。我用以下命令檢視某一元件需要的欄位：

```bash
python tools/render.py --component access --catalog
```

我可以重複指定 `--component` 選擇多個目錄；我省略這個選項時，工具會處理 `components/` 與 `manifests/` 中的全部檔案。

我先在 repository 外建立空白設定檔，再填入自己的設定。命令中的路徑由我換成實際私有目錄：

```bash
python tools/render.py --component access --write-settings /private/settings.json
```

我以參數名稱作為 JSON key，將值填成字串。我也可以將某個值寫成只有 `file` 欄位的物件，讓工具讀取私有檔案；我用這種方式提供 CA 憑證或已由其他流程保存的機敏設定。相對檔案路徑會從設定檔所在目錄解析。

我保留原檔的型別：字串欄位使用字串，原本的列表逐項提供設定。參數名稱旁的 `field` 與 `files` 讓我能對照設定位置；ITSM operation、索引名稱、LDAP 搜尋條件及探測內容都依自己的環境填入。

我以以下命令只產生檔案：

```bash
python tools/render.py --component access --settings /private/settings.json --output /private/rendered-access
```

我讓工具先檢查所有必要參數，再將設定寫到新的外部目錄。工具會把 `components/` 的內容填回 ConfigMap，保留原 Deployment、Service 與儲存關係；它不連線到叢集、不呼叫部署指令，也不啟動程式。

我將產生的檔案視為私有資料，保存在 repository 外。工具會拒絕將私有設定或輸出放進 repository，也不覆寫已有的輸出目錄。錯誤訊息只指出參數名稱或檔案，不輸出設定值。

## 我如何準備元件執行環境

我為 Python 元件準備各自的依賴，為 Perl 採集程式準備 DBI、對應資料庫 driver、JSON::Create、JSON::Parse，以及程式使用的 curl／jq 等工具。我依 [部署檔](../manifests/) 指定元件映像、Service、外部儲存及憑證。

我在 [LDAP Dockerfile](../components/access/Dockerfile) 與 [Agent Dockerfile](../components/elastic-agent-alert/Dockerfile) 保留建置內容；實際 base image 與部署 image 由私有設定提供。我在完成設定檢查後，依自己環境的部署程序使用產生的檔案。

我在 [外部資源清單](../config/external-resources.json) 記錄原 ES 停用部署引用的共用 ConfigMap 及其檔案名稱。我從自己的環境提供這些共用檔案，並準備 image pull Secret、Ingress TLS Secret、Heartbeat ServiceAccount／SCC、StorageClass 與對應儲存。這些資源由我的環境管理流程維護。
