

# 專案架構
```
docai_idps/
├─ README.md
├─ .gitignore
├─ Pipfile
├─ Pipfile.lock
├─ configs/
├─ data/
│  ├─ inputs/
│  │  ├─ raw/
│  │  │  └─ pdf/
│  │  └─ manifests/
│  └─ outputs/
│     ├─ stage1_ingest/
│     ├─ stage2_layout/
│     └─ stage3_ocr/
├─ scripts/
├─ src/
│  └─ docai_idps/
│     ├─ __init__.py
│     ├─ common/
│     │  └─ __init__.py
│     ├─ stage1_ingest/
│     │  └─ __init__.py
│     ├─ stage2_layout/
│     │  └─ __init__.py
│     └─ stage3_ocr/
│        └─ __init__.py
└─ tests/

```