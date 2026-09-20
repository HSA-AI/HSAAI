/**
 * FIX F-07: Mobile SQLite database — promise-mode API consistently.
 * Was mixing enablePromise(true) with callback-style openDatabase() — neither worked.
 */
import SQLite from 'react-native-sqlite-storage';

// Enable promise-based API (must be called before any openDatabase)
SQLite.enablePromise(true);

let db: SQLite.SQLiteDatabase | null = null;

const DB_NAME = 'hsaai.db';
const DB_VERSION = '1.0';
const DB_DISPLAY_NAME = 'HSAAI Database';
const DB_SIZE = 200000; // 200KB initial

export async function getDatabase(): Promise<SQLite.SQLiteDatabase> {
  if (db) return db;

  // FIX F-07: Promise-mode openDatabase — NO callback arguments.
  // The 2nd and 3rd args were callbacks that never fire in promise mode,
  // causing the promise to never resolve and the DB to never initialize.
  db = await SQLite.openDatabase({ name: DB_NAME, location: 'default' });
  console.log('[DB] Database opened');

  await initSchema(db);
  return db;
}

async function initSchema(database: SQLite.SQLiteDatabase): Promise<void> {
  // Conversations table
  await database.executeSql(`
    CREATE TABLE IF NOT EXISTS conversations (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      workspace_id TEXT NOT NULL DEFAULT 'hsa-main-workspace',
      created_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL,
      synced INTEGER DEFAULT 0
    );
  `);

  // Messages table
  await database.executeSql(`
    CREATE TABLE IF NOT EXISTS messages (
      id TEXT PRIMARY KEY,
      conversation_id TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
      content TEXT NOT NULL,
      agent TEXT,
      sources TEXT,
      created_at INTEGER NOT NULL,
      synced INTEGER DEFAULT 0,
      FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
    );
  `);

  // Documents cache table
  await database.executeSql(`
    CREATE TABLE IF NOT EXISTS documents_cache (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      department TEXT,
      category TEXT,
      size TEXT,
      uploaded_at TEXT,
      classification TEXT,
      summary TEXT,
      content TEXT,
      cached_at INTEGER NOT NULL
    );
  `);

  // Notifications table
  await database.executeSql(`
    CREATE TABLE IF NOT EXISTS notifications (
      id TEXT PRIMARY KEY,
      type TEXT NOT NULL,
      title TEXT NOT NULL,
      body TEXT NOT NULL,
      priority TEXT DEFAULT 'medium',
      read INTEGER DEFAULT 0,
      created_at TEXT NOT NULL,
      action_url TEXT,
      action_label TEXT
    );
  `);

  // Create indexes for performance
  await database.executeSql(`CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);`);
  await database.executeSql(`CREATE INDEX IF NOT EXISTS idx_documents_department ON documents_cache(department);`);
  await database.executeSql(`CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read);`);

  console.log('[DB] Schema initialized');
}

export async function closeDatabase(): Promise<void> {
  if (db) {
    await db.close();
    db = null;
    console.log('[DB] Database closed');
  }
}

export { DB_NAME, DB_VERSION, DB_DISPLAY_NAME, DB_SIZE };
