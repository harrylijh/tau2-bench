# Tool Call Reflection Mechanism

This document describes the tool call reflection mechanism implemented in the Tau2 benchmark orchestrator.

## Overview

The tool call reflection mechanism adds an extra layer of safety and validation to tool calls made by agents or users. Instead of executing tool calls directly, the orchestrator can optionally route them through a reflection system that uses an LLM to evaluate whether the tool call should be executed.

## Architecture

### New Components

1. **ToolCallReflector**: Core reflection logic
2. **ToolReflectionResult**: Result structure for reflection decisions
3. **Role.REFLECTION**: New role in the orchestrator flow

### Updated Flow

**Without Reflection:**
```
AGENT/USER → ENV (direct execution)
```

**With Reflection:**
```
AGENT/USER → REFLECTION → ENV → AGENT/USER
```

The reflection system adds an intermediate processing step where each tool call is individually evaluated.

## Configuration

### Basic Usage

```python
orchestrator = Orchestrator(
    domain="your_domain",
    agent=your_agent,
    user=your_user,
    environment=your_environment,
    task=your_task,
    enable_reflection=True,  # Enable reflection
    reflection_config={
        "model": "gpt-4.1"  # Model for reflection
    }
)
```

Note: The current implementation uses a single model parameter and does not support reflection modes or custom rules.

### Reflection Modes

*Note: The current implementation does not support configurable reflection modes. The reflection behavior is determined by the LLM's evaluation of the tool call context.*

### Custom Rules

*Note: The current implementation does not support custom rules configuration. Tool-specific guidance is provided through tool prompt files located in `data/tau2/tool_prompts/{domain}/{tool_name}.md`.*

## Reflection Process

### Individual Tool Call Processing

The reflection system processes each tool call separately in a loop:

1. **Tool Call Iteration**: Each tool call in a message is processed individually
2. **Context Building**: Gathers conversation history, available tools, task context for each call
3. **Persistence Check**: After 2 rejections, tool calls are automatically approved
4. **LLM Evaluation**: Uses configured LLM to evaluate the individual tool call
5. **Decision Storage**: Stores either approved `ToolCall` or rejection `ToolMessage`
6. **Execution**: All decisions are sent to environment as a batch
7. **Skipping**: Tool calls that do not have a tool prompt will skip the reflection step

### Three-Stage Workflow

1. **AGENT/USER → REFLECTION**: 
   - Original tool call message is added to trajectory
   - Each tool call is individually reflected upon
   - Decisions are stored in `tool_call_decisions`
   - Reflection messages are added for audit trail

2. **REFLECTION → ENV**:
   - Approved tool calls are executed by environment
   - Rejected tool calls use pre-generated `ToolMessage` responses
   - All responses maintain proper ID pairing

3. **ENV → AGENT/USER**:
   - Results are returned to original requestor
   - Mix of actual tool responses and rejection messages

## Key Features

### Individual Tool Call Processing
- **Granular Decisions**: Each tool call is evaluated separately, allowing mixed approvals/rejections
- **Per-Call Persistence**: Rejection counting and persistence logic applied individually
- **Flexible Outcomes**: Some tools calls can be approved while others are rejected in the same message

### Proper Message Pairing
- **API Compatibility**: Rejected tool calls receive `ToolMessage` responses with matching IDs
- **Azure OpenAI Compliance**: Maintains required tool call/response pairing for API validation
- **Seamless Integration**: Works with existing agent/user message flows

### Rich Audit Trail
- **Reflection Messages**: `ReflectionMessage` instances document decision reasoning
- **Original Preservation**: Original tool call messages are preserved with updated timestamps
- **Decision Tracking**: Full history of approvals, rejections, and modifications

### Robust Error Handling
- **Fail-Safe Design**: Defaults to allowing execution if reflection fails
- **Graceful Degradation**: Continues operation even with reflection errors
- **Comprehensive Logging**: Detailed logs for debugging and monitoring

## Performance Considerations

- Adds one LLM call per individual tool call (not per message)
- Increases latency proportional to number of tool calls
- Uses configurable model (default: gpt-4.1)
- Can be disabled for performance-critical scenarios
- Persistence mechanism reduces repeated reflection overhead

## Error Handling

- **Reflection Failure**: Defaults to allowing execution (fail-open)
- **JSON Parse Errors**: Falls back to original tool calls
- **Network Issues**: Graceful degradation with logging

## Monitoring

The reflection system provides detailed logging:
- Reflection decisions (approve/reject)
- Reasons for decisions
- Cost tracking
- Error conditions

## Implementation Details

### Key Files

- `src/tau2/orchestrator/tool_reflector.py`: Reflection logic
- `src/tau2/orchestrator/orchestrator.py`: Updated orchestrator with reflection
- `test_reflection.py`: Test script
- `reflection_example.py`: Usage examples

### Message Flow Updates

The orchestrator's step function now includes:
- **AGENT/USER → REFLECTION**: Routes tool calls to individual reflection evaluation
- **REFLECTION → ENV**: Processes approved tool calls and rejection messages
- **ENV → AGENT/USER**: Returns mixed results to original requestor

### Decision Storage

The reflection system uses `tool_call_decisions` to store:
- `ToolCall` objects for approved/modified tool calls
- `ToolMessage` objects for rejected tool calls (with matching IDs)

### Context Information

Reflection decisions are made based on:
- Recent conversation history (last 5 messages)
- Available tools and descriptions
- Task context and domain information  
- Tool-specific prompts from `data/tau2/tool_prompts/{domain}/{tool_name}.md`
- Agent system prompts or user task descriptions

## Future Enhancements

- **Configurable Reflection Modes**: Add support for conservative, permissive, and balanced modes
- **Custom Rules Engine**: Implement tool-specific custom rules configuration
- **Learning from Feedback**: Improve reflection based on outcomes
- **Batch Optimization**: Optimize LLM calls for multiple tool calls
- **Reflection Caching**: Cache decisions for similar tool calls
- **Human-in-the-Loop**: Option to escalate to human review
- **Performance Metrics**: Detailed analytics on reflection effectiveness
