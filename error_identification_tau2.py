import json
import argparse
from enum import Enum
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import litellm
from tqdm import tqdm

from src.tau2.data_model.simulation import (RewardInfo, Info, Results, RunConfig,
                                        SimulationRun, UserInfo, NLAssertionCheck)
from src.tau2.data_model.tasks import Task, Action
from src.tau2.data_model.message import Message, SystemMessage, UserMessage, AssistantMessage, ToolMessage, ToolCall
from src.tau2.metrics.agent_metrics import is_successful, AgentMetrics, get_metrics_df

from siela.generate_tool_prompt import load_tool_information

class FaultAuthor(Enum):
    USER = "user"
    AGENT = "agent"
    ENVIRONMENT = "environment"

class GoalCompletionResult(BaseModel):
    task_id: int | str
    goal_completed: bool
    rationale: str

    def model_dump(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal_completed": self.goal_completed,
            "rationale": self.rationale,
        }


class FaultAssignmentResult(BaseModel):
    task_id: int | str
    authors: List[FaultAuthor] 
    descriptions: List[str]

    def model_dump(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "author": [author.value for author in self.authors],
            "description": [description for description in self.descriptions],
        }


class FaultType(Enum):
    CALLED_WRONG_TOOL = "called_wrong_tool"
    USED_WRONG_TOOL_ARGUMENT = "used_wrong_tool_argument"
    USED_INVALID_FORMAT = "used_invalid_format"
    OTHER_TOOL_USE_ERROR = "other_tool_use_error"
    OTHER = "other"


class FaultTypeResult(BaseModel):
    task_id: int | str
    fault_types: List[FaultType]
    description: str

    def model_dump(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "fault_types": [ft.value for ft in self.fault_types],
            "description": self.description,
        }


class SimulationResult(BaseModel):
    domain: str
    task_id: int | str
    user_instruction: str
    agent_policy: str
    traj: List[Message]  
    ground_truth_actions: List[Action]
    ground_truth_outputs: Optional[List[str]] = None
    reward_info: RewardInfo


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read tau2-bench evaluation results and analyze faults.")
    parser.add_argument("--env", type=str, default="retail", choices=["airline", "retail", "telecom", "telecom-workflow"], help="The environment that the original trajectories are from (used to fetch the user instructions)")
    parser.add_argument("-r", "--results-path", type=str, default="/home/lijiah/workspace/tau2-bench/data/simulations/2025-07-22T08:21:20.114525_retail_llm_agent_gpt-4.1-mini_user_simulator_gpt-4.1.json", help="Path to the results file")
    parser.add_argument("--max-concurrency", type=int, default=10, help="Maximum number of concurrent API calls")
    parser.add_argument("-o", "--output-path", type=str, required=True, help="Path to the output file")
    parser.add_argument("--max-num-failed-results", "-n", type=int, help="Maximum number of failed results to analyze")
    parser.add_argument("-t", "--task-ids", type=str, nargs="+", help="Space-separated task IDs, such as 7 13 56.")
    parser.add_argument("--model", type=str, default="gpt-4.1-mini", help="LLM model to use for analysis")
    return parser.parse_args()

def extract_actual_actions(messages: List[Any]) -> List[Dict[str, Any]]:
    """
    Extract actual actions from message trajectory.
    
    Args:
        messages: List of messages containing tool calls
        
    Returns:
        List of dictionaries with 'name' and 'args' keys representing actions taken
    """
    actions = []
    
    for message in messages:
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                actions.append({
                    'name': tool_call.name,
                    'args': tool_call.arguments if hasattr(tool_call, 'arguments') else {}
                })
    
    return actions


def display_traj(messages: List[Any]) -> str:
    """Display trajectory in a readable format"""
    if len(messages) == 0:
        return "No messages in trajectory"
    
    # Filter out system messages
    filtered_messages = [msg for msg in messages if hasattr(msg, 'role') and not isinstance(msg, SystemMessage)]
    result = []
    for msg in filtered_messages:
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
        result.append(f"{role}: {content}\n{details}")

    return "\n".join(result)


