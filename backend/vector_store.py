"""
Vector Store for Receipt Search using Qdrant
Enables semantic search across receipts with grounding support
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# Try to import Qdrant
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.models import Distance, VectorParams, PointStruct
    QDRANT_AVAILABLE = True
    logger.info("✅ Qdrant available")
except ImportError:
    QDRANT_AVAILABLE = False
    logger.warning("⚠️ qdrant-client not installed")

# Try to import sentence transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
    logger.info("✅ Sentence Transformers available")
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("⚠️ sentence-transformers not installed")


class ReceiptVectorStore:
    """
    Vector store for receipt semantic search using Qdrant
    Stores receipt chunks with embeddings and grounding information
    """
    
    COLLECTION_NAME = "receipts"
    EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 dimension
    
    def __init__(self, persist_directory: str = "./qdrant_receipts"):
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        self.client = None
        self.embedding_model = None
        
        if QDRANT_AVAILABLE:
            try:
                self.client = QdrantClient(path=str(self.persist_directory))
                self._ensure_collection()
                logger.info(f"✅ Qdrant initialized at {self.persist_directory}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Qdrant: {e}")
                
        if EMBEDDINGS_AVAILABLE:
            try:
                # Use lightweight model for receipts
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("✅ Embedding model loaded")
            except Exception as e:
                logger.error(f"❌ Failed to load embedding model: {e}")

    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.COLLECTION_NAME for c in collections)
            
            if not exists:
                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=self.EMBEDDING_DIM,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"✅ Created collection: {self.COLLECTION_NAME}")
        except Exception as e:
            logger.error(f"❌ Failed to ensure collection: {e}")

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        if not self.embedding_model:
            return [0.0] * self.EMBEDDING_DIM
        
        try:
            embedding = self.embedding_model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"❌ Embedding failed: {e}")
            return [0.0] * self.EMBEDDING_DIM

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts"""
        if not self.embedding_model:
            return [[0.0] * self.EMBEDDING_DIM for _ in texts]
        
        try:
            embeddings = self.embedding_model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"❌ Batch embedding failed: {e}")
            return [[0.0] * self.EMBEDDING_DIM for _ in texts]

    def add_receipt(self, receipt_id: str, receipt_data: Dict[str, Any]) -> bool:
        """
        Add a receipt to the vector store
        
        Args:
            receipt_id: Unique receipt identifier
            receipt_data: Receipt data including shop_name, amount, items, raw_text, grounding
        """
        if not self.client:
            logger.warning("Qdrant not available, skipping vector storage")
            return False

        try:
            # Prepare searchable text
            shop_name = receipt_data.get('shop_name', '')
            items_text = ' '.join([item.get('name', '') for item in receipt_data.get('items', [])])
            raw_text = receipt_data.get('raw_text', '')
            
            # Combine for embedding
            full_text = f"{shop_name} {items_text} {raw_text}"
            
            # Generate embedding
            embedding = self.embed_text(full_text)
            
            # Prepare payload with all metadata
            payload = {
                "receipt_id": receipt_id,
                "shop_name": shop_name,
                "shop_address": receipt_data.get('shop_address', ''),
                "amount": receipt_data.get('amount', 0.0),
                "currency": receipt_data.get('currency', 'ZAR'),
                "customer_phone": receipt_data.get('customer_phone', ''),
                "customer_id": receipt_data.get('customer_id', ''),
                "items_count": len(receipt_data.get('items', [])),
                "items_json": json.dumps(receipt_data.get('items', [])),
                "raw_text": raw_text[:2000],  # Limit text length
                "fraud_flag": receipt_data.get('fraud_flag', 'valid'),
                "distance_km": receipt_data.get('distance_km'),
                "created_at": receipt_data.get('created_at', datetime.utcnow().isoformat()),
                # Grounding data
                "has_grounding": bool(receipt_data.get('grounding')),
                "grounding_json": json.dumps(receipt_data.get('grounding', {}))
            }
            
            # Add point to Qdrant
            point = PointStruct(
                id=hash(receipt_id) % (2**63),  # Convert to int ID
                vector=embedding,
                payload=payload
            )
            
            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=[point]
            )
            
            logger.info(f"✅ Added receipt {receipt_id} to vector store")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add receipt: {e}")
            return False

    def search_receipts(
        self, 
        query: str, 
        customer_phone: Optional[str] = None,
        shop_name: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Semantic search for receipts
        
        Args:
            query: Search query (e.g., "milk purchases", "Woolworths receipts")
            customer_phone: Filter by customer
            shop_name: Filter by shop
            limit: Max results
            
        Returns:
            List of matching receipts with scores
        """
        if not self.client:
            return []

        try:
            # Generate query embedding
            query_embedding = self.embed_text(query)
            
            # Build filter conditions
            filter_conditions = []
            
            if customer_phone:
                filter_conditions.append(
                    models.FieldCondition(
                        key="customer_phone",
                        match=models.MatchValue(value=customer_phone)
                    )
                )
            
            if shop_name:
                filter_conditions.append(
                    models.FieldCondition(
                        key="shop_name",
                        match=models.MatchText(text=shop_name)
                    )
                )
            
            # Build filter
            search_filter = None
            if filter_conditions:
                search_filter = models.Filter(
                    must=filter_conditions
                )
            
            # Search
            results = self.client.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=limit
            )
            
            # Format results
            formatted = []
            for hit in results:
                formatted.append({
                    "receipt_id": hit.payload.get("receipt_id"),
                    "shop_name": hit.payload.get("shop_name"),
                    "amount": hit.payload.get("amount"),
                    "customer_phone": hit.payload.get("customer_phone"),
                    "items_count": hit.payload.get("items_count"),
                    "fraud_flag": hit.payload.get("fraud_flag"),
                    "created_at": hit.payload.get("created_at"),
                    "score": hit.score,
                    "has_grounding": hit.payload.get("has_grounding", False)
                })
            
            return formatted
            
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics"""
        if not self.client:
            return {"available": False}
        
        try:
            collection_info = self.client.get_collection(self.COLLECTION_NAME)
            return {
                "available": True,
                "total_receipts": collection_info.points_count,
                "status": str(collection_info.status)
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    def delete_receipt(self, receipt_id: str) -> bool:
        """Delete a receipt from vector store"""
        if not self.client:
            return False
        
        try:
            self.client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="receipt_id",
                                match=models.MatchValue(value=receipt_id)
                            )
                        ]
                    )
                )
            )
            return True
        except Exception as e:
            logger.error(f"❌ Delete failed: {e}")
            return False


# Singleton instance
_vector_store = None

def get_receipt_vector_store() -> ReceiptVectorStore:
    """Get or create the vector store singleton"""
    global _vector_store
    if _vector_store is None:
        _vector_store = ReceiptVectorStore()
    return _vector_store
