# Elasticsearch Observability Platform

本平台由作者獨立開發，並獨立負責架構設計、部署、資料採集、生命週期管理、存取控制、告警整合與日常維運。平台將日誌、系統指標、服務可用性與 APM 資料集中管理，並透過 **event driven** 的告警流程，將異常送入**事件中心系統(ITSM)**，銜接後續處理。

此處公開原始 workspace 的去識別化程式碼、告警規則與部署設定，讓各項架構決策都能對照實作。

## Production 部署取捨

經評估既有 Production OCP 的共用運算資源與儲存條件，平台將 Elasticsearch 部署在獨立 Linux 主機。持續寫入、segment merge、shard recovery 與大量查詢都會競爭磁碟 I/O；獨立資料層可分開控制吞吐量、延遲、容量與資源配置。

Kibana、Fleet Server、APM Server、Heartbeat、Logstash、Nginx／LDAP 與告警服務配置在 OCP 服務層。平台依各元件的寫入量、持久化需求與故障影響安排資源，並將高 I/O 的 Elasticsearch 資料層與服務層分開管理。

部署評估依據包含工作負載與儲存實測。Elastic 的 Kubernetes 儲存建議指出，local storage 與 network-attached storage 的效能需要依 Elasticsearch 使用情境評估；這也可用來判斷既有 OCP 儲存是否適合承載資料節點。[Elastic 儲存建議](https://www.elastic.co/docs/deploy-manage/deploy/cloud-on-k8s/storage-recommendations)

```mermaid
flowchart TB
    subgraph OCP[OCP 服務層]
        Access[Nginx / LDAP]
        Kibana[Kibana]
        Fleet[Fleet Server]
        APM[APM Server]
        Kafka[Kafka Queue]
        Logstash[Logstash]
        Heartbeat[Heartbeat]
        Rules[ElastAlert / Agent 狀態監控]
        Poster[事件處理程式]
    end
    subgraph ES[獨立 Linux 主機上的 Elasticsearch]
        Coord[Coordination Nodes]
        Master[Master / Ingest]
        Data[Data Nodes]
    end
    Access --> Kibana
    Kibana --> Coord
    Fleet --> Coord
    APM --> Kafka --> Logstash --> Coord
    Heartbeat --> Coord
    Coord --> Data
    Master -. 叢集管理 .-> Data
    Rules -->|查詢監控資料| Coord
    Rules -->|異常事件| Poster
    Poster --> ITSM[事件中心系統 ITSM]
```

## Elasticsearch 節點分工與資料生命週期

Master 負責管理叢集狀態與 shard 配置，Ingest 負責寫入前的資料轉換。Coordination Nodes 接收查詢與寫入請求、分派工作並彙整結果，Data Nodes 負責索引、搜尋與儲存。

資料生命週期採用 **Hot／Cold** 管理：Hot 階段承接持續寫入與近期查詢，透過 ILM 控制 rollover，再依資料用途與保留需求進入 Cold，最後執行到期刪除。保留政策依資料種類配置，將查詢需求與儲存容量一併納入維運。

原本部署在 OCP 的 Elasticsearch 設定保留於 [Elasticsearch 原部署檔](manifests/elasticsearch-legacy/)。其中 `ES-*.yaml.disabled` 為原 ES 元件；這些檔案及相關 ConfigMap、Service、PV 與 PVC 呈現原本的節點配置與部署關係。

## 監控資料採集與呈現

Fleet 管理 Elastic Agent 的註冊、政策與整合設定，為各主機的資料採集提供一致的管理入口。Fleet 負責政策管理，Agent 則依政策向設定的 output 傳送資料。

Heartbeat 執行 HTTP、TCP 與 ICMP 探測，設定包含排程、逾時、預期回應與探測方式。APM 收集應用程式的交易、錯誤與追蹤資料，再由 Kafka 承接寫入、Logstash 消費與轉送至 Elasticsearch。

```mermaid
flowchart LR
    Fleet[Fleet Server] -. 政策管理 .-> Agent[Elastic Agent]
    Agent --> Coord[Coordination Nodes]
    Probe[Heartbeat HTTP / TCP / ICMP] --> Coord
    App[應用程式 APM Agent] --> APM[APM Server]
    APM --> Queue[Kafka Queue]
    Queue --> LS[Logstash]
    LS --> Coord
    Collectors[F5 / Deep Security / 網路監控] --> Ingest[採集程式 / Logstash]
    Ingest --> Coord
    Coord --> Data[Elasticsearch Data Nodes]
    Kibana[Kibana] -->|查詢與視覺化| Coord
```

Kafka 部署配置三個 broker/controller、三份複本與至少兩份同步複本，透過持久化儲存與 Logstash consumer 管理 APM 的資料傳遞。Kibana 集中呈現日誌、指標、可用性與 APM，供維運人員從異常現象追查對應主機或應用程式。

| 元件 | 實作重點 | 程式與設定 |
| --- | --- | --- |
| Kibana | 提供監控查詢、視覺化與權限管理入口。 | [Kibana 設定](components/kibana/CM-kbn1/kibana.yml)、[部署檔](manifests/kibana/) |
| Fleet／Elastic Agent | 集中管理 Agent，並配置 Fleet Server 的服務、憑證與連線設定。 | [Fleet 設定](components/fleet/)、[部署檔](manifests/fleet/) |
| APM／Kafka／Logstash | 建立 APM → Kafka → Logstash → Elasticsearch 的資料路徑。 | [APM 設定](components/apm-kafka/CM-apm-2kafka/apm-server.yml)、[Logstash pipeline](components/apm-kafka/CM-logstash-kafka-apm/logstash.conf)、[Kafka 部署](manifests/apm-kafka/ES-kafka.yaml) |
| Heartbeat | 以 HTTP、TCP 與 ICMP 檢查服務和主機的可用性。 | [探測設定](components/heartbeat/)、[部署檔](manifests/heartbeat/) |
| 網路監控 | Logstash 接收並處理網路監控事件。 | [Logstash pipeline](components/logstash/CM-nms_ls_pipeline/logstash.conf) |
| F5 | 採集 pool、member、可用狀態與連線數。 | [Python 採集程式](components/f5-metric-collection/f5_collection.py) |
| Deep Security | 採集 Agent 狀態、惡意程式、完整性與入侵防護事件。 | [Agent 狀態採集](components/security/DS_Agent_Status.pl)、[事件採集](components/security/DS_Event_Alert.pl)、[排程部署](manifests/security/) |
| vSphere | 配置 Elastic Agent 的虛擬化環境整合。 | [部署檔](manifests/vsphere/ES-vSphere-integration.yaml) |

## LDAP 認證與 Kibana 授權

Nginx 整合 LDAP 認證功能，透過 `auth_request` 呼叫 LDAP 認證服務。LDAP 確認登入身分後，請求才會進入 Kibana。

**LDAP 負責認證，Kibana 負責授權**。代理入口設定對應的後端授權身分，再以 Kibana 與 Elasticsearch 的角色權限控制可操作功能及資料範圍。LDAP bind 設定、後端授權資料與實際連線位置保存在 repository 外。

[Nginx 設定](components/access/CM-nginx1/nginx.conf)、[LDAP 認證程式](components/access/CM-python-ldap/nginx-ldap-auth-daemon.py) 與 [部署關係](manifests/access/)呈現登入入口、認證子請求及後端代理的串接方式。

## Event driven 告警與事件中心整合

異常事件驅動後續處理。ElastAlert 依查詢條件、門檻、事件次數與時間窗辨識異常；規則命中後，事件交由對應處理策略組裝 Incident，再呼叫事件中心系統(ITSM) API。

告警程式依來源處理差異：CPU、記憶體、磁碟、服務可用性、應用日誌、APM、安全事件與網路設備各有對應的參數解析、事件標題與描述欄位。Fleet Agent 狀態也會定期查詢，異常 Agent 會進入相同的事件處理流程。

```mermaid
flowchart LR
    ES[Elasticsearch 監控資料] --> Rules[ElastAlert 規則判斷]
    Fleet[Fleet Agent 狀態] --> Monitor[Agent 狀態監控程式]
    Rules -->|規則命中| Handler[AlertHandler / AlertStrategy]
    Monitor -->|異常狀態| Handler
    Handler --> Incident[組裝 Incident 欄位]
    Incident --> Client[ITSMClient]
    Client -->|API| Center[事件中心系統 ITSM]
```

[76 個原始告警規則](components/alerting/CM-Alert-condition/)、[事件處理策略與 ITSMClient](components/alerting/CM-Alert-poster/ticket_creater.py)、[Agent 狀態監控](components/alerting/CM-Alert-elastic_agent/elastic_agent_monitor.py)，以及 [獨立 Agent 告警程式](components/elastic-agent-alert/)保留於 repository。規則中的判斷結構、時間窗與參數位置維持原樣，實際目標及業務條件由外部設定提供。

## 原始碼目錄

原始 workspace 的 105 個程式與設定來源整理於以下目錄；ConfigMap 裡的程式及設定拆成獨立檔案，方便閱讀與維護。

```text
components/                 程式、告警規則與服務設定
  access/                   Nginx、LDAP 與入口頁
  alerting/                 ElastAlert、事件處理策略與 Agent 狀態監控
  elastic-agent-alert/      獨立 Agent 告警程式與 Dockerfile
  apm-kafka/                APM 與 Logstash Kafka pipeline
  elasticsearch-legacy/     原 ES 節點設定
  fleet/                    Fleet Server 設定與憑證欄位
  heartbeat/                HTTP、TCP、ICMP 探測設定
  kibana/                   Kibana 設定
  logstash/                 網路監控 pipeline
  f5-metric-collection/      F5 採集程式
  security/                 Deep Security 採集程式
manifests/                  依元件分類的 OCP 部署與儲存設定
config/                     外部參數目錄與 ConfigMap 檔案對應
tools/                      只處理本機檔案的組裝與靜態檢查工具
docs/                       元件導覽、設定方式與來源清單
```

各檔案的角色見[元件導覽](docs/components.md)，原始檔與公開檔案的對應記錄於[來源清單](docs/source-inventory.json)。環境專屬設定改為 `__CFG_0001__` 形式的參數，可透過[設定整理方式](docs/configuration.md)在 repository 外還原完整設定檔。

[靜態檢查](docs/validation.md)用於核對語法、設定對應與公開內容。
