import litellm
import json
import os
from typing import Optional, List

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data/tau2/domains")
POLICY_BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data/tau2/original_policies")



def restore_agent_policy(domain: str):
    """
    Copy the original agent policy from a the backup directory.
    
    This function retrieves the agent policy from a specified file path.
    If the file does not exist, it returns None.
    
    Returns:
        dict or None: The restored agent policy or None if not found.
    """
    if domain == "retail" or domain == "airline":
        policy_path = os.path.join(POLICY_BACKUP_DIR, f"{domain}/policy.md")
        # Check if the policy file exists
        if os.path.exists(policy_path):
            # copy the policy file to the data directory
            restored_policy_path = os.path.join(DATA_DIR, f"{domain}/policy.md")
            os.makedirs(os.path.dirname(restored_policy_path), exist_ok=True)
            with open(policy_path, "r") as f:
                policy_content = f.read()
            with open(restored_policy_path, "w") as f:
                f.write(policy_content)
            print(f"Restored policy for {domain} to {restored_policy_path}.")
            return None
        else:
            print(f"Policy file for {domain} not found at {policy_path}.")
            return None
    elif domain == "telecom":
        main_policy_path = os.path.join(POLICY_BACKUP_DIR, "telecom/main_policy.md")
        tech_policy_path = os.path.join(POLICY_BACKUP_DIR, "telecom/tech_support_manual.md")
        # Check if the policy files exist
        if os.path.exists(main_policy_path) and os.path.exists(tech_policy_path):
            # copy the policy files to the data directory
            restored_main_policy_path = os.path.join(DATA_DIR, "telecom/main_policy.md")
            restored_tech_policy_path = os.path.join(DATA_DIR, "telecom/tech_support_manual.md")
            os.makedirs(os.path.dirname(restored_main_policy_path), exist_ok=True)
            with open(main_policy_path, "r") as f:
                main_policy_content = f.read()
            with open(restored_main_policy_path, "w") as f:
                f.write(main_policy_content)
            with open(tech_policy_path, "r") as f:
                tech_policy_content = f.read()
            with open(restored_tech_policy_path, "w") as f:
                f.write(tech_policy_content)
            print(f"Restored telecom policies to {restored_main_policy_path} and {restored_tech_policy_path}.")
            return None
        else:
            print(f"Policy files for telecom not found at {main_policy_path} or {tech_policy_path}.")
            return None


# delete current tool prompts
def delete_tool_prompts(domain: str):
    """
    Deletes all tool prompt files for the specified domain.
    
    Args:
        domain (str): The domain for which to delete tool prompts.
    """
    from pathlib import Path
    import os
    # Ensure the directory exists before attempting to delete files
    tool_prompt_dir = Path(f"data/tau2/tool_prompts/{domain}")
    if tool_prompt_dir.exists():
        for file in tool_prompt_dir.iterdir():
            if file.is_file():
                os.remove(file)