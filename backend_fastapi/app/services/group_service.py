"""Service layer for managing user groups and memberships.
This service handles creation, deletion, and role management within groups.
"""

from uuid import UUID
from typing import List, Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.group import GroupRole, UserGroup, GroupMember
from app.models.user import User


class GroupService:
    """Stateless group management logic."""

    async def create_group(
        self,
        session: AsyncSession,
        owner_id: UUID,
        name: str,
        description: str | None = None,
    ) -> UserGroup:
        """Create a new group, assigning the creator as the group owner."""
        
        # Check if a group with this name already exists
        existing = await self._get_group_by_name(session, name)
        if existing:
            raise ConflictError(f"Group name '{name}' is already taken.")

        # Check if owner exists
        owner = await session.get(User, owner_id)
        if not owner:
            raise NotFoundError(f"Owner user with ID {owner_id} not found.")

        group = UserGroup(
            name=name,
            description=description,
            owner_id=owner_id,
        )
        session.add(group)
        await session.flush() # Get group ID

        # Add the creator as the group owner
        await self.add_member(session, group.id, owner_id, GroupRole.OWNER)
        
        await session.commit()
        await session.refresh(group)
        return group

    async def add_member(
        self, 
        session: AsyncSession, 
        group_id: UUID, 
        user_id: UUID, 
        role: GroupRole = GroupRole.MEMBER
    ) -> GroupMember:
        """Add a user to a group with a specific role."""
        
        # Check existence
        user = await session.get(User, user_id)
        if not user:
            raise NotFoundError(f"User with ID {user_id} not found.")
            
        group = await session.get(UserGroup, group_id)
        if not group:
            raise NotFoundError(f"Group with ID {group_id} not found.")
            
        # Check if already a member
        statement = select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
        existing_member = (await session.exec(statement)).first()
        if existing_member:
            raise ConflictError(f"User {user_id} is already a member of group {group_id}.")
            
        member = GroupMember(
            group_id=group_id,
            user_id=user_id,
            role=role,
        )
        session.add(member)
        await session.commit()
        await session.refresh(member)
        return member

    async def remove_member(self, session: AsyncSession, group_id: UUID, user_id: UUID) -> bool:
        """Remove a user from a group."""
        statement = select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
        member = (await session.exec(statement)).first()
        if not member:
            return False
        
        # Prevent removing the owner unless the group is being deleted (handled by higher layer)
        if member.role == GroupRole.OWNER:
            # In a full implementation, this should check if other members exist or require owner transfer.
            # For now, we allow it but a better API would prevent orphaned groups.
            pass

        await session.delete(member)
        await session.commit()
        return True

    async def get_group_member(self, session: AsyncSession, group_id: UUID, user_id: UUID) -> GroupMember | None:
        """Retrieve a specific membership record."""
        statement = select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
        result = await session.exec(statement)
        return result.first()
        
    async def get_groups_for_user(self, session: AsyncSession, user_id: UUID) -> List[UserGroup]:
        """List all groups a user is a member of."""
        statement = select(GroupMember).where(GroupMember.user_id == user_id)
        result = await session.exec(statement)
        members = result.all()
        
        # GroupMember relationship needs to be set up on User model for lazy loading, 
        # but for eager loading here, we fetch the group directly.
        groups = [member.group for member in members]
        return groups
        
    async def _get_group_by_name(self, session: AsyncSession, name: str) -> UserGroup | None:
        statement = select(UserGroup).where(UserGroup.name == name)
        result = await session.exec(statement)
        return result.first()

    async def get_group(self, session: AsyncSession, group_id: UUID) -> UserGroup | None:
        """Retrieve a single group by ID."""
        return await session.get(UserGroup, group_id)

    async def delete_group(self, session: AsyncSession, group_id: UUID) -> bool:
        """Delete a group and all its members. Returns True if deleted."""
        group = await session.get(UserGroup, group_id)
        if not group:
            return False
        await session.delete(group)
        await session.commit()
        return True


group_service = GroupService()
