import { getDatabase } from './database';
import type { KnowledgeDocument } from '@api/knowledge';

export async function cacheDocument(
  doc: KnowledgeDocument & { content?: string },
): Promise<void> {
  const db = await getDatabase();
  await db.executeSql(
    `INSERT OR REPLACE INTO documents_cache (id, title, department, category, size, uploaded_at, classification, summary, content, cached_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [
      doc.id,
      doc.title,
      doc.department || null,
      doc.category || null,
      doc.size || null,
      doc.uploadedAt,
      doc.classification,
      doc.summary || null,
      doc.content || null,
      Date.now(),
    ],
  );
}

export async function getCachedDocuments(department?: string): Promise<KnowledgeDocument[]> {
  const db = await getDatabase();
  const query = department
    ? `SELECT * FROM documents_cache WHERE department = ? ORDER BY cached_at DESC`
    : `SELECT * FROM documents_cache ORDER BY cached_at DESC`;
  const params = department ? [department] : [];

  const [results] = await db.executeSql(query, params);

  const docs: KnowledgeDocument[] = [];
  for (let i = 0; i < results.rows.length; i++) {
    const row = results.rows.item(i);
    docs.push({
      id: row.id,
      title: row.title,
      department: row.department,
      category: row.category,
      size: row.size,
      uploadedAt: row.uploaded_at,
      classification: row.classification,
      summary: row.summary,
    });
  }
  return docs;
}

export async function getCachedDocument(id: string): Promise<(KnowledgeDocument & { content: string }) | null> {
  const db = await getDatabase();
  const [results] = await db.executeSql(
    `SELECT * FROM documents_cache WHERE id = ?`,
    [id],
  );

  if (results.rows.length === 0) return null;

  const row = results.rows.item(0);
  return {
    id: row.id,
    title: row.title,
    department: row.department,
    category: row.category,
    size: row.size,
    uploadedAt: row.uploaded_at,
    classification: row.classification,
    summary: row.summary,
    content: row.content || '',
  };
}

export async function clearDocumentCache(): Promise<void> {
  const db = await getDatabase();
  await db.executeSql(`DELETE FROM documents_cache`);
}

export async function searchCachedDocuments(query: string): Promise<KnowledgeDocument[]> {
  const db = await getDatabase();
  const [results] = await db.executeSql(
    `SELECT * FROM documents_cache WHERE title LIKE ? OR summary LIKE ? ORDER BY cached_at DESC`,
    [`%${query}%`, `%${query}%`],
  );

  const docs: KnowledgeDocument[] = [];
  for (let i = 0; i < results.rows.length; i++) {
    const row = results.rows.item(i);
    docs.push({
      id: row.id,
      title: row.title,
      department: row.department,
      category: row.category,
      size: row.size,
      uploadedAt: row.uploaded_at,
      classification: row.classification,
      summary: row.summary,
    });
  }
  return docs;
}
