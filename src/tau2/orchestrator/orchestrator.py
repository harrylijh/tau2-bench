import time
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, List, Optional

from loguru import logger

from tau2.agent.base import BaseAgent, is_valid_agent_history_message
from tau2.agent.llm_agent import LLMSoloAgent
from tau2.data_model.message import (
    AssistantMessage,
    Message,
    MultiToolMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
    ReflectionMessage
)
from tau2.data_model.simulation import SimulationRun, TerminationReason
from tau2.data_model.tasks import EnvFunctionCall, InitializationData, Task
from tau2.environment.environment import Environment, EnvironmentInfo
from tau2.orchestrator.tool_reflector import ToolCallReflector, ToolReflectionResult
from tau2.user.base import BaseUser, is_valid_user_history_message
from tau2.user.user_simulator import DummyUser, UserSimulator, UserState
from tau2.utils.llm_utils import get_cost
from tau2.utils.utils import format_time, get_now


class Role(str, Enum):
    AGENT = "agent"
    USER = "user"
    ENV = "env"
    REFLECTION = "reflection"


DEFAULT_FIRST_AGENT_MESSAGE = AssistantMessage(
    role="assistant", content="Hi! How can I help you today?", cost=0.0
)


class Orchestrator:
    """
    Orchestrator for the simulation given a task.
    Passes messages between the Agent, User, and Environment.
    
    Features:
    - Standard message routing between Agent, User, and Environment
    - Optional tool call reflection mechanism for safety and validation
    - Support for solo mode and multi-participant simulations
    - Configurable termination conditions and error handling
    
    Tool Call Reflection:
    When enabled, tool calls from agents or users are first sent to a reflection
    system that uses an LLM to evaluate whether the tool call should be executed.
    The reflection system can:
    - Approve, reject, or modify tool calls
    - Provide explanations for decisions
    - Apply custom rules for specific tools
    - Support different reflection modes (conservative, permissive, balanced)
    """

    def __init__(
        self,
        domain: str,
        agent: BaseAgent,
        user: BaseUser,
        environment: Environment,
        task: Task,
        max_steps: int = 100,
        max_errors: int = 10,
        seed: Optional[int] = None,
        solo_mode: bool = False,
        enable_reflection: bool = False,
        reflection_config: Optional[dict] = None,
    ):
        self.domain = domain
        self.agent = agent
        self.user = user
        self.environment = environment
        self.task = task
        self.seed = seed
        self.solo_mode = solo_mode
        self.enable_reflection = enable_reflection
        self.tool_reflector = None
        self.reflection_rejection_count = {}  # Track rejected tool calls
        if self.enable_reflection:
            reflection_config = reflection_config or {}
            self.tool_reflector = ToolCallReflector(**reflection_config)
            self.tool_call_decisions: List[ToolCall | ToolMessage] = []  # Store decisions from reflection
        self.agent_state: Optional[Any] = None
        self.user_state: Optional[UserState] = None
        self.trajectory: list[Message] = []
        self.max_steps = max_steps
        self.max_errors = max_errors
        self.step_count = 0
        self.done = False
        self.termination_reason: Optional[TerminationReason] = None
        self.num_errors = 0
        self.from_role: Optional[Role] = None
        self.to_role: Optional[Role] = None
        self.message: Optional[Message] = None

    def initialize(self):
        """
        Initialize the orchestrator.
        - If the tasks specifies an initial state, use it to initialize the environment.
        - Initialize the agent and user states.
        - Send the first message (default message from the agent to the user).
        """
        initial_state = self.task.initial_state
        initialization_data = (
            initial_state.initialization_data if initial_state is not None else None
        )
        initialization_actions = (
            initial_state.initialization_actions if initial_state is not None else None
        )
        message_history = (
            deepcopy(initial_state.message_history)
            if initial_state is not None and initial_state.message_history is not None
            else []
        )
        for msg in message_history:
            msg.turn_idx = None

        # Add timestamps to the message history
        message_history = self._add_timestamps(message_history)

        if self.solo_mode:
            assert self.environment.solo_mode, "Environment should be in solo mode"
            assert isinstance(self.agent, LLMSoloAgent), (
                "Agent must be a LLMSoloAgent in solo mode"
            )
            assert isinstance(self.user, DummyUser), (
                "User must be a DummyUser in solo mode"
            )

        # Initialize Environment state
        self._initialize_environment(
            initialization_data=initialization_data,
            initialization_actions=initialization_actions,
            message_history=message_history,
        )

        # Set seeds for the agent, user
        if self.seed is not None:
            self.agent.set_seed(self.seed)
            self.user.set_seed(self.seed)

        # Initialize the agent and user states
        if len(message_history) > 0:
            self.validate_message_history(message_history)

            last_message = message_history[-1]
            # Last message is an assistant message
            if isinstance(last_message, AssistantMessage):
                self.from_role = Role.AGENT
                if not last_message.is_tool_call():  # Last message is for the user
                    self.to_role = Role.USER
                else:  # Last message is for the environment (or reflection if enabled)
                    self.to_role = Role.REFLECTION if self.enable_reflection else Role.ENV
                self.agent_state = self.agent.get_init_state(
                    message_history=[
                        msg
                        for msg in message_history
                        if is_valid_agent_history_message(msg)
                    ]
                )
                self.user_state = self.user.get_init_state(
                    message_history=[
                        msg
                        for msg in message_history[:-1]
                        if is_valid_user_history_message(msg)
                    ]
                )
                self.message = last_message
                if self.agent.is_stop(last_message):
                    self.done = True
                    self.termination_reason = TerminationReason.AGENT_STOP
            # Last message is a user message
            elif isinstance(last_message, UserMessage):
                self.from_role = Role.USER
                if not last_message.is_tool_call():  # Last message is for the agent
                    self.to_role = Role.AGENT
                else:  # Last message is for the environment (or reflection if enabled)
                    self.to_role = Role.REFLECTION if self.enable_reflection else Role.ENV
                self.user_state = self.user.get_init_state(
                    message_history=[
                        msg
                        for msg in message_history
                        if is_valid_user_history_message(msg)
                    ]
                )
                self.agent_state = self.agent.get_init_state(
                    message_history=[
                        msg
                        for msg in message_history[:-1]
                        if is_valid_agent_history_message(msg)
                    ]
                )
                self.message = last_message
                self.done = UserSimulator.is_stop(last_message)
                if self.done:
                    self.termination_reason = TerminationReason.USER_STOP
            # Last message is a tool message
            elif isinstance(last_message, ToolMessage):
                self.from_role = Role.ENV
                if last_message.requestor == "assistant":
                    self.to_role = Role.AGENT
                    self.agent_state = self.agent.get_init_state(
                        message_history=[
                            msg
                            for msg in message_history[:-1]
                            if is_valid_agent_history_message(msg)
                        ]
                    )
                    self.user_state = self.user.get_init_state(
                        message_history=[
                            msg
                            for msg in message_history
                            if is_valid_user_history_message(msg)
                        ]
                    )
                else:
                    self.to_role = Role.USER
                    self.agent_state = self.agent.get_init_state(
                        message_history=[
                            msg
                            for msg in message_history
                            if is_valid_agent_history_message(msg)
                        ]
                    )
                    self.user_state = self.user.get_init_state(
                        message_history=[
                            msg
                            for msg in message_history[:-1]
                            if is_valid_user_history_message(msg)
                        ]
                    )
                self.message = last_message
            else:
                raise ValueError(
                    f"Last message should be of type AssistantMessage, UserMessage, or ToolMessage, got {type(last_message)}"
                )
            self.trajectory = message_history

        else:
            self.agent_state = self.agent.get_init_state()
            self.user_state = self.user.get_init_state()
            if not self.solo_mode:
                first_message = deepcopy(DEFAULT_FIRST_AGENT_MESSAGE)
                first_message.timestamp = get_now()
                self.trajectory = [first_message]
                self.message = first_message
                self.from_role = Role.AGENT
                self.to_role = Role.USER
            else:
                first_message, agent_state = self.agent.generate_next_message(
                    None, self.agent_state
                )
                self.trajectory = [first_message]
                self.message = first_message
                self.from_role = Role.AGENT
                # In solo mode, if reflection is enabled and first message is a tool call, go to reflection
                if first_message.is_tool_call() and self.enable_reflection:
                    self.to_role = Role.REFLECTION
                else:
                    self.to_role = Role.ENV
                self.done = self.agent.is_stop(first_message)
                if self.done:
                    self.termination_reason = TerminationReason.AGENT_STOP

        self.environment.sync_tools()

    def run(self) -> SimulationRun:
        """
        Run the simulation.

        Returns:
            SimulationRun: The simulation run.
        """
        start_time = get_now()
        start = time.perf_counter()
        self.initialize()
        while not self.done:
            self.step()
            if self.step_count >= self.max_steps:
                self.done = True
                self.termination_reason = TerminationReason.MAX_STEPS
            if self.num_errors >= self.max_errors:
                self.done = True
                self.termination_reason = TerminationReason.TOO_MANY_ERRORS
        duration = time.perf_counter() - start
        messages = self.get_trajectory()
        res = get_cost(messages)
        if res is None:
            agent_cost, user_cost = None, None
        else:
            agent_cost, user_cost = res
        simulation_run = SimulationRun(
            id=str(uuid.uuid4()),
            task_id=self.task.id,
            start_time=start_time,
            end_time=get_now(),
            duration=duration,
            termination_reason=self.termination_reason.value,
            reward_info=None,
            user_cost=user_cost,
            agent_cost=agent_cost,
            messages=messages,
            seed=self.seed,
        )
        return simulation_run

    def step(self):
        """
        Perform one step of the simulation.
        Sends self.message from self.from_role to self.to_role
        This can either be a message from agent to user/environment, environment to agent, or user to agent
        Updates self.trajectory
        """
        if self.done:
            raise ValueError("Simulation is done")
        logger.debug(
            f"Step {self.step_count}. Sending message from {self.from_role} to {self.to_role}"
        )
        logger.debug(
            f"Step {self.step_count}.\nFrom role: {self.from_role}\nTo role: {self.to_role}\nMessage: {self.message}"
        )
        # AGENT/ENV -> USER
        if self.from_role in [Role.AGENT, Role.ENV] and self.to_role == Role.USER:
            user_msg, self.user_state = self.user.generate_next_message(
                self.message, self.user_state
            )
            user_msg.validate()
            if UserSimulator.is_stop(user_msg):
                self.done = True
                self.termination_reason = TerminationReason.USER_STOP
            self.trajectory.append(user_msg)
            self.message = user_msg
            self.from_role = Role.USER
            if user_msg.is_tool_call():
                # If reflection is enabled, go to reflection first, otherwise go to ENV
                self.to_role = Role.REFLECTION if self.enable_reflection else Role.ENV
            else:
                self.to_role = Role.AGENT
        # USER/ENV -> AGENT
        elif (
            self.from_role == Role.USER or self.from_role == Role.ENV
        ) and self.to_role == Role.AGENT:
            agent_msg, self.agent_state = self.agent.generate_next_message(
                self.message, self.agent_state
            )
            try:
                agent_msg.validate()
            except ValueError as e:
                logger.error(f"Invalid agent message: {e}")
                self.done = True
                self.termination_reason = TerminationReason.AGENT_STOP
                
            if self.agent.is_stop(agent_msg):
                self.done = True
                self.termination_reason = TerminationReason.AGENT_STOP
            self.trajectory.append(agent_msg)
            self.message = agent_msg
            self.from_role = Role.AGENT
            if agent_msg.is_tool_call():
                # If reflection is enabled, go to reflection first, otherwise go to ENV
                self.to_role = Role.REFLECTION if self.enable_reflection else Role.ENV
            else:
                self.to_role = Role.USER
        # AGENT/USER -> REFLECTION
        elif self.from_role in [Role.AGENT, Role.USER] and self.to_role == Role.REFLECTION:
            if not self.message.is_tool_call():
                raise ValueError("Only tool calls should be sent to reflection")
            
            # Build context for reflection
            reflection_context = self._build_reflection_context()
            
            # Store original tool calls for comparison
            original_calls = deepcopy(self.message.tool_calls)
            original_msg = deepcopy(self.message)
            # # Check if this is a repeated attempt at the same tool call
            # tool_signature = self._get_tool_call_signature(self.message.tool_calls[0])
            # rejection_count = self.reflection_rejection_count.get(tool_signature, 0)
            
            # # After 2 rejections, allow the tool call to proceed (respect user/agent persistence)
            # if rejection_count >= 2:
            #     # Reset counter since we're allowing execution
            #     self.reflection_rejection_count[tool_signature] = 0
            #     self.to_role = Role.ENV
            #     logger.info(f"Allowing tool call after {rejection_count} rejections due to persistence")
            # else:
            #     # Process each tool call individually
            tool_call_decisions = []
            
            for tool_call in self.message.tool_calls:
                # Check if tool prompt is available for this tool call
                if not self.tool_reflector.has_tool_prompt(self.domain, tool_call.name):
                    # Log and skip reflection for this tool call
                    logger.info(f"Tool prompt not available for {tool_call.name}, skipping reflection")
                    tool_call_decisions.append(tool_call)
                    # Add reflection message about skipped tool call
                    reflection_note = self._create_reflection_message(
                        content=f"REFLECTION_SKIPPED: Tool prompt not available for {tool_call.name}",
                    )
                    self.trajectory.append(reflection_note)
                    continue

                # Check rejection count for this specific tool call
                individual_signature = self._get_tool_call_signature(tool_call)
                individual_rejection_count = self.reflection_rejection_count.get(individual_signature, 0)
                
                # After 2 rejections, allow this tool call to proceed
                if individual_rejection_count >= 2:
                    self.reflection_rejection_count[individual_signature] = 0
                    tool_call_decisions.append(tool_call)
                    # Add reflection message about approved calls
                    reflection_note = self._create_reflection_message(
                            content="REFLECTION_PERSISTENCE_APPROVE: Tool call was allowed after multiple rejections due to persistence",
                        )
                    self.trajectory.append(reflection_note)
                    logger.info(f"Allowing tool call {tool_call.name} after {individual_rejection_count} rejections due to persistence")
                    continue
                
                # Perform reflection on individual tool call
                reflection_result = self.tool_reflector.reflect_on_tool_call(
                    tool_call, reflection_context
                )
                
                if reflection_result.should_execute:
                    # Add approved/modified tool calls
                    tool_call_decisions.append(reflection_result.tool_call)
                    
                    # Add reflection message about approved calls
                    if self._tool_call_were_modified(tool_call, reflection_result.tool_call):
                        reflection_note = self._create_reflection_message(
                            content="REFLECTION_MODIFIED: Some tool call parameters were adjusted by the reflection system",
                        )
                        self.trajectory.append(reflection_note)
                        logger.info("Some tool calls were modified by the reflection system")
                    else:
                        reflection_note = self._create_reflection_message(
                            content="REFLECTION_APPROVED: Tool calls were approved without modifications",
                        )
                        self.trajectory.append(reflection_note)
                        logger.info("Tool calls approved without modifications")

                    # Reset rejection counter for this tool call
                    if individual_signature in self.reflection_rejection_count:
                        self.reflection_rejection_count[individual_signature] = 0
                else:
                    # Tool call was rejected
                    self.reflection_rejection_count[individual_signature] = individual_rejection_count + 1
                    
                    # Create rejection tool message for this specific tool call to be sent to the environment
                    rejection_tool_msg = self._create_rejection_tool_message(
                        original_tool_call=tool_call,
                        reason=reflection_result.reason,
                        requestor=tool_call.requestor
                    )

                    tool_call_decisions.append(rejection_tool_msg)

                    # Add reflection message about rejection
                    rejection_note = self._create_reflection_message(
                        content=f"REFLECTION_REJECTED: Tool call {tool_call.name} was rejected by reflection: {reflection_result.reason}",
                    )
                    self.trajectory.append(rejection_note)
            
            self.tool_call_decisions = deepcopy(tool_call_decisions)

            # update the timestamp to match the current time
            original_msg.timestamp = get_now()
            self.trajectory.append(original_msg)

            self.from_role = Role.REFLECTION
            self.to_role = Role.ENV

        # REFLECTION -> ENV
        elif self.from_role == Role.REFLECTION and self.to_role == Role.ENV:
            if not self.tool_call_decisions:
                raise ValueError("No tool call decisions available from reflection")
            requestor = self.tool_call_decisions[0].requestor
            tool_msgs = []
            for tool_call_decision in self.tool_call_decisions:
                if isinstance(tool_call_decision, ToolCall):
                    # If it's a ToolCall, it means the tool call was approved or modified
                    tool_msg = self.environment.get_response(tool_call_decision)
                elif isinstance(tool_call_decision, ToolMessage):
                    # If it's a ToolMessage, it means the tool call was rejected
                    # update the timestamp to match the current time
                    tool_call_decision.timestamp = get_now()
                    tool_msg = tool_call_decision
                else:
                    raise ValueError(
                        f"Invalid tool call decision type: {type(tool_call_decision)}. Must be ToolCall or ToolMessage."
                    )
                tool_msgs.append(tool_msg)
                
            assert len(self.tool_call_decisions) == len(tool_msgs), (
                "Number of tool calls and tool call decisions should be the same"
            )
            self.trajectory.extend(tool_msgs)
            if (
                len(tool_msgs) > 1
            ):  # Packaging multiple tool messages into a MultiToolMessage
                self.message = MultiToolMessage(
                    role="tool",
                    tool_messages=tool_msgs,
                )
            else:
                self.message = tool_msgs[0]
            
            if requestor == "assistant":
                self.to_role = Role.AGENT
            if requestor == "user":
                self.to_role = Role.USER
            self.from_role = Role.ENV

        # AGENT/USER -> ENV
        elif self.from_role in [Role.AGENT, Role.USER] and self.to_role == Role.ENV:
            if not self.message.is_tool_call():
                raise ValueError("Agent or User should send tool call to environment")
            tool_msgs = []
            for tool_call in self.message.tool_calls:
                tool_msg = self.environment.get_response(tool_call)
                tool_msgs.append(tool_msg)
            assert len(self.message.tool_calls) == len(tool_msgs), (
                "Number of tool calls and tool messages should be the same"
            )
            self.trajectory.extend(tool_msgs)
            if (
                len(tool_msgs) > 1
            ):  # Packaging multiple tool messages into a MultiToolMessage
                self.message = MultiToolMessage(
                    role="tool",
                    tool_messages=tool_msgs,
                )
            else:
                self.message = tool_msgs[0]
            self.to_role = self.from_role
            self.from_role = Role.ENV
        else:
            raise ValueError(
                f"Invalid role combination. From role: {self.from_role}, To role: {self.to_role}"
            )
        self.step_count += 1
        self.environment.sync_tools()

    def get_trajectory(self) -> list[Message]:
        """
        Get the trajectory of the simulation.
        The trajectory is sorted by timestamp, turn_idx are added to messages, trajectory is returned.
        """
        messages: list[Message] = sorted(
            deepcopy(self.trajectory),
            key=lambda x: x.timestamp,
        )
        trajectory = []
        for i, msg in enumerate(messages):
            msg = deepcopy(msg)
            msg.turn_idx = i
            trajectory.append(msg)
        return trajectory

    @classmethod
    def validate_message_history(cls, message_history: list[Message]):
        """
        Validate a message history.
            - Should only contain AssistantMessage, UserMessage, ToolMessage, ReflectionMessage.
            - All assistant/user messages should be either to user or tool call, not both.
            - If n tool calls are made by a participant, exactly n tool messages should follow with requestor matching the participant.
        """
        num_expected_tool_messages = 0
        requestor = None
        for msg in message_history:
            if isinstance(msg, AssistantMessage) or isinstance(msg, UserMessage):
                msg.validate()
                if msg.is_tool_call():
                    if num_expected_tool_messages > 0:
                        raise ValueError(
                            f"{num_expected_tool_messages} tool messages are missing. Got {msg.role} message."
                        )
                    num_expected_tool_messages = len(msg.tool_calls)
                    requestor = msg.role
                else:
                    num_expected_tool_messages == 0
                    requestor = None
            elif isinstance(msg, ToolMessage):
                if num_expected_tool_messages == 0 or requestor is None:
                    raise ValueError("No tool messages expected.")
                if requestor != msg.requestor:
                    raise ValueError(
                        f"Got tool message from {msg.requestor}, expected {requestor}."
                    )
                num_expected_tool_messages -= 1
            else:
                raise ValueError(f"Invalid message type: {type(msg)}")

    def _initialize_environment(
        self,
        initialization_data: Optional[InitializationData],
        initialization_actions: Optional[list[EnvFunctionCall]],
        message_history: list[Message],
    ):
        """
        Initialize the environment.
        """
        self.environment.set_state(
            initialization_data=initialization_data,
            initialization_actions=initialization_actions,
            message_history=message_history,
        )

    def _get_environment_info(self) -> EnvironmentInfo:
        """
        Get the environment info.
        """
        return self.environment.get_info()

    def _count_errors(self, message_history: list[Message]) -> int:
        """
        Count the number of errors in the message history.
        """
        return sum(
            1 for msg in message_history if isinstance(msg, ToolMessage) and msg.error
        )

    def _add_timestamps(
        self, message_history: list[Message]
    ) -> list[tuple[str, Message]]:
        """
        Add timestamps to the message history.
        This is used to sort the messages by timestamp.
        """
        time_offset = datetime.now() - timedelta(seconds=len(message_history))
        for i, msg in enumerate(message_history):
            msg.timestamp = format_time(time_offset + timedelta(seconds=i))
        return message_history

    def _get_tool_call_signature(self, tool_call: ToolCall) -> str:
        """Create a simple signature for a tool call to track repeated attempts."""
        # Simple signature: tool_name + sorted argument keys
        arg_keys = sorted(tool_call.arguments.keys()) if tool_call.arguments else []
        return f"{tool_call.name}({','.join(arg_keys)})"

    def _tool_call_were_modified(self, original_call: ToolCall, modified_call: ToolCall) -> bool:
        """Simple check if tool call were modified by reflection."""
        if original_call.name != modified_call.name or original_call.arguments != modified_call.arguments:
            return True
        return False


    def _create_rejection_tool_message(self, original_tool_call: ToolCall, reason: str, requestor: str) -> ToolMessage:
        """Create a tool message indicating that the tool call was rejected by reflection."""
        # return ReflectionMessage(
        #     id="reflection_rejection",
        #     role="reflection",
        #     content=f"Reflection system suggests reconsidering this tool call: {reason}. Please review and try again if appropriate.",
        #     timestamp=get_now(),
        #     requestor=requestor,
        # )
        rejection_response = ToolMessage(
            id=original_tool_call.id,  # Use the SAME ID as the tool call
            role="tool",
            content=f"Tool call rejected by reflection system: {reason}",
            requestor=requestor,
            error=False,  # Not an error, just a policy decision
            timestamp=get_now(),
        )
        return rejection_response

    def _create_reflection_message(self, content: str) -> ReflectionMessage:
        """Create a reflection message."""
        return ReflectionMessage(
            role="reflection",
            content=content,
            timestamp=get_now(),
        )

    def _build_reflection_context(self) -> dict:
        """Build context information for tool call reflection."""
        context = {
            "conversation_history": self.trajectory,
            "available_tools": self.environment.get_tools(),
            "task_context": getattr(self.task, "description", ""),
            "domain": self.domain,
            "current_step": self.step_count,
        }
        
        # Add role-aware context
        if self.message and self.message.is_tool_call() and self.message.tool_calls:
            tool_call = self.message.tool_calls[0]  # Use first tool call for context
            requestor = tool_call.requestor
            
            # Role-aware context
            if requestor == "assistant":
                # Include agent's system prompt for agent tool calls
                context["agent_system_prompt"] = self.agent.system_prompt
            elif requestor == "user":
                # Include task description for user tool calls  
                context["user_task_description"] = getattr(self.task, "description", "")
        
        return context
