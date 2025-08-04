AGENT_MODEL="gpt-4.1"

USER_MODEL="gpt-4.1"

MAX_CONCURRENCY=5

# Prompt for domain name
read -p "Enter domain name [default: airline]: " ENV
ENV=${ENV:-airline}

# Prompt for enable reflection
read -p "Enable reflection in the agent [y/n default: no]: " ENABLE_REFLECTION
ENABLE_REFLECTION=${ENABLE_REFLECTION:-n}

# Prompt for task IDs
read -p "Enter space-separated task IDs [default: All]: " TASK_IDS
TASK_IDS=${TASK_IDS:-}

# Resume the simulation if save-to is provided
read -p "Enter save-to path to resume the previous simulation [default: None]: " SAVE_TO
SAVE_TO="${SAVE_TO:-None}"

# Set max steps, default 200
MAX_STEPS=200

NUM_TRIALS=1

# Prompt for task_set_name
if [[ "$ENV" == "telecom" ]]; then 
    read -p "Enter task set name [default: telecom]: " TASK_SET_NAME
    TASK_SET_NAME="${TASK_SET_NAME:-telecom}"
else
    TASK_SET_NAME="$ENV"
fi

set -e
set -x

if [ -n "$TASK_IDS" ]; then
    tau2 run \
     --domain "$ENV" \
     --agent-llm "$AGENT_MODEL" \
     --user-llm "$USER_MODEL" \
     --max-concurrency "$MAX_CONCURRENCY" \
     --num-trials "$NUM_TRIALS" \
     --max-steps "$MAX_STEPS" \
     --task-set-name "$TASK_SET_NAME" \
     --task-ids "$TASK_IDS" \
     --save-to "$SAVE_TO" \
     --enable-reflection "$ENABLE_REFLECTION"
else
    tau2 run \
     --domain "$ENV" \
     --agent-llm "$AGENT_MODEL" \
     --user-llm "$USER_MODEL" \
     --max-concurrency "$MAX_CONCURRENCY" \
     --num-trials "$NUM_TRIALS" \
     --max-steps "$MAX_STEPS" \
     --task-set-name "$TASK_SET_NAME" \
     --save-to "$SAVE_TO" \
     --enable-reflection "$ENABLE_REFLECTION"

fi