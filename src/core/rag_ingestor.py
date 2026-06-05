import os
import requests
import re
from typing import List, Dict
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

class PowerShellIngestor:
    """
    Downloads and parses PowerShell documentation from GitHub,
    splits by headers, and loads into ChromaDB.
    """
    REPO_URL = "https://api.github.com/repos/MicrosoftDocs/PowerShell-Docs/contents/reference/7.4/Microsoft.PowerShell.Core"
    RAW_BASE_URL = "https://raw.githubusercontent.com/MicrosoftDocs/PowerShell-Docs/main/reference/7.4/Microsoft.PowerShell.Core/"

    def __init__(self, persist_directory: str = "./rag_data/chroma_db"):
        self.persist_directory = persist_directory
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    def fetch_cmdlet_list(self) -> List[str]:
        response = requests.get(self.REPO_URL)
        response.raise_for_status()
        return [item["name"] for item in response.json() if item["name"].endswith(".md")]

    def parse_markdown(self, content: str, filename: str) -> List[Document]:
        cmdlet_name = filename.replace(".md", "")
        # Split by top-level headers (e.g., ## Syntax, ## Examples)
        sections = re.split(r'\n##\s+', content)
        documents = []
        
        # The first section is usually the title and description
        header_info = sections[0]
        documents.append(Document(
            page_content=header_info,
            metadata={"cmdlet": cmdlet_name, "section": "Description"}
        ))

        for section in sections[1:]:
            lines = section.split('\n')
            section_title = lines[0].strip()
            section_body = '\n'.join(lines[1:]).strip()
            
            if section_body:
                documents.append(Document(
                    page_content=f"Cmdlet: {cmdlet_name}\nSection: {section_title}\n{section_body}",
                    metadata={"cmdlet": cmdlet_name, "section": section_title}
                ))
        
        return documents

    def run(self, limit: int = 10):
        print(f"Fetching cmdlet list...")
        files = self.fetch_cmdlet_list()
        all_docs = []
        
        for i, filename in enumerate(files[:limit]):
            print(f"[{i+1}/{limit}] Downloading {filename}...")
            raw_url = self.RAW_BASE_URL + filename
            res = requests.get(raw_url)
            if res.status_code == 200:
                docs = self.parse_markdown(res.text, filename)
                all_docs.extend(docs)
        
        print(f"Loading {len(all_docs)} documents into ChromaDB at {self.persist_directory}...")
        Chroma.from_documents(
            documents=all_docs,
            embedding=self.embeddings,
            persist_directory=self.persist_directory
        )
        print("Ingestion complete.")

if __name__ == "__main__":
    ingestor = PowerShellIngestor()
    ingestor.run(limit=15) # Limiting for demo, increase for production
