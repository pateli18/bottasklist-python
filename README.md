# BotTaskList Python Package

Small tools an agent can call to create and update a task list it is working on:

- `add_tasks`
- `create_tasks`
- `updates_tasks_status`

## Installation

There are no external dependencies, if you don't want to `pip install` this feel free to copy `main.py` directly into your codebase.

```bash
pip install bottasklist
```

## Usage

```python
import json
from bottasklist import BotTaskList, ToolSchemaType
import openai

# initialize the task list and get the tools
bot_tasks = BotTaskList()
tools = bot_tasks.get_tools(tool_schema_type=ToolSchemaType.openai)

# initialize the openai client and the chat thread
openai_client = openai.OpenAI()
chat_thread = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Create a task list to build a website for a local gardening business"},
]

# call the openai client with the chat thread and tools
output = openai_client.chat.completions.create(
    model="gpt-4o",
    messages=chat_thread,
    tools=tools,
)

chat_thread.append(output.choices[0].message.model_dump())
for tool_call in output.choices[0].message.tool_calls:
    arguments = json.loads(tool_call.function.arguments)
    # execute the tool
    tool_output = bot_tasks.execute_tool(
        tool_call.function.name,
        arguments,
    )
    chat_thread.append(
        {
            "role": "tool",
            "content": tool_output,
            "name": tool_call.function.name,
            "tool_call_id": tool_call.id,
        }
    )

# print task list
print(bot_tasks)
```

### Customize Statuses

By default, task status is either `pending` or `complete`, and when a task is created the `default_task_status` is `pending`. You can customize both of these upon initialization:

```python
bot_tasks = BotTaskList(status=["new_status_1", "new_status_2"], default_status="new_status_1")
```
