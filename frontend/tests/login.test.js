const assert = require("node:assert");
const { test } = require("node:test");

function loadLoginPage() {
  delete require.cache[require.resolve("../pages/login/index")];
  let pageDefinition;
  global.Page = (definition) => {
    pageDefinition = definition;
  };
  require("../pages/login/index");
  delete global.Page;
  return pageDefinition;
}

test("test_login_page_stores_tokens_after_wx_login", async () => {
  const storage = new Map();
  const navs = [];
  global.wx = {
    login(options) {
      options.success({ code: "wx-code" });
    },
    request(options) {
      assert.equal(options.url, "http://localhost:8000/auth/wx-login");
      assert.deepEqual(options.data, { code: "wx-code" });
      options.success({
        statusCode: 200,
        data: {
          access_token: "access.jwt",
          refresh_token: "refresh.jwt",
          expires_in: 3600,
          user_profile: { id: "u1" }
        }
      });
    },
    setStorageSync(key, value) {
      storage.set(key, value);
    },
    navigateTo(options) {
      navs.push(options.url);
    },
    showToast() {}
  };

  const page = loadLoginPage();
  await page.onLogin();

  assert.equal(storage.get("access_token"), "access.jwt");
  assert.equal(storage.get("refresh_token"), "refresh.jwt");
  assert.deepEqual(navs, ["/pages/home/index"]);
  delete global.wx;
});
