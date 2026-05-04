const { API_BASE_URL } = require("./config");

const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";
const USER_PROFILE_KEY = "user_profile";

function saveSession(session) {
  wx.setStorageSync(ACCESS_TOKEN_KEY, session.access_token);
  wx.setStorageSync(REFRESH_TOKEN_KEY, session.refresh_token);
  if (session.user_profile) {
    wx.setStorageSync(USER_PROFILE_KEY, session.user_profile);
  }
}

function clearSession() {
  wx.removeStorageSync(ACCESS_TOKEN_KEY);
  wx.removeStorageSync(REFRESH_TOKEN_KEY);
  wx.removeStorageSync(USER_PROFILE_KEY);
}

function getAccessToken() {
  return wx.getStorageSync(ACCESS_TOKEN_KEY);
}

function getRefreshToken() {
  return wx.getStorageSync(REFRESH_TOKEN_KEY);
}

function loginWithWeChatCode(code) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_BASE_URL}/auth/wx-login`,
      method: "POST",
      data: { code },
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          saveSession(response.data);
          resolve(response.data);
          return;
        }
        reject(response);
      },
      fail: reject
    });
  });
}

function refreshAccessToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return Promise.resolve(false);
  }
  return new Promise((resolve) => {
    wx.request({
      url: `${API_BASE_URL}/auth/refresh`,
      method: "POST",
      header: {
        Authorization: `Bearer ${refreshToken}`
      },
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300 && response.data) {
          saveSession(response.data);
          resolve(true);
          return;
        }
        clearSession();
        resolve(false);
      },
      fail() {
        clearSession();
        resolve(false);
      }
    });
  });
}

module.exports = {
  clearSession,
  getAccessToken,
  getRefreshToken,
  loginWithWeChatCode,
  refreshAccessToken,
  saveSession
};