def display_actions(actions: List[Any]) -> str:
    """Display actions in JSON format"""
    action_dicts = []
    for action in actions:
        if hasattr(action, 'action_id'):
            action_dicts.append({
                "action_id": action.action_id,
                "name": action.name,
                "arguments": action.arguments,
                "requestor": action.requestor,
            })
        else:
            # Handle case where action might be a dict already
            action_dicts.append(action)
    
    return json.dumps(action_dicts, indent=2)

## TODO: decide if we want to keep this function
def display_nl_assertions(nl_assertions: List[Any]) -> str:
    """Display NL assertions in a readable format"""
    result = []
    for assertion in nl_assertions:
        result.append(f"Assertion: {assertion.nl_assertion}")
        result.append(f"Whether met the assertion: {assertion.met}")
        result.append(f"Justification: {assertion.justification}")
    
    return "\n".join(result)


def get_context_description() -> str:
    return """You will be given the ground truth action sequence, unmatched actions the set of required agent response outputs, and a trajectory.
- The ground truth action sequence is one example of a valid sequence of actions that lead to the goal state (the sequence of actions could be empty, meaning that no action should have been taken). The unmatched actions are the actions that were not matched with the ground truth action calls.
- The required agent response outputs are the set of outputs that the agent is expected to communicate to the user.
- The trajectory is the sequence of messages between the user and the agent.
- The trajectory has been determined to have a fault."""

def display_context(user_instruction: str, agent_policy: str, ground_truth_actions: List[Action], ground_truth_outputs: List[str], trajectory: List[Message], unmatched_actions: List[Action], author: FaultAuthor) -> str:
    '''
    display the context for fault assignment analysis by authors
    '''
    traj_display = display_traj(trajectory)
    actions_display = display_actions(ground_truth_actions)
    if len(unmatched_actions) > 0:
        unmatched_actions_display = display_actions(unmatched_actions)
    else:
        unmatched_actions_display = "No unmatched actions"

    # For user faults, show the user instruction but do not show the agent policy 
    if author.value == "user":
        context = f"""----- start user instruction -----
    {user_instruction}
    ----- end user instruction -----"""
                
    # For agent faults, do not show the user instruction but show the agent policy
    if author.value == "agent":
        context = f"""----- start agent policy -----
    {agent_policy}
    ----- end agent policy -----"""
        
    # For environment faults, show both the user instruction and the agent policy 
    if author.value == "environment":
        context = f"""----- start user instruction -----
    {user_instruction}
    ----- end user instruction -----
    ----- start agent policy -----
    {agent_policy}
    ----- end agent policy -----"""

    # Add the ground truth outputs
    if ground_truth_outputs:
        context += f"""

----- start required outputs -----
{ground_truth_outputs}
----- end required outputs -----"""

    # Add the ground truth actions, unmatched actions and trajectory
    context += f"""

----- start ground truth action sequence -----
{actions_display}
----- end ground truth action sequence -----

----- start unmatched actions -----
{unmatched_actions_display}
----- end unmatched actions -----

----- start trajectory -----
{traj_display}
----- end trajectory -----\n"""
    return context

