const KEY = 'zhishan_checkins';

const ITEMS = [
  { key: 'comfort', label: '饭后舒适' },
  { key: 'regular', label: '排便规律' },
  { key: 'energy', label: '下午精力' }
];

Page({
  data: {
    days: [],
    items: ITEMS,
    streak: 0
  },

  onLoad() {
    let saved = {};
    try {
      saved = wx.getStorageSync(KEY) || {};
    } catch (e) {
      saved = {};
    }
    const days = [];
    const today = new Date().getDate();
    for (let i = 1; i <= 14; i++) {
      const rec = saved[i] || {};
      days.push({
        day: i,
        today: i === today,
        checked: Object.keys(rec).length > 0,
        rec: rec
      });
    }
    this.saved = saved;
    this.setData({
      days: days,
      streak: this.countStreak(days),
      checkedCount: days.filter(function (d) { return d.checked; }).length,
      todayChecked: days.some(function (d) { return d.today && d.checked; })
    });
  },

  countStreak(days) {
    let n = 0;
    for (let i = days.length - 1; i >= 0; i--) {
      if (days[i].checked) n++;
      else break;
    }
    return n;
  },

  toggleItem(e) {
    const day = e.currentTarget.dataset.day;
    const item = e.currentTarget.dataset.item;
    const saved = this.saved;
    saved[day] = saved[day] || {};
    saved[day][item] = !saved[day][item];
    if (!Object.keys(saved[day]).some(k => saved[day][k])) {
      delete saved[day];
    }
    try {
      wx.setStorageSync(KEY, saved);
    } catch (err) {
      // 存储失败时仍然更新界面
    }
    this.onLoad();
  },

  onShareAppMessage() {
    return {
      title: '我坚持记录了两周饮食感受',
      path: '/pages/index/index'
    };
  }
});
