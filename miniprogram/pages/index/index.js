const app = getApp();

const CONSTITUTIONS = [
  { name: '气虚', desc: '容易疲乏、说话没劲' },
  { name: '湿热', desc: '口苦、出油、身体沉' }
];

const CONSTRAINTS = ['素食', '蛋奶素', '无麸质', '不吃苦味', '不吃辣'];

Page({
  data: {
    constitutions: CONSTITUTIONS,
    constraints: CONSTRAINTS,
    picked: '气虚',
    pickedDesc: '容易疲乏、说话没劲',
    selected: [],
    campusList: [],
    campus: '全部'
  },

  onLoad() {
    const compounds = {};
    app.globalData.db.dishes.forEach(d => {
      (d.campus || []).forEach(c => { compounds[c] = true; });
    });
    this.setData({
      campusList: ['全部'].concat(Object.keys(compounds)),
      picked: app.globalData.constitution,
      selected: app.globalData.constraints
    });
    this.syncDesc();
  },

  syncDesc() {
    const item = CONSTITUTIONS.find(c => c.name === this.data.picked);
    this.setData({ pickedDesc: item ? item.desc : '' });
  },

  pickConstitution(e) {
    this.setData({ picked: e.currentTarget.dataset.name });
    this.syncDesc();
  },

  toggleConstraint(e) {
    const name = e.currentTarget.dataset.name;
    const selected = this.data.selected.slice();
    const idx = selected.indexOf(name);
    if (idx >= 0) {
      selected.splice(idx, 1);
    } else {
      selected.push(name);
    }
    this.setData({ selected });
  },

  pickCampus(e) {
    this.setData({ campus: e.currentTarget.dataset.name });
  },

  generate() {
    app.globalData.constitution = this.data.picked;
    app.globalData.constraints = this.data.selected;
    app.globalData.seed = Date.now() % 100000;
    app.savePrefs();
    wx.navigateTo({ url: '/pages/result/result?campus=' + encodeURIComponent(this.data.campus) });
  },

  openRecord() {
    wx.navigateTo({ url: '/pages/record/record' });
  },

  openQuiz() {
    wx.navigateTo({ url: '/pages/quiz/quiz' });
  },

  // 转发给好友/群（免费，不需要认证）
  onShareAppMessage() {
    return {
      title: '知源食养 · 今天食堂吃什么，先选两下',
      path: '/pages/index/index'
    };
  },

  // 分享到朋友圈（免费；打开是"单页模式"，只展示这一页）
  onShareTimeline() {
    return {
      title: '知源食养 · 食堂选菜参考',
      query: ''
    };
  }
});