def get_fault_assignment_prompt(author: FaultAuthor) -> str:

    prompt = f"Determine if the {author.value} is responsible for the fault in the trajectory."

    if author == FaultAuthor.USER:
        prompt += "You are given a user instruction. The user instruction is the instruction given to the simulated user. The user is responsible for the fault if they fail to understand the correct intents in the user instruction, or provide incomplete or inaccurate information and instructions that are not grounded in the user instruction."

    elif author == FaultAuthor.AGENT:
        prompt += "You are given an agent policy. The agent policy includes a set of rules and best practices based on which the agent operates. The agent is responsible for the fault if they took an action that was not correct or with the wrong arguments, or acted against the rules and best practices in the agent policy."

    else:
        prompt += "The environment is responsible for all other faults besides the user and the agent. The user is responsible for the fault if they provide an ambiguous instruction or do not provide enough information for the agent to complete the task. The agent is responsible for the fault if they fail to follow the rules and best practices in the agent policy, or if they make a mistake in their reasoning or execution of actions. The environment is responsible for all other faults, such as system errors or unexpected behavior that is not caused by the user or the agent. The environment shall not be responsible for the fault if the user instruction is clear and the agent is provided with necessary tools and information to complete the tasks."

    prompt += f'''Return your response as a JSON object with the following format:
{{ 
    "responsible_entity": "{author.value}",
    "is_responsible": "yes" | "no",
    "rationale": "Your detailed reasoning for why the {author.value} is responsible or not responsible for the fault."
}}'''

    return prompt


def display_tool_info(domain: str, for_agent: bool = True) -> str:
    '''
    Display the agent or user tool information for the given domain.
    '''

    tool_info = load_tool_information(domain)

    if for_agent:
        if tool_info['agent_tools']:
            return "\n".join(
                [f"tool_name: {tool['name']}\ntool_type: agent_tool\ndescription: {tool['description']}\nparameters: {json.dumps(tool['parameters'], indent=2)}\n" for tool in tool_info['agent_tools']]
            )
        else:
            return ""
        
    else:
        if tool_info['user_tools']:
            return "\n".join(
                [f"tool_name: {tool['name']}\ntool_type: user_tool\ndescription: {tool['description']}\nparameters: {json.dumps(tool['parameters'], indent=2)}\n" for tool in tool_info['user_tools']]
            )
        else:
            return ""


def get_fault_type_analysis_prompt(fault_assignment_analysis: str, tool_info_str: str, user_or_agent: str) -> str:
    role = user_or_agent
    prompt = f"""
Your task is to determine the type of tool use fault that the {role} made in the trajectory.

The fault types are defined as follows:
- "called_wrong_tool": The {role} called a tool that was not appropriate for the task or the user instruction.
- "used_wrong_tool_argument": The {role} called the correct tool but with an incorrect argument or set of arguments, including wrong argument names or values.
- "used_invalid_format": The {role} used an invalid format for the tool call or the arguments, such as incorrect JSON format or missing required fields.
- "other_tool_use_error": The {role} fault is related to a tool call error, but does not fit into the above categories.
- "other": The fault does not belong to a tool use error, such as a logical error or misunderstanding of the task.

You are given the fault assignment analysis results, which include the reasons why the {role} is responsible for the fault.
=== start fault type analysis ===
{fault_assignment_analysis}
=== end fault type analysis ===

You are also given the list of tools available to the {role} in the domain, which includes the tool names and their descriptions.
=== start tool information ===
{tool_info_str}
=== end tool information ===

Return your response strictly as a JSON object with the following format. Note that the {role} can make multiple faults in the trajectory. Return all the applicable fault types as a list. Make sure the format is correct before returning.
{{
    "fault_type": ["called_wrong_tool" | "used_wrong_tool_argument" | "used_invalid_format" | "other_tool_use_error" | "other"],
    "description": "Your detailed reasoning for why the fault is of the specified type. State clearly which tool are involved and why the mistakes were made."
}} 

"""
    return prompt

