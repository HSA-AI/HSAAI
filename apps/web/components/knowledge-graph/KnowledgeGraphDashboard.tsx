"use client";

import { useEffect, useState } from "react";
import type { GraphEntity, GraphHealth, GraphRelationship } from "./types";
import { DocumentGraphView } from "./DocumentGraphView";
import { EntityCard } from "./EntityCard";
import { EntityDetailsDrawer } from "./EntityDetailsDrawer";
import { GraphHealthIndicator } from "./GraphHealthIndicator";
import { GraphIngestionStatus } from "./GraphIngestionStatus";
import { GraphSearchBar } from "./GraphSearchBar";
import { GraphStatsCards } from "./GraphStatsCards";
import { KnowledgeGraphCanvas } from "./KnowledgeGraphCanvas";
import { RelationshipPanel } from "./RelationshipPanel";

async function readJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, cache: "no-store" });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

export function KnowledgeGraphDashboard() {
  const [entities, setEntities] = useState<GraphEntity[]>([]);
  const [relationships, setRelationships] = useState<GraphRelationship[]>([]);
  const [health, setHealth] = useState<GraphHealth | null>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<GraphEntity | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setError(null);
      const [healthRes, entitiesRes, relationshipsRes] = await Promise.all([
        readJson<GraphHealth>("/api/knowledge-graph/health"),
        readJson<{ items: GraphEntity[] }>("/api/knowledge-graph/entities?limit=100"),
        readJson<{ items: GraphRelationship[] }>("/api/knowledge-graph/relationships?limit=200"),
      ]);
      setHealth(healthRes);
      setEntities(entitiesRes.items || []);
      setRelationships(relationshipsRes.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Knowledge Graph API unavailable");
    }
  }

  async function search() {
    const res = await readJson<{ entities: GraphEntity[]; relationships: GraphRelationship[] }>(`/api/knowledge-graph/search?q=${encodeURIComponent(query)}&limit=50`);
    setEntities(res.entities || []);
    setRelationships(res.relationships || []);
  }

  async function seed() {
    await readJson("/api/knowledge-graph/seed", { method: "POST" });
    await load();
  }

  useEffect(() => { void load(); }, []);

  return (
    <div className="space-y-6">
      {error && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div>}
      <GraphStatsCards health={health} />
      <div className="grid gap-4 xl:grid-cols-[1fr_360px]"><GraphSearchBar value={query} onChange={setQuery} onSearch={() => void search()} /><GraphHealthIndicator health={health} /></div>
      <GraphIngestionStatus health={health} onSeed={() => void seed()} />
      <div className="grid gap-5 xl:grid-cols-[1fr_380px]"><KnowledgeGraphCanvas entities={entities} relationships={relationships} /><RelationshipPanel relationships={relationships} /></div>
      <div className="grid gap-5 xl:grid-cols-[1fr_380px]"><div className="grid gap-4 md:grid-cols-2">{entities.map((entity) => <EntityCard key={entity.entity_key} entity={entity} onSelect={setSelected} />)}</div><DocumentGraphView entities={entities} /></div>
      <EntityDetailsDrawer entity={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
