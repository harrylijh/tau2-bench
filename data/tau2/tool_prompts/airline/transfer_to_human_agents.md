# transfer_to_human_agents

Tool Prompt for transfer_to_human_agents

## When to call the tool
- Use this tool ONLY if:
    1. The user explicitly requests to speak with or be transferred to a human agent/representative,
    OR
    2. The user's issue cannot be resolved within current system capabilities or is outside agent authority by policy (e.g., user wants to cancel or modify a flown reservation, change an unmodifiable field such as origin, or resolve an unsupported complex escalation).

## Before calling the tool
Required Parameters:
- `summary`: Briefly and accurately summarize the user's issue, including actions already attempted and reasons for transfer (e.g., 'User requests to modify origin airport on reservation M20IZO, which is not permitted per policy').

Checklist BEFORE using transfer_to_human_agents:
- Confirm you have tried all allowed actions and explained policy-based restrictions to the user.
- Clearly communicate the reason for transfer to both the user and in the summary for the human agent.

## Avoiding Common Errors:
- Do not transfer simply because a tool call fails; only transfer for explicit user request or true policy/in-system limitations.
- Always prefer solving standard requests within agent tools and policy before escalating to a human agent.

## After calling the tool
- Notify user they are being transferred, summarize the issue, and provide a smooth hand-off.