def goal_completion_analysis(sim_results: List[SimulationResult], max_concurrency: int, llm_model: str) -> List[GoalCompletionResult]:
    def analyse_goal_completion_status(sim: SimulationResult) -> GoalCompletionResult:
        # Prepare data for the context
        task_id = sim.task_id
        user_instruction = sim.user_instruction
        agent_policy = sim.agent_policy
        traj = sim.traj
        ground_truth_actions = sim.ground_truth_actions
        ground_truth_outputs = sim.ground_truth_outputs

        # Display unmatched actions if any
        if sim.reward_info.action_checks:
            unmatched_actions = [action_check.action for action_check in sim.reward_info.action_checks if not action_check.action_match]
        else:
            unmatched_actions = []

        # Prepare the context description
        ctx_desc = get_context_description()

        # Display the context for the goal completion analysis
        context = display_context(user_instruction=user_instruction,
                                  agent_policy=agent_policy,
                                  ground_truth_actions=ground_truth_actions,
                                  ground_truth_outputs=ground_truth_outputs,
                                  trajectory=traj,
                                  unmatched_actions=unmatched_actions,
                                  author=FaultAuthor.USER)
        
        instruction = f"""{ctx_desc}
Your task is to determine whether the simulated assistant has completed the goal state in the simulated interactive environment with the simulated user. If the Assistant completed the goal state, return "yes". If the assistant did not complete the goal state, return "no".

The user instruction describes the tasks and goals that the assistant and the simulated user should achieve.

The success of the task is determined by whether the assistant has completed the goal state, which is defined as the state where ALL the required tasks have been completed and all the required outputs have been communicated to the user. This is typically achieved when ALL the actions have been executed in the correct order and with the correct arguments.

However, PLEASE NOTE that the ground truth action sequence is one example of a valid sequence that leads to the goal state. It MIGHT NOT be the only valid sequence. For example, the assistant might combine different actions using different arguments or divide one action into multiple sub-actions. As long as the goal state is achieved, the assistant can be considered to have completed the goal state.

Before you answer, list out all the required tasks and sub-tasks in the user instruction. Go through the trajectory step by step and check if the assistant has completed all the required tasks and sub-tasks. Keep this list to yourself and DO NOT include it in the final answer.

Return your final answer as a JSON object with the following format:
{{
    "rationale": "Your detailed reasoning for why the goal state was completed or not completed.",
    "goal_completed": "yes" | "no"
}}"""
        
        # print(f"DEBUG full instruction: \n============\n{instruction}\n============\n")
        # print(f"DEBUG full context: \n============\n{context}\n============\n")

        res = litellm.completion(
            model=llm_model,
            messages=[{"role": "system", "content": instruction},
                      {"role": "user", "content": context}],
            custom_llm_provider = "openai"
        )

        response = res.choices[0].message.content
        try:
            # Parse the JSON response
            result_json = json.loads(response.strip('```json')) #Gemini sometimes returns code blocks with ```json
            rationale = result_json.get("rationale", "No rationale provided")
            goal_completed = result_json.get("goal_completed", "no").lower()
            
            # Convert string to boolean
            goal_completed_bool = goal_completed == "yes"
            
        except (json.JSONDecodeError, KeyError) as e:
            rationale = f"Error parsing response: {str(e)}. Original response: {response}"
            goal_completed_bool = False
            
        return GoalCompletionResult(task_id=task_id, goal_completed=goal_completed_bool, rationale=rationale)
            
    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        results = list(tqdm(
            executor.map(analyse_goal_completion_status, sim_results),
            total=len(sim_results),
            desc="Analyzing goal completion status"
        ))
    return results


