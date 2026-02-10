# 架构设计

## 整体架构

JoySafeter 采用分层架构模式，各层职责清晰：

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

### 核心模块

#### 1. 图构建系统

图构建系统采用工厂模式，根据图配置自动选择合适的构建器：

```mermaid
flowchart LR
    Config[图配置] --> Factory[GraphBuilder 工厂]
    Factory -->|标准节点| LangBuilder[LanggraphModelBuilder]
    Factory -->|useDeepAgents=True| DeepBuilder[DeepAgentsBuilder]

    LangBuilder --> BaseBuilder[BaseGraphBuilder]
    DeepBuilder --> BaseBuilder

    BaseBuilder --> Executors[节点执行器]
    BaseBuilder --> State[GraphState]

    Executors --> LangGraph[LangGraph Runtime]
    State --> LangGraph

    style Factory fill:#e1f5ff
    style LangBuilder fill:#fff3e0
    style DeepBuilder fill:#e8f5e8
    style BaseBuilder fill:#f3e5f5
```

**核心组件：**
- **GraphBuilder**: 工厂类，自动检测配置并选择构建器
- **LanggraphModelBuilder**: 构建标准 LangGraph 工作流，支持 11 种节点类型
- **DeepAgentsGraphBuilder**: 构建 Manager-Worker 星型拓扑，实现多智能体协作
- **BaseGraphBuilder**: 基础类，提供通用功能（节点/边管理、执行器创建）

#### 2. DeepAgents 多智能体编排

DeepAgents 实现星型拓扑，一个 Manager 协调多个 Worker：

```mermaid
flowchart TB
    Manager[Manager Agent<br/>useDeepAgents=True<br/>DeepAgent]

    Manager -->|task| Worker1[Worker 1<br/>CompiledSubAgent]
    Manager -->|task| Worker2[Worker 2<br/>CompiledSubAgent]
    Manager -->|task| Worker3[Worker 3<br/>CompiledSubAgent]
    Manager -->|task| CodeAgent[CodeAgent<br/>CompiledSubAgent]

    subgraph Backend["共享 Docker 后端"]
        Skills["/workspace/skills/<br/>预加载技能"]
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

**特性：**
- **星型拓扑**: Manager 直接连接到所有 SubAgents（非链式）
- **共享后端**: Docker 后端在多个 Agent 间共享，用于技能和代码执行
- **技能预加载**: 执行前将技能加载到 `/workspace/skills/`
- **任务委托**: Manager 使用 `task()` 工具将工作委托给 SubAgents

#### 3. 技能系统（渐进式披露）

技能系统实现渐进式披露，减少 Token 消耗：

```mermaid
sequenceDiagram
    participant Node as Agent 节点
    participant Middleware as SkillsMiddleware
    participant Loader as SkillSandboxLoader
    participant Backend as Docker 后端
    participant Filesystem as FilesystemMiddleware

    Node->>Middleware: 节点配置（技能 UUIDs）
    Middleware->>Loader: 预加载技能
    Loader->>Backend: 写入技能文件到 /workspace/skills/
    Backend-->>Loader: 技能已加载
    Loader-->>Middleware: 预加载完成

    Middleware->>Node: 注入技能摘要到系统提示
    Node->>Node: Agent 仅看到技能摘要

    Node->>Filesystem: Agent 读取 /workspace/skills/{skill_name}/SKILL.md
    Filesystem-->>Node: Agent 获得技能内容
```

**组件：**
- **SkillService**: CRUD 操作，权限控制，标签分类
- **SkillsMiddleware**: 自动将技能描述注入到系统提示中
- **SkillSandboxLoader**: 执行前将技能预加载到 Docker 后端
- **FilesystemMiddleware**: Agent 通过文件系统直接读取 `/workspace/skills/{skill_name}/` 目录下的技能文件（技能由 SkillSandboxLoader 在执行前预加载）

#### 4. 记忆系统（长短期记忆）

记忆系统提供跨会话的持久化记忆：

```mermaid
sequenceDiagram
    participant User as 用户输入
    participant Middleware as MemoryMiddleware
    participant Manager as MemoryManager
    participant DB as PostgreSQL
    participant Agent as Agent

    User->>Middleware: 用户消息
    Middleware->>Manager: 检索相关记忆
    Manager->>DB: 按 user_id/topics 查询记忆
    DB-->>Manager: 返回记忆
    Manager-->>Middleware: 相关记忆
    Middleware->>Agent: 注入记忆到系统提示
    Agent->>Agent: 带上下文处理
    Agent-->>User: 响应

    User->>Middleware: 用户输入（after_model）
    Middleware->>Manager: 存储/更新记忆
    Manager->>DB: 持久化记忆
