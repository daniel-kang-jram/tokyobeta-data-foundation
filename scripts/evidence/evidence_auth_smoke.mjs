#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const HOME_FALLBACK_MARKER = "KPI Landing (Gold)";
const MALFORMED_API_PATH_PATTERN = /\/api\/\/+/;
const METADATA_CONSOLE_FAILURE_PATTERN = /(Unexpected token '<'|evidencemeta\.json)/i;

const ROUTE_MATRIX = Object.freeze({
  occupancy: Object.freeze({
    path: "/occupancy",
    h1: "Occupancy Trend & Net Drivers",
    kpi_markers: Object.freeze(["Occupancy rate trend"]),
    time_context_markers: Object.freeze(["Time basis:", "Freshness:"]),
    funnel_markers: Object.freeze([]),
  }),
  moveins: Object.freeze({
    path: "/moveins",
    h1: "Move-in Profiling (Daily / Weekly / Monthly)",
    kpi_markers: Object.freeze(["Period Controls"]),
    time_context_markers: Object.freeze(["Time basis:", "Freshness:"]),
    funnel_markers: Object.freeze([]),
  }),
  moveouts: Object.freeze({
    path: "/moveouts",
    h1: "Move-out Profiling (Daily / Weekly / Monthly)",
    kpi_markers: Object.freeze(["Period Controls"]),
    time_context_markers: Object.freeze(["Time basis:", "Freshness:"]),
    funnel_markers: Object.freeze([]),
  }),
  geography: Object.freeze({
    path: "/geography",
    h1: "Geography & Property Breakdown",
    kpi_markers: Object.freeze(["Tokyo Occupancy Map (Latest Snapshot)"]),
    time_context_markers: Object.freeze(["Time basis:", "Freshness:"]),
    funnel_markers: Object.freeze([]),
  }),
  pricing: Object.freeze({
    path: "/pricing",
    h1: "Pricing and Segment Parity (Gold)",
    kpi_markers: Object.freeze(["Storyline"]),
    time_context_markers: Object.freeze(["Time basis:", "Freshness:"]),
    funnel_markers: Object.freeze([
      "Overall Conversion Rate (%)",
      "Municipality Segment Parity (Applications vs Move-ins)",
      "Nationality Segment Parity (Applications vs Move-ins)",
      "Monthly Conversion Trend",
    ]),
  }),
});

const NEGATIVE_MARKERS = Object.freeze([HOME_FALLBACK_MARKER]);
const DEFAULT_BASE_URL = "https://intelligence.jram.jp";
const DEFAULT_TIMEOUT_MS = 45_000;

function usage() {
  console.error(`Usage: node scripts/evidence/evidence_auth_smoke.mjs [options]

Options:
  --base-url <url>          Evidence app URL (default: EVIDENCE_APP_URL or ${DEFAULT_BASE_URL})
  --username <value>        Auth username (default: EVIDENCE_AUTH_USERNAME)
  --password <value>        Auth password (default: EVIDENCE_AUTH_PASSWORD)
  --artifact-dir <path>     Artifact output directory (default: output/evidence-auth-smoke)
  --timeout-ms <number>     Timeout per assertion in milliseconds (default: ${DEFAULT_TIMEOUT_MS})
  --dry-run                 Skip browser login/navigation and write deterministic placeholder artifacts
  --print-route-matrix      Print deterministic route matrix JSON and exit
  --help                    Show this usage text
`);
}

