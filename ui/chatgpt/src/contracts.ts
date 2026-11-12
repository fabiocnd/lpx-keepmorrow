/** Bounded presentation contracts for authenticated server results. */

export type Document = Record<string, unknown>;
export interface CollectionRef { collection_id: string; generation: string }
export interface ToolReply { structuredContent?: unknown; isError?: boolean | undefined }
export interface ToolClient {
  callServerTool(request: { name: string; arguments: Document }): Promise<ToolReply>;
  openLink(request: { url: string }): Promise<{ isError?: boolean | undefined }>;
}

export function object(value: unknown): Document {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("The server returned an unsupported response.");
  }
  return value as Document;
}

export function text(value: unknown, maximum = 4096): string {
  if (typeof value !== "string" || value.length > maximum) {
    throw new Error("The server returned an unsupported text field.");
  }
  return value;
}

export function integer(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    throw new Error("The server returned an unsupported count.");
  }
  return value;
}

export function items(value: unknown, maximum = 100): Document[] {
  if (!Array.isArray(value) || value.length > maximum) {
    throw new Error("The server returned an unsupported page.");
  }
  return value.map(object);
}

export function responseData(reply: ToolReply): Document {
  const envelope = object(reply.structuredContent);
  if (envelope.response_version !== 2) throw new Error("This interface requires the current Keepmorrow server.");
  if (envelope.status === "error" || reply.isError) {
    const code = typeof envelope.error_code === "string" ? envelope.error_code : "request_failed";
    const messages: Record<string, string> = {
      access_denied: "Access is unavailable. Review your current permissions in the secure portal.",
      authorization_denied: "Access is unavailable. Review your current permissions in the secure portal.",
      acceptance_required: "Accept the current terms and privacy notice in the secure portal to continue.",
      busy: "A content operation is in progress. Try again after it finishes.",
      operation_busy: "A content operation is in progress. Try again after it finishes.",
      collection_validation_failed: "The collection could not pass integrity verification.",
      resource_limit: "The request exceeds the current resource limit. Narrow the selection.",
    };
    throw new Error(messages[code] ?? "The request could not be completed. Refresh access or review the secure portal.");
  }
  if (envelope.status !== "ok") throw new Error("The server returned an unsupported status.");
  return object(envelope.data);
}

export function collectionRef(value: Document): CollectionRef {
  return { collection_id: text(value.collection_id, 128), generation: text(value.generation, 128) };
}

export function portalUrl(value: unknown): string {
  const candidate = new URL(text(value, 2048));
  const loopback = candidate.hostname === "127.0.0.1" || candidate.hostname === "localhost";
  if ((candidate.protocol !== "https:" && !(candidate.protocol === "http:" && loopback))
      || candidate.username || candidate.password || candidate.search || candidate.hash) {
    throw new Error("The secure portal address is unsupported.");
  }
  return candidate.href;
}

export function nextOffset(value: unknown): number | null {
  return value === null || value === undefined ? null : integer(value);
}

export function associationLabel(value: unknown): string {
  const state = object(value).state;
  if (state === "project_confirmed") return "Confirmed project";
  if (state === "standalone_confirmed") return "Confirmed standalone";
  if (state === "association_unknown") return "Project association unknown";
  throw new Error("The server returned an unsupported association state.");
}