```

**记忆类型：**
- **Fact（事实）**: 事实性知识（目标信息、漏洞）
- **Procedure（过程）**: 过程性知识（成功的攻击路径）
- **Episodic（情景）**: 会话特定的经验
- **Semantic（语义）**: 通用安全知识

#### 5. 中间件架构

使用策略模式的可扩展中间件系统：

```mermaid
flowchart TB
    Node[节点配置] --> Resolver[中间件解析器<br/>策略模式]

    Resolver --> SkillMW[SkillMiddleware<br/>优先级: 50]
    Resolver --> MemoryMW[MemoryMiddleware<br/>优先级: 50]
    Resolver --> TagMW[TaggingMiddleware<br/>优先级: 100]
    Resolver --> CustomMW[自定义中间件<br/>可扩展]

    SkillMW --> Merge[合并并按优先级排序]
    MemoryMW --> Merge
    TagMW --> Merge
    CustomMW --> Merge

    Merge --> Agent[带中间件链的 Agent]

    style Resolver fill:#e1f5ff
    style Merge fill:#fff3e0
    style Agent fill:#e8f5e8
```

**特性：**
- **策略模式**: 易于添加新的中间件类型
- **优先级系统**: 按优先级顺序执行中间件
- **错误隔离**: 失败的中间件不会影响其他中间件
- **向后兼容**: 新功能不影响现有代码

#### 6. 节点执行器（11 种类型）

| 分类 | 节点类型 | 说明 |
|------|----------|------|
| **智能体** | `agent`, `llm_node` | LLM 驱动的推理节点，支持工具调用 |
| **控制流** | `condition`, `router_node`, `loop_condition_node` | 条件分支、多路由、循环迭代 |
| **动作** | `tool_node`, `function_node`, `http_request_node` | 工具执行、沙箱代码、HTTP 请求 |
| **数据** | `json_parser_node`, `direct_reply` | JSON 解析、模板响应 |
| **聚合** | `aggregator_node` | 并行结果收集 |

### 核心流程

#### 图构建流程

```mermaid
sequenceDiagram
    participant Frontend as 前端
    participant API as REST API
    participant Factory as GraphBuilder
    participant Builder as LanggraphModelBuilder/DeepAgentsBuilder
    participant Base as BaseGraphBuilder
    participant Executors as 节点执行器
    participant Runtime as LangGraph Runtime

    Frontend->>API: 保存图（nodes, edges, variables）
    API->>Factory: build(graph, nodes, edges)
    Factory->>Factory: 检测 useDeepAgents
    Factory->>Builder: 创建合适的构建器
    Builder->>Base: 初始化基础构建器
    Builder->>Executors: 创建节点执行器
    Builder->>Runtime: 添加节点到 StateGraph
    Builder->>Runtime: 添加边（条件/普通）
    Builder->>Runtime: 编译图
    Runtime-->>Builder: CompiledStateGraph
    Builder-->>API: 编译后的图
    API-->>Frontend: 图已保存
```

#### 图执行流程

```mermaid
sequenceDiagram
    participant Frontend as 前端
    participant API as REST API
    participant Service as GraphService
    participant Builder as GraphBuilder
    participant Runtime as LangGraph Runtime
    participant Executors as 节点执行器
    participant SSE as SSE 流式输出

    Frontend->>API: POST /api/chat (SSE)
    API->>Service: 加载图配置
    Service->>Builder: 构建编译后的图
    Builder-->>Service: CompiledStateGraph
    Service->>Runtime: ainvoke({"messages": [...]})

    loop 每个节点
        Runtime->>Executors: 执行节点
        Executors-->>Runtime: 更新状态
        Runtime->>SSE: 推送事件（node_start/node_end）
        SSE-->>Frontend: 流式更新
    end

    Runtime-->>Service: 最终结果
    Service-->>SSE: 结束事件
    SSE-->>Frontend: 流式输出完成
```

#### DeepAgents 执行流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant Manager as Manager Agent
    participant Backend as 共享后端
    participant Worker1 as Worker 1
    participant Worker2 as Worker 2

    User->>Manager: 任务请求
    Manager->>Manager: 分析任务
    Manager->>Backend: 检查预加载技能
    Manager->>Worker1: task("子任务 1")
    Worker1->>Backend: 使用技能/代码执行
    Backend-->>Worker1: 结果
    Worker1-->>Manager: 子任务 1 结果

    Manager->>Worker2: task("子任务 2")
    Worker2->>Backend: 使用技能/代码执行
    Backend-->>Worker2: 结果
    Worker2-->>Manager: 子任务 2 结果

    Manager->>Manager: 整合结果
    Manager-->>User: 最终响应
```

### 数据流

**前端 ↔ 后端：**
- **REST API**: 图配置、技能管理、工具管理、工作区操作
- **SSE 流式输出**: 实时执行状态、流式输出、节点执行事件

**后端内部：**
- **GraphBuilder → NodeExecutors → LangGraph Runtime**: 图构建和执行
- **LangGraph Runtime → MCP Servers → Tools**: 工具调用和执行
- **Middleware → Agent → Model**: 请求处理管道

**后端 ↔ 数据层：**
- **PostgreSQL**: 图配置、技能、记忆、会话、工作区
- **Redis**: 缓存、限流、会话状态、临时数据