function parseArgs(argv) {
  const options = {
    baseUrl: process.env.EVIDENCE_APP_URL ?? DEFAULT_BASE_URL,
    username: process.env.EVIDENCE_AUTH_USERNAME ?? "",
    password: process.env.EVIDENCE_AUTH_PASSWORD ?? "",
    artifactDir: process.env.EVIDENCE_ARTIFACT_DIR ?? "output/evidence-auth-smoke",
    timeoutMs: Number.parseInt(process.env.EVIDENCE_SMOKE_TIMEOUT_MS ?? `${DEFAULT_TIMEOUT_MS}`, 10),
    dryRun: false,
    printRouteMatrix: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];

    if (arg === "--base-url") {
      options.baseUrl = argv[i + 1] ?? "";
      i += 1;
      continue;
    }

    if (arg === "--username") {
      options.username = argv[i + 1] ?? "";
      i += 1;
      continue;
    }

    if (arg === "--password") {
      options.password = argv[i + 1] ?? "";
      i += 1;
      continue;
    }

    if (arg === "--artifact-dir") {
      options.artifactDir = argv[i + 1] ?? "";
      i += 1;
      continue;
    }

    if (arg === "--timeout-ms") {
      options.timeoutMs = Number.parseInt(argv[i + 1] ?? "", 10);
      i += 1;
      continue;
    }

    if (arg === "--dry-run") {
      options.dryRun = true;
      continue;
    }

    if (arg === "--print-route-matrix") {
      options.printRouteMatrix = true;
      continue;
    }

    if (arg === "--help") {
      usage();
      process.exit(0);
    }

    throw new Error(`Unknown argument: ${arg}`);
  }

  if (!options.baseUrl) {
    throw new Error("Missing --base-url value.");
  }

  if (!Number.isFinite(options.timeoutMs) || options.timeoutMs <= 0) {
    throw new Error("timeout must be a positive integer.");
  }

  if (!options.artifactDir) {
    throw new Error("Missing --artifact-dir value.");
  }

  return {
    ...options,
    baseUrl: options.baseUrl.replace(/\/+$/, ""),
    artifactDir: path.resolve(options.artifactDir),
  };
}

function routeMatrixPayload() {
  return {
    routes: ROUTE_MATRIX,
    negative_markers: NEGATIVE_MARKERS,
  };
}

function ensureDir(directoryPath) {
  fs.mkdirSync(directoryPath, { recursive: true });
}

function writeJson(filePath, payload) {
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, "utf-8");
}

function collectArtifactSummary(artifactPaths) {
  const screenshotsCount = fs.existsSync(artifactPaths.screenshotsDir)
    ? fs.readdirSync(artifactPaths.screenshotsDir).length
    : 0;
  return {
    screenshots_count: screenshotsCount,
    console_log: fs.existsSync(artifactPaths.consoleLogPath),
    network_log: fs.existsSync(artifactPaths.networkLogPath),
  };
}

function buildMetadataUrl(baseUrl, routePath) {
  const normalizedRoute = routePath.replace(/^\/+/, "");
  if (!normalizedRoute) {
    return `${baseUrl}/api/evidencemeta.json`;
  }
  return `${baseUrl}/api/${normalizedRoute}/evidencemeta.json`;
}

async function waitForVisible(locator, timeoutMs) {
  await locator.first().waitFor({ state: "visible", timeout: timeoutMs });
}

async function assertHeading(page, headingText, timeoutMs) {
  const roleHeading = page.getByRole("heading", { level: 1, name: headingText });
  try {
    await waitForVisible(roleHeading, timeoutMs);
    return;
  } catch {
    await waitForVisible(page.locator("h1", { hasText: headingText }), timeoutMs);
  }
}

async function assertMarkerVisible(page, marker, timeoutMs) {
  await waitForVisible(page.getByText(marker, { exact: false }), timeoutMs);
}

async function assertNoHomeFallback(page) {
  const fallbackLocator = page.getByText(HOME_FALLBACK_MARKER, { exact: false });
  const fallbackCount = await fallbackLocator.count();
  if (fallbackCount > 0 && (await fallbackLocator.first().isVisible())) {
    throw new Error(
      `Detected Home fallback marker "${HOME_FALLBACK_MARKER}" on non-home route.`
    );
  }
}

