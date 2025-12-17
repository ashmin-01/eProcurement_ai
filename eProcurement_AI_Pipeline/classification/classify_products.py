import os
import json
import pandas as pd
import faiss
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from transformers import pipeline
import re
import logging

logger = logging.getLogger(__name__)

# ================= CONFIG =================
TOP_K = 5

BASE_DIR = Path(__file__).resolve().parent.parent

CLASSIFICATION_CSV = BASE_DIR / "classification" / "data" / "classification_tree.csv"
CACHE_DIR = BASE_DIR / "classification" / ".cache"
FAISS_INDEX_FILE = CACHE_DIR / "faiss_index.bin"
TAXONOMY_CACHE_FILE = CACHE_DIR / "taxonomy_df.pkl"


os.makedirs(CACHE_DIR, exist_ok=True)

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

LLM_MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

# =========================================

def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# ---------- TAXONOMY ----------
def load_taxonomy(csv_path):
    df = pd.read_csv(csv_path)

    parent_ids = set(df['parent_id'].dropna().astype(int))
    df['is_leaf'] = ~df['id'].isin(parent_ids)
    df = df[df['is_leaf']].copy()

    full_df = pd.read_csv(csv_path)
    id_to_name = full_df.set_index('id')['name'].to_dict()

    def resolve_path(path_str):
        ids = str(path_str).split(".")
        names = [id_to_name.get(int(i), f"Unknown({i})") for i in ids]
        return " > ".join(names)

    df['path_text'] = df['path'].apply(resolve_path)
    return df.reset_index(drop=True)

# ---------- EMBEDDINGS ----------
def embed_texts(model, texts):
    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True
    )
    return embeddings.astype("float32")

def build_or_load_faiss(df, embedding_model):
    if FAISS_INDEX_FILE.exists() and TAXONOMY_CACHE_FILE.exists():
        logger.info("Loading cached FAISS index...")
        index = faiss.read_index(str(FAISS_INDEX_FILE))
        df = pd.read_pickle(TAXONOMY_CACHE_FILE)
        return index, df

    logger.info("Building FAISS index...")
    embeddings = embed_texts(embedding_model, df['path_text'].tolist())
    dim = embeddings.shape[1]

    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    faiss.write_index(index, str(FAISS_INDEX_FILE))
    df.to_pickle(TAXONOMY_CACHE_FILE)

    return index, df

# ---------- SEARCH ----------
def search_candidates(query_text, df, index, embedding_model, top_k):
    emb = embed_texts(embedding_model, [query_text])
    scores, indices = index.search(emb, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        row = df.iloc[idx]
        results.append({
            "id": int(row['id']),
            "path_text": row['path_text'],
            "score": float(score)
        })
    return results

# ---------- LLM ----------
import re
import json

def llm_rerank(product, candidates, pipe):

    prompt = f"""<|system|>
You are a precise industrial classifier. Respond ONLY with a raw JSON object. Do not explain your choice.</s>
<|user|>
Classify this product:
Name: {product.get('product_name')}
Description: {product.get('short_description')}

Candidates:
{json.dumps(candidates, indent=2)}

Return JSON in this format: {{"selected_type_id": 123, "classification_path": "path", "confidence_score": 0.9}}</s>
<|assistant|>"""

    try:
        # Generate text
        output = pipe(prompt, max_new_tokens=150, temperature=0.1)
        full_text = output[0]["generated_text"]

        json_matches = re.findall(r"\{.*?\}", full_text, re.DOTALL)
        
        if json_matches:
            json_str = json_matches[-1]
            # (Basic cleaning)
            return json.loads(json_str)
        else:
            raise ValueError("No JSON block found in LLM response")

    except Exception as e:
        logger.error(f"LLM failed to produce valid JSON: {e}")
        # FALLBACK: Use the #1 candidate from FAISS (Similarity Search)
        best = candidates[0]
        return {
            "selected_type_id": int(best["id"]),
            "classification_path": best["path_text"],
            "confidence_score": float(best["score"]),
            "fallback": True 
        }

# ---------- CLASSIFIER ----------
class ProductClassifier:
    def __init__(self):
        logger.info("Initializing ProductClassifier...")

        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        self.df = load_taxonomy(CLASSIFICATION_CSV)
        self.index, self.df = build_or_load_faiss(self.df, self.embedding_model)

        
        self.pipe = None

    def _load_llm(self):
        """Lazy-load LLM only if needed."""
        if self.pipe is None:
            logger.info("Loading LLM for reranking...")
            self.pipe = pipeline(
                "text-generation",
                model=LLM_MODEL
            )

    def classify_product(self, product, use_llm=False):
        text = " ".join(
            clean_text(str(product.get(k, "")))
            for k in [
                "product_name",
                "short_description",
                "long_description",
                "technical_specifications"
            ]
        )

        if not text.strip():
            return {}

        candidates = search_candidates(
            text,
            self.df,
            self.index,
            self.embedding_model,
            TOP_K
        )

        if not candidates:
            return {}

        if use_llm:
            self._load_llm()
            return llm_rerank(product, candidates, self.pipe)

        # ✅ Embedding-only result
        best = candidates[0]
        return {
            "selected_type_id": best["id"],
            "classification_path": best["path_text"],
            "confidence_score": float(best["score"])
        }