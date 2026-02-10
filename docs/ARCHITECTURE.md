# Architecture

## Overall Architecture

JoySafeter follows a layered architecture pattern with clear separation of concerns:

```mermaid
flowchart TB
    subgraph Row1[" "]
        direction LR

        subgraph Frontend["Frontend Layer (Next.js 16 + React 19)"]
            direction TB
            UI["Visual Builder<br/>ReactFlow"]
            Trace["Execution Trace<br/>SSE Stream"]
            Workspace["Workspace Manager<br/>RBAC"]
            Copilot["Copilot AI<br/>Graph Assistant"]
        end

        subgraph API["API Layer (FastAPI)"]
            direction TB
            REST["REST APIs<br/>Auth/Graphs/Chat/Skills"]
            SSE["SSE Stream<br/>Real-time Events"]
        end

        subgraph Services["Service Layer"]
            direction TB
            GraphSvc["GraphService"]
            SkillSvc["SkillService"]
            MemorySvc["MemoryService"]
            McpSvc["McpClient<br/>Service"]
            ToolSvc["ToolService"]
        end

        subgraph Engine["Core Engine"]
            direction TB
            Builder["GraphBuilder<br/>Factory Pattern"]
            LangBuilder["LanggraphModel<br/>Builder<br/>Standard Workflows"]
            DeepBuilder["DeepAgents<br/>Builder<br/>Multi-Agent"]
            Executors["Node Executors<br/>11 Types"]
            Middleware["Middleware System<br/>Extensible"]
            SkillSys["Skill System<br/>Progressive Disclosure"]
            MemorySys["Memory System<br/>Long/Short-term"]
        end
    end

    subgraph Row2[" "]
        direction LR

        subgraph Runtime["Runtime Layer"]
            direction TB
            LangGraph["LangGraph Runtime<br/>StateGraph"]
            Checkpoint["Checkpointer<br/>State Persistence"]
        end

        subgraph Data["Data Layer"]
            direction TB
            PG["(PostgreSQL<br/>Graphs/Skills/Memories)"]
            Redis["(Redis<br/>Cache/Rate Limit)"]
        end

        subgraph MCP["MCP Tool Ecosystem"]
            direction TB
            MCPServers["MCP Servers<br/>200+ Security Tools"]
            Tools["Tool Registry<br/>Unified Management"]
        end
    end

    UI --> REST
    Trace --> SSE
    Workspace --> REST
    Copilot --> REST

    REST --> Services
    SSE --> Services

    Services --> Engine
    Engine --> Runtime
    Runtime --> Data
    Runtime --> MCP

    MCPServers --> Tools

    style Row1 fill:transparent,stroke:transparent
    style Row2 fill:transparent,stroke:transparent

    style Frontend fill:#e1f5ff
    style API fill:#f3e5f5
    style Services fill:#fff3e0
    style Engine fill:#e8f5e8
    style Runtime fill:#fff8e1
    style Data fill:#fce4ec
    style MCP fill:#e0f2f1

```

### Core Modules

#### 1. Graph Builder System

The graph builder system uses a factory pattern to automatically select the appropriate builder based on graph configuration:

```mermaid
flowchart LR
    Config[Graph Config] --> Factory[GraphBuilder Factory]
    Factory -->|Standard Nodes| LangBuilder[LanggraphModelBuilder]
    Factory -->|useDeepAgents=True| DeepBuilder[DeepAgentsBuilder]

    LangBuilder --> BaseBuilder[BaseGraphBuilder]
    DeepBuilder --> BaseBuilder

    BaseBuilder --> Executors[Node Executors]
    BaseBuilder --> State[GraphState]

    Executors --> LangGraph[LangGraph Runtime]
    State --> LangGraph

    style Factory fill:#e1f5ff
    style LangBuilder fill:#fff3e0
    style DeepBuilder fill:#e8f5e8
    style BaseBuilder fill:#f3e5f5
```

**Key Components:**
- **GraphBuilder**: Factory class that auto-detects configuration and selects builder
- **LanggraphModelBuilder**: Builds standard LangGraph workflows with 11 node types
- **DeepAgentsGraphBuilder**: Builds Manager-Worker star topology for multi-agent collaboration
- **BaseGraphBuilder**: Base class providing common functionality (node/edge management, executor creation)

#### 2. DeepAgents Multi-Agent Orchestration

