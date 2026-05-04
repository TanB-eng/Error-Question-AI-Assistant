const { loginWithWeChatCode } = require("../../services/auth");

Page({
  data: {
    loading: false,
    errorMessage: ""
  },

  onLogin() {
    return new Promise((resolve) => {
      this.setData({ loading: true, errorMessage: "" });
      wx.login({
        success: ({ code }) => {
          if (!code) {
            this.setData({ loading: false, errorMessage: "微信登录没有返回 code" });
            resolve(false);
            return;
          }
          loginWithWeChatCode(code)
            .then(() => {
              this.setData({ loading: false });
              wx.navigateTo({ url: "/pages/home/index" });
              resolve(true);
            })
            .catch((error) => {
              const message = error && error.message ? error.message : "登录失败";
              this.setData({ loading: false, errorMessage: message });
              wx.showToast({ title: message, icon: "none" });
              resolve(false);
            });
        },
        fail: (error) => {
          const message = error && error.errMsg ? error.errMsg : "微信登录失败";
          this.setData({ loading: false, errorMessage: message });
          wx.showToast({ title: message, icon: "none" });
          resolve(false);
        }
      });
    });
  }
});
