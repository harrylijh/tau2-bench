import litellm
import json
import os
import sys
from typing import Optional, List, Dict
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))


from src.tau2.domains.retail.tools import RetailTools
from src.tau2.domains.airline.tools import AirlineTools
from src.tau2.domains.telecom.tools import TelecomTools
from src.tau2.domains.telecom.user_tools import TelecomUserTools


LLM_MODEL = "gpt-4.1" 
TOOL_PROMPT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data/tau2/tool_prompts")


def load_tool_information(domain: str):
    """
    Load tool information for the specified domain.
    
    Args:
        domain (str): The domain for which to load tool information.
        
    Returns:
        list: A list of tool information dictionaries.
    """
    mock_db = None
    tool_info = {'agent_tools': [], 'user_tools': []}
    if domain == "retail":
        tools = RetailTools(mock_db).get_tools()
        for name, tool in tools.items():
            tool_info['agent_tools'].append(tool.openai_schema['function'])
        return tool_info
    elif domain == "airline":
        tools = AirlineTools(mock_db).get_tools()
        for name, tool in tools.items():
            tool_info['agent_tools'].append(tool.openai_schema['function'])
        return tool_info
    elif domain == "telecom":
        tools = TelecomTools(mock_db).get_tools()
        user_tools = TelecomUserTools(mock_db).get_tools()
        for name, tool in tools.items():
            tool_info['agent_tools'].append(tool.openai_schema['function'])
        for name, tool in user_tools.items():
            tool_info['user_tools'].append(tool.openai_schema['function'])
        return tool_info
    else:
        raise ValueError(f"Unknown domain: {domain}")


def load_tool_error_analysis(file_path: str, for_agent: bool) -> str:
    """
    Load tool error analysis from a JSON file.
    
    Args:
        file_path (Path): The path to the JSON file containing error analysis.
        
    Returns:
        dict: The loaded error analysis data.
    """
    # check if error_file_path exists
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Error file not found: {file_path}")
    
    with open(file_path, 'r') as f:
        error_analysis = json.load(f)
    
    # fault_assignment_analysis = error_analysis['fault_assignment_analysis']
    if for_agent:
        fault_type_analysis = error_analysis['agent_fault_type_analysis']
    else:
        fault_type_analysis = error_analysis['user_fault_type_analysis']

    # filter out the tool errors
    tools_errors_list =[]

    for e in fault_type_analysis:
        tools_errors_list.append({
            "task_id": e['task_id'],
            "fault_type": e['fault_types'],
            "tool_error_description": e['description'],
        })

    # convert tools_errors_list to a string for better readability
    tools_errors_str = "\n".join([f"Task ID: {e['task_id']}\nFault Type: {', '.join(e['fault_type'])}\nTool Error Description: {e['tool_error_description']}\n" for e in tools_errors_list])
    
    return tools_errors_str

