"""
Tool Call Reflection mechanism for the orchestrator.
Provides LLM-based reflection on whether tool calls should be executed.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any
import litellm

from loguru import logger

from tau2.data_model.message import Message, ToolCall, SystemMessage, UserMessage, AssistantMessage, ToolMessage, ReflectionMessage
from tau2.utils.llm_utils import get_response_cost
from tau2.environment.tool import Tool


@dataclass
class ToolReflectionResult:
    """Result of tool call reflection."""
    should_execute: bool
    tool_call: ToolCall  # Potentially modified tool calls
    reason: str  # Explanation for the decision
    cost: float = 0.0  # Cost of the reflection


class ToolCallReflector:
    """
    Handles LLM-based reflection on tool calls before execution.
    """
    
    def __init__(
        self,
        model: str = "gpt-4.1",
    ):
        self.model = model
        
    def reflect_on_tool_call(
        self, 
        tool_call: ToolCall, 
        context: Dict[str, Any]
    ) -> ToolReflectionResult:
        """
        Reflect on whether a single tool call should be executed.
        
        Args:
            tool_call: The tool call to reflect on
            context: Context information including conversation history, available tools, etc.
            
        Returns:
            ToolReflectionResult with decision and potentially modified tool call
        """
        try:
            # Generate reflection prompt
            reflection_prompt = self._generate_reflection_prompt(tool_call, context)
            
            # Create messages for LLM
            reflection_messages = [
                {"role": "system", "content": reflection_prompt},
                {"role": "user", "content": self._format_tool_call_for_reflection(tool_call)}
            ]
            
            # print("Reflection prompt:", reflection_prompt)
            # Get LLM reflection response
            if "gpt-" or "o4-" in self.model:
                custom_llm_provider = "azure"
            else:
                custom_llm_provider = 'openai'

            res = litellm.completion(
                model=self.model,
                messages=reflection_messages,
                custom_llm_provider=custom_llm_provider,
            )
            response = res.choices[0].message['content'].strip('```json').strip('```').strip()
            
            # Parse the reflection response
            result = self._parse_reflection_response(response, tool_call)
            result.cost = get_response_cost(res)
            
            logger.info(f"Tool reflection decision: {result.should_execute} - {result.reason}")
            return result
            
        except Exception as e:
            logger.error(f"Error in tool call reflection: {e}")
            # Default to allowing execution on error (fail-open)
            return ToolReflectionResult(
                should_execute=True,
                tool_call=tool_call,
                reason=f"Reflection failed, defaulting to execution: {str(e)}"
            )
        
    def _load_tool_prompt(self, domain: str, tool_name: str) -> Optional[str]:
        """Load tool prompt from file if available."""
        try:
            # Construct path: data/tau2/tool_prompts/{domain}/{tool_name}.md
            prompt_path = Path("data/tau2/tool_prompts") / domain / f"{tool_name}.md"
            
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            else:
                return None
        except Exception as e:
            logger.debug(f"Could not load tool prompt for {tool_name}: {e}")
            return None
    
    def has_tool_prompt(self, domain: str, tool_name: str) -> bool:
        """Check if tool prompt is available for the given tool."""
        tool_prompt = self._load_tool_prompt(domain, tool_name)
        return tool_prompt is not None

    def _generate_reflection_prompt(self, tool_call: ToolCall, context: Dict[str, Any]) -> str:
        """Generate the reflection prompt for the LLM."""
        
        # Get context information
        conversation_history = context.get("conversation_history", [])
        available_tools = context.get("available_tools", [])
        task_context = context.get("task_context", "")
        domain = context.get("domain", "")
        
        # Build tool descriptions
        tool_descriptions = self._format_available_tools(available_tools)
        
        # Get recent conversation context
        recent_context = self._format_recent_conversation(conversation_history)
        
        # Role-aware context
        role_context = self._format_role_context(context)
        
        # Tool prompts
        tool_prompts_section = self._format_tool_prompts(context, domain, tool_call.name)

        prompt = f"""You are an expert in validating the tool call. Your job is to analyze a proposed tool call and decide whether it should be executed.

DOMAIN: {domain}
TASK CONTEXT: {task_context}

{role_context}

AVAILABLE TOOLS:
{tool_descriptions}

{tool_prompts_section}

RECENT CONVERSATION:
{recent_context}

Your task is to analyze the proposed tool call and respond with a JSON object containing:
1. "should_execute": boolean - whether the tool call should be executed
2. "reason": string - explanation for your decision
3. "modified_call": object - the tool call to execute (may be modified from original). Do not modify the tool call ID, but you can change the arguments.

