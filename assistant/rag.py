import hashlib
import uuid
import zipfile
from pathlib import Path

from .excel import digest


class RagTools:
    def __init__(self, files, client, root, audit, owner="local", storage_root=None, vision_model="gemma3:4b"):
        self.files, self.client, self.root, self.audit = files, client, Path(root), audit
        self.owner = owner
        self.storage_root = Path(storage_root) if storage_root else self.root / "data"
        self.vision_model=vision_model
        self.collection_name = "personal_bge_v1_" + hashlib.sha256(owner.encode()).hexdigest()[:16]

    def read_document(self,path):
        from .documents import read_local,pdf_vision_ocr
        return read_local(path,pdf_ocr=pdf_vision_ocr(self.client,self.vision_model))

    def collection(self):
        import chromadb
        from chromadb.config import Settings
        db = chromadb.PersistentClient(path=str(self.storage_root / "chroma"),
                                       settings=Settings(anonymized_telemetry=False))
        return db.get_or_create_collection(self.collection_name, embedding_function=None,
                                           metadata={"hnsw:space": "cosine"})

    def text(self, path):
        p=self.files.path(path)
        if p.suffix.lower() not in {'.txt','.md','.pdf','.docx'}:
            raise ValueError('RAG hỗ trợ TXT, MD, PDF văn bản và DOCX.')
        document=self.read_document(p)
        if not document['full_text']:
            raise ValueError('Chưa đọc đủ phần chữ để index: '+document['coverage_note'])
        return document['text']

    def prepare(self, path):
        p = self.files.path(path)
        before = digest(p)
        text = self.text(str(p)).strip()
        if not text:
            raise ValueError("Tài liệu không có text có thể index. PDF scan cần OCR ngoài app.")
        if len(text) > 100000:
            raise ValueError("Tài liệu vượt 100000 ký tự. Hãy chia thành file nhỏ hơn.")
        if digest(p) != before:
            raise RuntimeError("Tài liệu thay đổi trong khi đọc.")
        return {"action": "rag_index", "path": str(p), "sha256": before,
                "characters": len(text), "preview": text[:1000], "approval_id": uuid.uuid4().hex}

    def embed(self, texts, query=False):
        from .memory import embed
        return embed(self.client, texts)

    def commit(self, plan):
        p = self.files.path(plan["path"])
        if digest(p) != plan["sha256"]:
            raise RuntimeError("Tài liệu thay đổi sau preview, hãy xin duyệt lại.")
        text = self.text(str(p))
        offsets=list(range(0,len(text),850))
        chunks = [text[i:i+1000] for i in offsets]
        import re
        page_marks=[(m.start(),int(m.group(1))) for m in re.finditer(r'\[trang (\d+)\]',text,re.I)]
        pages=[next((page for position,page in reversed(page_marks) if position<=offset),0) for offset in offsets]
        vectors = []
        self.audit("rag_index_started", {"path": str(p), "chunks": len(chunks)})
        for i in range(0, len(chunks), 8):
            vectors.extend(self.embed(chunks[i:i+8]))
        if digest(p) != plan["sha256"]:
            raise RuntimeError("Tài liệu thay đổi trong lúc embed; chưa cập nhật index.")
        coll = self.collection()
        prefix = hashlib.sha256(str(p).encode()).hexdigest()[:16]
        ids = [f"{prefix}_{plan['sha256'][:16]}_{i}" for i in range(len(chunks))]
        old = coll.get(where={"source": str(p)}, include=["metadatas"])["ids"]
        coll.upsert(ids=ids, embeddings=vectors, documents=chunks,
                    metadatas=[{"source": str(p), "sha256": plan["sha256"], "chunk": i+1,"page":pages[i]} for i in range(len(chunks))])
        stale = [key for key in old if key not in ids]
        if stale:
            coll.delete(ids=stale)
        result = {"ok": True, "source": str(p), "chunks": len(chunks), "embedding": "bge-m3 (CPU)"}
        self.audit("rag_index_success", result)
        return result

    def rag_search(self, query):
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            raise ValueError("Query RAG tối đa 2000 ký tự.")
        coll = self.collection()
        count = coll.count()
        if not count:
            return {"sources": [], "note": "Index rỗng. Dùng rag_index có xác nhận để thêm tài liệu."}
        hits = coll.query(query_embeddings=self.embed([query], query=True), n_results=min(5, count),
                          include=["documents", "metadatas", "distances"])
        results = []
        for text, meta, distance in zip(hits["documents"][0], hits["metadatas"][0], hits["distances"][0]):
            if distance > 0.6:continue
            try:
                current = self.files.path(meta["source"])
                if digest(current) != meta["sha256"]:
                    continue
            except (OSError, PermissionError):
                continue
            results.append({"source": meta["source"], "chunk": meta["chunk"],
                            "text": text, "cosine_distance": distance,"page":meta.get("page",0),"sha256":meta["sha256"]})
        return {"sources": results, "note": "Chỉ trả chunk của file còn trong whitelist và hash chưa thay đổi. "
                "Không có ngưỡng chứng minh đúng; nếu nguồn yếu hãy nói chưa đủ dữ liệu."}
