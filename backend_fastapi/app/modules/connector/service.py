"""Connector listing, OAuth, and MCP operations."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.connector.auth_manager import connector_auth_manager
from app.modules.connector.catalog import get_connector_definition, list_connector_definitions
from app.modules.connector.mcp_client import McpClientError, RemoteMcpClient
from app.modules.connector.model import UserConnector
from app.modules.connector.oauth_flow import (
    build_google_authorize_url,
    exchange_google_code,
    sign_oauth_state,
    verify_oauth_state,
)
from app.modules.connector.schema import (
    AuthorizeConnectorResponse,
    ConnectorCatalogItem,
    ConnectorStatusItem,
    ConnectorToolsResponse,
    UserConnectorSummary,
)


class ConnectorService:
    def _to_summary(self, row: UserConnector | None, connector_id: str) -> UserConnectorSummary | None:
        if row is None:
            return None
        return UserConnectorSummary(
            id=row.id,
            connector_id=row.connector_id,
            enabled=row.enabled,
            connected=bool(row.access_token),
            account_email=row.account_email,
            last_connected_at=row.last_connected_at,
            last_error=row.last_error,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def list_status(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> list[ConnectorStatusItem]:
        statement = select(UserConnector).where(UserConnector.user_id == user_id)
        rows = (await session.exec(statement)).all()
        by_connector = {row.connector_id: row for row in rows}

        items: list[ConnectorStatusItem] = []
        for definition in list_connector_definitions():
            row = by_connector.get(definition.id)
            items.append(
                ConnectorStatusItem(
                    catalog=ConnectorCatalogItem(
                        id=definition.id,
                        name=definition.name,
                        description=definition.description,
                        category=definition.category,
                        mcp_url=definition.mcp_url,
                        oauth_scopes=list(definition.oauth_scopes),
                        docs_url=definition.docs_url,
                    ),
                    connection=self._to_summary(row, definition.id),
                )
            )
        return items

    async def begin_oauth(
        self,
        session: AsyncSession,
        user_id: UUID,
        connector_id: str,
    ) -> AuthorizeConnectorResponse:
        definition = get_connector_definition(connector_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Unknown connector")

        state = sign_oauth_state(user_id=str(user_id), connector_id=connector_id)
        try:
            authorize_url = build_google_authorize_url(
                connector_id=connector_id,
                scopes=definition.oauth_scopes,
                state=state,
            )
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        return AuthorizeConnectorResponse(authorize_url=authorize_url)

    async def complete_oauth(
        self,
        session: AsyncSession,
        *,
        code: str,
        state: str,
    ) -> UserConnectorSummary:
        try:
            user_id_str, connector_id = verify_oauth_state(state)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        definition = get_connector_definition(connector_id)
        if definition is None:
            raise HTTPException(status_code=400, detail="Unknown connector")

        try:
            token_payload = await exchange_google_code(code)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        access_token = token_payload.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Missing access token")

        account_email = await connector_auth_manager.fetch_google_account_email(
            access_token,
            token_payload=token_payload,
        )
        row = await connector_auth_manager.upsert_tokens(
            session,
            user_id=UUID(user_id_str),
            connector_id=connector_id,
            access_token=access_token,
            refresh_token=token_payload.get("refresh_token"),
            expires_in=token_payload.get("expires_in"),
            scopes=token_payload.get("scope") or " ".join(definition.oauth_scopes),
            account_email=account_email,
        )
        summary = self._to_summary(row, connector_id)
        assert summary is not None
        return summary

    async def disconnect(
        self,
        session: AsyncSession,
        user_id: UUID,
        connector_id: str,
    ) -> None:
        definition = get_connector_definition(connector_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Unknown connector")
        await connector_auth_manager.disconnect(session, user_id=user_id, connector_id=connector_id)

    async def update_enabled(
        self,
        session: AsyncSession,
        user_id: UUID,
        connector_id: str,
        enabled: bool,
    ) -> UserConnectorSummary:
        definition = get_connector_definition(connector_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Unknown connector")
        try:
            row = await connector_auth_manager.set_enabled(
                session,
                user_id=user_id,
                connector_id=connector_id,
                enabled=enabled,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        summary = self._to_summary(row, connector_id)
        assert summary is not None
        return summary

    async def list_mcp_tools(
        self,
        session: AsyncSession,
        user_id: UUID,
        connector_id: str,
    ) -> ConnectorToolsResponse:
        definition = get_connector_definition(connector_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Unknown connector")

        try:
            access_token = await connector_auth_manager.get_valid_access_token(
                session,
                user_id=user_id,
                connector_id=connector_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        client = RemoteMcpClient(mcp_url=definition.mcp_url, access_token=access_token)
        try:
            tools = await client.list_tools()
        except McpClientError as exc:
            row = await self._get_row(session, user_id, connector_id)
            if row is not None:
                row.last_error = str(exc)[:500]
                await session.commit()
            raise HTTPException(status_code=502, detail=f"MCP request failed: {exc}") from exc
        except Exception as exc:
            row = await self._get_row(session, user_id, connector_id)
            if row is not None:
                row.last_error = str(exc)[:500]
                await session.commit()
            raise HTTPException(status_code=502, detail=f"MCP request failed: {exc}") from exc

        return ConnectorToolsResponse(connector_id=connector_id, tools=tools)

    async def _get_row(
        self,
        session: AsyncSession,
        user_id: UUID,
        connector_id: str,
    ) -> UserConnector | None:
        statement = select(UserConnector).where(
            UserConnector.user_id == user_id,
            UserConnector.connector_id == connector_id,
        )
        return (await session.exec(statement)).first()


connector_service = ConnectorService()
