/**
 * 体质倾向自评（小程序版）
 *
 * 与 constitution_quiz.py 的计分口径一致：
 *   转化分 = [(原始分 - 条目数) / (条目数 * 4)] * 100
 * 阈值：>=40 明显倾向，30~39 轻度倾向，<30 不明显。
 */

var quizData = require('../data/quiz.js');

var LEVEL_SCORE = { '没有': 1, '很少': 2, '有时': 3, '经常': 4, '总是': 5 };

function score(answers) {
  var totals = {};
  quizData.questions.forEach(function (q) {
    var raw = LEVEL_SCORE[answers[q.id] || '没有'] || 1;
    if (!totals[q.type]) totals[q.type] = [];
    totals[q.type].push(raw);
  });

  var out = {};
  Object.keys(totals).forEach(function (type) {
    var values = totals[type];
    var n = values.length;
    var sum = values.reduce(function (a, b) { return a + b; }, 0);
    out[type] = Math.round(((sum - n) / (n * 4)) * 1000) / 10;
  });
  quizData.types.forEach(function (t) {
    if (out[t] === undefined) out[t] = 0;
  });
  return out;
}

function classify(scores) {
  var ranked = Object.keys(scores)
    .filter(function (t) { return t !== '平和'; })
    .map(function (t) { return { type: t, score: scores[t] }; })
    .sort(function (a, b) { return b.score - a.score; });

  var top = ranked[0] || { type: '', score: 0 };

  if (scores['平和'] >= 60 && ranked.every(function (r) { return r.score < 30; })) {
    return { type: '平和', level: '较平稳', supported: false, also: [], note: '各方面比较平稳，按日常均衡饮食即可。' };
  }
  if (top.score < 30) {
    return { type: '不明显', level: '不明显', supported: false, also: [], note: '没有明显倾向，按日常均衡饮食即可。' };
  }

  var supported = quizData.supported.indexOf(top.type) >= 0;
  var also = ranked.slice(1).filter(function (r) {
    return r.score >= 30 && top.score - r.score < 10;
  }).map(function (r) { return r.type; });

  return {
    type: top.type,
    score: top.score,
    level: top.score >= 40 ? '明显倾向' : '轻度倾向',
    supported: supported,
    also: also,
    note: supported
      ? '可以按' + top.type + '的食养建议挑选菜品。'
      : top.type + '类暂未收录规则，暂时不能给针对性建议；可按通用少油少盐原则选。'
  };
}

function answered(answers) {
  return quizData.questions.filter(function (q) { return answers[q.id]; }).length;
}

module.exports = {
  data: quizData,
  score: score,
  classify: classify,
  answered: answered
};
