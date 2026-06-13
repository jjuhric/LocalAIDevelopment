from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from app.services.team_graph import compiled_team_graph
import logging

logger = logging.getLogger("uvicorn.error")
router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "altha_architect_session"

class ApprovalRequest(BaseModel):
    thread_id: str
    approve: bool
    human_notes: str = ""

class ForkRequest(BaseModel):
    thread_id: str
    checkpoint_id: str
    override_feedback: str

@router.post("/agent/team-chat")
def chat_with_team(request: ChatRequest):
    try:
        config = {"configurable": {"thread_id": request.thread_id}}
        current_state = compiled_team_graph.get_state(config)
        
        if current_state.next:
            return {
                "status": "PAUSED",
                "waiting_at_node": current_state.next[0],
                "current_code": current_state.values.get("current_code"),
                "message": "System frozen at breakpoint. Awaiting manual confirmation."
            }
            
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "current_code": "",
            "review_feedback": "",
            "loop_count": 0
        }
        final_state = compiled_team_graph.invoke(initial_state, config=config)
        
        post_state = compiled_team_graph.get_state(config)
        if post_state.next:
            return {
                "status": "PAUSED",
                "waiting_at_node": post_state.next[0],
                "current_code": post_state.values.get("current_code"),
                "message": "Breakpoint triggered. Review requested."
            }
            
        return {"status": "COMPLETED", "final_code": final_state.get("current_code")}
    except Exception as e:
        logger.error(f"Graph execution failure: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agent/team-approve")
def approve_agent_action(request: ApprovalRequest):
    try:
        config = {"configurable": {"thread_id": request.thread_id}}
        current_state = compiled_team_graph.get_state(config)
        
        if not current_state.next:
            raise HTTPException(status_code=400, detail="This thread is not currently paused.")
            
        payload_feedback = "APPROVED" if request.approve else f"REJECTED: {request.human_notes}"
        
        compiled_team_graph.update_state(
            config,
            {"review_feedback": payload_feedback},
            as_node=current_state.next[0]
        )
        final_state = compiled_team_graph.invoke(None, config=config)
        return {
            "status": "COMPLETED",
            "final_code": final_state.get("current_code"),
            "execution_history": [msg.content for msg in final_state.get("messages", [])]
        }
    except Exception as e:
        logger.error(f"Failed to resume graph: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================================
# NEW ENDPOINT 1: EXPOSE IMMUTABLE TEMPORAL HISTORIES
# ==========================================================
@router.get("/agent/team-history/{thread_id}")
def get_thread_history(thread_id: str):
    """Fetches the state snapshots of a specific thread configuration timeline."""
    try:
        config = {"configurable": {"thread_id": thread_id}}
        history_timeline = []
        
        # Pulling sequential checkpoints straight out of checkpointer database storage
        for state in compiled_team_graph.get_state_history(config):
            history_timeline.append({
                "checkpoint_id": state.config["configurable"].get("checkpoint_id"),
                "next_node_scheduled": state.next[0] if state.next else "END",
                "values": {
                    "current_code": state.values.get("current_code"),
                    "review_feedback": state.values.get("review_feedback"),
                    "loop_count": state.values.get("loop_count")
                }
            })
        return {"thread_id": thread_id, "history_timeline": history_timeline}
    except Exception as e:
        logger.error(f"Failed to query thread history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================================
# NEW ENDPOINT 2: FORK STATE MACHINE TIME TREES
# ==========================================================
@router.post("/agent/team-fork")
def fork_thread_history(request: ForkRequest):
    """Insects mutations into a historical checkpoint, resolving namespace trees dynamically."""
    try:
        # 1. Establish the base search config coordinate
        search_config = {"configurable": {"thread_id": request.thread_id}}
        target_state_config = None

        # 2. Iterate through the checkpointer ledger to locate the complete, true configuration object
        for state in compiled_team_graph.get_state_history(search_config):
            if state.config["configurable"].get("checkpoint_id") == request.checkpoint_id:
                # Inherit the absolute complete validated config map (including internal namespace keys)
                target_state_config = state.config
                break

        if not target_state_config:
            raise HTTPException(
                status_code=404, 
                detail=f"Checkpoint metadata hash '{request.checkpoint_id}' could not be located in this thread."
            )

        # 3. Execute the state dictionary mutation using the completely validated state config object
        payload_feedback = f"HUMAN OVERRIDE REJECTION CRITERIA: {request.override_feedback}"
        
        compiled_team_graph.update_state(
            target_state_config,  # Passes complete coordinates including true checkpoint_ns
            {"review_feedback": payload_feedback},
            as_node="reviewer"    # Preserves systemic node execution boundaries
        )
        
        # 4. Invoke passing None signals the runtime engine to fork and resume off this exact coordinate branch
        final_state = compiled_team_graph.invoke(None, config=target_state_config)
        
        return {
            "status": "FORK_COMPLETED",
            "final_code": final_state.get("current_code")
        }
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Failed to execute history fork: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))