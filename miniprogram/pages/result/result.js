const app = getApp();

const BADGE = {
  '宜': { cls: 'badge-yi', text: '✓ 推荐' },
  '慎': { cls: 'badge-shen', text: '! 适量' },
  '禁': { cls: 'badge-jin', text: '✕ 暂不建议' }
};

Page({
  data: {
    constitution: '',
    constraints: [],
    cards: [],
    blocked: 0,
    remaining: 0,
    empty: false,
    message: ''
  },

  onLoad(query) {
    // 先解码再判断"全部"，否则编码串永远不等于"全部"，会被当成校区名去筛
    const raw = query.campus ? decodeURIComponent(query.campus) : '全部';
    this.campus = raw === '全部' ? null : raw;
    app.planDone = true;
    this.refresh();
  },

  refresh() {
    const g = app.globalData;
    const result = g.engine.plan(g.db, g.constitution, {
      constraints: g.constraints,
      campus: this.campus,
      seed: g.seed,
      limit: 3
    });

    const cards = (result.recommendations || []).map(d => ({
      name: d.name,
      property: d.property,
      calories: d.calories,
      rationale: d.rationale,
      place: (d.canteen || []).map(c => c.location + '·' + c.window).join('；'),
      price: (d.canteen || [])[0] ? (d.canteen[0].price || '') : '',
      badge: BADGE[d.verdict] || BADGE['宜'],
      evidence: (d.evidence || []).filter(e => e.action !== '宜').map(e => e.rule_id + '：' + e.rationale),
      showEvidence: false
    }));

    this.setData({
      constitution: g.constitution,
      constraints: g.constraints,
      cards: cards,
      blocked: result.blockedCount || 0,
      remaining: result.remaining || 0,
      empty: result.status !== 'ok',
      message: result.message || ''
    });
  },

  toggleEvidence(e) {
    const i = e.currentTarget.dataset.index;
    const key = 'cards[' + i + '].showEvidence';
    this.setData({ [key]: !this.data.cards[i].showEvidence });
  },

  reroll() {
    app.globalData.seed = (app.globalData.seed + 17) % 100000;
    this.refresh();
  },

  back() {
    wx.navigateBack();
  },

  onShareAppMessage() {
    const g = app.globalData;
    const first = this.data.cards.length ? this.data.cards[0].name : '今日推荐';
    return {
      title: '我今天的' + g.constitution + '食养推荐：' + first,
      path: '/pages/index/index'
    };
  },

  onShareTimeline() {
    return {
      title: '今日食养推荐（' + this.data.constitution + '）'
    };
  }
});
