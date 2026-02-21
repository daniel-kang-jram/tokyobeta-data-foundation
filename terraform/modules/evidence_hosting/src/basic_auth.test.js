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
    "${auth_login_copy_language}": opts.copyLanguage || "bilingual",
  });

  const sandbox = {};
  vm.createContext(sandbox);
  vm.runInContext(`${rendered}\nthis.__handler = handler;`, sandbox);
  return sandbox.__handler;
}

function renderForSizeCheck(opts = {}) {
  const templatePath = path.join(__dirname, "basic_auth.js");
  const template = fs.readFileSync(templatePath, "utf8");
  return renderTemplate(template, {
    "${auth_users_json}": JSON.stringify(opts.authUsers || []),
    "${auth_ui_mode}": opts.authUiMode || "login_page",
    "${auth_session_max_age_seconds}": String(opts.sessionMaxAge || 28800),
    "${auth_login_copy_language}": opts.copyLanguage || "bilingual",
  });
}

function toBase64(input) {
  return Buffer.from(input, "utf8").toString("base64");
}

function eventOf(uri, querystring, headers) {
  return {
    request: {
      uri: uri || "/",
      querystring: querystring || "",
      headers: headers || {},
    },
  };
}

function eventOfWithCookies(uri, querystring, headers, cookies) {
  return {
    request: {
      uri: uri || "/",
      querystring: querystring || "",
      headers: headers || {},
      cookies: cookies || {},
    },
  };
}

function eventOfQueryObject(uri, queryObject, headers) {
  return {
    request: {
      uri: uri || "/",
      querystring: queryObject || {},
      headers: headers || {},
    },
  };
}

function getStatus(resp) {
  if (resp.statusCode != null) {
    return Number(resp.statusCode);
  }
  if (resp.status != null) {
    return Number(resp.status);
  }
  return NaN;
}

function getHeader(resp, key) {
  if (!resp.headers) {
    return null;
  }
  const lowered = key.toLowerCase();
  const v = resp.headers[lowered] || resp.headers[key];
  if (!v) {
    return null;
  }
  if (Array.isArray(v)) {
    if (!v.length) {
      return null;
    }
    return v[0].value || null;
  }
  if (typeof v.value === "string") {
    return v.value;
  }
  return null;
}

function getCookie(resp, cookieName) {
  if (!resp.cookies) {
    return null;
  }
  const c = resp.cookies[cookieName];
  if (!c) {
    return null;
  }
  return c;
}

function testUnauthenticatedRootRedirectsToLoginPage() {
  const handler = loadHandler({
    authUsers: [toBase64("demo:pass")],
    authUiMode: "login_page",
  });
  const resp = handler(eventOf("/", "", {}));
  assert.strictEqual(getStatus(resp), 302);
  const location = getHeader(resp, "location");
  assert.ok(location.includes("/__auth/login?return_to=%2F"));
}

function testLoginPageRenderedForGetLogin() {
  const handler = loadHandler({
    authUsers: [toBase64("demo:pass")],
    authUiMode: "login_page",
    copyLanguage: "en",
  });
  const resp = handler(eventOf("/__auth/login", "", {}));
  assert.strictEqual(getStatus(resp), 200);
  const contentType = getHeader(resp, "content-type");
  assert.ok(contentType && contentType.indexOf("text/html") >= 0);
  assert.ok((resp.body || "").includes("IM Dashboard Sign In"));
  assert.ok(!(resp.body || "").includes("ログイン"));
  assert.ok(!(resp.body || "").includes("ユーザーID"));
}

function testInvalidCredentialShowsInlineErrorWithoutBrowserPopup() {
  const handler = loadHandler({
    authUsers: [toBase64("demo:pass")],
    authUiMode: "login_page",
  });
  const resp = handler(
    eventOf("/__auth/login", "return_to=%2Fsegments", {
      authorization: { value: `Basic ${toBase64("demo:wrong")}` },
    })
  );
  assert.strictEqual(getStatus(resp), 401);
  assert.strictEqual(getHeader(resp, "www-authenticate"), null);
  assert.ok((resp.body || "").toLowerCase().includes("invalid"));
}

