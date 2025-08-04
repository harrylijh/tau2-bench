#!/usr/bin/env python3
"""
Task Sampler for TAU2 Benchmark

This module implements functionality to:
1. Filter out tasks from tasks_full.json that exist in tasks.json
2. Use vector similarity search to find similar tasks for sampling
"""

import json
import numpy as np
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import argparse
import os


def load_json_file(file_path: str) -> List[Dict[str, Any]]:
    """Load tasks from a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json_file(data: List[Dict[str, Any]], file_path: str) -> None:
    """Save tasks to a JSON file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_user_scenario_text(task: Dict[str, Any]) -> str:
    """Extract text from user_scenario for embedding."""
    user_scenario = task.get('user_scenario', {})
    
    # Extract all relevant text from user_scenario
    text_parts = []
    
    # Add persona if exists
    if user_scenario.get('persona'):
        text_parts.append(f"Persona: {user_scenario['persona']}")
    
    # Add instructions
    instructions = user_scenario.get('instructions', {})
    if instructions:
        for key, value in instructions.items():
            if value and isinstance(value, str):
                text_parts.append(f"{key}: {value}")
    
    # Also include ticket information as it's part of the scenario context
    if task.get('ticket'):
        text_parts.append(f"Ticket: {task['ticket']}")
    
    return " ".join(text_parts)


def create_task_embeddings(tasks: List[Dict[str, Any]], model: SentenceTransformer) -> np.ndarray:
    """Create embeddings for all tasks using their user_scenario content."""
    texts = [extract_user_scenario_text(task) for task in tasks]
    embeddings = model.encode(texts)
    return embeddings


def filter_excluded_tasks(tasks_full: List[Dict[str, Any]], tasks_selected: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter out tasks from tasks_full that exist in tasks_selected."""
    selected_ids = {task['id'] for task in tasks_selected}
    task_excluded = [task for task in tasks_full if task['id'] not in selected_ids]
    return task_excluded


def find_most_similar_tasks(
    tasks_selected: List[Dict[str, Any]], 
    task_excluded: List[Dict[str, Any]], 
    model: SentenceTransformer
) -> List[Dict[str, Any]]:
    """
    For each task in tasks_selected, find the most similar task from task_excluded.
    If the most similar task is already selected, pick the next most similar one.
    """
    if not task_excluded:
        print("Warning: No excluded tasks available for sampling.")
        return []
    
    # Create embeddings for both sets
    print("Creating embeddings for selected tasks...")
    selected_embeddings = create_task_embeddings(tasks_selected, model)
    
    print("Creating embeddings for excluded tasks...")
    excluded_embeddings = create_task_embeddings(task_excluded, model)
    
    # Calculate similarity matrix
    print("Calculating similarity matrix...")
    similarity_matrix = cosine_similarity(selected_embeddings, excluded_embeddings)
    
    task_sampled = []
    used_indices = set()
    
    print("Finding most similar tasks...")
    for i, selected_task in enumerate(tasks_selected):
        # Get similarity scores for this selected task
        similarities = similarity_matrix[i]
        
        # Sort excluded tasks by similarity (descending)
        sorted_indices = np.argsort(similarities)[::-1]
        
        # Find the most similar task that hasn't been used yet
        for idx in sorted_indices:
            if idx not in used_indices:
                task_sampled.append(task_excluded[idx])
                used_indices.add(idx)
                
                # Print similarity info for debugging
                similarity_score = similarities[idx]
                print(f"Selected task ID: {selected_task['id']}")
                print(f"Most similar excluded task ID: {task_excluded[idx]['id']}")
                print(f"Similarity score: {similarity_score:.4f}")
                print("-" * 50)
                break
        else:
            print(f"Warning: No unused similar task found for {selected_task['id']}")
    
    return task_sampled


def sample_similar_tasks(
    tasks_json_path: str, 
    tasks_full_json_path: str, 
    output_path: str,
    model_name: str = 'all-MiniLM-L6-v2'
) -> None:
    """
    Main function to sample similar tasks.
    
    Args:
        tasks_json_path: Path to tasks.json
        tasks_full_json_path: Path to tasks_full.json
        output_path: Path to save the sampled tasks
        model_name: Name of the sentence transformer model to use
    """
    print(f"Loading sentence transformer model: {model_name}")
    model = SentenceTransformer(model_name)
    
    print("Loading tasks from files...")
    tasks_selected = load_json_file(tasks_json_path)
    tasks_full = load_json_file(tasks_full_json_path)
    
    print(f"Loaded {len(tasks_selected)} selected tasks")
    print(f"Loaded {len(tasks_full)} full tasks")
    
    # Step 1: Filter out selected tasks from full tasks
    print("Filtering excluded tasks...")
    task_excluded = filter_excluded_tasks(tasks_full, tasks_selected)
    print(f"Found {len(task_excluded)} excluded tasks")
    
    # Step 2: Find most similar tasks
    print("Finding most similar tasks...")
    task_sampled = find_most_similar_tasks(tasks_selected, task_excluded, model)
    print(f"Sampled {len(task_sampled)} similar tasks")
    
    # Step 3: Save results
    print(f"Saving sampled tasks to {output_path}")
    save_json_file(task_sampled, output_path)
    
    print("Task sampling completed successfully!")
    print(f"Output saved to: {output_path}")


def main():
    """Command line interface for the task sampler."""
    parser = argparse.ArgumentParser(description='Sample similar tasks from TAU2 benchmark')
    parser.add_argument('--tasks-json', required=True, help='Path to tasks.json')
    parser.add_argument('--tasks-full-json', required=True, help='Path to tasks_full.json')
    parser.add_argument('--output', required=True, help='Output path for sampled tasks')
    parser.add_argument('--model', default='all-MiniLM-L6-v2', 
                       help='Sentence transformer model name (default: all-MiniLM-L6-v2)')
    
    args = parser.parse_args()
    
    # Validate input files
    if not os.path.exists(args.tasks_json):
        raise FileNotFoundError(f"Tasks file not found: {args.tasks_json}")
    if not os.path.exists(args.tasks_full_json):
        raise FileNotFoundError(f"Tasks full file not found: {args.tasks_full_json}")
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    sample_similar_tasks(
        args.tasks_json,
        args.tasks_full_json,
        args.output,
        args.model
    )


if __name__ == "__main__":
    main()
