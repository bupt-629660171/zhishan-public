const app = getApp();
const quiz = require('../../utils/quiz.js');

Page({
  data: {
    index: 0,
    total: 0,
    question: null,
    levels: [],
    answers: {},
    picked: '',
    percent: 0,
    done: false,
    result: null,
    canAdopt: false
  },

  onLoad() {
    const total = quiz.data.questions.length;
    this.setData({
      total: total,
      levels: quiz.data.levels,
      question: quiz.data.questions[0],
      percent: 0
    });
  },

  pickLevel(e) {
    const level = e.currentTarget.dataset.level;
    const answers = Object.assign({}, this.data.answers);
    answers[this.data.question.id] = level;
    this.setData({ answers: answers, picked: level });
  },

  goNext() {
    const answers = this.data.answers;
    if (!answers[this.data.question.id]) {
      wx.showToast({ title: '先选一个频率', icon: 'none' });
      return;
    }
    if (this.data.index >= this.data.total - 1) {
      this.finish();
      return;
    }
    const next = this.data.index + 1;
    this.setData({
      index: next,
      question: quiz.data.questions[next],
      picked: answers[quiz.data.questions[next].id] || '',
      percent: Math.round((next / this.data.total) * 100)
    });
  },

  goPrev() {
    if (this.data.index === 0) return;
    const prev = this.data.index - 1;
    this.setData({
      index: prev,
      question: quiz.data.questions[prev],
      picked: this.data.answers[quiz.data.questions[prev].id] || '',
      percent: Math.round((prev / this.data.total) * 100)
    });
  },

  finish() {
    const scores = quiz.score(this.data.answers);
    const result = quiz.classify(scores);
    this.setData({
      done: true,
      result: result,
      percent: 100,
      canAdopt: result.supported
    });
  },

  adopt() {
    if (!this.data.result || !this.data.result.supported) return;
    app.globalData.constitution = this.data.result.type;
    app.savePrefs();
    wx.showToast({ title: '已采用', icon: 'success' });
    setTimeout(function () { wx.navigateBack(); }, 600);
  },

  restart() {
    this.setData({
      index: 0,
      question: quiz.data.questions[0],
      answers: {},
      picked: '',
      percent: 0,
      done: false,
      result: null
    });
  },

  onShareAppMessage() {
    return { title: '11 道题，看看你最近更像哪种状态', path: '/pages/index/index' };
  }
});
