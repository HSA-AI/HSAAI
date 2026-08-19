export type GraphEntity = {
  id?: number;
  entity_key: string;
  name: string;
  entity_type: string;
  description?: string;
  classification?: string;
  visibility?: string;
  source_ref?: string;
  confidence?: number;
};

export type GraphRelationship = {
  id?: number;
  relationship_key: string;
  source_key: string;
  relationship_type: string;
  target_key: string;
  label?: string;
  confidence?: number;
};

export type GraphHealth = {
  status: string;
  engine: string;
  entities: number;
  relationships: number;
  documents: number;
  graph_rag_bridge_enabled?: boolean;
  graph_ingestion_enabled?: boolean;
  neo4j_configured?: boolean;
  last_ingestion?: { status?: string; source_ref?: string; created_at?: string } | null;
};