Consider the following questions using the available context, especially focusing on the tool prompts and recent conversation. If you think the requestor called the wrong tool after careful consideration, you can reject it and suggest the correct tool name in your reasons.
- Is the tool call appropriate for the current context?
- Do the parameters make sense?
- Are there missing required parameters?
- Does the tool call align with the user's intent?


Respond only with a valid JSON object, no additional text."""

        return prompt
    
    def _format_role_context(self, context: Dict[str, Any]) -> str:
        """Format role-aware context for the reflection prompt."""
        if "agent_system_prompt" in context:
            return f"""AGENT CONTEXT:
{context["agent_system_prompt"]}"""
        elif "user_task_description" in context:
            return f"""USER TASK CONTEXT:
{context["user_task_description"]}"""
        else:
            return ""
    
    def _format_tool_prompts(self, context: Dict[str, Any], domain: str, tool_name: str) -> str:
        """Format tool prompts section for the reflection prompt."""
        tool_prompt = self._load_tool_prompt(domain, tool_name)
        if tool_prompt:
            return f"""TOOL PROMPT:
Tool: {tool_name}
{tool_prompt}"""
        else:
            return ""

    def _format_available_tools(self, tools: List[Tool]) -> str:
        """Format available tools for the prompt."""
        if not tools:
            return "No tools available"
        
        tool_descriptions = []
        for tool in tools:
            description = f"- {tool.name}: {tool.short_desc}"
            if tool.long_desc:
                description += f"\n  Description: {tool.long_desc}"
            tool_descriptions.append(description)
        
        return "\n".join(tool_descriptions)
    
    def _format_recent_conversation(self, messages: List[Message]) -> str:
        """Format recent conversation for context."""
        if not messages:
            return "No recent conversation"
        
        formatted = []
        for msg in messages[:-10]: # Limit to last 10 messages
            role = msg.role.capitalize() if hasattr(msg, 'role') else 'Unknown'
            content = msg.content if hasattr(msg, 'content') and msg.content else '[Tool call or empty message]'
            details = ""
            if isinstance(msg, UserMessage) or isinstance(msg, AssistantMessage):
                if msg.tool_calls:
                    tool_calls = []
                    for tool in msg.tool_calls:
                        tool_calls.append(
                            f"Tool: {tool.name}\nArgs: {json.dumps(tool.arguments)}"
                        )
                    details = "\n".join(tool_calls)
            elif isinstance(msg, ToolMessage):
                details = f"Tool ID: {msg.id}. Requestor: {msg.requestor}"
                if msg.error:
                    details += "(Error)"
            formatted.append(f"{role}: {content}\n{details}")      

        return "\n".join(formatted) if formatted else "No recent conversation"
    
    def _format_tool_call_for_reflection(self, tool_call: ToolCall) -> str:
        """Format tool call for the reflection prompt."""
        formatted_call = {
            "name": tool_call.name,
            "arguments": tool_call.arguments,
            "id": tool_call.id
        }
        
        return json.dumps(formatted_call, indent=2)
    
    def _parse_reflection_response(
        self, 
        response_content: str, 
        original_tool_call: ToolCall
    ) -> ToolReflectionResult:
        """Parse the LLM reflection response."""
        try:
            # Try to parse JSON response
            response_json = json.loads(response_content.strip())
            
            should_execute = response_json.get("should_execute", True)
            reason = response_json.get("reason", "No reason provided")
            modified_call_data = response_json.get("modified_call", {})
            
            # If should_execute is False, return original tool calls
            if not should_execute:
                return ToolReflectionResult(
                    should_execute=False,
                    tool_call=original_tool_call,
                    reason=reason
                )
            
            # Parse modified tool call
            if modified_call_data:
                modified_call = ToolCall(
                    id=modified_call_data.get("id", original_tool_call.id),
                    name=modified_call_data.get("name", original_tool_call.name),
                    arguments=modified_call_data.get("arguments", original_tool_call.arguments),
                    requestor=original_tool_call.requestor
                )
            else:
                # No modifications, use original call
                modified_call = original_tool_call
            
            return ToolReflectionResult(
                should_execute=should_execute,
                tool_call=modified_call,
                reason=reason
            )
            
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(f"Failed to parse reflection response: {e}. Response: {response_content}")
            # Default to allowing execution with original call
            return ToolReflectionResult(
                should_execute=True,
                tool_call=original_tool_call,
                reason=f"Failed to parse reflection response, allowing execution: {str(e)}"
            )