function testValidCredentialSetsSessionCookieAndRedirects() {
  const handler = loadHandler({
    authUsers: [toBase64("demo:pass")],
    authUiMode: "login_page",
    sessionMaxAge: 28800,
  });
  const resp = handler(
    eventOf("/__auth/login", "return_to=%2Fsegments", {
      authorization: { value: `Basic ${toBase64("demo:pass")}` },
    })
  );
  assert.strictEqual(getStatus(resp), 302);
  assert.strictEqual(getHeader(resp, "location"), "/segments");
  assert.strictEqual(getHeader(resp, "set-cookie"), null);
  const cookie = getCookie(resp, "evidence_session");
  assert.ok(cookie);
  assert.ok((cookie.value || "").length > 0);
  assert.ok((cookie.attributes || "").indexOf("HttpOnly") >= 0);
  assert.ok((cookie.attributes || "").indexOf("Secure") >= 0);
  assert.ok((cookie.attributes || "").indexOf("SameSite=Lax") >= 0);
  assert.ok((cookie.attributes || "").indexOf("Max-Age=28800") >= 0);
}

function testValidSessionAllowsProtectedRequest() {
  const handler = loadHandler({
    authUsers: [toBase64("demo:pass")],
    authUiMode: "login_page",
    sessionMaxAge: 28800,
  });
  const loginResp = handler(
    eventOf("/__auth/login", "return_to=%2F", {
      authorization: { value: `Basic ${toBase64("demo:pass")}` },
    })
  );
  const cookie = getCookie(loginResp, "evidence_session");
  const session = cookie ? cookie.value : null;
  assert.ok(session);
  const protectedResp = handler(
    eventOf("/geography", "", {
      cookie: { value: `evidence_session=${session}` },
    })
  );
  assert.strictEqual(protectedResp.uri, "/geography");
}

function testExpiredOrInvalidSessionRedirectsToLogin() {
  const handler = loadHandler({
    authUsers: [toBase64("demo:pass")],
    authUiMode: "login_page",
  });
  const resp = handler(
    eventOf("/geography", "", {
      cookie: { value: "evidence_session=invalid-token" },
    })
  );
  assert.strictEqual(getStatus(resp), 302);
  assert.ok(getHeader(resp, "location").startsWith("/__auth/login?return_to="));
}

function testLogoutClearsCookieAndRedirectsToLogin() {
  const handler = loadHandler({
    authUsers: [toBase64("demo:pass")],
    authUiMode: "login_page",
  });
  const resp = handler(eventOf("/__auth/logout", "", {}));
  assert.strictEqual(getStatus(resp), 302);
  assert.strictEqual(getHeader(resp, "location"), "/__auth/login");
  const cookie = getCookie(resp, "evidence_session");
  assert.ok(cookie);
  assert.strictEqual(cookie.value, "");
  assert.ok((cookie.attributes || "").indexOf("Max-Age=0") >= 0);
}

function testOpenRedirectProtectionFallbacksToRoot() {
  const handler = loadHandler({
    authUsers: [toBase64("demo:pass")],
    authUiMode: "login_page",
  });
  const resp = handler(
    eventOf("/__auth/login", "return_to=https%3A%2F%2Fevil.com", {
      authorization: { value: `Basic ${toBase64("demo:pass")}` },
    })
  );
  assert.strictEqual(getStatus(resp), 302);
  assert.strictEqual(getHeader(resp, "location"), "/");
}

function testBrowserBasicModeBackCompat() {
  const handler = loadHandler({
    authUsers: [toBase64("demo:pass")],
    authUiMode: "browser_basic",
  });
  const resp = handler(eventOf("/", "", {}));
  assert.strictEqual(getStatus(resp), 401);
  const challenge = getHeader(resp, "www-authenticate");
  assert.ok(challenge && challenge.indexOf("Basic") >= 0);
}

function testRenderedFunctionSizeWithinCloudFrontLimit() {
  const rendered = renderForSizeCheck({
    authUsers: [toBase64("demo:pass"), toBase64("demo2:pass2")],
    authUiMode: "login_page",
    copyLanguage: "en",
    sessionMaxAge: 28800,
  });
  assert.ok(
    Buffer.byteLength(rendered, "utf8") < 9800,
    "Rendered CloudFront function should stay safely under size limit"
  );
}

