import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function backendBase(): string {
  return (
    process.env.BACKEND_PROXY_TARGET?.trim().replace(/\/+$/, "") ||
    "http://127.0.0.1:8000"
  );
}

type Ctx = { params: Promise<{ path: string[] }> };

/** Headers that prevent SSE / chunked responses from streaming through Next. */
const HOP_BY_HOP_OR_BUFFERING = new Set([
  "content-length",
  "content-encoding",
  "transfer-encoding",
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "upgrade",
]);

function buildResponseHeaders(upstream: Headers, isEventStream: boolean): Headers {
  const out = new Headers();
  upstream.forEach((value, key) => {
    if (HOP_BY_HOP_OR_BUFFERING.has(key.toLowerCase())) return;
    out.set(key, value);
  });
  if (isEventStream) {
    // Force pass-through streaming behavior end-to-end.
    out.set("Cache-Control", "no-cache, no-transform");
    out.set("X-Accel-Buffering", "no");
    out.set("Connection", "keep-alive");
    // Tell any downstream compressor (Next dev server, CDN, etc.) NOT to
    // gzip this response; gzip block buffering destroys SSE streaming.
    out.set("Content-Encoding", "identity");
    out.set("Vary", "Accept");
  }
  return out;
}

async function proxy(request: NextRequest, context: Ctx): Promise<Response> {
  const { path } = await context.params;
  const pathStr = (path ?? []).join("/");
  const qs = request.nextUrl.search;
  const url = `${backendBase()}/api/v1/${pathStr}${qs}`;

  const headers = new Headers(request.headers);
  headers.delete("host");
  // Remove anything that asks upstream to compress (gzip/br) so the proxy can
  // forward the raw byte stream chunk-by-chunk.
  headers.delete("accept-encoding");

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
    // @ts-expect-error – Node fetch supports `duplex` but it isn't in the lib types yet.
    duplex: "half",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    // Buffer small JSON request bodies instead of streaming to avoid
    // intermittent socket resets in the dev proxy path.
    const rawBody = await request.text();
    init.body = rawBody.length > 0 ? rawBody : undefined;
  }

  try {
    const res = await fetch(url, init);
    const upstreamCt = res.headers.get("content-type") ?? "";
    const isEventStream = upstreamCt.includes("text/event-stream");

    return new NextResponse(res.body, {
      status: res.status,
      statusText: res.statusText,
      headers: buildResponseHeaders(res.headers, isEventStream),
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Upstream proxy failure";
    return NextResponse.json(
      {
        detail: `Backend proxy error: ${message}`,
      },
      { status: 502 },
    );
  }
}

export function GET(request: NextRequest, context: Ctx) {
  return proxy(request, context);
}

export function POST(request: NextRequest, context: Ctx) {
  return proxy(request, context);
}

export function PUT(request: NextRequest, context: Ctx) {
  return proxy(request, context);
}

export function PATCH(request: NextRequest, context: Ctx) {
  return proxy(request, context);
}

export function DELETE(request: NextRequest, context: Ctx) {
  return proxy(request, context);
}

export function OPTIONS(request: NextRequest, context: Ctx) {
  return proxy(request, context);
}

export function HEAD(request: NextRequest, context: Ctx) {
  return proxy(request, context);
}
