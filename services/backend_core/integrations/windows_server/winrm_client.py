class WinRMReadOnlyClient:
    def run_read_only(self, command: str) -> dict:
        allowed = command.lower().startswith(("get-", "where-object", "select-object"))
        return {"allowed": allowed, "command": command, "mode": "read-only-contract"}