def get_prompt_template(tool_info: Dict, tool_error_str: str, for_agent: bool) -> str:

    tool_info_str = ""
    if for_agent:
        if tool_info['agent_tools']:
            tool_info_str = "\n".join(
                [f"tool_name: {tool['name']}\ntool_type: agent_tool\ndescription: {tool['description']}\nparameters: {json.dumps(tool['parameters'], indent=2)}\n" for tool in tool_info['agent_tools']]
            )
    else:
        if tool_info['user_tools']:
            tool_info_str = "\n".join(
                [f"tool_name: {tool['name']}\ntool_type: user_tool\ndescription: {tool['description']}\nparameters: {json.dumps(tool['parameters'], indent=2)}\n" for tool in tool_info['user_tools']]
            )

    prompt = f'''
## Instructions

You are an expert in analyzing the tool use errors and suggesting improved prompt instructions for the tools involved.
- You are given a list of tool errors that occurred during the evaluation of a customer service agent. You are also given the list of available tools with the tool information and the parameters.

- Your task is to read the error analysis and summarize the common patterns and persistant issues with a certain tool call. Focus on the specific issues identified in the errors and write a prompt on how the agent can be guided with prompts to prevent similar issues in the future.

- The prompt should be structured in a way that it can be used by the agent to understand when to call the tool, what parameters are required, and how to handle common errors. You may include examples of correct usage of the tool and common mistakes to avoid.

- The improved prompts should be clear, concise and provide sufficient detail to help the agent understand when to call the tool and how to use the tool with correct parameters.

- The tools information is provided in the `tools_information` section. You should only generate tool prompts for tools listed in the `tools_information section. Do not make up any new tool names.

## Example:

==== start of tool prompt ====
Tool Prompt for modify_pending_order_address

## When to call the tool
- Use this tool only when a user requests to change the shipping address for a pending order. Confirm that the order status is 'pending' before proceeding. If the order is not pending, inform the user that the address cannot be modified.

## Before calling the tool
Required Parameters: You must provide the following parameters when calling the tool:
- `order_id`: The unique identifier for the order whose address you want to modify.
- `new_address`: The new shipping address to which the order should be sent.

Retrieving Missing Parameters: 
- If you do not have the `order_id`, authenticate the user by locating their user ID via email or by using their name and zip code. Once authenticated, you can retrieve the order details, including the `order_id`, by calling the `get_order_details` tool.
- Ensure you confirm the new address with the user before proceeding.

User Confirmation: Before making the tool call, clearly explain the modification details to the user and ask for explicit confirmation (yes/no) to proceed with the address change. For example, you might say, "I will change the shipping address for your order #W00011122 to [new address]. Do you confirm this change?"

Avoiding Common Errors:
- Always check the order status using `get_order_details` before calling the tool to ensure the order is pending.
- Do not confuse this tool with `modify_user_address`, which changes the default address in the user profile. Ensure you are modifying the address for the specific order.
- If the user has multiple orders that need address changes, iterate through each order and confirm the address change for each one, rather than stopping after the first order.

## After calling the tool
- Handling Tool Output: After calling the tool, verify the response to ensure the address was successfully updated. Communicate the new address back to the user, confirming the change. For example, say, "Your order #W00011122 has been updated to ship to [new address]." If there was an error, inform the user appropriately.

==== end of tool prompt ====

## Output Format
Return ONLY the tool names and the tool prompts in the following JSON format. Do not include any other information or commentary. Include all the tools that you think need improved prompts in you JSON response.
IMPORTANT: Ensure the JSON is valid and properly formatted. If you encounter any issues with the JSON formatting, please fix them before returning the response.

{{
    "exchange_delivered_order_item": "tool prompt for the tool",
    "modify_pending_order_address": "tool prompt for the tool",
    ......
}}
'''
    context = f'''
## Context

==== start of tool errors ====
{tool_error_str}
==== end of tool errors ====

==== start of tools information ====
{tool_info_str}
==== end of tools information ====
    '''
    return prompt, context

def save_tool_prompts(tool_prompts: Dict, domain: str) -> None:
    """
    Save tool prompts to markdown files in the specified directory structure.
    
    Args:
        tool_prompt_dict: Dictionary containing tool names as keys and tool data as values
        domain: Domain name (e.g., 'airline', 'telecom')
        base_dir: Base directory for saving tool prompts (default: "data/tau2/tool_prompts")
    """
    from pathlib import Path
    
    if tool_prompts['agent_tools'] == {} and tool_prompts['user_tools'] == {}:
        print(f"No tool prompts found for domain: {domain}")
        return
    
    # Create the directory structure
    base_dir = TOOL_PROMPT_DIR
    domain_dir = Path(base_dir) / domain
    if not domain_dir.exists():
        domain_dir.mkdir(parents=True, exist_ok=True)

    
    if tool_prompts['agent_tools']:

        # Save each tool prompt as a markdown file
        for tool_name, tool_prompt_content in tool_prompts['agent_tools'].items():
            
            # Create filename (sanitize tool name for filesystem)
            safe_tool_name = tool_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
            filename = f"{safe_tool_name}.md"
            file_path = domain_dir / filename
            
            # Write the tool prompt to the markdown file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# {tool_name}\n\n")
                f.write(tool_prompt_content)

    if tool_prompts['user_tools']:
        # Save each tool prompt as a markdown file
        for tool_name, tool_prompt_content in tool_prompts['user_tools'].items():
            
            # Create filename (sanitize tool name for filesystem)
            safe_tool_name = tool_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
            filename = f"{safe_tool_name}.md"
            file_path = domain_dir / filename
            
            # Write the tool prompt to the markdown file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# {tool_name}\n\n")
                f.write(tool_prompt_content)

    print(f"Saved {len(tool_prompts['agent_tools'])} agent tool and {len(tool_prompts['user_tools'])} user tool prompts for '{domain}'")

