const app = getApp();

const CONSTITUTIONS = [
  { name: '气虚', desc: '容易疲乏、说话没劲' },
  { name: '湿热', desc: '口苦、出油、身体沉' }
];

const CONSTRAINT_NAMES = ['素食', '蛋奶素', '无麸质', '不吃苦味', '不吃辣'];

/**
 * 像素碗：每个方块 20rpx。
 * 关键：碗身用米色填充，否则白底上看不见，只剩边框像四条腿。
 */
function buildBowl() {
  const U = 20;
  const rects = [];
  const add = function (x, y, w, h, c) {
    rects.push({ id: rects.length, x: x * U, y: y * U, w: w * U, h: h * U, c: c });
  };

  const INK = "#10241A";        // 深色描边，压在深绿底上仍清晰
  const BODY = "#F5E7C8";       // 米色碗身
  const SOUP = "#DFA07A";
  const CREAM = "#F3E0B8";
  const GREEN = "#6E9A5E";
  const CLAY = "#C4694E";

  add(1, 10, 9, 1, "rgba(0,0,0,0.22)");  // 投影
  add(8, 0, 1, 5, CLAY);                 // 筷子
  add(9, 0, 1, 6, CLAY);

  add(2, 6, 7, 1, SOUP);                 // 汤面
  add(3, 6, 2, 1, "#FFFDF8");            // 蛋
  add(3, 6, 1, 1, "#E8B44E");            // 蛋黄
  add(5, 6, 1, 1, CREAM);                // 面条
  add(6, 6, 2, 1, GREEN);                // 青菜

  add(1, 5, 9, 1, INK);                  // 碗沿
  add(1, 6, 1, 3, INK);                  // 左壁
  add(9, 6, 1, 3, INK);                  // 右壁
  add(2, 6, 7, 3, BODY);                 // 碗身
  add(2, 9, 7, 1, INK);                  // 碗底

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
    const recorded = Object.keys(saved).length;

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
    app.globalData.constraints = list
      .filter(function (it) { return it.on; })
      .map(function (it) { return it.name; });
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
