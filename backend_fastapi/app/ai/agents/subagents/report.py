from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.runnables import Runnable

from app.ai.config import AgentSettings
from app.ai.utils.markdown import read_markdown_file
from app.ai.tools.file_generator import (
    create_html_report,
    create_pdf_report,
    create_docx_document,
    create_pptx_presentation,
    create_markdown_report,
)


def get_report_subagent_spec() -> Runnable:
    system_prompt = read_markdown_file("app/ai/prompts/report.md")
    tools = [
        create_html_report,
        create_pdf_report,
        create_docx_document,create_pptx_presentation,
        create_markdown_report,
    ]
    return {
        "name": "report-agent",
        "description": "Used to generate reports",
        "system_prompt": system_prompt,
        "tools": tools,
    }
