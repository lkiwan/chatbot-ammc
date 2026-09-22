import json

import chromadb

from config import CHROMA_DIR, CHUNKS_PATH, COLLECTION


def build_index(force: bool = False) -> None:
    chunks = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        collection = client.get_collection(COLLECTION)
        if not force:
            print(f"Index deja present ({collection.count()} chunks). "
                  "Utilisez --force pour le reconstruire.")
            return
        client.delete_collection(COLLECTION)
    except Exception:
        pass

    collection = client.get_or_create_collection(COLLECTION)

    batch = 64
    for i in range(0, len(chunks), batch):
        part = chunks[i : i + batch]
        collection.add(
            ids=[str(c["id"]) for c in part],
            documents=[c["text"] for c in part],
            metadatas=[{"page": c["page"], "source": c["source"]} for c in part],
        )

    print(f"Index vectoriel : {collection.count()} chunks -> {CHROMA_DIR}")


if __name__ == "__main__":
    build_index()