const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

function renderTemplate(template, replacements) {
  let out = template;
  Object.keys(replacements).forEach((key) => {
    out = out.split(key).join(replacements[key]);
  });
  return out;
}

function loadHandler(opts = {}) {
  const templatePath = path.join(__dirname, "basic_auth.js");
  const template = fs.readFileSync(templatePath, "utf8");
  const rendered = renderTemplate(template, {
    "${auth_users_json}": JSON.stringify(opts.authUsers || []),
    "${auth_ui_mode}": opts.authUiMode || "login_page",
    "${auth_session_max_age_seconds}": String(opts.sessionMaxAge || 28800),
    "${auth_login_copy_language}": opts.copyLanguage || "en",
  });

  const sandbox = {};
  vm.createContext(sandbox);
  vm.runInContext(`${rendered}\nthis.__handler = handler;`, sandbox);
  return sandbox.__handler;
}

function toBase64(input) {
  return Buffer.from(input, "utf8").toString("base64");
}

function eventOf(uri, querystring, headers, cookies) {
  return {
    request: {
      uri: uri || "/",
      querystring: querystring || "",
      headers: headers || {},
      cookies: cookies || {},
    },
  };
}

function getCookie(resp, cookieName) {
  if (!resp.cookies) {
    return null;
  }
  return resp.cookies[cookieName] || null;
}

function loginAndGetSession(handler) {
  const loginResp = handler(
    eventOf("/__auth/login", "return_to=%2F", {
      authorization: { value: `Basic ${toBase64("demo:pass")}` },
    })
  );
  const cookie = getCookie(loginResp, "evidence_session");
  assert.ok(cookie && cookie.value, "expected evidence_session cookie from login");
  return cookie.value;
}

function testRewritesExtensionlessProtectedRouteToIndexHtml() {
  const handler = loadHandler({
    authUsers: [toBase64("demo:pass")],
    authUiMode: "login_page",
  });
  const session = loginAndGetSession(handler);
  const resp = handler(
    eventOf(
      "/occupancy",
      "",
      {},
      {
        evidence_session: { value: session },
      }
    )
  );

  assert.strictEqual(resp.uri, "/occupancy/index.html");
}

function testRewritesTrailingSlashProtectedRouteToIndexHtml() {
  const handler = loadHandler({
    authUsers: [toBase64("demo:pass")],
    authUiMode: "login_page",
  });
  const session = loginAndGetSession(handler);
  const resp = handler(
    eventOf(
      "/moveins/",
      "",
      {},
      {
        evidence_session: { value: session },
      }
    )
  );

  assert.strictEqual(resp.uri, "/moveins/index.html");
}

function testDoesNotRewriteApiAndStaticAssetPaths() {
  const handler = loadHandler({
    authUsers: [toBase64("demo:pass")],
    authUiMode: "login_page",
  });
  const session = loginAndGetSession(handler);
  const authCookie = {
    evidence_session: { value: session },
  };

  const apiResp = handler(eventOf("/api/evidencemeta.json", "", {}, authCookie));
  const appResp = handler(eventOf("/_app/immutable/entry/start.js", "", {}, authCookie));
  const dataResp = handler(eventOf("/data/manifest.json", "", {}, authCookie));

  assert.strictEqual(apiResp.uri, "/api/evidencemeta.json");
  assert.strictEqual(appResp.uri, "/_app/immutable/entry/start.js");
  assert.strictEqual(dataResp.uri, "/data/manifest.json");
}

function runAllTests() {
  const tests = [
    testRewritesExtensionlessProtectedRouteToIndexHtml,
    testRewritesTrailingSlashProtectedRouteToIndexHtml,
    testDoesNotRewriteApiAndStaticAssetPaths,
  ];
  for (const t of tests) {
    t();
  }
}

runAllTests();
console.log("basic_auth_rewrite.test.js: all tests passed");
