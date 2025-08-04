import json
import random

def sample_tasks(input_file, output_file, sample_size=100):
    """
    Randomly sample tasks from a JSON file and save to a new file.
    
    Args:
        input_file (str): Path to the input JSON file
        output_file (str): Path to save the sampled data
        sample_size (int): Number of samples to extract (default: 100)
    
    Returns:
        list: The sampled data
    """
    # Read the JSON file
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Check if we have enough samples
    if len(data) < sample_size:
        print(f"Warning: File only has {len(data)} items, sampling all of them.")
        sample_size = len(data)
    
    # Randomly sample
    sampled_data = random.sample(data, sample_size)
    
    # Save to output file
    with open(output_file, 'w') as f:
        json.dump(sampled_data, f, indent=2)
    
    print(f"Sampled {len(sampled_data)} items from {len(data)} total items.")
    print(f"Saved to: {output_file}")
    
    return sampled_data

# Example usage:
if __name__ == "__main__":
    input_file = "data/tau2/domains/telecom/tasks_full.json"
    output_file = "data/tau2/domains/telecom/tasks_sample_100.json"
    
    # Sample 100 tasks
    sampled_tasks = sample_tasks(input_file, output_file, 100)
    
    # Optional: Set seed for reproducible results
    # random.seed(42)
    # sampled_tasks = sample_tasks(input_file, output_file, 100)
