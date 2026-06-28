import { apiBaseUrl, parseApiErrorMessage } from "./api";

const connectorBase = `${apiBaseUrl}/api/v1/connectors`;

export type ConnectorCatalogItem = {
  id: string;
  name: string;
  description: string;
  category: string;
  mcp_url: string;
  oauth_scopes: string[];
  docs_url: string;
};

export type UserConnectorSummary = {
  id: string;
  connector_id: string;
  enabled: boolean;
  connected: boolean;
  account_email: string | null;
  last_connected_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
};

export type ConnectorStatusItem = {
  catalog: ConnectorCatalogItem;
  connection: UserConnectorSummary | null;
};

export type ConnectorToolInfo = {
  name: string | null;
  description: string | null;
};

function authHeaders(accessToken: string): HeadersInit {
  return {
    Authorization: `Bearer ${accessToken.trim()}`,
    "Content-Type": "application/json",
  };
}

export async function fetchConnectors(
  accessToken: string,
): Promise<ConnectorStatusItem[]> {
  const res = await fetch(connectorBase, {
    headers: authHeaders(accessToken),
  });
  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }
  return res.json();
}

export async function beginConnectorOAuth(
  accessToken: string,
  connectorId: string,
): Promise<string> {
  const res = await fetch(`${connectorBase}/${connectorId}/authorize`, {
    method: "POST",
    headers: authHeaders(accessToken),
  });
  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }
  const payload = (await res.json()) as { authorize_url: string };
  return payload.authorize_url;
}

export async function updateConnectorEnabled(
  accessToken: string,
  connectorId: string,
  enabled: boolean,
): Promise<UserConnectorSummary> {
  const res = await fetch(`${connectorBase}/${connectorId}`, {
    method: "PATCH",
    headers: authHeaders(accessToken),
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }
  return res.json();
}

export async function disconnectConnector(
  accessToken: string,
  connectorId: string,
): Promise<void> {
  const res = await fetch(`${connectorBase}/${connectorId}`, {
    method: "DELETE",
    headers: authHeaders(accessToken),
  });
  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }
}

export async function fetchConnectorTools(
  accessToken: string,
  connectorId: string,
): Promise<ConnectorToolInfo[]> {
  const res = await fetch(`${connectorBase}/${connectorId}/tools`, {
    headers: authHeaders(accessToken),
  });
  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }
  const payload = (await res.json()) as { tools: ConnectorToolInfo[] };
  return payload.tools;
}

export function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function connectorIconId(id: string): "calendar" | "drive" | "mail" | "plug" {
  if (id.includes("calendar")) return "calendar";
  if (id.includes("drive")) return "drive";
  if (id.includes("gmail")) return "mail";
  return "plug";
}
