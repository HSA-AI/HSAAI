import client from './client';

export interface KnowledgeDocument {
  id: string;
  title: string;
  department: string;
  category: string;
  size: string;
  uploadedAt: string;
  classification: 'public' | 'internal' | 'confidential' | 'restricted';
  summary?: string;
}

export interface SearchResult {
  id: string;
  title: string;
  snippet: string;
  score: number;
  source: string;
  page?: number;
}

export async function getDocuments(
  department?: string,
  category?: string,
  page: number = 1,
  limit: number = 20,
): Promise<{ documents: KnowledgeDocument[]; total: number }> {
  const params: Record<string, unknown> = { page, limit };
  if (department) params.department = department;
  if (category) params.category = category;
  const { data } = await client.get('/v1/knowledge/documents', { params });
  return data;
}

export async function searchKnowledge(query: string): Promise<SearchResult[]> {
  const { data } = await client.post('/v1/knowledge/search', { query });
  return data.results || [];
}

export async function getDocument(docId: string): Promise<KnowledgeDocument & { content: string }> {
  const { data } = await client.get(`/v1/knowledge/documents/${docId}`);
  return data;
}

export async function uploadDocument(
  file: { uri: string; name: string; type: string },
  metadata: { department: string; category: string; classification: string },
): Promise<KnowledgeDocument> {
  const formData = new FormData();
  formData.append('file', file as unknown as Blob);
  formData.append('department', metadata.department);
  formData.append('category', metadata.category);
  formData.append('classification', metadata.classification);

  const { data } = await client.post('/v1/knowledge/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}
