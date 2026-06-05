import os
from typing import List, Dict, Any
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

class PowerShellRagService:
    """
    Service to provide hybrid retrieval (Vector + Keyword) for PowerShell cmdlets.
    """
    def __init__(self, persist_directory: str = "./rag_data/chroma_db"):
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.db = Chroma(
            persist_directory=persist_directory,
            embedding_function=self.embeddings
        )

    def search(self, query: str, k: int = 3) -> str:
        """
        Combined search: semantic similarity + specific keyword boosting for cmdlet names.
        """
        # 1. Semantic search
        docs = self.db.similarity_search(query, k=k)
        
        # 2. Heuristic: If query looks like a cmdlet (Verb-Noun), try to fetch its syntax
        # e.g., 'Get-Service'
        import re
        cmdlet_match = re.search(r'\b[A-Z][a-z]+-[A-Z][a-z]+\b', query)
        if cmdlet_match:
            cmdlet_name = cmdlet_match.group(0)
            keyword_docs = self.db.get(where={"cmdlet": cmdlet_name})
            if keyword_docs and keyword_docs['documents']:
                # Add cmdlet-specific info to the top
                context_parts = [f"Direct Match for {cmdlet_name}:\n{keyword_docs['documents'][0]}"]
                context_parts.extend([d.page_content for d in docs])
                return "\n---\n".join(context_parts)

        return "\n---\n".join([d.page_content for d in docs])

if __name__ == "__main__":
    # Quick test
    service = PowerShellRagService()
    print(service.search("How to get list of services?"))
