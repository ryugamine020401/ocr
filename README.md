
專案內共分 4 個虛擬環境，虛擬環境都使用 pipenv 建立，所有 Python 版本都是 3.12.10。

專案的目的在透過 WER/CER 評斷以下幾種工具的好壞與否
1. tesseract
2. paddleOCR
3. Document AI
4. MinerU
5. docling

# 建立環境
建立環境方式如下
1. clone 專案
2. 在四個資料夾內建立 .venv 的資料夾
```
mkdir .venv
```
3. 安裝 python 3.12.10 和 pipenv，並建立 python==3.12.10 的虛擬環境
```
python -m pipenv install --python=3.12.10
```
4. 進入虛擬環境後，透過 `requirements.txt` 安裝相關套件
```
pipenv shell
pipenv install -r requirements.txt
```

# 使用方法
1. 先進入 `ocr_eval` 的虛擬環境 且至少應包含以下必須的內容，沒有也可以先建立資料夾
```
ocr_eval/
|
└─ data/
   │
   ├─ images/            # (必須)整個資料集的圖片
   ├─ gt/                # 自己製作的 ground truth 
   ├─ ocr_gt/            # (必須)整個資料集的gt(.json)
   └─pred/               # 各 OCR 模型輸出

```
2. 進入虛擬環境依照順序執行程式，先對整個資料集採樣，取 30 張出來
```
python 00_sample.py
```
> 可以修改 `seed` 來讓實驗可以重現

3. 根據取出的 30 張圖片找尋相對應的 gt，並輸出到 gt 資料夾內，作為本次實驗的 gt
```
python 01_extract_gt.py
```

4. 開始使用 tesseract，會使用挑選出的 30 張圖片來計算評分
```
python 02_run_tesseract.py
```

5. 同上 
```
python 03_run_paddle.py
```

6. 進入 `mineru_eval` 或是 `docling_eval` 或是 `docai_eval`，同時必須建立虛擬環境，建立方式同 `ocr_eval`
```
mkdir .venv
python -m install --python=3.12.10
pipenv shell
pipenv install -r requirements.txt
```

7. 後執行程式，會連同該工具的評分一起計算
```
python main.py
```

8. 回到 `ocr_eval` 執行最後一步驟
```
python 04_merge_results.py
```

9. 最後都會將結果儲存在 data 資料夾內