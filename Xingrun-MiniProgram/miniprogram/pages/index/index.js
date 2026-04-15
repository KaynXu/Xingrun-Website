const { resolveParentEntryPath } = require('../../utils/parentApi');

Page({
  onLoad() {
    wx.reLaunch({
      url: resolveParentEntryPath(wx),
    });
  },
});
