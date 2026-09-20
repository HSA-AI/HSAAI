// FIX F-01: api is a default export — was using named import { api } causing TS2305 build error.
import api from "./api";
export type ChatPayload = { user: string; message: string; workspace_id: string };
export async function sendChat(payload: ChatPayload) { const { data } = await api.post("/v1/chat", payload); return data; }
