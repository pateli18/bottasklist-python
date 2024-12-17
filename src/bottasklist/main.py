import json
import random
import string
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, Optional, Union

# Tool Schema


class ToolSchemaType(str, Enum):
    openai = "openai"
    claude = "claude"


@dataclass
class BotTaskListToolProperty:
    type: str
    description: str
    items: Optional[dict] = None
    enum: Optional[list[str]] = None

    @property
    def serialized(self) -> dict:
        base: dict = {"type": self.type, "description": self.description}
        if self.items is not None:
            base["items"] = self.items
        if self.enum is not None:
            base["enum"] = self.enum
        return base


@dataclass
class BotTaskListTool:
    name: str
    description: str
    properties: dict[str, BotTaskListToolProperty]
    required: list[str]

    def tool_schema(self, tool_schema_type: ToolSchemaType) -> dict:
        if tool_schema_type == ToolSchemaType.openai:
            return self._openai_serialized()
        elif tool_schema_type == ToolSchemaType.claude:
            return self._claude_serialized()
        else:
            raise ValueError(f"Invalid tool schema type: {tool_schema_type}")

    def _openai_serialized(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        k: v.serialized for k, v in self.properties.items()
                    },
                    "required": self.required,
                },
            },
        }

    def _claude_serialized(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    k: v.serialized for k, v in self.properties.items()
                },
                "required": self.required,
            },
        }


# Task List


class BotTaskListValidationError(Exception):
    pass


@dataclass
class BotTask:
    id: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime

    def __str__(self) -> str:
        return f"{self.description} - **Status:** {self.status}"