async function authenticate(page, options) {
  await page.goto(options.baseUrl, { waitUntil: "domcontentloaded", timeout: options.timeoutMs });

  const passwordInput = page.locator('input[type="password"]').first();
  if (!(await passwordInput.isVisible())) {
    return;
  }

  if (!options.username || !options.password) {
    throw new Error(
      "Auth fields were detected but credentials are missing. Set EVIDENCE_AUTH_USERNAME/EVIDENCE_AUTH_PASSWORD."
    );
  }

  const usernameCandidates = [
    'input[name="username"]',
    "#username",
    'input[name="email"]',
    'input[type="email"]',
    'input[type="text"]',
  ];

  let usernameFieldVisible = false;
  let usernameFilled = false;
  for (const selector of usernameCandidates) {
    const candidate = page.locator(selector).first();
    if (await candidate.isVisible()) {
      usernameFieldVisible = true;
      await candidate.fill(options.username);
      usernameFilled = true;
      break;
    }
  }

  if (usernameFieldVisible && !usernameFilled) {
    throw new Error("Unable to find a visible username/email field on login page.");
  }

  await passwordInput.fill(options.password);

  const loginButton = page.getByRole("button", {
    name: /sign in|log in|login|continue/i,
  });
  if ((await loginButton.count()) > 0 && (await loginButton.first().isVisible())) {
    await loginButton.first().click();
  } else {
    await passwordInput.press("Enter");
  }

  await page.waitForLoadState("networkidle", { timeout: options.timeoutMs });
}

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(
      `Unable to import "playwright". Install it before non-dry runs (for example: npm --yes --package=playwright exec -- node scripts/evidence/evidence_auth_smoke.mjs). Details: ${detail}`
    );
  }
}

function initializeArtifacts(artifactDir) {
  const screenshotsDir = path.join(artifactDir, "screenshots");
  ensureDir(artifactDir);
  ensureDir(screenshotsDir);
  return {
    screenshotsDir,
    consoleLogPath: path.join(artifactDir, "console_logs.json"),
    networkLogPath: path.join(artifactDir, "network_logs.json"),
    summaryPath: path.join(artifactDir, "summary.json"),
  };
}

function createRouteResult(routeContract) {
  return {
    path: routeContract.path,
    h1: routeContract.h1,
    kpi_markers: [...routeContract.kpi_markers],
    time_context_markers: [...routeContract.time_context_markers],
    funnel_markers: [...routeContract.funnel_markers],
    metadata_url: "",
    status: "pending",
    error: null,
  };
}

async function runDryMode(options, artifactPaths) {
  const routeResults = {};
  for (const [routeKey, routeContract] of Object.entries(ROUTE_MATRIX)) {
    const result = createRouteResult(routeContract);
    result.metadata_url = buildMetadataUrl(options.baseUrl, routeContract.path);
    result.status = "dry-run";
    routeResults[routeKey] = result;

    const placeholderPath = path.join(artifactPaths.screenshotsDir, `${routeKey}.txt`);
    fs.writeFileSync(
      placeholderPath,
      `dry-run placeholder for ${routeContract.path}; screenshot capture skipped\n`,
      "utf-8"
    );
  }

  writeJson(artifactPaths.consoleLogPath, []);
  writeJson(artifactPaths.networkLogPath, []);
  const summary = {
    mode: "dry-run",
    base_url: options.baseUrl,
    artifact_dir: options.artifactDir,
    route_results: routeResults,
    malformed_api_requests: [],
    metadata_console_failures: [],
    negative_markers: NEGATIVE_MARKERS,
  };
  summary.artifacts = collectArtifactSummary(artifactPaths);
  writeJson(artifactPaths.summaryPath, summary);
}

