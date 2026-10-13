# 元件導覽

原始 workspace 依服務責任整理，保留程式邏輯、部署關係與停用狀態。ConfigMap 的 `data` 拆分至 `components/`，再透過[檔案對應表](../config/configmap-files.json)組裝回完整 ConfigMap。

| 目錄 | 保留內容 |
| --- | --- |
| [access](../components/access/) | 包含兩組 Nginx 代理設定、LDAP 認證 helper、入口頁與 LDAP 映像建置檔。 |
| [alerting](../components/alerting/) | 包含 ElastAlert 共用設定、76 個規則、額外的 CPU 郵件規則、不同來源的事件處理策略、ITSM 設定欄位及 Agent 狀態查詢程式。 |
| [elastic-agent-alert](../components/elastic-agent-alert/) | 包含獨立的 Agent 告警程式、事件處理程式、依賴清單與 Dockerfile。 |
| [apm-kafka](../components/apm-kafka/) | 包含 APM Kafka output 與 Logstash consumer／Elasticsearch output。 |
| [elasticsearch-legacy](../components/elasticsearch-legacy/) | 包含原本 master／ingest、coordination 與 data node 的設定。 |
| [fleet](../components/fleet/) | 包含 Elastic Agent／Fleet Server 設定與外部 CA 憑證欄位。 |
| [heartbeat](../components/heartbeat/) | 保留原有探測型態、排程、請求與回應判斷結構；目標、業務標籤及請求內容改為外部參數。 |
| [kibana](../components/kibana/) | 包含 Elasticsearch 連線、加密金鑰欄位、查詢與報表設定。 |
| [logstash](../components/logstash/) | 包含網路事件 pipeline、Logstash 共用設定與 JVM options。 |
| [f5-metric-collection](../components/f5-metric-collection/) | 包含 pool／member 狀態、可用性與連線數採集流程，以及 Elasticsearch 寫入。 |
| [security](../components/security/) | 包含 Deep Security API 狀態查詢、資料庫事件查詢、事件欄位組裝與 Elasticsearch 寫入。 |

## 部署關係與停用狀態

[manifests](../manifests/)保留 Deployment、StatefulSet、CronJob、ConfigMap、Service、Ingress、LocalVolume、PV 與 PVC。selector、volume、mountPath 與 subPath 的對應也予以保留，方便從程式追溯部署位置。

`ES-*.yaml.disabled` 保存原 Elasticsearch 部署；原本已停用的 Grafana PV 也予以保留。檔案的 `.disabled` 副檔名會在組裝時保留。

Kibana 負責管理 ILM、角色與 Agent policies；repository 呈現 workspace 內的部署檔與程式。README 說明 Hot／Cold 的管理方式，環境中的政策設定由環境維運流程管理。

## 去識別化與整理修正

條件分支、規則門檻、時間窗、事件欄位與 API 呼叫流程予以保留。帳密、token、CA 憑證、服務位置、目標清單、業務查詢條件、主機選擇與私有映像改為外部參數；內部命名則改為中性名稱。

Kubernetes 自動產生的狀態與管理紀錄已移除，原始文件改寫為目前的 README 與元件導覽。原 Agent 事件處理 ConfigMap 中字典欄位缺少逗號的語法問題已修正，並記錄於[來源清單](source-inventory.json)的 `syntax_repairs`。

拆檔後已對齊 Dockerfile 的 COPY 路徑、事件處理程式的設定檔位置與 Fleet 的 ConfigMap subPath；既有 Apim_Alert 策略的註冊及 Heartbeat 的 serviceAccountName 欄位位置也已補上。這些必要的整理修正記錄於同一份清單的 `packaging_repairs`。
