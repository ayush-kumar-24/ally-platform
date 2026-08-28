// k6 load test for Ally's backend.
//
// Run locally:   BASE_URL=https://staging.example.com k6 run scripts/load-test/k6-script.js
// Run in CI:     see .github/workflows/load-test.yml (workflow_dispatch)
//
// This hits only read/health endpoints by default so a first run can't write
// junk data or burn LLM credits. Add authenticated / write scenarios only
// once you've confirmed the target is a staging environment, never prod.

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const AUTH_TOKEN = __ENV.AUTH_TOKEN || ""; // optional bearer token for authenticated checks

// Peak virtual users and total ramp duration are overridable from the
// workflow_dispatch inputs / environment, so one script covers a 50-VU smoke
// test and a 10,000-VU run.
const PEAK_VUS = Number(__ENV.PEAK_VUS || 50);
const RAMP_DURATION = __ENV.RAMP_DURATION || "1m";
const HOLD_DURATION = __ENV.HOLD_DURATION || "3m";

const errorRate = new Rate("errors");

export const options = {
  scenarios: {
    ramping_load: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: RAMP_DURATION, target: PEAK_VUS }, // ramp up
        { duration: HOLD_DURATION, target: PEAK_VUS }, // hold at peak
        { duration: "30s", target: 0 }, // ramp down
      ],
      gracefulRampDown: "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"], // fail the run if >5% of requests error
    http_req_duration: ["p(95)<2000"], // 95% of requests under 2s
  },
};

function authHeaders() {
  return AUTH_TOKEN ? { Authorization: `Bearer ${AUTH_TOKEN}` } : {};
}

export default function () {
  // 1. Health check — cheap, no DB pool usage, good canary for App Runner scaling.
  const health = http.get(`${BASE_URL}/`);
  check(health, {
    "health check status is 200": (r) => r.status === 200,
  }) || errorRate.add(1);

  // 2. A representative authenticated read, only if a token was provided.
  // Swap the path below for whichever GET endpoint you want to stress
  // (e.g. /api/v1/dashboard, /api/v1/founder-dna) once you've confirmed the
  // target is staging, not production.
  if (AUTH_TOKEN) {
    const dashboard = http.get(`${BASE_URL}/api/v1/dashboard`, {
      headers: authHeaders(),
    });
    check(dashboard, {
      "dashboard status is 200 or 401": (r) => r.status === 200 || r.status === 401,
    }) || errorRate.add(1);
  }

  sleep(1);
}
