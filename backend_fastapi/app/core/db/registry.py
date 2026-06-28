"""Register all SQLModel tables with SQLAlchemy metadata."""


def register_models() -> None:
    """Import every table model so SQLAlchemy/Alembic see the full schema."""
    from app.modules.agent.model import Agent  # noqa: F401
    from app.modules.auth.model import AuthIdentity  # noqa: F401
    from app.modules.chat.model import Conversation, Message, MessageBlock  # noqa: F401
    from app.modules.group.model import GroupMember, UserGroup  # noqa: F401
    from app.modules.observability.model import ApiLog  # noqa: F401
    from app.modules.skills.model import AgentSkill  # noqa: F401
    from app.modules.user.model import User  # noqa: F401
