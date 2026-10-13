# 靜態檢查與測試

以下命令檢查原始碼與設定檔；檢查工具只處理本機檔案。

```bash
python tools/validate.py
python -m unittest discover -s tests
```

靜態檢查確認 Python 語法、YAML／JSON 格式、ConfigMap 檔案對應、外部參數登錄與文件連結；另核對公開內容是否殘留來源帳密、憑證、網路位置與組織識別資訊。

測試確認外部設定中的引號、換行與特殊字元能在 YAML／Python 中正確處理、缺少設定時會停止產生檔案，以及私有輸出必須保存在 repository 外。
