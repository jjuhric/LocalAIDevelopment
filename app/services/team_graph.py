import os
import re
import operator
from typing import TypedDict, Annotated, Sequence
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver  # Production uses SqliteSaver/PostgresSaver

# ==========================================
# 1. STRUCTURING THE TEAM STATE
# ==========================================
class TeamState(TypedDict):
    """The central single source of truth passed between all nodes."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_action: str      # Tracks who should act next: 'coder', 'reviewer', or 'finish'
    current_code: str     # Holds the cleaned script draft text
    review_feedback: str  # Holds bugs, fixes, or adjustments requested by the reviewer
    loop_count: int       # Prevent infinite loops by tracking adversarial iterations

# ==========================================
# 2. INITIALIZE THE MODEL
# ==========================================
llm = ChatOpenAI(
    base_url=os.getenv("LLM_BASE_URL"),
    api_key=os.getenv("LLM_API_KEY"),
    model=os.getenv("LLM_MODEL_NAME"),
    temperature=0.1  # Low temperature ensures deterministic, logical code generations
)

# ==========================================
# 3. DEFINE THE WORKER NODES
# ==========================================

def supervisor_node(state: TeamState):
    """Acts as the conductor. Determines if the graph should continue or exit."""
    loop_count = state.get("loop_count", 0)
    feedback = state.get("review_feedback", "").upper()
    current_code = state.get("current_code", "").strip()

    # Base case 1: No code written yet? Go straight to coder
    if not current_code:
        return {"next_action": "coder", "loop_count": loop_count + 1}

    # Base case 2: Safeguard against runaway local iterations
    if loop_count >= 4:
        return {"next_action": "finish"}

    # Base case 3: Reviewer explicitly greenlit the code
    if "APPROVED" in feedback:
        return {"next_action": "finish"}

    # If code exists but isn't approved yet, bounce it back to the coder to fix
    return {"next_action": "coder", "loop_count": loop_count + 1}


def coder_node(state: TeamState):
    """Generates or updates Python script logic based on reviewer critiques."""
    # Grab the original human instruction from the very first message
    user_instruction = state["messages"][0].content
    feedback = state.get("review_feedback", "Initial draft requested.")
    historical_code = state.get("current_code", "")

    system_prompt = (
        "You are an expert Python Developer node.\n"
        f"Task Goal: {user_instruction}\n\n"
        f"Your Previous Code Draft:\n{historical_code}\n\n"
        f"Reviewer Feedback to fix:\n{feedback}\n\n"
        "Output ONLY the functional Python script logic. Start directly with imports. "
        "Do not wrap your response in markdown code blocks or backticks. "
        "Do not include conversational chat intros or outros."
    )

    response = llm.invoke([HumanMessage(content=system_prompt)])
    raw_code = response.content.strip()

    # SANITIZATION STEP: Highly robust regex extraction
    # 1. Strip out any prepended conversational headers like "[Coder Output]:" or "[Coder]:"
    raw_code_clean = re.sub(r"^(?:\s*\[.*?\]:?\s*)+", "", raw_code, flags=re.IGNORECASE | re.MULTILINE).strip()

    # 2. Search for code blocks wrapped in ```python ... ``` anywhere in the response
    code_match = re.search(r"```python\s*(.*?)\s*```", raw_code_clean, flags=re.DOTALL | re.IGNORECASE)
    if code_match:
        clean_code = code_match.group(1).strip()
    else:
        # 3. Fallback: Search for generic ``` ... ``` code blocks
        generic_match = re.search(r"```\s*(.*?)\s*```", raw_code_clean, flags=re.DOTALL)
        if generic_match:
            clean_code = generic_match.group(1).strip()
        else:
            # 4. Fallback: Assume the response is raw code if no blocks were found
            clean_code = raw_code_clean

    # If code extraction resulted in nothing, preserve the previous draft as a safety fall-through
    if not clean_code and historical_code:
        clean_code = historical_code

    return {
        "messages": [AIMessage(content="[Coder]: Generated updated script draft.")],
        "current_code": clean_code,
        "next_action": "reviewer"
    }


def reviewer_node(state: TeamState):
    """Examines draft scripts for security, logic flaws, and criteria alignment."""
    code_to_review = state.get("current_code", "").strip()
    user_instruction = state["messages"][0].content

    if not code_to_review:
        return {
            "messages": [AIMessage(content="[Reviewer]: Found empty code artifact.")],
            "review_feedback": "ERROR: Coder provided an empty string. Rewrite the full code structure.",
            "next_action": "supervisor"
        }

    system_prompt = (
        "You are a strict, pedantic Senior QA Engineer node.\n"
        f"Original User Intent: {user_instruction}\n\n"
        "Evaluate this raw Python script text for compilation bugs, accuracy, or missing features:\n"
        "-------------------------------------\n"
        f"{code_to_review}\n"
        "-------------------------------------\n\n"
        "CRITICAL CRITERIA:\n"
        "1. If the code completely satisfies the request with no errors, respond with exactly: APPROVED\n"
        "2. If it misses features, loops infinitely, or fails criteria, output your specific repair instructions."
    )

    response = llm.invoke([HumanMessage(content=system_prompt)])
    review_output = response.content.strip()

    # Normalize review output to handle prepended tags (e.g., "[Reviewer Output]:")
    review_normalized = re.sub(r"^(?:\s*\[.*?\]:?\s*)+", "", review_output, flags=re.IGNORECASE | re.MULTILINE).strip()

    if "APPROVED" in review_normalized.upper():
        return {
            "messages": [AIMessage(content="[Reviewer]: Code verified and approved.")],
            "review_feedback": "APPROVED",
            "next_action": "supervisor"
        }

    return {
        "messages": [AIMessage(content=f"[Reviewer Feedback]: {review_output}")],
        "review_feedback": review_output,
        "next_action": "supervisor"
    }

# ==========================================
# 4. GRAPH ENGINE COMPILATION
# ==========================================
workflow = StateGraph(TeamState)

# Add our nodes to the blueprint map
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("coder", coder_node)
workflow.add_node("reviewer", reviewer_node)

# Establish the entry point wire
workflow.set_entry_point("supervisor")

# Bind normal structural transitions
workflow.add_edge("coder", "reviewer")
workflow.add_edge("reviewer", "supervisor")

# Define conditional logic routing out of the supervisor
def router_logic(state: TeamState):
    if state["next_action"] == "coder":
        return "coder"
    return "end"

workflow.add_conditional_edges(
    "supervisor",
    router_logic,
    {
        "coder": "coder",
        "end": END
    }
)

memory_checkpointer = MemorySaver()
# Compile into an executable runner
# Old compilation line:
# compiled_team_graph = workflow.compile(checkpointer=memory_checkpointer)

# New Breakpoint-Enabled Compilation line:
# This instructs LangGraph to completely halt execution every single time the state machine 
# transitions away from the reviewer node back into the supervisor block.
compiled_team_graph = workflow.compile(
    checkpointer=memory_checkpointer,
    interrupt_after=["reviewer"]
)