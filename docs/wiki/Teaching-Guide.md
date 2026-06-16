# Teaching Guide & Instructor Resources

## Overview

This guide provides instructors with frameworks, discussion prompts, and assessment strategies for teaching the Building Local AI Architectures course.

---

## Course Structure

### Duration
- **Full Course**: 8-12 weeks (40-60 hours)
- **Intensive**: 2 weeks (full-time immersion)
- **Self-paced**: 12-16 weeks

### Level
- **Prerequisites**: Python basics, familiarity with APIs
- **Target Audience**: Junior engineers, bootcamp graduates, self-taught developers
- **Not Required**: ML theory, deep learning knowledge, Linux expertise

---

## Chapter-by-Chapter Teaching Strategy

## Chapter 1: Infrastructure Foundation (Docker & FastAPI)

### Learning Objectives
- [ ] Understand why containerization solves dependency conflicts
- [ ] Explain the difference between Compute and Orchestration layers
- [ ] Configure docker-compose for local LLM workloads
- [ ] Troubleshoot timeout issues in production

### Teaching Approach

**Week 1: Conceptual**
1. Start with a failure scenario: "Your colleague's code works on their Mac but crashes on your Linux machine"
2. Explain containerization as a "shipping container for code"
3. Show docker-compose.yml line-by-line with analogies:
   - `ports: "8000:8000"` = "postcode mapping"
   - `volumes:` = "portable storage"
   - `timeout-keep-alive 120` = "patience for slow workers"

**Week 1: Hands-on**
1. Have students build the Dockerfile from scratch
2. Show breaking it (remove timeout) and fixing it (add back timeout)
3. Deploy to two different machines and verify reproducibility

### Discussion Questions

1. **Why not just pip install everything locally?**
   - Answer: Dependency conflicts, version mismatches, OS-specific binaries, "works on my machine" syndrome

2. **What happens if we set timeout-keep-alive to 30?**
   - Answer: Local LLM inference (~45s) exceeds timeout, connection drops mid-generation

3. **Could we use Kubernetes instead of Docker Compose?**
   - Answer: Yes, but overkill for single-machine setups. Kubernetes for multi-node orchestration.

### Assessment

**Activity 1: Dockerfile Modification**
- Start with broken Dockerfile (missing timeout)
- Students fix it and deploy
- Success metric: API responds to requests without timeout

**Activity 2: Multi-Machine Setup**
- Have students push image to Docker Hub
- Pull on a different machine
- Verify identical behavior (reproducibility checkpoint)

**Activity 3: Debugging Practice**
- Provide docker-compose.yml with 3 intentional errors
- Students identify and fix each (missing port mapping, volume mismatch, etc.)

---

## Chapter 2: State Machines & Checkpointing

### Learning Objectives
- [ ] Design TypedDict state schemas for complex workflows
- [ ] Understand why checkpointing prevents data loss
- [ ] Implement fault tolerance in multi-step processes
- [ ] Debug state transitions using checkpoint history

### Teaching Approach

**Week 2: Conceptual**
1. Analogy: "State machine = conversation between coworkers"
   - Each person (node) reads the current clipboard (state)
   - Does their job
   - Updates the clipboard
   - Passes to next person
2. Checkpointing = "photograph the clipboard after every handoff"

**Week 2: Hands-on**
1. Have students write state schema by hand first (on whiteboard)
2. Translate to TypedDict
3. Build graph incrementally (add one node at a time)
4. Test with manual checkpoint inspection

### Discussion Questions

1. **What's the difference between state and state history?**
   - Answer: State = current clipboard. History = all previous photos of the clipboard.

2. **Why `Annotated[list, operator.add]` instead of just `list`?**
   - Answer: Without it, a node returning `{"messages": [x]}` overwrites the entire history. With `operator.add`, it appends.

3. **When would you use MemorySaver vs SqliteSaver?**
   - Answer: MemorySaver for dev/testing (RAM). SqliteSaver for production on single machines. PostgresSaver for distributed systems.

### Assessment

**Activity 1: Schema Design**
- Given a workflow description, students design TypedDict
- Example: "AI generates code, reviews it, debugs errors"
- States must include: code, review_feedback, error_log, iteration_count

**Activity 2: Checkpoint Inspection**
- Students run a graph, intentionally crash it mid-execution
- Query checkpoint history
- Resume from last checkpoint (verify state is intact)

**Activity 3: Time-Travel Debugging**
- Show students how to resume from intermediate checkpoints
- "What was the state after step 2?"
- Use this to debug incorrect decisions

---

## Chapter 3: Peer-to-Peer Networks

