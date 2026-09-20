// FIX D-11: was starting with Python-style triple-quoted docstring — invalid JavaScript.
// HSAAI Performance Validation — k6 Load Test (Phase 14)
// Run with: k6 run tests/load/k6_loadtest.js
// Prerequisites: HSAAI stack running via docker-compose up -d
//
// Test scenarios:
// 1. Smoke test (low load, verify functionality)
// 2. Load test (sustained moderate load)
// 3. Stress test (find breaking point)
// 4. Spike test (sudden traffic surge)
// 5. Soak test (long duration, find memory leaks)
import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// ─── Configuration ──────────────────────────────────────────────
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const LLM_URL = __ENV.LLM_URL || 'http://localhost:8090';
const RAG_URL = __ENV.RAG_URL || 'http://localhost:8001';

// ─── Custom Metrics ─────────────────────────────────────────────
const errorRate = new Rate('errors');
const llmLatency = new Trend('llm_latency_ms', true);
const ragLatency = new Trend('rag_latency_ms', true);
const cacheHits = new Counter('cache_hits');

// ─── Test Scenarios ─────────────────────────────────────────────
export const options = {
  scenarios: {
    // Scenario 1: Smoke test — verify functionality
    smoke: {
      executor: 'constant-vus',
      vus: 1,
      duration: '30s',
      tags: { scenario: 'smoke' },
    },
    // Scenario 2: Load test — sustained moderate load
    load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 50 },   // ramp up
        { duration: '5m', target: 50 },   // sustain
        { duration: '2m', target: 100 },  // ramp up
        { duration: '5m', target: 100 },  // sustain
        { duration: '2m', target: 0 },    // ramp down
      ],
      startTime: '30s',
      tags: { scenario: 'load' },
    },
    // Scenario 3: Stress test — find breaking point
    stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 100 },
        { duration: '5m', target: 200 },
        { duration: '2m', target: 400 },
        { duration: '5m', target: 400 },
        { duration: '2m', target: 600 },
        { duration: '5m', target: 600 },
        { duration: '2m', target: 0 },
      ],
      startTime: '15m',
      tags: { scenario: 'stress' },
    },
    // Scenario 4: Spike test — sudden surge
    spike: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 0 },
        { duration: '1m', target: 500 },  // sudden spike
        { duration: '5m', target: 500 },
        { duration: '1m', target: 0 },
      ],
      startTime: '30m',
      tags: { scenario: 'spike' },
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],  // 95% < 500ms, 99% < 1s
    errors: ['rate<0.01'],                              // < 1% errors
    llm_latency_ms: ['p(95)<5000', 'p(99)<10000'],     // LLM: 95% < 5s, 99% < 10s
    rag_latency_ms: ['p(95)<1000'],                     // RAG: 95% < 1s
  },
};

// ─── Test Functions ─────────────────────────────────────────────
export default function () {
  const token = __ENV.AUTH_TOKEN || 'test-token';
  const headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'X-Tenant-Id': 'hsa-foods',
  };

  group('Health Check', () => {
    const res = http.get(`${BASE_URL}/health`, { headers });
    check(res, {
      'health 200': (r) => r.status === 200,
      'health ok': (r) => r.json('status') === 'ok',
    });
  });

  group('RAG Query', () => {
    const start = Date.now();
    const res = http.post(`${RAG_URL}/query`, JSON.stringify({
      query: 'What is the procurement policy for suppliers?',
      tenant_id: 'hsa-foods',
      top_k: 5,
    }), { headers });
    ragLatency.add(Date.now() - start);
    check(res, {
      'rag 200': (r) => r.status === 200,
      'rag has results': (r) => r.json('results') !== undefined,
    });
    errorRate.add(res.status !== 200);
  });

  group('LLM Generate', () => {
    const start = Date.now();
    const res = http.post(`${LLM_URL}/v1/generate`, JSON.stringify({
      prompt: 'Summarize the procurement policy in 3 sentences.',
      max_tokens: 256,
      tenant_id: 'hsa-foods',
      use_cache: true,
    }), { headers });
    const latency = Date.now() - start;
    llmLatency.add(latency);
    check(res, {
      'llm 200': (r) => r.status === 200,
      'llm has text': (r) => r.json('text') !== undefined,
    });
    if (res.status === 200 && res.json('cache_hit')) {
      cacheHits.add(1);
    }
    errorRate.add(res.status !== 200);
  });

  sleep(1);  // 1 request per second per VU
}

// ─── Teardown ───────────────────────────────────────────────────
export function teardown() {
  console.log('Load test complete. Check Grafana for detailed metrics.');
}

// ─── Handle Summary ─────────────────────────────────────────────
export function handleSummary(data) {
  return {
    'tests/load/results.json': JSON.stringify(data, null, 2),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}

function textSummary(data, opts = {}) {
  const lines = [];
  lines.push('=== HSAAI Load Test Summary ===');
  lines.push(`Total requests: ${data.metrics.http_reqs.values.count}`);
  lines.push(`Avg latency: ${data.metrics.http_req_duration.values.avg.toFixed(2)}ms`);
  lines.push(`P95 latency: ${data.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms`);
  lines.push(`P99 latency: ${data.metrics.http_req_duration.values['p(99)'].toFixed(2)}ms`);
  lines.push(`Error rate: ${(data.metrics.errors.values.rate * 100).toFixed(2)}%`);
  return lines.join('\n');
}
