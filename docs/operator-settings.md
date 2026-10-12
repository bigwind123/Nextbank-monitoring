# 我的外部設定

我將 `operator.json` 放在 repository 外，再透過 `python -m scripts.platform init --operator` 載入。所有服務位址、帳號、密碼、金鑰與監控目標都留在執行環境。

| 欄位 | 我填入的內容 |
| --- | --- |
| `itsm.base` | 我填入事件中心系統(ITSM)的 REST 呼叫位置。 |
| `itsm.user`、`itsm.caller` | 我填入事件中心使用的登入與事件提出者識別。 |
| `itsm.operation` | 我指定 Incident 建立操作；未指定時我使用 iTop 的 `core/create`。 |
| `itsm.ca_file` | 我指定事件中心的受信任 CA。 |
| `secrets.itsm-password` | 我提供事件中心的密碼。 |
| `collectors.f5.base`、`collectors.f5.user` | 我指定 F5 REST 連線與使用者。 |
| `secrets.f5-password` | 我提供 F5 密碼。 |
| `collectors.deepsecurity.base` | 我指定 Deep Security Manager。 |
| `secrets.security-api-key` | 我提供 Deep Security API key。 |
| `collectors.security-events.lookback_minutes` | 我指定資料庫事件回查時間。 |
| `secrets.security-odbc` | 我提供含連線資訊的 ODBC connection string；容器內含 FreeTDS driver。 |
| `vsphere.hosts`、`vsphere.user` | 我指定 vSphere 採集來源與使用者。 |
| `secrets.vsphere-password` | 我提供 vSphere 密碼。 |
| `ldap.base`、`ldap.base_dn`、`ldap.bind_dn`、`ldap.filter`、`ldap.ca_file` | 我指定 LDAPS 搜尋與認證條件，filter 以 `{user}` 代入經過跳脫的使用者名稱。 |
| `secrets.ldap-bind-password` | 我提供 LDAP 搜尋帳號的密碼。 |
| `monitors` | 我提供 Heartbeat 的 HTTP／ICMP monitor 清單。 |
| `rules.<rule-id>.enabled` | 我啟用指定規則。 |
| `rules.<rule-id>.parameters` | 我填入規則目錄所列的外部查詢參數。 |
| `rules.<rule-id>.config` | 我覆寫該規則的索引、門檻、時間窗或查詢。 |
| `kafka_security` | 我提供 Python Kafka client 的 TLS／SASL 設定；我同步調整 Beats 與 Logstash 的部署設定。 |

我用 HTTPS／LDAPS 連接外部服務，並讓所有 HTTP request 驗證伺服器憑證。Kafka 的完整本機部署使用封閉 Compose network；我在跨主機部署時設定 Kafka TLS／SASL。

我替外部 LDAP 使用者建立個別的 Kibana／Elasticsearch 權限對應。公開執行套件建立的本機使用者只用於自己的隔離環境；接入既有目錄時，我保留既有角色與認證配置。
