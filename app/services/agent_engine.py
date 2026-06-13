import os
from langchain_openai import ChatOpenAI
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from app.tools.s3_memory import save_to_long_term_memory, read_from_long_term_memory
from app.tools.vector_memory import save_semantic_memory, search_semantic_memory, ingest_local_file

# Initialize the LLM using environment variables
llm = ChatOpenAI(
    base_url=os.getenv("LLM_BASE_URL"), 
    api_key=os.getenv("LLM_API_KEY"), 
    model=os.getenv("LLM_MODEL_NAME"), 
    timeout=60.0,
    temperature=0.1,
    max_retries=3
)

tools = [
    save_to_long_term_memory, 
    read_from_long_term_memory,
    save_semantic_memory, 
    search_semantic_memory, 
    ingest_local_file
]

system_message = """
You are a highly capable AI assistant equipped with advanced memory systems:
1. S3 Document Storage (`save_to_long_term_memory` / `read_from_long_term_memory`): For saving newly generated exact files or exact file retrieval.
2. Semantic Vector Storage (`save_semantic_memory` / `search_semantic_memory`): For quick facts, personal preferences, and ingested document knowledge. 
3. Document Ingestion (`ingest_local_file`): Use this when the user asks you to read, learn, or memorize a large file they have provided.

CRITICAL INSTRUCTION: If the user asks a question about rules, protocols, or specific setups (e.g., "what color should the server be?"), ALWAYS use `search_semantic_memory` to check your ingested documents BEFORE assuming it is a general question or giving generic advice.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_message),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(llm, tools, prompt)

# verbose=True keeps the internal monologue visible in the Docker logs
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)