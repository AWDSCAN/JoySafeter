/**
 * Visualization types for Command Mode execution state.
 * Used by execution store, eventProcessor, and execution types.
 */

export interface GraphState {
  context?: Record<string, any>
  messages?: any[]
  current_node?: string
  route_decision?: string
  route_reason?: string
  route_history?: string[]
  loop_count?: number
  loop_condition_met?: boolean
  max_loop_iterations?: number
  parallel_mode?: boolean
  task_states?: Record<string, TaskState>
  loop_states?: Record<string, any>
  task_results?: Array<{
    status: 'success' | 'error'
    error_msg?: string
    result?: any
    task_id: string
  }>
  parallel_results?: any[]
  loop_body_trace?: string[]
}

export interface TaskState {
  status: 'pending' | 'running' | 'completed' | 'error'
  result?: any
  error_msg?: string
}

export interface TraceStep {
  nodeId: string
  nodeType: string
  timestamp: number
  command: {
    update: Record<string, any>
    goto?: string
    reason?: string
  }
  stateSnapshot: GraphState
  routeDecision?: {
    result: boolean | string
    reason: string
    goto: string
  }
}
