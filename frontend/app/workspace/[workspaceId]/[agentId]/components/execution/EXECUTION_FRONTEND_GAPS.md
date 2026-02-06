# Execution 前端整体功能：待完善与待整理

基于当前 Execution Panel（Langfuse 风格树 + 时间线 + 详情）与后端 Trace/Observation 的对接情况，整理如下。

---

## 一、待完善（功能与体验）

### 1. 历史 Trace 未接入

- **现状**：后端已提供 `/v1/traces`（列表、详情、observations），前端仅使用**当前会话的 SSE 流**构建 steps/tree，未调用 traces API。
- **缺口**：
  - 无「历史执行列表」：无法按 thread/graph 查看过往 trace。
  - 无「从历史加载某次 trace」：无法点某次执行再在树/时间线/详情中回放。
- **建议**：新增「历史 Trace」入口（如侧栏或 Tab），调用 `GET /v1/traces`、`GET /v1/traces/:id`、`GET /v1/traces/:id/observations`，将返回的 observations 转成与当前 `ExecutionStep` 兼容的结构，复用现有 Tree/Timeline/Detail 展示；若后端返回结构与前端不一致，需在 adapter 层做字段映射。

### 2. 时间线视图未支持搜索

- **现状**：树视图（ExecutionTree）已支持 `searchQuery` 过滤；时间线视图（ExecutionTimelineView）仅用 `treeRoots` 渲染，未接收或应用 `searchQuery`。
- **建议**：时间线视图要么接收 `searchQuery` 并对用于渲染的节点做过滤，要么在无搜索时保持现状，并在 UI 上提示「搜索仅对树视图生效」（若产品接受）。

### 3. Trace 级 Token 汇总未展示

- **现状**：MetadataTab 已按 step 展示 `promptTokens` / `completionTokens` / `totalTokens`；后端 trace 有 `total_tokens` 聚合，前端未展示「本次执行总 token」。
- **建议**：在 Panel 头部或摘要区增加「本次 Trace 总 Token」；若仅做当前流展示、不做历史加载，可先在流结束时从当前 steps 中汇总所有 model_io 的 token 显示；若后续接入历史 trace，则直接使用接口返回的 `total_tokens`。

### 4. 错误与空状态不统一

- **现状**：ExecutionTree 有「Ready to execute」「Waiting for next step…」「No results for "..."」；ExecutionDetailPanel 有「Select a step to inspect payload」、各 Tab 内 EmptyState；流错误会通过 eventAdapter 添加 error step，但无全局「执行失败」横幅或重试入口。
- **建议**：统一「无数据 / 错误」的展示策略（如顶部 banner + 空状态文案），并为流错误提供「重试」或「关闭并清空」的明确操作。

### 5. 国际化未完全覆盖

- **现状**：部分文案已用 `t('workspace.xxx', { defaultValue: '...' })`；ExecutionDetailPanel 内仍有硬编码英文（如 "Thought Output", "Node Output", "Completion Info", "Raw Data", "No output yet", "Select a step to view metadata"）；搜索占位 "Search steps..."、Timeline 的 "Timeline View"、"No results for" 等也未走 i18n。
- **建议**：为上述文案增加 i18n key，并在 `workspace` 命名空间下提供中英文（或当前支持语言）文案。

### 6. 可访问性与键盘

- **现状**：已支持上下键切换选中、`/` 聚焦搜索、Escape 关闭搜索；树节点展开/折叠依赖点击。
- **建议**：如需增强可访问性，可考虑 Enter 展开/折叠当前节点、焦点进入面板时的默认焦点策略、以及树/时间线切换的 Tab 顺序与 ARIA 标注。

### 7. Interrupt / Resume 与当前树的一致性

- **现状**：InterruptPanel 与 resume 流程存在；resume 后新事件会通过同一 store 追加，thread_id 一致。
- **建议**：在「从中断恢复」场景下做一次端到端验证：resume 后新产生的 steps 是否与现有 tree/timeline 正确合并、是否出现重复或错位；若有 edge case，在 eventAdapter 或 store 的「步骤去重/排序」逻辑中补齐。

---

## 二、待整理（代码与结构）

### 1. SSE 事件与前端类型的对应关系

- **现状**：`chatBackend` 的 `StreamEventEnvelope` 与后端 SSE 格式一致；`eventAdapter` 将事件转为 `ExecutionStep` 并注入 `traceId` / `observationId` / `parentObservationId` 等；`tree-building` 根据 `parentObservationId` 或 `nodeId` 建树。
- **建议**：在 `eventAdapter.ts` 或 `lib/tree-building.ts` 顶部用注释维护一份「SSE 事件类型 → 前端 Step 类型 / 树节点类型」的简要映射表，便于后续维护与排查。

### 2. Store 中树计算的触发方式

- **现状**：`executionStore` 在 `syncComputedProperties` 中根据 `steps` 调用 `buildExecutionTree(steps)` 得到 `treeRoots`、`treeNodeMap`，每次 get 会走派生逻辑。
- **建议**：若后续步骤量或订阅方增多，可评估将 `buildExecutionTree` 移到 selector（如 zustand 的 selector 或 useMemo）以减少重复计算；当前若性能无问题可保持现状，仅在文档中注明「tree 由 steps 派生」。

### 3. 空状态组件的复用

- **现状**：ExecutionDetailPanel 内有 `EmptyState`；ExecutionTree 有内联的「Ready to execute」等占位。
- **建议**：若多处空状态样式一致，可抽成共用组件（如 `ExecutionEmptyState`），统一图标、文案和可选的 CTA，便于统一改版与 i18n。

### 4. 类型与文件边界

- **现状**：`@/types` 中 `ExecutionStep` / `ExecutionTreeNode` / `ExecutionTreeFlatItem` 定义清晰；`execution/` 下 contexts、ExecutionDetailPanel、ExecutionTree、ExecutionTimeline 职责分明；`lib/tree-building` 与 UI 解耦。
- **建议**：保持当前边界；若新增「历史 trace 列表」等视图，建议将「Trace 列表项」「Trace 详情（只读）」等类型放在 `@/types` 或 `execution` 模块内统一管理，避免与现有 ExecutionStep 混在一起。

### 5. 测试

- **现状**：未见 `tree-building`、`eventAdapter`、ExecutionPanel 的单元测试或 e2e。
- **建议**：优先为 `tree-building.ts`（如 `buildExecutionTree`、`buildTreeByObservation`、`getTraceDuration`）和 `eventAdapter`（如若干典型事件 → step 的映射）补充单测；e2e 可覆盖「执行一次 → 树/时间线/详情有内容」和「清空后无步骤」等关键路径。

---

## 三、优先级建议

| 优先级 | 项 | 说明 |
|--------|----|------|
| 高 | 历史 Trace 接入 | 与后端能力对齐，提升可观测性 |
| 高 | Trace 级 Token 汇总 | 成本/用量可见，与后端 total_tokens 一致 |
| 中 | 时间线搜索 或 说明 | 要么功能对齐树视图，要么明确范围 |
| 中 | 错误/空状态与 i18n | 体验与国际化完整性 |
| 低 | 可访问性、Interrupt 验证、空状态复用、文档与单测 | 稳健性与可维护性 |

---

以上为执行流前端的待完善与待整理项汇总；实施时可按优先级分迭代推进。
