/**
 * 知源食养 · 本地规则引擎（小程序离线版）
 *
 * 与 Python 版 rule_engine.py 保持判定一致：命中即取最高档（禁 > 慎 > 宜），
 * 无命中按"宜"放行。所有数据来自 data/db.json，无需网络。
 */

var ACTION_RANK = { '宜': 0, '慎': 1, '禁': 2 };
var SUPPORTED = ['气虚', '湿热'];

/** 线性同余伪随机，保证同一种子结果稳定（替代 Python 的 random.Random(seed)） */
function makeRng(seed) {
  var s = (seed || 1) % 2147483647;
  if (s <= 0) s += 2147483646;
  return function () {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function shuffle(arr, seed) {
  var rand = makeRng(seed);
  for (var i = arr.length - 1; i > 0; i--) {
    var j = Math.floor(rand() * (i + 1));
    var tmp = arr[i];
    arr[i] = arr[j];
    arr[j] = tmp;
  }
  return arr;
}

/** 单道菜判定 */
function evaluate(dish, constitution, db) {
  var rules = (db.rules[constitution] || []);
  if (SUPPORTED.indexOf(constitution) < 0) {
    return { verdict: '未知', evidence: [], rationale: '暂不支持该类体质' };
  }

  var tags = dish.tags || [];
  var matched = [];
  for (var i = 0; i < rules.length; i++) {
    var rule = rules[i];
    if (tags.indexOf(rule.tag) >= 0) {
      matched.push({
        rule_id: rule.code,
        action: rule.action,
        tag: rule.tag,
        rationale: rule.rationale,
        source_ref: rule.source_ref
      });
    }
  }

  if (matched.length === 0) {
    return {
      verdict: '宜',
      evidence: [{
        rule_id: 'NEUTRAL',
        action: '宜',
        tag: 'neutral',
        rationale: '未命中本体质的禁忌条规，按平性处理，可正常食用。',
        source_ref: '规则表默认：无禁忌证据即放行'
      }],
      rationale: '未命中本体质的禁忌条规，按平性处理，可正常食用。'
    };
  }

  matched.sort(function (a, b) {
    if (ACTION_RANK[b.action] !== ACTION_RANK[a.action]) {
      return ACTION_RANK[b.action] - ACTION_RANK[a.action];
    }
    return a.rule_id < b.rule_id ? -1 : 1;
  });

  var verdict = matched[0].action;
  var top = matched.filter(function (e) { return e.action === verdict; });
  return {
    verdict: verdict,
    evidence: matched,
    rationale: top.map(function (e) { return e.rule_id + '：' + e.rationale; }).join('；')
  };
}

/** 生成方案 */
function plan(db, constitution, options) {
  options = options || {};
  var constraints = options.constraints || [];
  var campus = options.campus || null;
  var limit = options.limit || 3;
  var seed = options.seed || 1;

  if (SUPPORTED.indexOf(constitution) < 0) {
    return { status: 'error', message: '暂不支持该类体质', recommendations: [], blocked: [] };
  }

  var blockedIds = {};
  constraints.forEach(function (type) {
    (db.constraints[type] || []).forEach(function (id) { blockedIds[id] = type; });
  });

  var kept = [];
  var blocked = [];

  db.dishes.forEach(function (dish) {
    if (dish.kind !== 'dish') return;
    if (campus && (dish.campus || []).indexOf(campus) < 0) return;

    if (blockedIds[dish.id]) {
      blocked.push({ name: dish.name, reason: '用户限制：' + blockedIds[dish.id] });
      return;
    }

    var v = evaluate(dish, constitution, db);
    if (v.verdict === '禁') {
      blocked.push({ name: dish.name, reason: '体质禁忌：' + v.rationale });
      return;
    }

    kept.push({
      id: dish.id,
      name: dish.name,
      property: dish.property,
      explanation: dish.explanation,
      calories: dish.calories,
      canteen: dish.canteen,
      campus: dish.campus,
      tags: dish.tags,
      verdict: v.verdict,
      rationale: v.rationale,
      evidence: v.evidence
    });
  });

  if (kept.length === 0) {
    return { status: 'empty', message: '严格过滤后暂无符合条件的菜品，请减少限制后重试。', recommendations: [], blocked: blocked };
  }

  shuffle(kept, seed);
  kept.sort(function (a, b) {
    var pa = ACTION_RANK[a.verdict], pb = ACTION_RANK[b.verdict];
    if (pa !== pb) return pa - pb;
    var hasYiA = a.evidence.some(function (e) { return e.action === '宜'; }) ? 1 : 0;
    var hasYiB = b.evidence.some(function (e) { return e.action === '宜'; }) ? 1 : 0;
    if (hasYiA !== hasYiB) return hasYiB - hasYiA;
    return b.evidence.length - a.evidence.length;
  });

  return {
    status: 'ok',
    constitution: constitution,
    recommendations: kept.slice(0, limit),
    total: db.dishes.filter(function (d) { return d.kind === 'dish'; }).length,
    blockedCount: blocked.length,
    remaining: kept.length,
    blocked: blocked
  };
}

module.exports = { evaluate: evaluate, plan: plan, SUPPORTED: SUPPORTED };