def fault_assignment_analysis(sim_results: List[SimulationResult], max_concurrency: int, llm_model: str, goal_completion_results: Optional[List[GoalCompletionResult]]) -> List[FaultAssignmentResult]:

    def assign_fault(sim: SimulationResult, goal_completion_context: Optional[str]) -> FaultAssignmentResult:
        str_to_author = {
            "user": FaultAuthor.USER,
            "agent": FaultAuthor.AGENT,
            "environment": FaultAuthor.ENVIRONMENT,
        }

        # Prepare data for the context
        task_id = sim.task_id
        user_instruction = sim.user_instruction
        agent_policy = sim.agent_policy
        traj = sim.traj
        ground_truth_actions = sim.ground_truth_actions
        ground_truth_outputs = sim.ground_truth_outputs

        # Display unmatched actions if any
        if sim.reward_info.action_checks:
            unmatched_actions = [action_check.action for action_check in sim.reward_info.action_checks if not action_check.action_match]
            # if unmatched_actions:
            #     print(f"DEBUG: Unmatched actions for task {task_id}:\n{unmatched_actions}")
        else:
            unmatched_actions = []

   
        ctx_desc = get_context_description()
        if goal_completion_context:
            ctx_desc += f'''\nYou are also given an additional analysis on whether the agent has completed the goal state. 
            Note that although the trajectory is determined to have a fault, the ground truth sequence may not be the only valid sequence to the goal state.
            {goal_completion_context}
            '''
        
        # Assign fault by author
        author_list = []
        rationale_list = []
        for author in FaultAuthor:
            context = display_context(user_instruction = user_instruction, 
                                      agent_policy=agent_policy, 
                                      ground_truth_actions = ground_truth_actions, 
                                      ground_truth_outputs = ground_truth_outputs, 
                                      trajectory= traj, 
                                      author = author,
                                      unmatched_actions = unmatched_actions)

            assignment_prompt = ctx_desc + get_fault_assignment_prompt(author)
            # print(f"DEBUG {author.value}_PROMPT:\n", assignment_prompt)
            # if author == FaultAuthor.AGENT: 
            #     print(f"DEBUG agent context: \n============\n{context}\n============\n")

            res = litellm.completion(
                model=llm_model,
                messages=[{"role": "system", "content": assignment_prompt},
                          {"role": "user", "content": context}],
                custom_llm_provider = "openai"
            )

            response = res.choices[0].message.content

            try:
                # Parse the JSON response
                result_json = json.loads(response.strip('```json')) #Gemini sometimes returns code blocks with ```json
                rationale = result_json.get("rationale", "No rationale provided")
                is_faulty = result_json.get("is_responsible", "no").lower() == "yes"
                responsible_entity = result_json.get("responsible_entity", "environment").lower()
                
                # Map string to enum, default to environment if invalid
                author = str_to_author.get(responsible_entity, FaultAuthor.ENVIRONMENT)
                
            except (json.JSONDecodeError, KeyError) as e:
                # Fallback: if JSON parsing fails, default to environment with error message
                author = FaultAuthor.ENVIRONMENT
                rationale = f"Error parsing response: {str(e)}. Original response: {response}"
                is_faulty = False  # Default to not faulty if parsing fails
                author = FaultAuthor.ENVIRONMENT  # Default to environment if parsing fails          
            # If the author is responsible for the fault, append to the lists
            if is_faulty:
                author_list.append(author)
            rationale_list.append(rationale)
            
        return FaultAssignmentResult(task_id=task_id, authors=author_list, descriptions=rationale_list)

    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        if len(goal_completion_results)>0:
            goal_completion_context = [f"Completion Status: {'Task goal completed.' if r.goal_completed else 'Task goal not completed.'}\nRationale: {r.rationale}" for r in goal_completion_results]
        else:
            goal_completion_context = ["" for _ in sim_results]  # Empty context if no goal completion results
        results = list(tqdm(
            executor.map(assign_fault, sim_results, goal_completion_context),
            total=len(sim_results),
            desc="Analysing fault assignments"
        ))

    return results


