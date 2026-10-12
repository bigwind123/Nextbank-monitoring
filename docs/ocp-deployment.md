# 我的 OCP 部署流程

我把 Elasticsearch 與 Kafka 放在獨立 Linux 主機，並將 Kibana、Nginx／LDAP 認證服務、Fleet、APM、Logstash、Heartbeat、告警與採集程式部署到 OCP。我先用完整 Linux 部署完成 Fleet 初始化，再將相同的執行設定與產生的憑證帶到服務層。

我先在外部 `operator.json` 指定獨立 Elasticsearch 的 `es`、`es_host`、`es_port`，以及 Kafka 的 `kafka_brokers`，再載入同一個 runtime 目錄。我把外部 LDAP 設定與 LDAPS CA 一起放在該目錄，保留每個使用者的權限對應。我為所有公開服務的 Route 主機名稱提供有效的 TLS 憑證。

我先將自訂映像建置並推送到自己的 registry。以下的變數由我在執行環境設定，不寫入 repository。

```powershell
docker build -f docker/app.Dockerfile -t "$ImagePrefix/app:local" .
docker build -f docker/alerting.Dockerfile -t "$ImagePrefix/alerting:local" .
docker build -f docker/security-collector.Dockerfile -t "$ImagePrefix/security-collector:local" .
docker push "$ImagePrefix/app:local"
docker push "$ImagePrefix/alerting:local"
docker push "$ImagePrefix/security-collector:local"
python -m scripts.platform init --runtime $Runtime --operator $OperatorFile
python -m scripts.platform ocp --runtime $Runtime --operator $OperatorFile --namespace $Namespace --storage-class $StorageClass --image-prefix $ImagePrefix
oc apply -f "$Runtime/ocp/services.yaml"
oc wait --for=condition=complete job/prepare-runtime -n $Namespace --timeout=180s
oc get pods -n $Namespace
```

我使用支援 ReadWriteMany 的 StorageClass 保存服務層的 runtime 設定，並替有本機狀態的元件建立獨立 PVC。我不把 Elasticsearch data path 放在這個共享 volume。

我讓一般應用使用 OCP 的 namespace UID 配置。Elastic Agent 需要的 root 權限與 Heartbeat ICMP 的 `NET_RAW` 權限，我只給對應的 ServiceAccount；我依自己的 OCP SCC 管理程序配置 `fleet-agent` 與 `heartbeat-service`，再啟動這些 Pod。

我不會由產生器直接部署到 cluster。所有含實際位址與機敏設定的 Secret、ConfigMap 與 manifests 都產生在 repository 外的 runtime 目錄，我在自己的環境執行 `oc apply`。
