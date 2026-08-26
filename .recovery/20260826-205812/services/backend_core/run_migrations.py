from backend_core.db.database import run_migrations, check_db

if __name__ == "__main__":
    run_migrations()
    import json; print(json.dumps({"migrations": "ok", "database": check_db()}))
