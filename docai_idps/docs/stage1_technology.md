# Stage 1 技術說明

## 目的

Stage 1 是整條 pipeline 的 ingestion 與 preprocessing 層。

它的工作是把每份輸入 PDF 轉成標準化的雙重表示（Dual Representation）：

- 視覺流：頁面影像
- 文字流：帶有座標資訊的文字資料

這樣後續階段就能同時利用頁面影像做版面分析，也能把文字資料當成後備文字來源與上下文語料。

## 使用的技術

### 1. `pypdf`

`pypdf` 用來做輕量級 PDF 解析與文件層級資訊讀取。

在目前實作中，主要負責：

- 讀取頁數
- 取得文件基本資訊所需的 PDF 結構
- 作為文件層級檢查的基礎工具

### 2. `pypdfium2`

`pypdfium2` 是目前 Stage 1 的核心渲染與文字抽取引擎。

它負責：

- 將每一頁 PDF 渲染成 PNG 圖片
- 抽取 PDF 原生文字層內容
- 抽取字元級座標資訊

這一點很重要，因為 Stage 1 不只是把 PDF 轉成圖片，同時也保留了可供後續處理的原生文字層。

### 3. `Pillow`

`Pillow` 在目前流程中是渲染輸出的輔助套件。

`pypdfium2` 會先產生位圖，再轉成 PIL image，最後將其存成 PNG。

## 目前的處理流程

對每一份輸入 PDF，Stage 1 會執行以下步驟：

1. 驗證輸入檔案
2. 產生標準化的 `doc_id`
3. 讀取 PDF 基本資訊
4. 將每一頁渲染成頁面影像
5. 抽取原生文字層內容
6. 抽取 word-level 與 char-level 座標資料
7. 將標準化 artifact 輸出到指定目錄

## 輸出 Artifact

每份 PDF 會在以下路徑產出對應資料夾：

`data/outputs/stage1_ingest/{doc_id}/`

主要輸出內容如下：

- `document.json`
  - 文件層級 artifact
- `meta/ingest.json`
  - 執行資訊與統計
- `pages/*.png`
  - 渲染後的頁面影像
- `text/full_text.txt`
  - 全文件文字內容
- `text/pages_text.json`
  - 每頁文字內容
- `text/words.json`
  - word-level 文字與邊界框
- `text/chars.json`
  - char-level 文字與邊界框

## 為什麼 Stage 1 很重要

Stage 1 的設計重點是雙重表示（Dual Representation）。

也就是系統會同時保留：

- 影像表示：提供後續視覺版面分析使用
- 文字表示：提供檢索、fallback 與推理使用

這樣做的好處是：

- Stage 2 可以直接使用頁面影像做 layout detection
- Stage 3 可以利用文字與座標做精細對位，或在必要時做 OCR fallback
- 後續 context-linking 可以直接把文字流當成可檢索語料

## 目前實作的技術特性

目前 Stage 1 已支援：

- 僅處理 PDF 輸入
- 將 PDF 渲染成 PNG
- 抽取 PDF 原生文字層
- 輸出 word-level 與 char-level bounding boxes
- 對整個輸入資料夾進行批次處理

目前尚未包含：

- 對純掃描 PDF 的 OCR fallback
- 影像型文件的完整 OCR
- 噪聲符號正規化
- 語意層級的文字切塊

## 如何介紹 Stage 1

你可以這樣介紹：

> Stage 1 負責將原始 PDF 轉成統一的機器可讀 artifact。  
> 它會同時產生頁面影像與帶有座標資訊的原生文字資料，形成 dual representation。  
> 目前實作使用 `pypdf` 進行 PDF 基本資訊讀取，並使用 `pypdfium2` 完成頁面渲染與文字層抽取。

如果想要更短版，也可以這樣說：

> Stage 1 會把每份 PDF 轉成 page images 與 coordinate-aware text artifacts，作為後續版面分析與文件理解的基礎。

## 目前設計的優點

- 結構簡單且穩定
- 容易批次處理
- 同時保留視覺與文字資訊
- 很適合接續 Docling 做版面分析
- 很適合後續接 PaddleOCR 做 fallback 或補強

## 目前的限制

- 仍依賴 PDF 原生文字層是否存在、以及其品質是否良好
- 掃描型 PDF 仍需要後續 OCR fallback
- 目前 word grouping 採 whitespace-based 方法，對 CJK 文件仍可能需要調整
- 某些符號可能因 PDF 編碼問題而出現噪聲

## 在完整 Pipeline 中的位置

Stage 1 是以下階段的基礎：

- Stage 2：使用 Docling 做 layout analysis
- Stage 3：使用 PaddleOCR 做 OCR fallback 與 specialized extraction

如果沒有乾淨且標準化的 Stage 1，後續階段就必須重複直接處理原始 PDF，這會讓整體系統更複雜，也更難維持一致性。
