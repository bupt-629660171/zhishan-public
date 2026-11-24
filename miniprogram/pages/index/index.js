const app = getApp();

const CONSTITUTIONS = [
  { name: '气虚', desc: '容易疲乏、说话没劲' },
  { name: '湿热', desc: '口苦、出油、身体沉' }
];

const CONSTRAINT_NAMES = ['素食', '蛋奶素', '无麸质', '不吃苦味', '不吃辣'];

// 像素碗：用 20rpx 的方块拼出来（WXML 不支持内联 SVG）
function buildBowl() {
  const U = 20;
  const rects = [];
  const add = (x, y, w, h, c) => rects.push({ id: rects.length, x: x * U, y: y * U, w: w * U, h: h * U, c: c });

  add(1, 12, 8, 1, '#EADFC8');           // 桌面阴影
  add(9, 1, 1, 7, '#B9643F');            // 筷子
  add(10, 0, 1, 8, '#B9643F');
  add(2, 5, 6, 1, '#E0A17C');            // 汤面
  add(3, 5, 1, 1, '#F5E6C4');            // 面条
  add(5, 5, 1, 1, '#F5E6C4');
  add(4, 6, 2, 1, '#FFFDF8');            // 蛋
  add(4, 6, 1, 1, '#E8B44E');
  add(7, 5, 1, 1, '#5E7F52');            // 青菜
  add(1, 7, 8, 1, '#3B3227');            // 碗沿
  add(1, 8, 1, 3, '#3B3227');            // 左壁
  add(8, 8, 1, 3, '#3B3227');            // 右壁
  add(2, 8, 6, 3, '#FFFDF8');            // 碗身
  add(3, 11, 4, 1, '#3B3227');           // 碗底

  return rects;
}

function readCheckins() {
  try {
    return wx.getStorageSync('zhishan_checkins') || {};
  } catch (e) {
    return {};
  }
}

Page({
  data: {
    constitutions: CONSTITUTIONS,
    picked: '气虚',
    pickedDesc: '容易疲乏、说话没劲',
    constraintList: [],
    campusList: [],
    campus: '全部',
    bowl: [],
    segs: [],
    recorded: 0,
    streak: 0,
    ruleVersion: '',
    quest: []
  },

  onLoad() {
    const compounds = {};
    app.globalData.db.dishes.forEach(function (d) {
      (d.campus || []).forEach(function (c) { compounds[c] = true; });
    });
    const campuses = ['全部'].concat(Object.keys(compounds)).map(function (name) {
      return { name: name, on: name === '全部' };
    });
    this.setData({
      bowl: buildBowl(),
      campusList: campuses,
      ruleVersion: app.globalData.db.meta.rule_version
    });
    this.syncFromGlobal();
  },

  onShow() {
    this.syncFromGlobal();
    this.refreshProgress();
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
    this.refreshQuest();
  },

  refreshProgress() {
    const saved = readCheckins();
    const days = Object.keys(saved).map(Number).sort(function (a, b) { return a - b; });
    const recorded = days.length;

    let streak = 0;
    for (let i = 14; i >= 1; i--) {
      if (saved[i]) streak++;
      else if (streak > 0) break;
    }

    const today = new Date().getDate();
    const segs = [];
    for (let i = 1; i <= 14; i++) {
      segs.push({ id: i, on: !!saved[i], today: i === today && !saved[i] });
    }

    this.setData({ recorded: recorded, streak: streak, segs: segs });
    this.refreshQuest();
  },

  refreshQuest() {
    const g = app.globalData;
    const hasConstraint = (this.data.constraintList || []).some(function (c) { return c.on; });
    const quest = [
      { t: '01 感受扫描', s: g.constitution ? '已选择 ' + g.constitution : '待选择', cls: 'done' },
      { t: '02 边界装备', s: hasConstraint ? '已设置忌口' : '点一下即可设置', cls: hasConstraint ? 'done' : 'current' },
      { t: '03 今日推荐', s: g.planDone ? '已生成' : '待生成', cls: g.planDone ? 'done' : '' },
      { t: '04 两周记录', s: this.data.streak ? '连续 ' + this.data.streak + ' 天' : '还没开始', cls: this.data.streak ? 'done' : '' }
    ];
    this.setData({ quest: quest });
  },

  pickConstitution(e) {
    const name = e.currentTarget.dataset.name;
    const item = CONSTITUTIONS.filter(function (c) { return c.name === name; })[0];
    app.globalData.constitution = name;
    app.savePrefs();
    this.setData({ picked: name, pickedDesc: item ? item.desc : '' });
    this.refreshQuest();
  },

  toggleConstraint(e) {
    const name = e.currentTarget.dataset.name;
    const list = this.data.constraintList.map(function (it) {
      return it.name === name ? { name: it.name, on: !it.on } : it;
    });
    app.globalData.constraints = list.filter(function (it) { return it.on; }).map(function (it) { return it.name; });
    app.savePrefs();
    this.setData({ constraintList: list });
    this.refreshQuest();
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
    app.planDone = true;
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
    return { title: '知源食养 · 今天食堂吃什么，先选两下', path: '/pages/index/index' };
  },

  onShareTimeline() {
    return { title: '知源食养 · 食堂选菜参考' };
  }
});
