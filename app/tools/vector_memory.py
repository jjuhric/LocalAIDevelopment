import os
import chromadb
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 1. Connect to ChromaDB container
chroma_client = chromadb.HttpClient(host="chromadb", port=8000)

# 2. Load the local embedding math engine
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# 3. Initialize LangChain vector store wrapper
vector_store = Chroma(
    client=chroma_client, 
    collection_name="agent_memory", 
    embedding_function=embeddings
)

@tool
def save_semantic_memory(information: str) -> str:
    """
    Saves general facts or preferences to vector DB.
    Use this when the user shares a personal fact (e.g., 'My favorite color is...').
    """
    try:
        vector_store.add_texts(texts=[information])
        return "SUCCESS: Saved semantically."
    except Exception as e:
        return f"ERROR: {str(e)}"

@tool
def search_semantic_memory(query: str) -> str:
    """
    Searches vector DB based on the concept or meaning of the query.
    Use this to recall facts, user preferences, ingested document contents, protocols, and rules. 
    Always use this tool to check for specific rules before providing generic advice.
    """
    try:
        results = vector_store.similarity_search(query, k=2) 
        if not results: 
            return "No relevant memories found."
        return "\n".join([f"- {doc.page_content}" for doc in results])
    except Exception as e:
        return f"ERROR: {str(e)}"

@tool
def ingest_local_file(filename: str) -> str:
    """
    Reads a large text/markdown file from the local filesystem, splits it into chunks, and saves it.
    Use this when the user asks you to read, ingest, or memorize a local file.
    """
    try:
        clean_filename = os.path.basename(filename)
        file_path = os.path.join("/app/docs", clean_filename)
        
        if not os.path.exists(file_path):
            return f"ERROR: Could not find the file '{clean_filename}'."
            
        with open(file_path, "r", encoding="utf-8") as f:
            document_text = f.read()
            
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, 
            chunk_overlap=200, 
            length_function=len
        )
        
        chunks = text_splitter.split_text(document_text)
        vector_store.add_texts(texts=chunks)
        
        return f"SUCCESS: '{clean_filename}' split into {len(chunks)} chunks and memorized."
    except Exception as e:
        return f"ERROR: {str(e)}"