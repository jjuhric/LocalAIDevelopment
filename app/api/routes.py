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
    thread_id: str = "altha_dev_session"

class ApprovalRequest(BaseModel):
    thread_id: str
    approve: bool
    feedback: str = ""

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
        config = {"configurable": {"thread_id": request.thread_id}}
        
        # Check if the thread already exists and is paused at a breakpoint
        current_state = compiled_team_graph.get_state(config)
        
        if current_state.next:
            # The graph is paused waiting for user action!
            return {
                "status": "PAUSED",
                "waiting_at_node": current_state.next[0],
                "current_code": current_state.values.get("current_code"),
                "message": "The system is awaiting human approval before proceeding."
            }
            
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "current_code": "",
            "review_feedback": "",
            "loop_count": 0
        }
        
        # Execute the graph. It will run until it hits END or our configured breakpoint!
        final_state = compiled_team_graph.invoke(initial_state, config=config)
        
        # Re-check state to see if it paused mid-execution or completed entirely
        post_execution_state = compiled_team_graph.get_state(config)
        if post_execution_state.next:
            return {
                "status": "PAUSED",
                "waiting_at_node": post_execution_state.next[0],
                "current_code": post_execution_state.values.get("current_code"),
                "message": "Breakpoint triggered. Review requested."
            }
            
        return {
            "status": "COMPLETED",
            "final_code": final_state.get("current_code"),
            "execution_history": [msg.content for msg in final_state.get("messages", [])]
        }
    except Exception as e:
        logger.error(f"Graph execution failure: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agent/team-approve")
def approve_agent_action(request: ApprovalRequest):
    """Resumes a paused graph by manually injecting human approval state."""
    try:
        config = {"configurable": {"thread_id": request.thread_id}}
        current_state = compiled_team_graph.get_state(config)
        
        if not current_state.next:
            raise HTTPException(status_code=400, detail="This thread is not currently paused.")
            
        # Determine the user update based on approval feedback
        if request.approve:
            user_feedback = "APPROVED"
        else:
            user_feedback = f"HUMAN OVERRIDE REJECTION: {request.feedback}"
            
        # 1. Update the state directory dynamically with the human's input
        compiled_team_graph.update_state(
            config,
            {"review_feedback": user_feedback},
            as_node=current_state.next[0] # Impersonate the paused node to update its context cleanly
        )
        
        # 2. Resume execution by invoking the graph with None as the state parameter
        # Passing None tells LangGraph to pick up exactly where the checkpointer left off!
        final_state = compiled_team_graph.invoke(None, config=config)
        
        return {
            "status": "COMPLETED",
            "final_code": final_state.get("current_code"),
            "execution_history": [msg.content for msg in final_state.get("messages", [])]
        }
    except Exception as e:
        logger.error(f"Failed to resume graph: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))