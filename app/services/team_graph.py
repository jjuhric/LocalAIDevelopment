import os
import re
from typing import TypedDict, Annotated, Sequence
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
# IMPORT THE COMMAND PRIMITIVE
from langgraph.types import Command

class TeamState(TypedDict):
    messages: Sequence[BaseMessage]
    current_code: str     
    review_feedback: str  
    loop_count: int       

llm = ChatOpenAI(
    base_url=os.getenv("LLM_BASE_URL"),
    api_key=os.getenv("LLM_API_KEY"),
    model=os.getenv("LLM_MODEL_NAME"),
    temperature=0.1,
    timeout=60.0
)

# NOTE: The supervisor_node has been completely deleted.

def coder_node(state: TeamState) -> Command:
    """Autonomous Coder Peer. Decides to pass execution directly to the Reviewer."""
    user_instruction = state["messages"][0].content
    feedback = state.get("review_feedback", "Initial draft requested.")
    historical_code = state.get("current_code", "")
    loop_count = state.get("loop_count", 0) + 1

    # Safe exit wall inside the node itself
    if loop_count > 4:
        return Command(
            update={"review_feedback": "ERROR: Maximum engineering iterations exceeded."},
            goto=END
        )

    system_prompt = (
        "You are an expert Python Developer node.\n"
        f"Task Goal: {user_instruction}\n\n"
        f"Previous Draft:\n{historical_code}\n\n"
        f"Feedback to fix:\n{feedback}\n\n"
        "Output ONLY raw Python script logic. Do not wrap in markdown blocks."
    )

    response = llm.invoke([HumanMessage(content=system_prompt)])
    raw_code = response.content.strip()

    # Regex Sanitization Gate
    raw_code_clean = re.sub(r"^(?:\s*\[.*?\]:?\s*)+", "", raw_code, flags=re.IGNORECASE | re.MULTILINE).strip()
    code_match = re.search(r"```python\s*(.*?)\s*```", raw_code_clean, flags=re.DOTALL | re.IGNORECASE)
    clean_code = code_match.group(1).strip() if code_match else raw_code_clean

    # PEER-TO-PEER HANDOFF: Command explicitly passes state updates and routes directly to the reviewer node
    return Command(
        update={
            "current_code": clean_code,
            "loop_count": loop_count
        },
        goto="reviewer_node"
    )


def reviewer_node(state: TeamState) -> Command:
    """Autonomous Reviewer Peer. Evaluates state metrics and routes to Coder or END."""
    code_to_review = state.get("current_code", "").strip()
    user_instruction = state["messages"][0].content

    system_prompt = (
        "You are a strict QA Engineer node.\n"
        f"User Intent: {user_instruction}\n\n"
        f"Evaluate this script text:\n{code_to_review}\n\n"
        "If clean, reply exactly: APPROVED\n"
        "Else, provide explicit missing logic metrics."
    )

    response = llm.invoke([HumanMessage(content=system_prompt)])
    review_output = response.content.strip()
    
    if "APPROVED" in review_output.upper():
        # PEER-TO-PEER TERMINATION: Explicit greenlight shuts down the state machine natively
        return Command(
            update={"review_feedback": "APPROVED"},
            goto=END
        )

    # PEER-TO-PEER REJECTION: Direct loop back to the Coder without an intermediate supervisor step
    return Command(
        update={"review_feedback": review_output},
        goto="coder_node"
    )

# ==========================================================
# GRAPH DEFINITION: CLEAN AND DECOUPLED
# ==========================================================
workflow = StateGraph(TeamState)

# Register the autonomous peers
workflow.add_node("coder_node", coder_node)
workflow.add_node("reviewer_node", reviewer_node)

# Set the entry point straight to the developer node
workflow.set_entry_point("coder_node")

# CRITICAL: Notice there are NO static edges or conditional routing functions defined here!
# The entire architecture's routing topology is dictated dynamically by the Command returns.

memory_checkpointer = MemorySaver()
compiled_team_graph = workflow.compile(
    checkpointer=memory_checkpointer,
    interrupt_after=["coder_node"]  # Forces a hard serialization freeze the split second the coder returns its Command object!
)