const app = getApp();

const CONSTITUTIONS = [
  { name: '气虚', desc: '容易疲乏、说话没劲' },
  { name: '湿热', desc: '口苦、出油、身体沉' }
];

const CONSTRAINT_NAMES = ['素食', '蛋奶素', '无麸质', '不吃苦味', '不吃辣'];

Page({
  data: {
    constitutions: CONSTITUTIONS,
    picked: '气虚',
    pickedDesc: '容易疲乏、说话没劲',
    constraintList: [],
    campusList: [],
    campus: '全部'
  },

  onLoad() {
    // 校区列表：从数据里去重
    const compounds = {};
    app.globalData.db.dishes.forEach(function (d) {
      (d.campus || []).forEach(function (c) { compounds[c] = true; });
    });
    const campuses = ['全部'].concat(Object.keys(compounds)).map(function (name) {
      return { name: name, on: name === '全部' };
    });
    this.setData({ campusList: campuses });
    this.syncFromGlobal();
  },

  // 从自评页返回时页面是缓存的，必须用 onShow 重新读
  onShow() {
    this.syncFromGlobal();
  },

  syncFromGlobal() {
    const picked = app.globalData.constitution || '气虚';
    const selected = app.globalData.constraints || [];
    const list = CONSTRAINT_NAMES.map(function (name) {
      return { name: name, on: selected.indexOf(name) >= 0 };
    });
    const item = CONSTITUTIONS.filter(function (c) { return c.name === picked; })[0];
    this.setData({
      picked: picked,
      pickedDesc: item ? item.desc : '',
      constraintList: list
    });
  },

  pickConstitution(e) {
    const name = e.currentTarget.dataset.name;
    const item = CONSTITUTIONS.filter(function (c) { return c.name === name; })[0];
    this.setData({ picked: name, pickedDesc: item ? item.desc : '' });
  },

  toggleConstraint(e) {
    const name = e.currentTarget.dataset.name;
    const list = this.data.constraintList.map(function (it) {
      return it.name === name ? { name: it.name, on: !it.on } : it;
    });
    this.setData({ constraintList: list });
  },

  pickCampus(e) {
    const name = e.currentTarget.dataset.name;
    const list = this.data.campusList.map(function (it) {
      return { name: it.name, on: it.name === name };
    });
    this.setData({ campusList: list, campus: name });
  },

  generate() {
    const selected = this.data.constraintList
      .filter(function (it) { return it.on; })
      .map(function (it) { return it.name; });

    app.globalData.constitution = this.data.picked;
    app.globalData.constraints = selected;
    app.globalData.seed = Date.now() % 100000;
    app.savePrefs();
    wx.navigateTo({
      url: '/pages/result/result?campus=' + encodeURIComponent(this.data.campus)
    });
  },

  openRecord() {
    wx.navigateTo({ url: '/pages/record/record' });
  },

  openQuiz() {
    wx.navigateTo({ url: '/pages/quiz/quiz' });
  },

  onShareAppMessage() {
    return {
      title: '知源食养 · 今天食堂吃什么，先选两下',
      path: '/pages/index/index'
    };
  },

  onShareTimeline() {
    return { title: '知源食养 · 食堂选菜参考' };
  }
});
