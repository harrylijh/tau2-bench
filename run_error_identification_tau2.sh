#!/bin/bash

# Interactive script to run error_identification_by_author.py

# Prompt for input JSON file
# default_input="visualize_results/uploads/agent-gpt-4.1-mini_user-gemini-2.5-flash-preview-04-17-llm_range-0-10_0522050804.json"
default_input="data/simulations/telecom/telecom_baseline_llm_agent_gpt-4.1_user_simulator_gpt-4.1.json"
read -p "Enter input results JSON file [${default_input}]: " INPUT_JSON
INPUT_JSON=${INPUT_JSON:-$default_input}

# Prompt for model name
read -p "Enter model name [default: gemini-2.5-pro]: " MODEL
# MODEL=${MODEL:-gpt-4.1}
MODEL=${MODEL:-gemini-2.5-pro}

# Prompt for task IDs
read -p "Enter space-separated task IDs [default: all]: " TASK_IDS
TASK_IDS=${TASK_IDS:-}

# Prompt for max number of failed results
read -p "Enter max number of failed results to analyze [default: all]: " MAX_FAILED
MAX_FAILED=${MAX_FAILED:-0}

# Compose output file name
BASENAME=$(basename "$INPUT_JSON" .json)
TASK_IDS_CLEAN=$(echo "$TASK_IDS" | tr ' ' '-')
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT_JSON="err_ana_results/analysis-by-author_${BASENAME}_tasks-${TASK_IDS_CLEAN}_judge-${MODEL}_${TIMESTAMP}.json"
# Ensure output directory exists
mkdir -p "$(dirname "$OUTPUT_JSON")"


export OPENAI_API_KEY="sk-5v0aDB9hXoZzxtmGitpAgA"  # Set your OpenAI API key here
export OPENAI_BASE_URL="http://ai06.labs.hpecorp.net:4000"  # Set your OpenAI API base URL here

set -e  # Exit on error

# Run the script
if [ "$TASK_IDS" ]; then
    python error_identification_tau2.py --model "$MODEL" -r "$INPUT_JSON" -o "$OUTPUT_JSON" -t $TASK_IDS -n "$MAX_FAILED"
else
    python error_identification_tau2.py --model "$MODEL" -r "$INPUT_JSON" -o "$OUTPUT_JSON" -n "$MAX_FAILED"
    fi

# cat $OUTPUT_JSON
