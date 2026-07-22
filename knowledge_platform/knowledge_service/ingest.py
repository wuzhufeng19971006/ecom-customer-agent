"""数据加载：把 JSONL 形式的 FAQ / 商品知识灌入 ChromaDB。

用法：
    python -m knowledge_platform.knowledge_service.ingest --source data/faq.jsonl --collection kb_faq

JSONL 每行格式：
    {"question": "...", "answer": "...", "tags": ["..."]}
灌库时，向量化文本 = "Q: {question}\nA: {answer}"，元数据保留原始字段。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

from common.logger.logger import get_logger, setup_logging
from knowledge_platform.knowledge_service.retriever.retriever import COLLECTIONS, get_store

log = get_logger(__name__)


def _read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                log.error("ingest.parse_failed", line=i, error=str(e))
                sys.exit(1)
    return records


async def ingest(source: Path, collection: str, *, clear: bool = False) -> int:
    if collection not in COLLECTIONS:
        raise ValueError(f"unknown collection: {collection}, valid: {COLLECTIONS}")

    records = _read_jsonl(source)
    if not records:
        log.warning("ingest.empty", source=str(source))
        return 0

    store = get_store()

    if clear:
        # Chroma 没有原生 clear，通过 delete 即可（按条件全部删除）
        try:
            existing = store._collections[collection].get()
            if existing["ids"]:
                store._collections[collection].delete(ids=existing["ids"])
                log.info("ingest.cleared", collection=collection, removed=len(existing["ids"]))
        except Exception as e:  # noqa: BLE001
            log.warning("ingest.clear_failed", error=str(e))

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for r in records:
        q = r.get("question", "").strip()
        a = r.get("answer", "").strip()
        if not q or not a:
            continue
        doc = f"Q: {q}\nA: {a}"
        meta = {k: v for k, v in r.items() if k not in ("question", "answer")}
        # Chroma 元数据 value 必须是 str/int/float/bool，统一转 str
        meta = {k: (",".join(v) if isinstance(v, list) else str(v)) for k, v in meta.items()}
        ids.append(str(uuid4()))
        documents.append(doc)
        metadatas.append(meta)

    if not documents:
        log.warning("ingest.no_valid_records", source=str(source))
        return 0

    await store.add(collection, ids=ids, documents=documents, metadatas=metadatas)
    log.info(
        "ingest.done",
        collection=collection,
        source=str(source),
        added=len(documents),
        total=store.count(collection),
    )
    return len(documents)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--collection", required=True, choices=list(COLLECTIONS))
    parser.add_argument("--clear", action="store_true", help="灌库前清空集合")
    args = parser.parse_args()

    setup_logging()
    n = asyncio.run(ingest(args.source, args.collection, clear=args.clear))
    print(f"ingested {n} records into {args.collection}")


if __name__ == "__main__":
    main()