function testQuerystringObjectShapeDoesNotCrashAndUsesReturnTo() {
  const handler = loadHandler({
    authUsers: [toBase64("demo:pass")],
    authUiMode: "login_page",
  });
  const resp = handler(
    eventOfQueryObject("/__auth/login", { return_to: { value: "/segments" } }, {})
  );
  assert.strictEqual(getStatus(resp), 200);
  assert.ok((resp.body || "").includes("/segments"));
}

function testCloudFrontCookieObjectAllowsProtectedRequest() {
  const handler = loadHandler({
    authUsers: [toBase64("demo:pass")],
    authUiMode: "login_page",
    sessionMaxAge: 28800,
  });
  const loginResp = handler(
    eventOf("/__auth/login", "return_to=%2F", {
      authorization: { value: `Basic ${toBase64("demo:pass")}` },
    })
  );
  const cookie = getCookie(loginResp, "evidence_session");
  const session = cookie ? cookie.value : null;
  assert.ok(session);

  const protectedResp = handler(
    eventOfWithCookies("/pricing", "", {}, {
      evidence_session: { value: session },
    })
  );
  assert.strictEqual(protectedResp.uri, "/pricing");
}

function testUnauthenticatedAuthAssetBypassesLoginRedirect() {
  const handler = loadHandler({
    authUsers: [toBase64("demo:pass")],
    authUiMode: "login_page",
  });
  const resp = handler(eventOf("/__auth/assets/bg.mp4", "", {}));
  assert.strictEqual(resp.uri, "/__auth/assets/bg.mp4");
}

function testLoginPageUsesFadedVideoBackground() {
  const handler = loadHandler({
    authUsers: [toBase64("demo:pass")],
    authUiMode: "login_page",
    copyLanguage: "en",
  });
  const resp = handler(eventOf("/__auth/login", "", {}));
  const body = resp.body || "";
  assert.ok(body.includes("class='bgv'"));
  assert.ok(body.includes("src='/__auth/assets/bg.mp4'"));
  assert.ok(body.includes("opacity:.62"));
  assert.ok(body.includes("animation:bgPan 16s ease-in-out infinite alternate"));
  assert.ok(body.includes("@keyframes bgPan"));
  assert.ok(body.includes("*,:before,:after{box-sizing:border-box}"));
  assert.ok(body.includes("width:min(760px,94vw)"));
  assert.ok(body.includes(".hd{background:#fff;color:#0f172a;padding:34px 36px"));
  assert.ok(body.includes(".bd{padding:34px 36px}"));
  assert.ok(body.includes(".hd h1{margin:8px 0 4px;font-size:34px;line-height:1.12}"));
  assert.ok(body.includes(".r label{display:block;font-size:18px;font-weight:700;margin:0 0 10px}"));
  assert.ok(body.includes(".r input{width:100%;height:56px"));
  assert.ok(body.includes("button{width:100%;height:56px"));
  assert.ok(!body.includes("Portfolio access"));
  assert.ok(!body.includes("運用ダッシュボード"));
}

function runAllTests() {
  const tests = [
    testUnauthenticatedRootRedirectsToLoginPage,
    testLoginPageRenderedForGetLogin,
    testInvalidCredentialShowsInlineErrorWithoutBrowserPopup,
    testValidCredentialSetsSessionCookieAndRedirects,
    testValidSessionAllowsProtectedRequest,
    testExpiredOrInvalidSessionRedirectsToLogin,
    testLogoutClearsCookieAndRedirectsToLogin,
    testOpenRedirectProtectionFallbacksToRoot,
    testBrowserBasicModeBackCompat,
    testRenderedFunctionSizeWithinCloudFrontLimit,
    testQuerystringObjectShapeDoesNotCrashAndUsesReturnTo,
    testCloudFrontCookieObjectAllowsProtectedRequest,
    testUnauthenticatedAuthAssetBypassesLoginRedirect,
    testLoginPageUsesFadedVideoBackground,
  ];

  for (const t of tests) {
    t();
  }
}

runAllTests();
console.log("basic_auth.test.js: all tests passed");