class BotTaskList:
    def __init__(
        self,
        statuses: Optional[list[str]] = None,
        default_status: Optional[str] = None,
    ):
        """
        Initialize the task list.

        Args:
            statuses: The statuses to use for the task list. If not provided,
                the default statuses ("pending", "complete") are used.
            default_status: The default status to use for the task list. The
                default status must be within the statuses list. The default
                status is "pending".
        """
        if statuses is None:
            statuses = ["pending", "complete"]
        if default_status is None:
            default_status = "pending"
        if default_status not in statuses:
            raise BotTaskListValidationError(
                f"Default status {default_status} not in statuses {statuses}"
            )
        self.statuses = statuses
        self.default_status = default_status
        self.tasks: list[BotTask] = []

    def _generate_id(self) -> str:
        alphabet = string.ascii_lowercase + string.digits
        return "".join(random.choices(alphabet, k=8))

    def add_tasks(self, descriptions: list[str]) -> list[str]:
        """
        Add tasks to the task list.

        Args:
            descriptions: The descriptions of the tasks to add.

        Returns:
            The ids of the tasks that were added.
        """
        created_at = datetime.now()
        updated_at = created_at
        ids = []
        for description in descriptions:
            id = self._generate_id()
            self.tasks.append(
                BotTask(
                    id,
                    description,
                    self.default_status,
                    created_at,
                    updated_at,
                )
            )
            ids.append(id)
        return ids

    def get_tasks(
        self,
        status_filter: Optional[list[str]] = None,
        sort_by: Optional[Literal["created_at", "updated_at"]] = None,
        top_n: Optional[int] = None,
    ) -> list[BotTask]:
        """
        Get the tasks from the task list.

        Args:
            status_filter: The statuses to filter the tasks by. If not provided,
                all tasks are returned.
            sort_by: The field to sort the tasks by. If not provided, the
                tasks are sorted by created_at.
            top_n: The number of tasks to return. If not provided, all tasks
                are returned.

        Returns:
            The tasks that match the filter and sort criteria.
        """
        output_tasks = self.tasks
        if status_filter is not None and len(status_filter) > 0:
            for status in status_filter:
                if status not in self.statuses:
                    raise BotTaskListValidationError(
                        f"Status {status} not in statuses {self.statuses}"
                    )
            output_tasks = [
                task for task in output_tasks if task.status in status_filter
            ]
        if sort_by:
            output_tasks = sorted(
                output_tasks, key=lambda x: getattr(x, sort_by)
            )
        if top_n:
            output_tasks = output_tasks[:top_n]
        return output_tasks

    def update_task_statuses(self, ids: list[str], status: str) -> list[str]:
        """
        Update the statuses of the tasks.

        Args:
            ids: The ids of the tasks to update.
            status: The status to update the tasks to.

        Returns:
            The ids of the tasks that were updated.
        """
        if status not in self.statuses:
            raise BotTaskListValidationError(
                f"Status {status} not in statuses {self.statuses}"
            )
        updated_ids = []
        for task in self.tasks:
            if task.id in ids:
                task.status = status
                task.updated_at = datetime.now()
                updated_ids.append(task.id)

        # check for ids that are not updated_ids and do not exist in self.tasks
        missing_ids = set(ids) - set(updated_ids)
        if len(missing_ids) > 0:
            raise BotTaskListValidationError(
                f"Task ids {missing_ids} not found in task list"
            )
        return updated_ids

    def get_tools(
        self,
        tool_schema_type: ToolSchemaType = ToolSchemaType.openai,
    ) -> list[dict]:
        """
        Get the tool schemas for the task list that can be used in a chat

        Args:
            tool_schema_type: The type of tool schema to use. The default is
                openai.

        Returns:
            The tool schemas for the task list.
        """
        add_tasks_tool = BotTaskListTool(
            name="bottasklist_add_tasks",
            description="Add tasks to the task list",
            properties={
                "descriptions": BotTaskListToolProperty(
                    type="array",
                    description="The descriptions of the tasks to add",
                    items={
                        "type": "string",
                        "description": "The description of the task",
                    },
                ),
            },
            required=["descriptions"],
        )

        update_tasks_statuses_tool = BotTaskListTool(
            name="bottasklist_update_tasks_statuses",
            description="Update the status of the tasks",
            properties={
                "ids": BotTaskListToolProperty(
                    type="array",
                    description="The ids of the tasks to update",
                    items={
                        "type": "string",
                        "description": "The id of the task",
                    },
                ),
                "status": BotTaskListToolProperty(
                    type="string",
                    description="The status to update the tasks to",
                    enum=self.statuses,
                ),
            },
            required=["ids", "status"],
        )

        get_tasks_tool = BotTaskListTool(
            name="bottasklist_get_tasks",
            description="Get the tasks",
            properties={
                "status_filter": BotTaskListToolProperty(
                    type="array",
                    description="The statuses to filter the tasks by",
                    items={
                        "type": "string",
                        "description": "The status of the task",
                        "enum": self.statuses,
                    },
                ),
                "sort_by": BotTaskListToolProperty(
                    type="string",
                    description="The field to sort the tasks by",
                    enum=["created_at", "updated_at"],
                ),
                "top_n": BotTaskListToolProperty(
                    type="number",
                    description="The number of tasks to return",
                ),
            },
            required=[],
        )

        tools = [
            add_tasks_tool,
            update_tasks_statuses_tool,
            get_tasks_tool,
        ]

        tool_schemas = [tool.tool_schema(tool_schema_type) for tool in tools]

        return tool_schemas

    def _serialize_tool_output(
        self,
        output: Union[list[str], list[BotTask]],
        enforce_str_output: bool,
    ) -> Union[str, list[str], list[BotTask]]:
        final_output = output
        if enforce_str_output:
            if len(output) > 0 and isinstance(output[0], BotTask):
                output = [str(task) for task in output]
            final_output = json.dumps(output)
        return final_output

    def execute_tool(
        self,
        tool_name: str,
        tool_args: dict,
        enforce_str_output: bool = True,
        catch_validation_errors: bool = True,
    ) -> Union[str, list[str], list[BotTask]]:
        """
        Execute a tool call.

        Args:
            tool_name: The name of the tool to execute
            tool_args: The arguments to pass to the tool
            enforce_str_output: If True, the output will be converted to a JSON string. Defaults to True.
            catch_validation_errors: If True, BotTaskListValidationErrors will be caught and cast to strings. You can then pass this to the model you are using to fix the tool call. Defaults to False.

        Returns:
            The output of the tool
        """
        tool_name = tool_name.replace("bottasklist_", "")
        try:
            output = getattr(self, tool_name)(**tool_args)
        except BotTaskListValidationError as e:
            if catch_validation_errors:
                return str(e)
            else:
                raise e
        return self._serialize_tool_output(output, enforce_str_output)
