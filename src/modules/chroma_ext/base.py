from typing import Any, Dict, List

import chromadb
import pandas as pd
from chromadb import QueryResult

from service.logger import LoggerConfigurator

from .utils import BM25Reranker, MyEmbeddingFunction


class ChromaAdapter:
    """HTTP adapter for ChromaDB with semantic search and BM25 reranking.

    Notes:
        1. Retrieves relevant documents from ChromaDB based on user queries (RAG).
        2. Reranks retrieved documents by lexical similarity using BM25.
    """

    def __init__(
        self,
        logger: LoggerConfigurator,
        similarity_filter: float = 1.5,
        reranker_type: str = "bm25",
        text_type: str = "query",
        **kwargs,
    ):
        self.logger = logger
        self.logger.info("Initializing ChromaAdapter")
        self.reranker_type = reranker_type
        if reranker_type == "bm25":
            self.reranker = BM25Reranker(logger=logger)
        else:
            NotImplementedError("Only BM25 reranker is supported.")

        self.api_key = kwargs.get("API_KEY", None)
        self.logger.info(f"CHROMA_API_KEY: {self.api_key[:4]}**{self.api_key[-4:]}")
        self.api_url = kwargs.get("API_URL", "https://llm.api.cloud.yandex.net:443/foundationModels/v1/textEmbedding")
        self.logger.info(f"CHROMA_API_URL: {self.api_url}")
        self.folder_id = kwargs.get("FOLDER_ID", None)
        self.logger.info(f"CHROMA_FOLDER_ID: {self.folder_id[:4]}**{self.folder_id[-4:]}")

        self.host = kwargs.get("CHROMA_HOST", "127.0.0.1")
        self.logger.info(f"CHROMA_HOST: {self.host}")

        self.port = kwargs.get("CHROMA_PORT", 8000)
        self.logger.info(f"CHROMA_PORT: {self.port}")

        self.topk_documents = kwargs.get("CHROMA_TOPK_DOCUMENTS", 5)
        self.logger.info(f"CHROMA_TOPK: {self.topk_documents}")

        self.max_rag_documents = kwargs.get("CHROMA_MAX_RAG_DOCUMENTS", 20)
        self.logger.info(f"CHROMA_MAX_RAG: {self.max_rag_documents}")

        self.similarity_filter = similarity_filter
        self.logger.info(f"similarity_filter score: {self.similarity_filter}")

        self.client = chromadb.HttpClient(host=self.host, port=self.port)
        self._embedding_function = None

        self._tokenizer = None
        self._reranker_model = None
        self.text_type = text_type

        if self.folder_id is None:
            raise ValueError("FOLDER_ID must be provided")
        if self.api_key is None:
            raise ValueError("API_KEY must be provided")
        if self.topk_documents >= self.max_rag_documents:
            raise ValueError("TOPK_DOCUMENTS must be less than MAX_RAG_DOCUMENTS")
        self.logger.info("Initialized ChromaAdapter")

    @property
    def embedding_function(self):
        self.logger.debug("embedding_function initialized")
        if self._embedding_function is None:
            self._embedding_function = MyEmbeddingFunction(
                logger=self.logger,
                api_url=self.api_url,
                folder_id=self.folder_id,
                iam_token=self.api_key,
                text_type=self.text_type,
            )
        self.logger.debug("embedding_function initialized")
        return self._embedding_function

    def get_info_from_db(
        self, query: str, collection_name: str, n_results: int = 30, where: dict | None = None, **kwargs
    ) -> QueryResult:
        """Extract semantically similar documents from ChromaDB.

        Args:
            query: User's sub-question.
            collection_name: Target ChromaDB collection.
            n_results: Maximum number of results to retrieve.
            where: Optional metadata filter (e.g. topic filter).

        Returns:
            Raw ChromaDB QueryResult.
        """
        self.logger.debug(f"get_info_from_db called for {collection_name}")
        collection = self.client.get_collection(name=collection_name, embedding_function=self.embedding_function)

        return collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
            where=where,
        )

    def get_filtered_documents(self, data_raw: Dict[str, Any]) -> dict:
        self.logger.debug(f"get_filtered_documents: documents number {len(data_raw['documents'])}")
        distances = data_raw["distances"][0]
        documents = data_raw["documents"][0]
        metadatas = data_raw["metadatas"][0]

        return {
            "documents": [
                doc.split("<body>")[-1].replace("</body>", "")
                for doc, dist in zip(documents, distances)
                if dist < self.similarity_filter
            ],
            "metadatas": [metadatas[idx] for idx, dist in enumerate(distances) if dist < self.similarity_filter],
        }

    def get_pairs(self, query: str, documents: List[str]) -> List[List[str]]:
        self.logger.debug(f"called get_pairs for {query}")
        return [[query, doc] for doc in documents]

    def apply_reranker(self, query, documents):
        self.logger.debug(f"called apply_reranker for {query}")
        if self.reranker_type == "bm25":
            self.reranker.fit(documents)
            return self.reranker.rerank(query=query, top_k=self.topk_documents)
        return None

    def get_info(self, query: str, collection_name: str, topics: list[str] | None = None) -> pd.DataFrame:
        """Main retrieval method: semantic search + distance filter + BM25 rerank.

        Args:
            query: User's sub-question.
            collection_name: ChromaDB collection name.
            topics: Optional list of topic strings for metadata pre-filtering.

        Returns:
            DataFrame with columns ["documents", "metadatas"].
        """
        self.logger.debug(f"get_info called for query='{query}' collection='{collection_name}' topics={topics}")

        where = None
        if topics:
            if len(topics) == 1:
                where = {"topic": topics[0]}
            else:
                where = {"topic": {"$in": topics}}

        data_raw = self.get_info_from_db(
            query=query,
            collection_name=collection_name,
            n_results=self.max_rag_documents,
            where=where,
        )
        filtered_documents = self.get_filtered_documents(data_raw)

        if not filtered_documents["documents"]:
            self.logger.debug(f"No documents found in {collection_name}")
            return pd.DataFrame.from_dict(
                data={
                    "documents": [],
                    "metadatas": [],
                }
            )

        idx_relevant_documents = self.apply_reranker(query=query, documents=filtered_documents["documents"])
        self.logger.debug(f"get_info finished: returned {len(idx_relevant_documents)} documents")
        return pd.DataFrame.from_dict(
            data={
                "documents": [filtered_documents["documents"][idx] for idx in idx_relevant_documents],
                "metadatas": [filtered_documents["metadatas"][idx] for idx in idx_relevant_documents],
            }
        )

    def health_check(self) -> bool:
        """Simple connectivity check."""
        return True
