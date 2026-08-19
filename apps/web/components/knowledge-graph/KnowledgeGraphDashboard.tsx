"use client";

import { useEffect, useState, useCallback } from "react";
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
import { ErrorCard } from "@/components/error-card";
import { apiGet, apiPost, type ApiError } from "@/lib/safe-fetch";

// ═══════════════════════════════════════════════════════════════════════
// FIX V3: Replaced the broken readJson() helper that used
// `throw new Error(await response.text())` — which captured entire HTML
// pages as the error message and rendered them in the UI.
// Now uses the enterprise safeFetch utility that:
//   1. Never uses response.text() as error message
//   2. Validates Content-Type is JSON before parsing
//   3. Returns structured ApiError objects with Arabic messages
// ═══════════════════════════════════════════════════════════════════════

export function KnowledgeGraphDashboard() {
  const [entities, setEntities] = useState<GraphEntity[]>([]);
  const [relationships, setRelationships] = useState<GraphRelationship[]>([]);
  const [health, setHealth] = useState<GraphHealth | null>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<GraphEntity | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    const [healthRes, entitiesRes, relationshipsRes] = await Promise.all([
      apiGet<GraphHealth>("/api/knowledge-graph/health"),
      apiGet<{ items: GraphEntity[] }>("/api/knowledge-graph/entities?limit=100"),
      apiGet<{ items: GraphRelationship[] }>("/api/knowledge-graph/relationships?limit=200"),
    ]);

    // Check for errors
    if (healthRes.error) {
      setError(healthRes.error);
      setLoading(false);
      return;
    }
    if (entitiesRes.error) {
      setError(entitiesRes.error);
      setLoading(false);
      return;
    }
    if (relationshipsRes.error) {
      setError(relationshipsRes.error);
      setLoading(false);
      return;
    }

    setHealth(healthRes.data);
    setEntities(entitiesRes.data?.items || []);
    setRelationships(relationshipsRes.data?.items || []);
    setLoading(false);
  }, []);

  const search = useCallback(async () => {
    const res = await apiGet<{ entities: GraphEntity[]; relationships: GraphRelationship[] }>(
      `/api/knowledge-graph/search?q=${encodeURIComponent(query)}&limit=50`
    );
    if (res.error) {
      setError(res.error);
      return;
    }
    setError(null);
    setEntities(res.data?.entities || []);
    setRelationships(res.data?.relationships || []);
  }, [query]);

  const seed = useCallback(async () => {
    const res = await apiPost("/api/knowledge-graph/seed");
    if (res.error) {
      setError(res.error);
      return;
    }
    await load();
  }, [load]);

  useEffect(() => { void load(); }, [load]);

  return (
    <div className="space-y-6">
      <ErrorCard error={error} onRetry={() => void load()} />
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 rounded-full border-4 border-border border-t-primary-gold animate-spin" />
        </div>
      )}
      {!loading && !error && (
        <>
          <GraphStatsCards health={health} />
          <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
            <GraphSearchBar value={query} onChange={setQuery} onSearch={() => void search()} />
            <GraphHealthIndicator health={health} />
          </div>
          <GraphIngestionStatus health={health} onSeed={() => void seed()} />
          <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
            <KnowledgeGraphCanvas entities={entities} relationships={relationships} />
            <RelationshipPanel relationships={relationships} />
          </div>
          <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
            <div className="grid gap-4 md:grid-cols-2">
              {entities.map((entity) => (
                <EntityCard key={entity.entity_key} entity={entity} onSelect={setSelected} />
              ))}
            </div>
            <DocumentGraphView entities={entities} />
          </div>
          <EntityDetailsDrawer entity={selected} onClose={() => setSelected(null)} />
        </>
      )}
    </div>
  );
}
