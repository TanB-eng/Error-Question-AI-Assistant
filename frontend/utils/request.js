function request(options) {
  if (typeof wx !== "undefined" && wx.request) {
    return wx.request(options);
  }

  return Promise.resolve({
    statusCode: 0,
    data: null,
    options
  });
}

module.exports = {
  request
};
