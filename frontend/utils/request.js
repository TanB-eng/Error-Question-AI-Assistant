const { API_BASE_URL } = require("../services/config");
const { clearSession, getAccessToken, refreshAccessToken } = require("../services/auth");

function request(options) {
  return requestWithAuth(options, false);
}

function requestWithAuth(options, hasRefreshed) {
  if (typeof wx === "undefined" || !wx.request) {
    return Promise.resolve({
      statusCode: 0,
      data: null,
      options
    });
  }

  return performRequest(options).then((response) => {
    if (response.statusCode !== 401) {
      return response;
    }
    if (hasRefreshed) {
      clearSession();
      wx.redirectTo({ url: "/pages/login/index" });
      return response;
    }
    return refreshAccessToken().then((refreshed) => {
      if (!refreshed) {
        wx.redirectTo({ url: "/pages/login/index" });
        return response;
      }
      return requestWithAuth(options, true);
    });
  });
}

function performRequest(options) {
  return new Promise((resolve, reject) => {
    const token = getAccessToken();
    const header = Object.assign({}, options.header || {});
    if (token) {
      header.Authorization = `Bearer ${token}`;
    }
    wx.request(Object.assign({}, options, {
      url: normalizeUrl(options.url),
      header,
      success: resolve,
      fail: reject
    }));
  });
}

function normalizeUrl(url) {
  if (/^https?:\/\//.test(url)) {
    return url;
  }
  if (url.startsWith("/")) {
    return `${API_BASE_URL}${url}`;
  }
  return `${API_BASE_URL}/${url}`;
}

module.exports = {
  request
};