def fault_type_analysis(sim_results: List[SimulationResult], faults_analysis: Optional[List[FaultAssignmentResult]], tool_info_str: str, max_concurrency: int, llm_model: str, user_or_agent: str) -> List[FaultTypeResult]:
    """
    Analyze the fault type for each simulation result using a large language model (LLM).
    Args:
        results: List of SimulationResult objects containing the simulation results.
        max_concurrency: Maximum number of concurrent API calls.
        llm_model: The LLM model to use for analysis.
    Returns:
        List of FaultTypeResult objects containing the fault type analysis results.
    """

    def analyse_fault_type(sim: SimulationResult, fault_analysis: Optional[FaultAssignmentResult]) -> FaultTypeResult:
        str_to_fault_type = {
            "other_tool_use_error": FaultType.OTHER_TOOL_USE_ERROR,
            "called_wrong_tool": FaultType.CALLED_WRONG_TOOL,
            "used_wrong_tool_argument": FaultType.USED_WRONG_TOOL_ARGUMENT,
            "used_invalid_format": FaultType.USED_INVALID_FORMAT,
            "other": FaultType.OTHER,
        }

        # Prepare data for the context
        task_id = sim.task_id
        user_instruction = sim.user_instruction
        agent_policy = sim.agent_policy
        traj = sim.traj
        ground_truth_actions = sim.ground_truth_actions
        ground_truth_outputs = sim.ground_truth_outputs

        # Display unmatched actions if any
        if sim.reward_info.action_checks:
            unmatched_actions = [action_check.action for action_check in sim.reward_info.action_checks if not action_check.action_match]
            # if unmatched_actions:
            #     print(f"DEBUG: Unmatched actions for task {task_id}:\n{unmatched_actions}")
        else:
            unmatched_actions = []

        ctx_desc = get_context_description()

        # If fault_analysis is provided, use its rationale for the context
        if fault_analysis:
            if user_or_agent == "user":
                fault_assignment_rationale = fault_analysis.descriptions[0]  # Use the first description for user faults
            else:
                fault_assignment_rationale = fault_analysis.descriptions[1]
        else:
            fault_assignment_rationale = ""
        
        # Display the context for the fault type analysis
        if user_or_agent == "user":
            author = FaultAuthor.USER
        elif user_or_agent == "agent":
            author = FaultAuthor.AGENT
        else:
            raise ValueError("user_or_agent must be either 'user' or 'agent'")

        context = display_context(user_instruction = user_instruction, 
                                  agent_policy=agent_policy, 
                                  ground_truth_actions = ground_truth_actions, 
                                  ground_truth_outputs = ground_truth_outputs, 
                                  trajectory= traj, 
                                  unmatched_actions = unmatched_actions,
                                  author = author)

        fault_type_prompt = ctx_desc + get_fault_type_analysis_prompt(fault_assignment_rationale, tool_info_str, user_or_agent)


        res = litellm.completion(
            model=llm_model,
            messages=[{"role": "system", "content": fault_type_prompt},
                      {"role": "user", "content": context}],
            custom_llm_provider = "openai"
        )

        response = res.choices[0].message.content

        try:
                # Parse the JSON response
                result_json = json.loads(response.strip('```json')) #Gemini sometimes returns code blocks with ```json
                description = result_json.get("description", "No description provided")
                fault_type_list = result_json.get("fault_type", ["other"])
                if not isinstance(fault_type_list, list):
                    raise TypeError(f"Fault type should be a list (Expected list, got {type(fault_type_list).__name__})")
                fault_types = [str_to_fault_type.get(ft, FaultType.OTHER) for ft in fault_type_list]

        except (json.JSONDecodeError, KeyError) as e:
                # Fallback: if JSON parsing fails, default to other with error message
                fault_types = [FaultType.OTHER]  # Default to other if parsing fails
                description = f"Error parsing response: {str(e)}. Original response: {response}"

        except TypeError as e:
            # Handle case where fault_type is not a list
            print(f"Type error: {e}")
            fault_types = [FaultType.OTHER]
            description = f"Error in fault type format: {str(e)}. Original response: {response}"


        return FaultTypeResult(task_id=task_id, fault_types=fault_types, description=description)

    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        results = list(tqdm(
            executor.map(analyse_fault_type, sim_results, faults_analysis),
            total=len(sim_results),
            desc="Analyzing fault types"
        ))
    return results


