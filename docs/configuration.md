# 設定整理方式

公開程式與環境設定分開保存。`__CFG_0001__` 形式的字串代表外部參數；[參數目錄](../config/parameters.json)記錄每個參數的用途、類別與使用檔案，不包含實際值。

執行本機檔案工具需使用 Python 3.10 以上及根目錄的[依賴清單](../requirements.txt)。以下命令可檢視指定元件需要的欄位：

```bash
python tools/render.py --component access --catalog
```

`--component` 可重複指定以選擇多個目錄；省略此選項時，工具會處理 `components/` 與 `manifests/` 中的全部檔案。

先在 repository 外建立空白設定檔，再填入環境設定。命令中的路徑需替換為實際私有目錄：

```bash
python tools/render.py --component access --write-settings /private/settings.json
```

JSON key 使用參數名稱，值填為字串。若需讓工具讀取私有檔案，參數值可設為只有 `file` 欄位的物件；此方式適用於提供 CA 憑證或由其他流程保存的機敏設定。相對檔案路徑會從設定檔所在目錄解析。

設定值需保留原檔型別：字串欄位使用字串，原本的列表逐項提供設定。參數名稱旁的 `field` 與 `files` 可用來對照設定位置；ITSM operation、索引名稱、LDAP 搜尋條件及探測內容依執行環境填入。

以下命令只產生檔案：

```bash
python tools/render.py --component access --settings /private/settings.json --output /private/rendered-access
```

工具會先檢查所有必要參數，再將設定寫到新的外部目錄，並把 `components/` 的內容填回 ConfigMap，保留原 Deployment、Service 與儲存關係。工具不連線到叢集、不呼叫部署指令，也不啟動程式。

產生的檔案屬於私有資料，需保存在 repository 外。工具會拒絕將私有設定或輸出放進 repository，也不覆寫已有的輸出目錄。錯誤訊息只指出參數名稱或檔案，不輸出設定值。

## 元件執行環境

Python 元件需準備各自的依賴；Perl 採集程式需準備 DBI、對應資料庫 driver、JSON::Create、JSON::Parse，以及程式使用的 curl／jq 等工具。[部署檔](../manifests/)指定元件映像、Service、外部儲存及憑證。

建置內容保留於 [LDAP Dockerfile](../components/access/Dockerfile) 與 [Agent Dockerfile](../components/elastic-agent-alert/Dockerfile)；實際 base image 與部署 image 由私有設定提供。設定檢查完成後，產生的檔案可供後續依該環境的既有部署程序使用。

[外部資源清單](../config/external-resources.json)記錄原 ES 停用部署引用的共用 ConfigMap 及其檔案名稱。執行環境需提供這些共用檔案，並準備 image pull Secret、Ingress TLS Secret、Heartbeat ServiceAccount／SCC、StorageClass 與對應儲存；相關資源由環境管理流程維護。
