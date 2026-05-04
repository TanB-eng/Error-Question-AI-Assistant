const { loginWithWeChatCode } = require("../../services/auth");

Page({
  onLogin() {
    return new Promise((resolve) => {
      wx.login({
        success: ({ code }) => {
          loginWithWeChatCode(code)
            .then(() => {
              wx.navigateTo({ url: "/pages/home/index" });
              resolve(true);
            })
            .catch(() => {
              wx.showToast({ title: "登录失败", icon: "none" });
              resolve(false);
            });
        },
        fail: () => {
          wx.showToast({ title: "登录失败", icon: "none" });
          resolve(false);
        }
      });
    });
  }
});
