# Chapter 4: Real-Time Event Streaming (astream_events)

## 4.1 The Concept: Breaking Synchronous Wait Times

### The Problem: Frozen UI

Standard graph execution uses **synchronous blocking** with `.invoke()`:

```python
# User clicks "Generate Code" button
result = graph.invoke(initial_state)  # Blocks for 45 seconds
# Browser freezes
# ████████████████░░░░░░░░░░░░░░░░░░░░░░ (no progress bar)
# User thinks it crashed, closes browser ❌
```

**What's happening:**
1. User sends request
2. Server starts `.invoke()` (calls Coder → Reviewer → Reviser)
3. Each step takes 15+ seconds on local GPU
4. HTTP connection is open but **no data flows back**
5. Browser shows spinning wheel with **zero feedback**
6. At 45 seconds, finally returns result

Result: **Terrible user experience**.

### The Solution: Server-Sent Events (SSE) with astream_events

Instead of `.invoke()`, we replace it with `.astream_events(version="v2")`:

```python
# User clicks button
async for event in graph.astream_events(...):  # Non-blocking!
    # Real-time events stream back to browser
    # "Node: Coder started"
    # "Token: def "
    # "Token: calculate_"
    # "Token: fibonacci(...)"
    # "Node: Coder finished"
    # "Node: Reviewer started"
    # "Token: APPROVED"
```

The browser gets **live updates** as computation happens:

```
████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░ (60% done)
"Generating... token 145 of 256"
```

This creates the **"typing out loud"** effect seen in ChatGPT.

---

## 4.2 The Theory: Server-Sent Events (SSE)

### How SSE Works

**Traditional Request-Response (Synchronous):**
```
Browser                           Server
  │                                │
  ├─ POST /api/chat ──────────────>│
  │                                ├─ Process (45 seconds)
  │                                │
  │  (Frozen waiting)              │
  │<─────── Response (huge JSON) ───┤
  │                                │
```

**Server-Sent Events (Asynchronous):**
```
Browser                           Server
  │                                │
  ├─ GET /stream ─────────────────>│
  │<─ Connection open ─────────────┤
  │                                │
  │<─ data: {"token": "def"} ──────┤  (1ms)
  │<─ data: {"token": " calc"} ────┤  (2ms)
  │<─ data: {"token": "_fib"} ─────┤  (3ms)
  │  (Browser updates UI!)         │
  │<─ data: {"token": "..."} ──────┤  (45s)
```

**Key differences:**
- SSE keeps HTTP connection **open**
- Server **pushes data** to browser (not response-based)
- Browser updates UI **incrementally** as events arrive
- Network protocol: `text/event-stream`

---

## 4.3 The Implementation: FastAPI Streaming

### Basic FastAPI Route

