const { getParentBindings, getParentSession } = require('./utils/parentApi');

App({
  globalData: {
    serverUrl: 'https://xingrun.online',
    parentSession: null,
    parentBindings: [],
  },

  onLaunch() {
    this.globalData.parentSession = getParentSession(wx);
    this.globalData.parentBindings = getParentBindings(wx);
  },
});