DeepAgents implements a star topology with one Manager coordinating multiple Workers:

```mermaid
flowchart TB
    Manager[Manager Agent<br/>useDeepAgents=True<br/>DeepAgent]

    Manager -->|task| Worker1[Worker 1<br/>CompiledSubAgent]
    Manager -->|task| Worker2[Worker 2<br/>CompiledSubAgent]
    Manager -->|task| Worker3[Worker 3<br/>CompiledSubAgent]
    Manager -->|task| CodeAgent[CodeAgent<br/>CompiledSubAgent]

    subgraph Backend["Shared Docker Backend"]
        Skills["/workspace/skills/<br/>Pre-loaded Skills"]
    end

    Worker1 --> Backend
    Worker2 --> Backend
    Worker3 --> Backend
    CodeAgent --> Backend

    style Manager fill:#e1f5ff
    style Worker1 fill:#fff4e1
    style Worker2 fill:#fff4e1
    style Worker3 fill:#fff4e1
    style CodeAgent fill:#fff4e1
    style Backend fill:#e8f5e8
```

**Features:**
- **Star Topology**: Manager connects directly to all SubAgents (not chain)
- **Shared Backend**: Docker backend shared across agents for skills and code execution
- **Skill Preloading**: Skills loaded to `/workspace/skills/` before execution
- **Task Delegation**: Manager uses `task()` tool to delegate work to SubAgents

#### 3. Skill System (Progressive Disclosure)

The skill system implements progressive disclosure to reduce token consumption:

```mermaid
sequenceDiagram
    participant Node as Agent Node
    participant Middleware as SkillsMiddleware
    participant Loader as SkillSandboxLoader
    participant Backend as Docker Backend
    participant Filesystem as FilesystemMiddleware

    Node->>Middleware: Node config with skill UUIDs
    Middleware->>Loader: Preload skills
    Loader->>Backend: Write skill files to /workspace/skills/
    Backend-->>Loader: Skills loaded
    Loader-->>Middleware: Preload complete

    Middleware->>Node: Inject skill summaries in system prompt
    Node->>Node: Agent sees skill summaries only

    Node->>Filesystem: Agent reads /workspace/skills/{skill_name}/SKILL.md
    Filesystem-->>Node: Agent receives skill content
```

**Components:**
- **SkillService**: CRUD operations with permission control
- **SkillsMiddleware**: Automatically injects skill descriptions into system prompts
- **SkillSandboxLoader**: Preloads skills to Docker backend before execution
- **FilesystemMiddleware**: Agent directly reads skill files from `/workspace/skills/{skill_name}/` via filesystem access (skills are preloaded by SkillSandboxLoader before execution)

#### 4. Memory System (Long/Short-term Memory)

The memory system provides persistent memory across sessions:

```mermaid
sequenceDiagram
    participant User as User Input
    participant Middleware as MemoryMiddleware
    participant Manager as MemoryManager
    participant DB as PostgreSQL
    participant Agent as Agent

    User->>Middleware: User message
    Middleware->>Manager: Retrieve relevant memories
    Manager->>DB: Query memories by user_id/topics
    DB-->>Manager: Return memories
    Manager-->>Middleware: Relevant memories
    Middleware->>Agent: Inject memories in system prompt
    Agent->>Agent: Process with context
    Agent-->>User: Response

    User->>Middleware: User input (after_model)
    Middleware->>Manager: Store/update memory
    Manager->>DB: Persist memory
```

**Memory Types:**
- **Fact**: Factual knowledge (target info, vulnerabilities)
- **Procedure**: Procedural knowledge (successful attack paths)
- **Episodic**: Session-specific experiences
- **Semantic**: General security knowledge

#### 5. Middleware Architecture

Extensible middleware system using strategy pattern:

```mermaid
flowchart TB
    Node[Node Config] --> Resolver[Middleware Resolver<br/>Strategy Pattern]

    Resolver --> SkillMW[SkillMiddleware<br/>Priority: 50]
    Resolver --> MemoryMW[MemoryMiddleware<br/>Priority: 50]
    Resolver --> TagMW[TaggingMiddleware<br/>Priority: 100]
    Resolver --> CustomMW[Custom Middleware<br/>Extensible]

    SkillMW --> Merge[Merge & Sort by Priority]
    MemoryMW --> Merge
    TagMW --> Merge
    CustomMW --> Merge

    Merge --> Agent[Agent with Middleware Chain]

    style Resolver fill:#e1f5ff
    style Merge fill:#fff3e0
    style Agent fill:#e8f5e8
```

