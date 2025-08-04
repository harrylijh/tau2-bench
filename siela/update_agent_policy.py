import litellm
import json
import os
from typing import Optional, List

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data/tau2/domains")
LLM_MODEL = "gpt-4.1" 
POLICY_BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data/tau2/original_policies")


def update_agent_policy(error_analysis_file: str, domain: str, model_name: str = LLM_MODEL):
    """
    Update the agent policy using error analysis results.
    """
    # Load the error analysis results
    error_analysis_results = load_error_analysis_results(error_analysis_file)

    # load the original agent policy
    original_policy = load_agent_policy(domain)
    if not original_policy:
        raise ValueError("Original agent policy could not be loaded.")
    
    # Update the agent policy based on the error analysis results
    new_policy = create_updated_policy(
        error_analysis_results, 
        original_policy,
        domain,
        model_name
    )

    # Save the updated agent policy
    save_updated_policy(new_policy, domain)

    return new_policy

def load_error_analysis_results(file_path: str) -> str:
    """
    Load error analysis results from a json file into a JSON object.
    Args:
        file_path (str): Path to the error analysis file.
    Returns:
        dict: Parsed JSON object containing error analysis results.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Error analysis file {file_path} does not exist.")
    
    with open(file_path, 'r') as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding JSON from {file_path}: {e}")
    
    agent_faults = [['task_id: '+str(e['task_id']), e['description'][1]] for e in data['fault_assignment_analysis'] if 'agent'in e['author']]
    
    return "\n".join([f"{e[0]}: {e[1]}" for e in agent_faults])


def load_agent_policy(domain: str) -> str:
    """
    Load the original agent policy for a specific domain.
    """
    # TODO: implement the logic to load the agent policy for 'workflow' and 'solo' modes

    main_policy = ""
    tech_support_policy = ""

    if domain == "retail" or domain == "airline":
        main_policy_path = os.path.join(DATA_DIR, domain, "policy.md")
        if not os.path.exists(main_policy_path):
            raise FileNotFoundError(f"Agent policy file {main_policy_path} does not exist.")

        with open(main_policy_path, 'r') as file:
            main_policy = file.read()
        
        policy = "<main_policy>\n" + main_policy + "\n</main_policy>"
        print(f"Agent policy loaded for {domain} domain.")
        return policy

    if domain == "telecom":
        main_policy_path = os.path.join(DATA_DIR, domain, "main_policy.md")
        tech_support_policy_path = os.path.join(DATA_DIR, domain, "tech_support_manual.md")
        if not os.path.exists(main_policy_path):
            raise FileNotFoundError(f"Agent policy file {main_policy_path} does not exist.")

        with open(main_policy_path, 'r') as file:
            main_policy = file.read()
        with open(tech_support_policy_path, 'r') as file:
            tech_support_policy = file.read()

        policy = ("<main_policy>\n"
        + main_policy
        + "\n</main_policy>\n"
        + "<tech_support_policy>\n"
        + tech_support_policy
        + "\n</tech_support_policy>"
        )
    
        print(f"Agent policy loaded for {domain} domain.")
        return policy


def create_updated_policy(error_analysis_results: dict, agent_policy: str, domain: str, model_name: str) -> List[str]:
    """
    Create an updated agent policy based on error analysis results.
    Args:
        error_analysis_results (dict): Parsed JSON object containing error analysis results.
        agent_policy (str): Original agent policy.
    Returns:
        str: Updated agent policy.
    """
    prompt = get_prompt_template(domain)

    res = litellm.completion(
        messages = [
            {"role": "user", "content": prompt.format(
                policy=agent_policy, 
                fault_analysis=error_analysis_results,
                domain=domain
                )},
        ],
        model = model_name,
        custom_llm_provider = "azure"
    )
    if domain == "retail" or domain == "airline":
        try:
            updated_policy = res["choices"][0]["message"]["content"].strip()
            return [updated_policy]
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding JSON response: {e}")


    if domain == "telecom":
        try:
            updated_policy = json.loads(res["choices"][0]["message"]["content"].strip("```json").strip("```"))
            return [updated_policy["main_policy"], updated_policy["tech_support_policy"]]
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding JSON response: {e}")




def get_prompt_template(domain: str) -> str:
    """
    Get the prompt template for updating the agent policy.
    """
    ### TODO: Implement the logic to return the correct prompt template for workflow and solo modes

    if domain == "retail" or domain == "airline":
        return '''
# Instructions
You are an agent responsible for improving the quality of the policy instructions provided to a customer service LLM agent in {domain} domain. Your goal is to enhance these policy instructions so the agent can avoid similar errors and perform more accurately on test cases, while adhering strictly to the original policy.

## Criteria
- You will be provided with the agent policy and the fault analysis on the test cases where the current policy failed. 
- Your first task is to summarize the common patterns of agent faults based on the provided fault analysis results. 
- Use the results to understand the specific agent behaviors that led to the mistakes. For instance, if the agent failed to gather a required value or confirmation before the next action, update the routine to include this step. Or if the agent failed to understand some underlying system constraints, update the routine to clarify these constraints.
- Thoroughly go through the existing policy and use your insights to improve it accordingly. Add any missing steps or clarifications that would help the agent avoid these mistakes in the future. You can use step-by-step instructions and examples to improve clarity and structure.
- Do not remove any existing instructions or constraints from the original policy. Ensure that your improvements remain compliant with the original policy.

## Output Requirements
Return only the agent policy. Do not include the thought process or any additional commentary.

You will be provided with:
1) The ground-truth policy for the customer service agent containing detailed instructions.
2) The fault analysis results that show the agent's faults using this policy routine.

# Context Data

## 1. Original policy
{policy}

## 2. Fault analysis results
{fault_analysis}
'''
    
    elif domain == "telecom":
#          return '''
# # # Instructions
# # You are an agent responsible for improving the quality of the policy instructions provided to a customer service LLM agent in {domain} domain. Your goal is to enhance these policy instructions so the agent can avoid similar errors and perform more accurately on test cases, while adhering strictly to the original policy.

# # ## Criteria
# # - You will be provided with the main agent policy, the technical support policy and the fault analysis on the test cases where the current policy failed. 
# # - Your first task is to summarize the common patterns of agent faults based on the provided fault analysis results. 
# # - Use the results to understand the specific agent behaviors that led to the mistakes. For instance, if the agent failed to gather a required value before calling a function, update the routine to include this step. Or if the agent failed to understand some underlying system constraints, update the routine to clarify these constraints.
# # - Thoroughly go through the existing policy and use your insights to improve it accordingly. Add any missing steps or clarifications that would help the agent avoid these mistakes in the future. You may reformat the routine if necessary and use step-by-step instructions and examples to improve clarity and structure.
# # - Do not remove any existing instructions or constraints from the original policy. Ensure that your improvements remain compliant with the original policy.

# # ## Output Requirements
# # Return only the main agent policy and the technical support policy in the following JSON format. Do not include the thought process or any additional commentary.

# # {{
# #     "main_policy": "<updated_main_policy>",
# #     "tech_support_policy": "<updated_tech_support_policy>"
# # }}


# # You will be provided with:
# # 1) The ground-truth policy for the customer service agent containing detailed instructions.
# # 2) The fault analysis results that show the agent's faults using this policy routine.

# # # Context Data

# # ## 1. Original policy
# # {policy}

# # ## 2. Fault analysis results
# # {fault_analysis}
# # '''
        return '''
# Instructions
You are an agent responsible for improving the quality of the policy instructions provided to a customer service LLM agent in {domain} domain. Your goal is to enhance these policy instructions so the agent can avoid similar errors and perform more accurately on test cases, while adhering strictly to the original policy.

## Criteria
- You will be provided with the main agent policy, the technical support policy and the fault analysis on the test cases where the current policy failed. 
- Your first task is to summarize the common patterns of agent faults based on the provided fault analysis results. 
- Use the results to understand the specific agent behaviors that led to the mistakes. For instance, if the agent failed to gather a required value before calling a function, update the routine to include this step. Or if the agent failed to understand some underlying system constraints, update the routine to clarify these constraints.
- Thoroughly go through the existing policy and use your insights to improve it accordingly. Add any missing steps or clarifications that would help the agent avoid these mistakes in the future. You may reformat the routine if necessary and use step-by-step instructions and examples to improve clarity and structure.
- Do not remove any existing instructions or constraints from the original policy. Ensure that your improvements remain compliant with the original policy.

## Output Requirements
Return only the main agent policy and the technical support policy in the following JSON format. Do not include the thought process or any additional commentary.

{{
    "main_policy": "<updated_main_policy>",
    "tech_support_policy": "<updated_tech_support_policy>"
}}


You will be provided with:
1) The ground-truth policy for the customer service agent containing detailed instructions.
2) The fault analysis results that show the agent's faults using this policy routine.

# Context Data

## 1. Original policy
{policy}

## 2. Fault analysis results
{fault_analysis}
'''

def save_updated_policy(updated_policy: List[str], domain: str):
    """
    Save the updated agent policy to a file.
    """
    from datetime import datetime
    time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if len(updated_policy) == 1:         # For retail and airline, save as a single file
        # create backup with time stamp if it exists
        if not os.path.exists(POLICY_BACKUP_DIR):
            os.makedirs(POLICY_BACKUP_DIR)
        backup_path = os.path.join(POLICY_BACKUP_DIR, f"{domain}/policy_backup_{time_stamp}.md")
        if os.path.exists(os.path.join(DATA_DIR, f"{domain}/policy.md")):
            os.rename(os.path.join(DATA_DIR, f"{domain}/policy.md"), backup_path)
        with open(os.path.join(DATA_DIR, f"{domain}/policy.md"), 'w') as file:
            file.write(updated_policy[0])
    
    elif len(updated_policy) == 2:         # For telecom, save policies separately
        # create backup if it exists
        backup_main_path = os.path.join(POLICY_BACKUP_DIR, f"{domain}/main_policy_backup_{time_stamp}.md")
        backup_tech_support_path = os.path.join(POLICY_BACKUP_DIR, f"{domain}/tech_support_policy_backup_{time_stamp}.md")
        if os.path.exists(os.path.join(DATA_DIR, f"{domain}/main_policy.md")):
            os.rename(os.path.join(DATA_DIR, f"{domain}/main_policy.md"), backup_main_path)
        if os.path.exists(os.path.join(DATA_DIR, f"{domain}/tech_support_policy.md")):
            os.rename(os.path.join(DATA_DIR, f"{domain}/tech_support_policy.md"), backup_tech_support_path)
        with open(os.path.join(DATA_DIR, f"{domain}/main_policy.md"), 'w') as file:
            file.write(updated_policy[0])
        with open(os.path.join(DATA_DIR, f"{domain}/tech_support_manual.md"), 'w') as file:
            file.write(updated_policy[1])

    return None

# if __name__ == "__main__":
#     main()