def clean_json_string(json_str):
    """
    Clean a JSON string by escaping control characters that cause parsing errors.
    
    Args:
        json_str (str): The JSON string to clean
        
    Returns:
        str: Cleaned JSON string that can be safely parsed
    """
    # Replace common control characters with their escape sequences
    replacements = {
        '\n': '\\n',      # newline
        '\r': '\\r',      # carriage return
        '\t': '\\t',      # tab
        '\b': '\\b',      # backspace
        '\f': '\\f',      # form feed
    }
    
    # Apply replacements only within string values (between quotes)
    cleaned = json_str
    for char, escape in replacements.items():
        cleaned = cleaned.replace(char, escape)
    
    return cleaned


def generate_tool_prompt(domain: str, error_file_path: str, model_name: str = LLM_MODEL) -> Dict[str, Dict]:
    """
    Generate tool prompt for the specified domain.
    
    Args:
        domain (str): The domain for which to generate the tool prompt.
        
    Returns:
        str: The generated tool prompt.
    """

    # Load tool information
    tool_info = load_tool_information(domain)

    tool_prompts = {'agent_tools': {}, 'user_tools': {}}
    if not tool_info['agent_tools'] and not tool_info['user_tools']:
        raise ValueError(f"No tools found for domain: {domain}")
    
    if tool_info['agent_tools']:
        #Load tool error analysis for agent tools
        tool_error_str = load_tool_error_analysis(error_file_path, for_agent=True)
        prompt, context = get_prompt_template(tool_info, tool_error_str, for_agent=True)

        res = litellm.completion(
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": context},
            ],
            model = model_name,
            custom_llm_provider = "openai"
        ) 
        response = res.choices[0].message['content'].strip('```json').strip('```').strip()


        try:
            tool_prompts['agent_tools'] = json.loads(response)
        except json.JSONDecodeError as e:
            cleaned_response = clean_json_string(response)
            try:
                tool_prompts['agent_tools'] = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON response for agent tools: {e}")
                print(f"Response content: {response}")
                raise

    if tool_info['user_tools']:
        #Load tool error analysis
        tool_error_str = load_tool_error_analysis(error_file_path, for_agent=False)
        prompt, context = get_prompt_template(tool_info, tool_error_str, for_agent=False)

        res = litellm.completion(
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": context},
            ],
            model = model_name,
            custom_llm_provider = "openai"
        ) 
        response = res.choices[0].message['content'].strip('```json').strip('```').strip()
        try:
            tool_prompts['user_tools'] = json.loads(response)
        except json.JSONDecodeError as e:
            try:
                cleaned_response = clean_json_string(response)
                tool_prompts['user_tools'] = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON response for user tools: {e}")
                print(f"Response content: {response}")
                raise


    # Save the tool prompts to markdown files
    save_tool_prompts(tool_prompts, domain)
    return tool_prompts

if __name__ == "__main__":
    # Example usage
    domain = "retail"  # Change to "airline" or "telecom" as needed
    tool_info = load_tool_information(domain)
    print(json.dumps(tool_info, indent=2))