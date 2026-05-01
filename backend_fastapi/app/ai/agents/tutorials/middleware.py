

"""
Process state before the model is called (e.g., message trimming, context injection)
Modify or validate the model’s response (e.g., guardrails, content filtering)
Handle tool execution errors with custom logic
Implement dynamic model selection based on state or context
Add custom logging, monitoring, or analytics
"""


from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware, HumanInTheLoopMiddleware, ModelCallLimitMiddleware, ToolCallLimitMiddleware, ModelFallbackMiddleware, PIIMiddleware, TodoListMiddleware, LLMToolSelectorMiddleware, ToolRetryMiddleware, ModelRetryMiddleware, ShellToolMiddleware, FilesystemFileSearchMiddleware, FilesystemMiddleware, HostExecutionPolicy
from app.ai.tools.rag import search_rag, answer_rag


global_limiter = ToolCallLimitMiddleware(thread_limit=20, run_limit=10)
search_limiter = ToolCallLimitMiddleware(tool_name="search", thread_limit=5, run_limit=3)
database_limiter = ToolCallLimitMiddleware(tool_name="query_database", thread_limit=10)
strict_limiter = ToolCallLimitMiddleware(tool_name="scrape_webpage", run_limit=2, exit_behavior="error")


rag_tools = [search_rag, answer_rag]




tools = rag_tools
agent = create_agent(
    model="gemini-2.0-flash",
    tools=tools,
    middleware=[
        SummarizationMiddleware(            
            model="gemini-2.0-flash",
            trigger=("tokens", 4000),
            keep=("messages", 20),),
        HumanInTheLoopMiddleware(
            interrupt_on={
                "your_send_email_tool": {
                    "allowed_decisions": ["approve", "edit", "reject"],
                },
                "your_read_email_tool": False,
            }
            ),
        ModelCallLimitMiddleware(
            thread_limit=10,
            run_limit=5,
            exit_behavior="end",
        ),
        # Global limit
        ToolCallLimitMiddleware(thread_limit=20, run_limit=10),
        # Tool-specific limit
        ToolCallLimitMiddleware(
            tool_name="search",
            thread_limit=5,
            run_limit=3,
        ),
        ModelFallbackMiddleware(
            "gemini-2.0-flash",
            "gemini-2.0-pro",
        ),
        PIIMiddleware("email", strategy="redact", apply_to_input=True),
        PIIMiddleware("credit_card", strategy="mask", apply_to_input=True),
        TodoListMiddleware("todo_list"),
        # Use an LLM to intelligently select relevant tools before calling the main model. LLM tool selectors are useful for the following:
        LLMToolSelectorMiddleware(
            model="gemini-2.0-flash",
            max_tools=3,
            always_include=["search"],
        ),
        ToolRetryMiddleware(
            max_retries=3,
            backoff_factor=2.0,
            initial_delay=1.0,
        ),
        ModelRetryMiddleware(
            max_retries=3,
            backoff_factor=2.0,
            initial_delay=1.0,
        ),
        ShellToolMiddleware(
            workspace_root="/workspace",
            execution_policy=HostExecutionPolicy(),
        ),
        FilesystemFileSearchMiddleware(
            root_path="/workspace",
            use_ripgrep=True,
        ),
        FilesystemMiddleware(
            backend=None,  # Optional: custom backend (defaults to StateBackend)
            system_prompt="Write to the filesystem when...",  # Optional custom addition to the system prompt
            custom_tool_descriptions={
                "ls": "Use the ls tool when...",
                "read_file": "Use the read_file tool to..."
            }  # Optional: Custom descriptions for filesystem tools
        ),

    ],
)   