```python
# app/api/routes.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json

router = APIRouter()

@router.post("/agent/stream")
async def chat_stream(request: ChatRequest):
    """Stream graph events to browser in real-time"""
    
    config = {
        "configurable": {
            "thread_id": request.thread_id
        }
    }
    
    async def event_generator():
        """Generator yields SSE-formatted events"""
        # Hook directly into the execution engine
        async for event in compiled_team_graph.astream_events(
            initial_state,
            config=config,
            version="v2"  # Use version 2 event format
        ):
            kind = event["event"]
            node_name = event.get("metadata", {}).get("langgraph_node", "system")
            
            # Filter for token streaming events
            if kind == "on_chat_model_stream":
                chunk_obj = event.get("data", {}).get("chunk")
                if chunk_obj is not None:
                    # Defensive type checking
                    token = getattr(chunk_obj, "content", "") if hasattr(chunk_obj, "content") else str(chunk_obj)
                    if token:
                        # SSE format: data: <JSON>\n\n
                        yield f"data: {json.dumps({'event': 'TOKEN', 'node': node_name, 'token': token})}\n\n"
    
    # Return streaming response
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

### Line-by-Line Breakdown

| Code Segment | Explanation & Teaching Point |
|--------------|-------------------------------|
| `async def event_generator():` | Python generator function that yields events one-by-one. The `async` keyword allows non-blocking waits. |
| `async for event in compiled_team_graph.astream_events(...):` | Initializes a **continuous event listener** that catches every state transition, tool call, and token generation as it happens inside the graph framework. Unlike `.invoke()`, this doesn't block. |
| `if kind == "on_chat_model_stream":` | We filter the massive firehose of graph events to target **specifically** the raw text chunks streaming out of the local LLM. Other events like `on_chain_start`, `on_tool_call`, etc. are ignored. |
| `chunk_obj = event.get("data", {}).get("chunk")` | Navigates nested JSON to extract the chunk object from the event. Not every event has this. |
| `getattr(chunk_obj, "content", "")` | **Defensive Shield**: Because nodes might return complex objects (AIMessage, Command, etc.) instead of flat dictionaries, we use `getattr` and `hasattr` to safely attempt extraction without crashing. If the attribute doesn't exist, return `""`. |
| `yield f"data: {...}\n\n"` | **SSE Formatting**: The `data: ` prefix and `\n\n` suffix are **required** by the SSE protocol. They tell the browser that the current packet is complete and should be rendered immediately. |

---

## 4.4 Browser-Side Event Listener

### JavaScript Client

```javascript
// frontend/stream.js
async function streamAgentResponse(userMessage) {
    const response = await fetch('/api/agent/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage, thread_id: 'session_123' })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value);
        const lines = buffer.split('\n');
        buffer = lines.pop();  // Keep incomplete line in buffer

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const json = JSON.parse(line.slice(6));
                console.log(`[${json.node}] ${json.token}`);
                document.getElementById('output').innerText += json.token;
            }
        }
    }
}
```

**Flow:**
1. Browser sends POST request
2. Server starts streaming events
3. Browser's event listener reads each line
4. Parses `data: ` prefix, extracts JSON
5. Updates UI with each token
6. User sees real-time generation ✅

---

## 4.5 Complete Streaming Example

### Server: LangGraph Events

```python
# app/api/routes.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    thread_id: str

