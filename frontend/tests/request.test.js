const assert = require("node:assert");
const { test } = require("node:test");

const { request } = require("../utils/request");

test("test_request_exports_basic_wrapper", () => {
  assert.equal(typeof request, "function");
});
