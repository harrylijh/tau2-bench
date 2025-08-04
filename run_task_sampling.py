#!/usr/bin/env python3
"""
Example script to run task sampling on telecom domain data
"""

from task_sampler import sample_similar_tasks
import os

def run_telecom_sampling():
    """Run task sampling on telecom domain data."""
    
    # Define paths
    base_path = "/home/lijiah/workspace/tau2-bench/data/tau2/domains/telecom"
    tasks_json_path = os.path.join(base_path, "tasks.json")
    tasks_full_json_path = os.path.join(base_path, "tasks_full.json")
    output_path = os.path.join(base_path, "tasks_sampled.json")
    
    print("Running task sampling on telecom domain...")
    print(f"Selected tasks: {tasks_json_path}")
    print(f"Full tasks: {tasks_full_json_path}")
    print(f"Output: {output_path}")
    print("-" * 60)
    
    try:
        sample_similar_tasks(
            tasks_json_path=tasks_json_path,
            tasks_full_json_path=tasks_full_json_path,
            output_path=output_path,
            model_name='all-MiniLM-L6-v2'  # Fast and effective model
        )
        
        print("\n" + "=" * 60)
        print("Task sampling completed successfully!")
        print(f"Results saved to: {output_path}")
        
    except Exception as e:
        print(f"Error during task sampling: {e}")
        raise

if __name__ == "__main__":
    run_telecom_sampling()