@router.post("/agent/stream")
async def chat_stream(request: ChatRequest):
    """Stream real-time graph execution events to client"""
    
    try:
        # Prepare initial state
        initial_state = {
            "messages": [{"role": "user", "content": request.message}],
            "current_code": "",
            "review_feedback": "",
            "loop_count": 0,
        }
        
        config = {
            "configurable": {"thread_id": request.thread_id}
        }
        
        async def event_generator():
            """Generator yields SSE-formatted events"""
            event_count = 0
            
            try:
                async for event in compiled_team_graph.astream_events(
                    initial_state,
                    config=config,
                    version="v2"
                ):
                    event_count += 1
                    
                    # Categorize events
                    kind = event["event"]
                    metadata = event.get("metadata", {})
                    node_name = metadata.get("langgraph_node", "system")
                    
                    # Emit node lifecycle events
                    if kind == "on_chain_start":
                        yield f"data: {json.dumps({'type': 'node_start', 'node': node_name})}\n\n"
                    
                    elif kind == "on_chain_end":
                        result = event.get("data", {}).get("output")
                        yield f"data: {json.dumps({'type': 'node_end', 'node': node_name, 'output': result})}\n\n"
                    
                    # Emit token streaming events
                    elif kind == "on_chat_model_stream":
                        chunk_obj = event.get("data", {}).get("chunk")
                        if chunk_obj is not None:
                            token = getattr(chunk_obj, "content", "") if hasattr(chunk_obj, "content") else str(chunk_obj)
                            if token:
                                yield f"data: {json.dumps({'type': 'token', 'node': node_name, 'token': token})}\n\n"
                
                # Final completion event
                yield f"data: {json.dumps({'type': 'complete', 'total_events': event_count})}\n\n"
                
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
    
    except Exception as e:
        logger.error(f"Stream setup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### Client: React Component

```typescript
// frontend/AgentStream.tsx
import React, { useState } from 'react';

export function AgentStream() {
    const [output, setOutput] = useState('');
    const [streaming, setStreaming] = useState(false);

    const handleStream = async () => {
        setStreaming(true);
        setOutput('');

        try {
            const response = await fetch('/api/agent/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: 'Generate a fibonacci function',
                    thread_id: 'user_123'
                })
            });

            if (!response.ok) throw new Error('Stream failed');

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (reader) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const event = JSON.parse(line.slice(6));
                            
                            if (event.type === 'node_start') {
                                setOutput(prev => prev + `\n[${event.node}] Starting...\n`);
                            } else if (event.type === 'token') {
                                setOutput(prev => prev + event.token);
                            } else if (event.type === 'node_end') {
                                setOutput(prev => prev + `\n[${event.node}] Completed\n`);
                            }
                        } catch (e) {
                            console.error('Parse error:', e);
                        }
                    }
                }
            }
        } finally {
            setStreaming(false);
        }
    };

    return (
        <div>
            <button onClick={handleStream} disabled={streaming}>
                {streaming ? 'Streaming...' : 'Start Stream'}
            </button>
            <pre>{output}</pre>
        </div>
    );
}
```

---

## 4.6 Event Types in astream_events

### Common LangGraph Events

| Event Type | Meaning | Use Case |
|------------|---------|----------|
| `on_chain_start` | Node execution begins | Show "Generating..." UI |
| `on_chain_end` | Node execution completes | Show node result, log time |
| `on_chat_model_stream` | LLM token generated | Display token in real-time |
| `on_tool_call` | Tool execution started | Log tool usage |
| `on_tool_end` | Tool execution completed | Log tool result |
| `on_chain_stream` | Streaming output | Alternative token stream |

### Filtering Events

```python
async for event in compiled_graph.astream_events(..., version="v2"):
    kind = event["event"]
    
    # Show only LLM streaming
    if kind == "on_chat_model_stream":
        process_token(event)
    
    # Show all state updates
    elif kind == "on_state_updated":
        state = event.get("data", {}).get("values")
        print(f"State updated: {state}")
    
    # Show node boundaries
    elif kind in ("on_chain_start", "on_chain_end"):
        print(f"{kind}: {event['metadata']['langgraph_node']}")
```

---

## 4.7 Error Handling in Streams

### Graceful Error Recovery

```python
async def event_generator():
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            async for event in compiled_graph.astream_events(...):
                yield f"data: {json.dumps(event)}\n\n"
            
            # Success
            break
        
        except Exception as e:
            retry_count += 1
            if retry_count < max_retries:
                yield f"data: {json.dumps({'type': 'error', 'retrying': True})}\n\n"
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
            else:
                yield f"data: {json.dumps({'type': 'error', 'fatal': True, 'message': str(e)})}\n\n"
```

---

## Student Comprehension Check

### Question 1: SSE vs. Traditional APIs
**Q: Why must the yield statement end with `\n\n`?**

**A:** It is a requirement of the Server-Sent Events (SSE) network protocol. The double newline acts as a frame terminator, telling the receiving browser client that the current data packet is complete and should be rendered immediately rather than buffered for more data.

### Question 2: Defensive Shield
**Q: Why do we need the "Defensive Shield" (getattr) when processing stream events?**

**A:** Because the `astream_events` listener catches everything flowing through the graph. Sometimes a node passes a complex Python object (like an `AIMessage` class or `Command` object) rather than a simple dictionary. If we try to blindly call `.get()` or access `.content` on a class object, the server will crash with an `AttributeError`. Using `getattr` with a default value allows safe extraction.

### Question 3: Streaming vs. Invoke
**Q: What's the key difference between `.invoke()` and `.astream_events()`?**

**A:** `.invoke()` **blocks** until the entire graph execution completes, then returns the final result. `.astream_events()` **non-blocking** and emits events as they happen. With `.invoke()`, the browser waits 45 seconds with no feedback. With `.astream_events()`, the browser gets real-time updates every millisecond.

### Question 4: Event Filtering
**Q: Why do we filter for `on_chat_model_stream` instead of emitting all events?**

**A:** The `astream_events` firehose emits hundreds of events per second (node starts, tool calls, state updates, etc.). Emitting all of them would flood the network and browser with unnecessary data. By filtering for `on_chat_model_stream`, we capture only the text tokens being generated by the LLM, which is what users care about seeing in real-time.

---

## Key Takeaways

✅ **Server-Sent Events** enable real-time UI updates without blocking  
✅ **astream_events** hooks into the graph execution engine for live telemetry  
✅ **Token streaming** creates the "typing out loud" UX like ChatGPT  
✅ **Event filtering** optimizes network bandwidth and browser performance  
✅ **Error recovery** gracefully handles streaming interruptions  

---

## Additional Resources

- [FastAPI StreamingResponse Documentation](https://fastapi.tiangolo.com/advanced/streaming-responses/)
- [Server-Sent Events (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [LangGraph astream_events](https://langchain-ai.github.io/langgraph/)

---

**Complete Course:** [Building Local AI Architectures](Home)
