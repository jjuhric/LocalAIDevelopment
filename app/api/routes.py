import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
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

# =========================================================================
# PRODUCTION REFACTOR: PROPERLY SCOPED REAL-TIME SSE ASYNC STREAMING
# =========================================================================
@router.post("/agent/team-chat")
async def chat_with_team_stream(request: ChatRequest):
    """Initializes or resumes a decentralized peer graph, streaming token chunks 
    and node transitions in real-time over an active SSE connection.
    """
    config = {"configurable": {"thread_id": request.thread_id}}
    
    initial_state = {
        "messages": [HumanMessage(content=request.message)],
        "current_code": "",
        "review_feedback": "",
        "loop_count": 0
    }

    # INDENTED BY 4 SPACES: Now safely nested inside the route function scope!
    async def event_generator():
        try:
            # Hooking v2 structural tracking streams cleanly out of the state manager
            async for event in compiled_team_graph.astream_events(initial_state, config=config, version="v2"):
                kind = event["event"]
                node_name = event.get("metadata", {}).get("langgraph_node", "system")

                # Telemetry Marker 1: Graph Start
                if kind == "on_chain_start" and event.get("name") == "LangGraph":
                    yield f"data: {json.dumps({'event': 'GRAPH_START', 'thread_id': request.thread_id})}\n\n"
                
                # Telemetry Marker 2: Peer Node Activated
                elif kind == "on_chat_model_start":
                    yield f"data: {json.dumps({'event': 'NODE_START', 'node': node_name})}\n\n"

                # Defensive Type Shield: Catch raw character chunks from LM Studio VRAM
                elif kind == "on_chat_model_stream":
                    event_data = event.get("data", {})
                    chunk_obj = event_data.get("chunk")
                    
                    if chunk_obj is not None:
                        token_chunk = getattr(chunk_obj, "content", "") if hasattr(chunk_obj, "content") else str(chunk_obj)
                        if token_chunk:
                            yield f"data: {json.dumps({'event': 'TOKEN_STREAM', 'node': node_name, 'token': token_chunk})}\n\n"

                # Telemetry Marker 3: Peer Node Deactivated
                elif kind == "on_chat_model_end":
                    yield f"data: {json.dumps({'event': 'NODE_COMPLETE', 'node': node_name})}\n\n"

        except Exception as e:
            logger.error(f"Streaming thread failure: {str(e)}")
            yield f"data: {json.dumps({'event': 'ERROR', 'detail': str(e)})}\n\n"

    # Return the stream handler cleanly from the parent endpoint namespace
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/agent/team-approve")
def approve_agent_action(request: ApprovalRequest):
    try:
        config = {"configurable": {"thread_id": request.thread_id}}
        current_state = compiled_team_graph.get_state(config)
        
        if not current_state.next:
            raise HTTPException(status_code=400, detail="This thread is not currently paused.")
            
        payload_feedback = "SYSTEM_HUMAN_APPROVED" if request.approve else f"MANUAL_HUMAN_REJECTION: {request.human_notes}"
        
        compiled_team_graph.update_state(
            config,
            {"review_feedback": payload_feedback},
            as_node=current_state.next[0]
        )
        final_state = compiled_team_graph.invoke(None, config=config)
        return {
            "status": "COMPLETED",
            "final_code": final_state.get("current_code")
        }
    except Exception as e:
        logger.error(f"Failed to resume graph: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/agent/team-history/{thread_id}")
def get_thread_history(thread_id: str):
    try:
        config = {"configurable": {"thread_id": thread_id}}
        history_timeline = []
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

@router.post("/agent/team-fork")
def fork_thread_history(request: ForkRequest):
    try:
        search_config = {"configurable": {"thread_id": request.thread_id}}
        target_state_config = None

        for state in compiled_team_graph.get_state_history(search_config):
            if state.config["configurable"].get("checkpoint_id") == request.checkpoint_id:
                target_state_config = state.config
                break

        if not target_state_config:
            raise HTTPException(status_code=404, detail="Checkpoint could not be located.")

        compiled_team_graph.update_state(
            target_state_config,
            {"review_feedback": f"MANUAL_HUMAN_REJECTION: {request.override_feedback}"},
            as_node="reviewer_node"
        )
        final_state = compiled_team_graph.invoke(None, config=target_state_config)
        return {
            "status": "FORK_COMPLETED",
            "final_code": final_state.get("current_code")
        }
    except Exception as e:
        logger.error(f"Failed to execute history fork: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))