### Learning Objectives
- [ ] Explain why centralized supervisors cause context dilution
- [ ] Design P2P routing using Command primitives
- [ ] Implement conditional routing (loops, branches)
- [ ] Calculate token cost savings vs. centralized approach

### Teaching Approach

**Week 3: Conceptual**
1. **Show the problem**: Centralized manager reading all worker outputs
   - Analogy: "CEO reading 10 department reports before every decision"
   - Result: CEO forgets details (Lost in the Middle)
2. **Show the solution**: Workers pass baton directly
   - Analogy: "Assembly line where each worker hands to the next"
   - Result: Each worker focused, no bottleneck

**Week 3: Hands-on**
1. Have students trace execution manually on paper (P2P workflow diagram)
2. Implement simple Coder → Reviewer loop
3. Add conditional routing (approved vs. needs revision)
4. Measure token costs before/after

### Discussion Questions

1. **What happens if a node sends to a non-existent node?**
   - Answer: LangGraph will error (raise KeyError). That's why Command is better than string magic.

2. **How do we prevent infinite loops (Coder ↔ Reviewer forever)?**
   - Answer: Iteration counters, max-loop limits, or change detection.

3. **Can nodes send to multiple peers in parallel?**
   - Answer: Not with Command primitives. Those are strictly sequential. For parallel, use separate Command branches or sub-graphs.

### Assessment

**Activity 1: Trace Execution**
- Provide P2P workflow + 5 intermediate state snapshots
- Students sequence them correctly
- Verify understanding of routing

**Activity 2: Build Conditional Router**
- Students implement reviewer that routes: approved → END, rejected → Coder
- Add max_iterations limit
- Test with different scenarios (quick approval, multiple revisions)

**Activity 3: Token Cost Calculator**
- Show token count for centralized manager prompt (all worker outputs)
- Show token count for P2P (only focused prompts per node)
- Calculate cost savings: `savings = (centralized_tokens - p2p_tokens) * token_price`

---

## Chapter 4: Real-Time Event Streaming

### Learning Objectives
- [ ] Understand SSE protocol and why it enables real-time UI
- [ ] Implement async generators for non-blocking streams
- [ ] Debug streaming issues (buffering, timeouts, partial data)
- [ ] Build browser clients to consume SSE streams

### Teaching Approach

**Week 4: Conceptual**
1. **Show the problem**: Synchronous blocking
   - Browser waits 45 seconds with spinning wheel
   - No feedback = user thinks it crashed
2. **Show the solution**: Event streaming
   - Browser gets updates every 100ms
   - Progress bar updates in real-time
   - "Typing out loud" like ChatGPT

**Week 4: Hands-on**
1. Implement streaming route step-by-step
2. Build simple HTML client to consume events
3. Debug common issues (missing `\n\n`, buffering, partial JSON)
4. Upgrade to React component

### Discussion Questions

1. **Why must SSE events end with `\n\n`?**
   - Answer: SSE protocol spec. Double newline = frame terminator.

2. **What happens if we forget the `data: ` prefix?**
   - Answer: Browser won't parse the event. Will look for that prefix.

3. **Could we use WebSockets instead of SSE?**
   - Answer: Yes, but SSE is simpler (built on HTTP). WebSockets for bidirectional comms.

### Assessment

**Activity 1: Streaming Route**
- Students implement `/stream` endpoint
- Must emit at least 3 event types (start, token, end)
- Must properly format with `\n\n`

**Activity 2: HTML Client**
- Students build basic HTML + JavaScript to consume stream
- Display tokens in real-time (update DOM)
- Handle disconnection gracefully

**Activity 3: Debug Scenario**
- Provide broken streaming code (common mistakes):
  - Missing `\n\n`
  - Wrong media type
  - Synchronous `.invoke()` instead of async `.astream_events()`
- Students identify and fix

---

## Integration Project: Full Multi-Agent System

### Project Scope

Students build a complete system combining all 4 chapters:

1. **Chapter 1 (Infrastructure)**: Docker + FastAPI
2. **Chapter 2 (State)**: Checkpointing + fault recovery
3. **Chapter 3 (P2P)**: Multi-agent workflow
4. **Chapter 4 (Streaming)**: Real-time UI

### Project Requirements

**Backend**
- [ ] 3+ agents (Coder, Reviewer, Debugger)
- [ ] TypedDict state schema with all fields
- [ ] SqliteSaver checkpointing
- [ ] P2P routing with Command primitives
- [ ] `/stream` endpoint with SSE events
- [ ] Error handling + retry logic