async function runSmoke(options, artifactPaths) {
  const { chromium } = await loadPlaywright();
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const consoleLogs = [];
  const networkLogs = [];
  const routeResults = {};
  const malformedApiRequests = [];
  const metadataConsoleFailures = [];

  page.on("console", (message) => {
    const entry = {
      type: message.type(),
      text: message.text(),
      location: message.location(),
    };
    consoleLogs.push(entry);
    if (METADATA_CONSOLE_FAILURE_PATTERN.test(entry.text)) {
      metadataConsoleFailures.push(entry);
    }
  });

  page.on("pageerror", (error) => {
    const text = error instanceof Error ? error.message : String(error);
    const entry = { type: "pageerror", text };
    consoleLogs.push(entry);
    if (METADATA_CONSOLE_FAILURE_PATTERN.test(text)) {
      metadataConsoleFailures.push(entry);
    }
  });

  page.on("request", (request) => {
    const entry = {
      type: "request",
      method: request.method(),
      url: request.url(),
      resourceType: request.resourceType(),
    };
    networkLogs.push(entry);
    if (MALFORMED_API_PATH_PATTERN.test(entry.url)) {
      malformedApiRequests.push(entry);
    }
  });

  page.on("response", async (response) => {
    const entry = {
      type: "response",
      url: response.url(),
      status: response.status(),
      contentType: response.headers()["content-type"] ?? "",
    };
    networkLogs.push(entry);
    if (MALFORMED_API_PATH_PATTERN.test(entry.url)) {
      malformedApiRequests.push(entry);
    }
  });

  try {
    await authenticate(page, options);

    for (const [routeKey, routeContract] of Object.entries(ROUTE_MATRIX)) {
      const routeResult = createRouteResult(routeContract);
      routeResults[routeKey] = routeResult;

      try {
        await page.goto(`${options.baseUrl}${routeContract.path}`, {
          waitUntil: "networkidle",
          timeout: options.timeoutMs,
        });

        await assertHeading(page, routeContract.h1, options.timeoutMs);

        for (const marker of routeContract.kpi_markers) {
          await assertMarkerVisible(page, marker, options.timeoutMs);
        }

        for (const marker of routeContract.time_context_markers) {
          await assertMarkerVisible(page, marker, options.timeoutMs);
        }

        for (const marker of routeContract.funnel_markers) {
          await assertMarkerVisible(page, marker, options.timeoutMs);
        }

        await assertNoHomeFallback(page);

        const metadataUrl = buildMetadataUrl(options.baseUrl, routeContract.path);
        routeResult.metadata_url = metadataUrl;

        const metadataResponse = await context.request.get(metadataUrl, {
          timeout: options.timeoutMs,
        });
        const metadataStatus = metadataResponse.status();
        const contentType = metadataResponse.headers()["content-type"] ?? "";
        if (metadataStatus !== 200) {
          throw new Error(`Metadata status ${metadataStatus} for ${metadataUrl}`);
        }
        if (!contentType.toLowerCase().includes("application/json")) {
          throw new Error(
            `Metadata content-type must include application/json for ${metadataUrl}; got "${contentType}"`
          );
        }

        await metadataResponse.json();

        const screenshotPath = path.join(artifactPaths.screenshotsDir, `${routeKey}.png`);
        await page.screenshot({ path: screenshotPath, fullPage: true });

        routeResult.status = "passed";
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        routeResult.status = "failed";
        routeResult.error = message;

        const failureShotPath = path.join(
          artifactPaths.screenshotsDir,
          `${routeKey}-failure.png`
        );
        await page.screenshot({ path: failureShotPath, fullPage: true });
      }
    }
  } finally {
    await browser.close();
  }

  writeJson(artifactPaths.consoleLogPath, consoleLogs);
  writeJson(artifactPaths.networkLogPath, networkLogs);

  const summary = {
    mode: "run",
    base_url: options.baseUrl,
    artifact_dir: options.artifactDir,
    route_results: routeResults,
    malformed_api_requests: malformedApiRequests,
    metadata_console_failures: metadataConsoleFailures,
    negative_markers: NEGATIVE_MARKERS,
  };
  summary.artifacts = collectArtifactSummary(artifactPaths);
  writeJson(artifactPaths.summaryPath, summary);

  const failedRoutes = Object.entries(routeResults)
    .filter(([, routeResult]) => routeResult.status !== "passed")
    .map(([routeKey]) => routeKey);

  if (malformedApiRequests.length > 0) {
    throw new Error(`Detected malformed metadata requests matching /api// (${malformedApiRequests.length}).`);
  }
  if (metadataConsoleFailures.length > 0) {
    throw new Error(
      `Detected metadata-related console/page errors (${metadataConsoleFailures.length}).`
    );
  }
  if (failedRoutes.length > 0) {
    throw new Error(`Route assertions failed for: ${failedRoutes.join(", ")}`);
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const routeMatrix = routeMatrixPayload();

  if (options.printRouteMatrix) {
    process.stdout.write(`${JSON.stringify(routeMatrix, null, 2)}\n`);
    return;
  }

  const artifactPaths = initializeArtifacts(options.artifactDir);
  if (options.dryRun) {
    await runDryMode(options, artifactPaths);
    return;
  }

  await runSmoke(options, artifactPaths);
}

main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`Evidence authenticated smoke failed: ${message}`);
  process.exit(1);
});
