class WindowsEventLogReader:
    def status(self) -> dict:
        return {"configured": False, "mode": "read-only", "note": "Enable WinRM/Windows Event Forwarding in the enterprise environment."}
