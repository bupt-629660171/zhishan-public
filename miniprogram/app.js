const db = require('./data/db.js');
const engine = require('./utils/engine.js');

App({
  globalData: {
    db: db,
    engine: engine,
    constitution: '气虚',
    constraints: [],
    seed: 7,
    plan: null
  },

  onLaunch() {
    // 记录最近一次选择，减少重复输入
    try {
      const saved = wx.getStorageSync('zhishan_prefs');
      if (saved && saved.constitution) {
        this.globalData.constitution = saved.constitution;
        this.globalData.constraints = saved.constraints || [];
      }
    } catch (e) {
      // 首次打开没有缓存，忽略
    }
  },

  savePrefs() {
    try {
      wx.setStorageSync('zhishan_prefs', {
        constitution: this.globalData.constitution,
        constraints: this.globalData.constraints
      });
    } catch (e) {
      // 存储失败不影响使用
    }
  }
});