def prepare_simulation_results(file_path: str, task_ids: Optional[list[str]], max_num_failed_results: Optional[int]) -> List[SimulationResult]:
    """
    Prepare the failed simulation results.
    
    Args:
        file_path: Path to the results file.

    Returns:
        List of SimulationResult objects containing the simulation results.
    """
    simulation_results = []

    # Load the results file
    with open(file_path, 'r') as file:
        json_data = json.load(file)

    results = Results.model_validate(json_data, from_attributes=True)


    simulation_info = results.info
    for sim in results.simulations:
        if not is_successful(sim.reward_info.reward):  # Filter failed simulations
            task = next((t for t in results.tasks if t.id == sim.task_id), None)
            if not task:
                print(f"Warning: Task {sim.task_id} not found in results.tasks")
                continue
            task_id = task.id
            user_instruction = str(task.user_scenario) if task.user_scenario else "No user scenario available"
            agent_policy = str(simulation_info.environment_info.policy) if simulation_info.environment_info.policy else "No policy available"

            # Append the task and simulation run
            simulation_results.append(SimulationResult.model_validate({
                'domain': simulation_info.environment_info.domain_name,
                'task_id': task_id,
                'user_instruction': user_instruction,
                'agent_policy': agent_policy,
                'traj': sim.messages,
                'ground_truth_actions': task.evaluation_criteria.actions,
                'ground_truth_outputs': task.evaluation_criteria.communicate_info,
                'reward_info': sim.reward_info
            }, from_attributes=True))  # Use model_validate to ensure correct types and skip validation

    # Filter by task IDs if specified
    if task_ids:
        task_id_set = set(str(tid) for tid in task_ids)
        simulation_results = [res for res in simulation_results if str(res.task_id) in task_id_set]


    # Limit the number of failed simulations if specified
    if max_num_failed_results:
        if max_num_failed_results == 0:
            # analyze all failed results
            print("No limit on the number of failed results to analyze")
            pass
        elif len(simulation_results) > max_num_failed_results:
            simulation_results = simulation_results[:max_num_failed_results]
            print(f"Limited to {len(simulation_results)} failed simulations for analysis")

    # Check if any failed simulation runs were found
    if not simulation_results:
        print("No failed simulation runs found for the specified task IDs")
        return [], []
    
    else:
        print(f"Found {len(simulation_results)} failed simulation runs out of {len(results.simulations)} total")
        return simulation_results