**Features:**
- **Strategy Pattern**: Easy to add new middleware types
- **Priority System**: Middleware executed in priority order
- **Error Isolation**: Failed middleware doesn't break others
- **Backward Compatible**: New features don't affect existing code

#### 6. Node Executors (11 Types)

| Category | Node Types | Description |
|----------|------------|-------------|
| **Agent** | `agent`, `llm_node` | LLM-powered reasoning with tool access |
| **Control Flow** | `condition`, `router_node`, `loop_condition_node` | Conditional branching, multi-path routing, iteration |
| **Actions** | `tool_node`, `function_node`, `http_request_node` | Tool execution, sandbox code, HTTP calls |
| **Data** | `json_parser_node`, `direct_reply` | JSON parsing, template responses |
| **Aggregation** | `aggregator_node` | Parallel result collection |

### Core Workflows

#### Graph Building Flow

```mermaid
sequenceDiagram
    participant Frontend as Frontend
    participant API as REST API
    participant Factory as GraphBuilder
    participant Builder as LanggraphModelBuilder/DeepAgentsBuilder
    participant Base as BaseGraphBuilder
    participant Executors as Node Executors
    participant Runtime as LangGraph Runtime

    Frontend->>API: Save graph (nodes, edges, variables)
    API->>Factory: build(graph, nodes, edges)
    Factory->>Factory: Detect useDeepAgents
    Factory->>Builder: Create appropriate builder
    Builder->>Base: Initialize base builder
    Builder->>Executors: Create node executors
    Builder->>Runtime: Add nodes to StateGraph
    Builder->>Runtime: Add edges (conditional/normal)
    Builder->>Runtime: Compile graph
    Runtime-->>Builder: CompiledStateGraph
    Builder-->>API: Compiled graph
    API-->>Frontend: Graph saved
```

#### Graph Execution Flow

```mermaid
sequenceDiagram
    participant Frontend as Frontend
    participant API as REST API
    participant Service as GraphService
    participant Builder as GraphBuilder
    participant Runtime as LangGraph Runtime
    participant Executors as Node Executors
    participant SSE as SSE Stream

    Frontend->>API: POST /api/chat (SSE)
    API->>Service: Load graph config
    Service->>Builder: Build compiled graph
    Builder-->>Service: CompiledStateGraph
    Service->>Runtime: ainvoke({"messages": [...]})

    loop Each Node
        Runtime->>Executors: Execute node
        Executors-->>Runtime: Update state
        Runtime->>SSE: Push event (node_start/node_end)
        SSE-->>Frontend: Stream update
    end

    Runtime-->>Service: Final result
    Service-->>SSE: End event
    SSE-->>Frontend: Stream complete
```

#### DeepAgents Execution Flow

```mermaid
sequenceDiagram
    participant User as User
    participant Manager as Manager Agent
    participant Backend as Shared Backend
    participant Worker1 as Worker 1
    participant Worker2 as Worker 2

    User->>Manager: Task request
    Manager->>Manager: Analyze task
    Manager->>Backend: Check preloaded skills
    Manager->>Worker1: task("Sub-task 1")
    Worker1->>Backend: Use skills/code execution
    Backend-->>Worker1: Results
    Worker1-->>Manager: Sub-task 1 result

    Manager->>Worker2: task("Sub-task 2")
    Worker2->>Backend: Use skills/code execution
    Backend-->>Worker2: Results
    Worker2-->>Manager: Sub-task 2 result

    Manager->>Manager: Synthesize results
    Manager-->>User: Final response
```

### Data Flow

**Frontend ↔ Backend:**
- **REST API**: Graph configuration, skill management, tool management, workspace operations
- **SSE Stream**: Real-time execution status, streaming output, node execution events

**Backend Internal:**
- **GraphBuilder → NodeExecutors → LangGraph Runtime**: Graph construction and execution
- **LangGraph Runtime → MCP Servers → Tools**: Tool invocation and execution
- **Middleware → Agent → Model**: Request processing pipeline

**Backend ↔ Data Layer:**
- **PostgreSQL**: Graph configurations, skills, memories, sessions, workspaces
- **Redis**: Cache, rate limiting, session state, temporary data
