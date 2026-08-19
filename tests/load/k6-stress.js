/**
 * HSAAI K6 Stress Test — 10K-100K Request Validation
 *
 * Stages:
 *   1. Warm-up: 10 → 100 VUs over 2 min
 *   2. Ramp-up: 100 → 1000 VUs over 5 min
 *   3. Peak: 1000 VUs sustained for 10 min
 *   4. Stress: 1000 → 5000 VUs over 5 min
 *   5. Extreme: 5000 VUs for 5 min
 *   6. Cool-down: 5000 → 10 VUs over 2 min
 *
 * Usage:
 *   k6 run tests/load/k6-stress.js
 *   k6 run --out influxdb=http://influxdb:8086/k6 tests/load/k6-stress.js
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

// Custom metrics
const errorRate = new Rate("errors");
const chatLatency = new Trend("chat_latency", true);
const searchLatency = new Trend("search_latency", true);

export const options = {
  stages: [
    { duration: "2m", target: 100 },    // Warm-up
    { duration: "5m", target: 1000 },   // Ramp-up
    { duration: "10m", target: 1000 },  // Sustained peak
    { duration: "5m", target: 5000 },   // Stress
    { duration: "5m", target: 5000 },   // Extreme
    { duration: "2m", target: 10 },     // Cool-down
  ],
  thresholds: {
    http_req_duration: ["p(95)<3000", "p(99)<5000"],  // P95<3s, P99<5s
    errors: ["rate<0.05"],                              // <5% error rate
    chat_latency: ["p(95)<5000", "p(99)<10000"],        // Chat P95<5s
    search_latency: ["p(95)<2000"],                     // Search P95<2s
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";

const QUERIES = [
  "ما هي سياسة العمل عن بُعد؟",
  "How do I request annual leave?",
  "ما هي إجراءات الأمن السيبراني؟",
  "What training programs are available?",
  "كيف أصل إلى مستندات الامتثال؟",
];

export default function () {
  const query = QUERIES[Math.floor(Math.random() * QUERIES.length)];

  // 80% search, 20% chat
  if (Math.random() < 0.8) {
    // Search
    const searchStart = Date.now();
    const searchRes = http.get(
      `${BASE_URL}/v1/rag/search?query=${encodeURIComponent(query)}&limit=5`,
      { timeout: "10s" }
    );
    searchLatency.add(Date.now() - searchStart);

    check(searchRes, {
      "search status 200": (r) => r.status === 200,
      "search has results": (r) => {
        try { return JSON.parse(r.body).results !== undefined; }
        catch { return false; }
      },
    }) || errorRate.add(1);

  } else {
    // Chat
    const chatStart = Date.now();
    const chatRes = http.post(
      `${BASE_URL}/chat`,
      JSON.stringify({
        message: query,
        workspace_id: "k6-stress-test",
      }),
      {
        headers: { "Content-Type": "application/json" },
        timeout: "30s",
      }
    );
    chatLatency.add(Date.now() - chatStart);

    check(chatRes, {
      "chat status 200": (r) => r.status === 200,
      "chat has response": (r) => {
        try { return JSON.parse(r.body).response !== undefined || JSON.parse(r.body).message !== undefined; }
        catch { return r.status === 200; }
      },
    }) || errorRate.add(1);
  }

  sleep(Math.random() * 2 + 0.5);  // 0.5-2.5s think time
}
