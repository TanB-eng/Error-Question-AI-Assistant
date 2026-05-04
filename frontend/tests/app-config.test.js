const assert = require("node:assert");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");

test("app_json_declares_login_and_home", () => {
  const appPath = path.join(__dirname, "..", "app.json");
  const app = JSON.parse(fs.readFileSync(appPath, "utf8"));
  assert.ok(app.pages.includes("pages/login/index"));
  assert.ok(app.pages.includes("pages/home/index"));
});
