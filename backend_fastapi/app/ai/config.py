"""Minimal agent configuration."""


class AgentSettings:
    deep_agent = {
        "agent_config": {
            "model": "gemini-2.5-flash",
            "model_provider": "google_vertexai",
            "vertex_project": "sea-ml-hub",
            "vertex_location": "asia-southeast1",
            "temperature": 0,
            "max_output_tokens": 8192,
            "recursion_limit": 25,
            "timeout_seconds": 90,
        },
    }
