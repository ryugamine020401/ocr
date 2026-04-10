# Stage 1 驗收 Checklist

使用這份清單來判斷 Stage 1 ingestion 是否達到可接受狀態，並能安全地進入 Stage 2。

## 驗收範圍

Stage 1 只有在同時產出以下兩種資料流時，才算完成：

- [x] 視覺輸出：頁面影像
- [x] 文字輸出：抽取出的文字與其座標資訊

## 必要輸出檔案

針對每份文件，在 `data/outputs/stage1_ingest/{doc_id}/` 底下至少要能看到：

- [x] `document.json` : 文件的總索引
- [x] `meta/ingest.json` : ingestion 任務的執行摘要
- [x] `pages/0001.png` : 與所有對應頁面的影像
- [x] `text/full_text.txt` : PDF 的純文字串接版本
- [x] `text/pages_text.json` : page-level 的文字資料
- [x] `text/words.json` : 單字 + 座標
- [x] `text/chars.json` : 字元 + 座標


## 文件層級檢查

檢查 `document.json`：

- [x] `doc_id` 是否與輸出資料夾名稱一致
- [x] `source_file` 與 `source_path` 是否指向正確的輸入 PDF
- [x] `mime_type` 是否為 `application/pdf`
- [x] `file_size_bytes` 是否大於 0
- [x] 是否有 `sha256`
- [x] `num_pages` 是否與實際頁數一致
- [x] `dpi` 是否與執行時設定相符
- [ ] `text_source` 是否有正確填寫
- [ ] `has_text_layer` 是否符合該 PDF 的實際情況

檢查 `meta/ingest.json`：

- [x] `num_pages` 是否與 `document.json` 一致
- [x] `num_words` 是否大於等於 0
- [x] `num_chars` 是否大於等於 0
- [x] 是否有 `created_at`

## 頁面影像檢查

針對 `document.json` 中每一頁：

- [x] `image_path` 指向的檔案是否存在
- [x] `width` 與 `height` 是否為正數
- [x] 輸出的頁面影像數量是否等於 `num_pages`
- [ ] 檔名是否連續，例如 `0001.png`、`0002.png`

## 文字資料流檢查

檢查 `text/pages_text.json`：

- [x] 頁面數量是否等於 `num_pages`
- [x] 每頁是否都有 `page_index`、`page_number`、`text`、`text_length`、`word_count`
- [x] 如果文件有文字層，`text_length` 應大於 0

檢查 `text/full_text.txt`：

- [x] 對於有文字層的 PDF，檔案內容不應為空
- [x] 抽查時，內容應大致對得上原始 PDF --> 但沒有順序，順序混亂

## 座標資訊檢查

檢查 `text/words.json` 與 `text/chars.json`：

- [x] 每筆資料是否包含 `text`、`bbox`、`polygon`、`page_index`、`page_number`
- [x] `bbox` 格式是否為 `[x, y, w, h]` --> 左上角 + 寬高 / `polygon` 是四個角點座標 
- [x] `w > 0`
- [x] `h > 0`
- [x] `x >= 0`
- [x] `y >= 0`
- [ ] 座標是否落在頁面尺寸範圍內，或至少非常接近頁面邊界

可人工抽查幾筆資料：

- [ ] 靠近頁面上方的文字，`y` 應較小
- [ ] 靠近頁面下方的文字，`y` 應較大
- [ ] 靠左的文字，`x` 應較小

## 品質檢查

Stage 1 可接受的條件：

- [ ] 文字大致可閱讀
- [ ] 頁面順序正確
- [ ] 座標沒有明顯上下顛倒或整體偏移
- [ ] `word_count` 與文件型態相符，不明顯異常

現階段可接受的不完美情況：

- 某些符號可能因 PDF 原生文字層編碼而顯示異常
- 中英混排或 CJK 文件的切詞方式未必理想
- 表格內容後續仍可能需要 Stage 3 OCR 或正規化補強

## 快速驗收判準

如果同時滿足以下條件，就可以判定 Stage 1 通過：

- [x] 執行流程沒有報錯
- [x] 所有必要輸出檔案都有產生
- [x] 頁面影像數量與 `num_pages` 一致
- [x] 對於文字型 PDF，文字輸出不是空的
- [x] 座標輸出存在且數值合理
- [x] 抽查時沒有發現明顯的頁面、圖片、文字對不上情況

## 建議的 Smoke Test 組合

在正式凍結 Stage 1 前，建議至少驗證：

- [ ] 一份英文文字型 PDF
- [ ] 一份中文文字型 PDF
- [ ] 一份版面或表格較複雜的 PDF