def main():
    from pathlib import Path
    args = get_args()
    domain = args.env
    file_path = Path(args.results_path)
    task_ids = args.task_ids or []
    max_num_failed_results = args.max_num_failed_results or None
    model_name = args.model


    # Prepare failed simulation results
    simulation_results = prepare_simulation_results(
        file_path=file_path,
        task_ids=task_ids,
        max_num_failed_results=max_num_failed_results
    )


    ## DEBUG: print the display action of the first simulation result
    # if len(simulation_results) > 0:
        # print(f"DEBUG: First simulation result actions:\n{display_actions(simulation_results[0].ground_truth_actions)}")
        # print(f"DEBUG: First simulation result unmatched actions:\n{display_actions([action_check.action for action_check in simulation_results[0].reward_info.action_checks if not action_check.action_match])}")
        # print(f"DEBUG: First simulation result trajectory:\n{display_traj(simulation_results[0].traj)}")
        # print(f"DEBUG: First simulation result user instruction:\n{simulation_results[0].user_instruction}")
        # print(f"DEBUG: First simulation result agent policy:\n{simulation_results[0].agent_policy}")

    # exit(0)  # Exit early for debugging

    # Check if any failed simulation runs were found
    if not simulation_results:
        print("No failed results to analyze")
        return

    print(f"Analyzing {len(simulation_results)} failed results...")

    # Get agent policy from environment info
    
    # Perform analyses
    print("Performing goal completion analysis...")
    goal_completion_results = goal_completion_analysis(
        simulation_results,
        max_concurrency=args.max_concurrency,
        llm_model = model_name,
    )
    print(f"Goal completion analysis complete.")

    print("Performing fault assignment analysis...")
    fault_assignment_results = fault_assignment_analysis(
        simulation_results,
        max_concurrency=args.max_concurrency,
        llm_model=model_name,
        goal_completion_results=goal_completion_results
    )

    print("Performing fault type analysis...")
    # Filter to only agent faults for fault type analysis
    agent_faults_analysis = []
    for i, result in enumerate(fault_assignment_results):
        if FaultAuthor.AGENT in result.authors:
            agent_faults_analysis.append(fault_assignment_results[i])
    failed_results_due_to_agent = [simulation_results[i] for i, r in enumerate(fault_assignment_results) if FaultAuthor.AGENT in r.authors] 

    agent_tool_info_str = display_tool_info(domain, for_agent=True)

    agent_fault_type_results = fault_type_analysis(
        failed_results_due_to_agent,
        max_concurrency=args.max_concurrency,
        faults_analysis=agent_faults_analysis,
        tool_info_str=agent_tool_info_str,
        llm_model=model_name, 
        user_or_agent="agent",
    )

    print("Performing user fault type analysis...")
    user_tool_info_str = display_tool_info(domain, for_agent=False)

    print(f"User tool info:\n{user_tool_info_str}\n")

    if user_tool_info_str:
        # Filter to only user faults for fault type analysis
        user_faults_analysis = []
        for i, result in enumerate(fault_assignment_results):
            if FaultAuthor.USER in result.authors:
                user_faults_analysis.append(fault_assignment_results[i])
        failed_results_due_to_user = [simulation_results[i] for i, r in enumerate(fault_assignment_results) if FaultAuthor.USER in r.authors]

        user_fault_type_results = fault_type_analysis(
            failed_results_due_to_user,
            max_concurrency=args.max_concurrency,
            faults_analysis=user_faults_analysis,
            tool_info_str=user_tool_info_str,
            llm_model=model_name,
            user_or_agent="user",
        )
    else:
        user_fault_type_results = []
        print("No user tools available for fault type analysis.")

    # Prepare output data
    output_data = {
        "goal_completion_analysis": [result.model_dump() for result in goal_completion_results],
        "fault_assignment_analysis": [result.model_dump() for result in fault_assignment_results],
        "agent_fault_type_analysis": [result.model_dump() for result in agent_fault_type_results],
        "user_fault_type_analysis": [result.model_dump() for result in user_fault_type_results]
    }

    # Save results to output file
    with open(args.output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"Analysis complete. Results saved to {args.output_path}")
    
    # Print summary statistics
    completed_goals = sum(1 for r in goal_completion_results if r.goal_completed)
    print(f"Goal completion: {completed_goals}/{len(goal_completion_results)} ({completed_goals/len(goal_completion_results)*100:.1f}%)")
    
    fault_counts = {}
    for result in fault_assignment_results:
        for author in result.authors:
            fault_counts[author.value] = fault_counts.get(author.value, 0) + 1
    print("Fault assignment:", fault_counts)
    
    if agent_fault_type_results:
        type_counts = {}
        for result in agent_fault_type_results:
            for fault_type in result.fault_types:
                type_counts[fault_type.value] = type_counts.get(fault_type.value, 0) + 1
        print("Agent Fault types:", type_counts)

    if user_fault_type_results:
        user_type_counts = {}
        for result in user_fault_type_results:
            for fault_type in result.fault_types:
                user_type_counts[fault_type.value] = user_type_counts.get(fault_type.value, 0) + 1
        print("User Fault types:", user_type_counts)

if __name__ == "__main__":
    # domain = 'airline'
    # user_tool_info_str = display_tool_info(domain, for_agent=False)
    # if user_tool_info_str:
    #     print(f"User tool info for {domain}:\n{user_tool_info_str}\n")
    # if user_tool_info_str:
    #     # Filter to only user faults for fault type analysis
    #     user_faults_analysis = []
    #     for i, result in enumerate(fault_assignment_results):
    #         if FaultAuthor.USER in result.authors:
    #             user_faults_analysis.append(fault_assignment_results[i])
    #     failed_results_due_to_user = [simulation_results[i] for i, r in enumerate(fault_assignment_results) if FaultAuthor.USER in r.authors]
    main()