**Frontend**
- [ ] React component consuming SSE stream
- [ ] Real-time token display
- [ ] Node lifecycle visualization
- [ ] Checkpoint history browser
- [ ] Error recovery UI

**DevOps**
- [ ] docker-compose.yml with proper timeouts
- [ ] .env configuration
- [ ] Volume persistence
- [ ] Logging + monitoring

### Grading Rubric

| Component | Points | Criteria |
|-----------|--------|----------|
| **Architecture** | 20 | Proper separation of concerns, Docker usage, async patterns |
| **State Machine** | 20 | Correct TypedDict, checkpointing works, state persists |
| **P2P Routing** | 20 | Nodes route correctly, conditional logic works, no infinite loops |
| **Streaming** | 20 | SSE format correct, tokens stream in real-time, no buffering issues |
| **Error Handling** | 10 | Graceful failures, retry logic, informative errors |
| **Documentation** | 10 | Code comments, README, inline explanations |

### Example Projects

**Beginner**: Code generation + single-pass review
**Intermediate**: Code → Lint → Unit Test → Document pipeline
**Advanced**: Multi-language transpiler with refactoring agent

---

## Discussion Prompts for Each Chapter

### Chapter 1
- How would you handle a GPU machine in a different data center?
- What if LM Studio takes 2+ minutes for complex reasoning?
- How do you monitor container health in production?

### Chapter 2
- What's the minimum viable state schema?
- How long should you keep checkpoint history?
- Could you use this for conversational AI (multi-turn chat)?

### Chapter 3
- What if an agent needs to query multiple peers?
- How do you handle agent versioning?
- Can you add new agents to a running system?

### Chapter 4
- How do you handle network interruptions mid-stream?
- What if the LLM crashes while streaming?
- How would you implement live progress percentage?

---

## Common Misconceptions

### Misconception 1
**"Containerization means my code runs faster"**
- Reality: Containers have minimal overhead (~5%). They solve reproducibility, not speed.

### Misconception 2
**"Checkpointing saves automatically without my involvement"**
- Reality: You must attach checkpointer at compile time AND use proper thread_id.

### Misconception 3
**"P2P means all agents are equal and autonomous"**
- Reality: P2P still requires explicit routing via Command. Nodes don't self-organize.

### Misconception 4
**"SSE replaces WebSockets"**
- Reality: SSE is one-way (server → client). WebSockets are bidirectional. Choose based on needs.

---

## Recommended Reading

- **Docker**: [Docker Official Guide](https://docs.docker.com/get-started/)
- **Async Python**: Luciano Ramalho - "Fluent Python" (Chapter on asyncio)
- **State Machines**: "Designing Data-Intensive Applications" by Martin Kleppmann
- **Streaming**: "Building Microservices" by Sam Newman (Chapter on async communication)

---

## Pacing Guide

### 8-Week Course (Moderate Pace)
- Week 1: Chapter 1 (Docker & FastAPI)
- Week 2: Chapter 2 (State Machines)
- Week 3: Chapter 3 (P2P Networks)
- Week 4: Chapter 4 (Streaming)
- Weeks 5-8: Integration project + presentations

### 12-Week Course (Slow Pace, Deep Dives)
- Weeks 1-2: Chapter 1 (Docker, networking, deployment)
- Weeks 3-4: Chapter 2 (State design, checkpoint strategies)
- Weeks 5-6: Chapter 3 (Multi-agent workflows, orchestration)
- Weeks 7-8: Chapter 4 (Streaming, performance optimization)
- Weeks 9-12: Integration project, case studies, production deployment

### 2-Week Intensive
- Day 1-2: Chapters 1-2 (compressed)
- Day 3-4: Chapters 3-4 (compressed)
- Day 5-10: Integration project
- Day 11: Code reviews & presentations
- Day 12: Q&A, next steps

---

## Feedback & Iteration

### How to Assess Understanding

1. **Concept Checks**: Ask students to explain without code
2. **Live Coding**: Have them build something unseen
3. **Debugging**: Give broken code, ask for fixes
4. **Teaching**: Ask them to explain to a peer

### Common Struggles

- **Async/await confusion**: Spend extra time on this
- **State schema design**: Students over-complicate it
- **Routing logic**: Difficult to debug; use manual traces
- **SSE format**: Off-by-one errors in `\n\n`

### Recommended Interventions

- Pair weaker students with stronger ones
- Provide working reference implementations
- Record live coding sessions for review
- Create debug checklist for common issues

---

## Additional Resources for Students

- Complete code examples in `/examples` directory
- Video walkthroughs of each chapter
- Recorded Q&A sessions
- Troubleshooting Discord channel
- Monthly office hours

---

**Happy teaching! 🎓**
