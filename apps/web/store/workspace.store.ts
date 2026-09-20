import { create } from "zustand";
type WorkspaceState = { workspaceId: string; setWorkspace: (id: string) => void };
export const useWorkspaceStore = create<WorkspaceState>((set) => ({ workspaceId: "default", setWorkspace: (workspaceId) => set({ workspaceId }) }));
