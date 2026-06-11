from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
from app.services.agent_engine import agent_executor
from app.services.team_graph import compiled_team_graph # <-- IMPORT THE NEW GRAPH
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)
router = APIRouter()

class ChatRequest(BaseModel):
    message: str

@router.post("/agent/chat")
def chat_with_agent(request: ChatRequest):
    try:
        result = agent_executor.invoke({"input": request.message})
        return {"agent_reply": result["output"]}
    except Exception as e:
        logger.error(f"Agent execution crashed: {str(e)}")
        raise HTTPException(status_code=500, detail="The AI encountered a critical error processing your request.")

# --- NEW MULTI-AGENT ENDPOINT ---
@router.post("/agent/team-chat")
def chat_with_team(request: ChatRequest):
    try:
        # Initialize the State dictionary for LangGraph
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "current_code": "",
            "review_feedback": "",
            "loop_count": 0
        }

        # CRITICAL: Define the thread configuration metadat
        # This thread_id is the unique key used to look up checkpoints in the DB. 
        config = { "configurable": {"thread_id": "altha_dev_session_1"}}
        
        # Execute the State Graph machine
        final_state = compiled_team_graph.invoke(initial_state, config=config)
        
        return {
            "final_code": final_state.get("current_code"),
            "execution_history": [msg.content for msg in final_state["messages"]]
        }
    except Exception as e:
        logger.error(f"Team graph crashed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Graph error: {str(e)}")