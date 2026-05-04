const assert = require("node:assert");
const { test } = require("node:test");

function loadFreshRequest() {
  delete require.cache[require.resolve("../utils/request")];
  delete require.cache[require.resolve("../services/auth")];
  return require("../utils/request");
}

test("test_refresh_once_then_retry_original_request", async () => {
  const calls = [];
  const storage = new Map([
    ["access_token", "old-token"],
    ["refresh_token", "refresh-token"]
  ]);
  global.wx = {
    getStorageSync(key) {
      return storage.get(key);
    },
    setStorageSync(key, value) {
      storage.set(key, value);
    },
    removeStorageSync(key) {
      storage.delete(key);
    },
    redirectTo(options) {
      calls.push(["redirect", options.url]);
    },
    request(options) {
      calls.push(["request", options.url, options.header && options.header.Authorization]);
      if (options.url.endsWith("/auth/refresh")) {
        options.success({
          statusCode: 200,
          data: {
            access_token: "new-token",
            refresh_token: "new-refresh",
            expires_in: 3600,
            user_profile: { id: "u1" }
          }
        });
        return;
      }
      const count = calls.filter((call) => call[1].endsWith("/protected")).length;
      options.success({ statusCode: count === 1 ? 401 : 200, data: { ok: true } });
    }
  };
  const { request } = loadFreshRequest();

  const response = await request({ url: "/protected", method: "GET" });

  assert.equal(response.statusCode, 200);
  assert.equal(storage.get("access_token"), "new-token");
  assert.deepEqual(
    calls.filter((call) => call[0] === "request").map((call) => call[2]),
    ["Bearer old-token", "Bearer refresh-token", "Bearer new-token"]
  );
  delete global.wx;
});

test("test_second_401_redirects_to_login", async () => {
  const calls = [];
  const storage = new Map([
    ["access_token", "old-token"],
    ["refresh_token", "refresh-token"]
  ]);
  global.wx = {
    getStorageSync(key) {
      return storage.get(key);
    },
    setStorageSync(key, value) {
      storage.set(key, value);
    },
    removeStorageSync(key) {
      storage.delete(key);
    },
    redirectTo(options) {
      calls.push(["redirect", options.url]);
    },
    request(options) {
      calls.push(["request", options.url]);
      if (options.url.endsWith("/auth/refresh")) {
        options.success({
          statusCode: 200,
          data: { access_token: "new-token", refresh_token: "new-refresh", expires_in: 3600 }
        });
        return;
      }
      options.success({ statusCode: 401, data: {} });
    }
  };
  const { request } = loadFreshRequest();

  const response = await request({ url: "/protected", method: "GET" });

  assert.equal(response.statusCode, 401);
  assert.deepEqual(calls.at(-1), ["redirect", "/pages/login/index"]);
  delete global.wx;
});
