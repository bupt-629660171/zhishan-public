/**
 * 对拍脚本：JS 引擎 vs Python 引擎
 *
 * 用法：node tools/parity_check.js
 * 前置：python tools/export_miniprogram.py
 *
 * 任何一次判定不一致都会让脚本以非 0 退出，便于接进 CI。
 */
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const db = require(path.join(root, 'miniprogram/data/db.js'));
const expected = JSON.parse(fs.readFileSync(path.join(root, 'tools/_expected.json'), 'utf8'));
const engine = require(path.join(root, 'miniprogram/utils/engine.js'));

let total = 0;
const bad = [];

for (const constitution of ['气虚', '湿热']) {
  for (const dish of db.dishes) {
    if (dish.kind !== 'dish') continue;
    total += 1;
    const got = engine.evaluate(dish, constitution, db).verdict;
    if (expected[constitution][dish.name] !== got) {
      bad.push(`${constitution} / ${dish.name}: py=${expected[constitution][dish.name]} js=${got}`);
    }
  }
}

console.log(`对拍 ${total} 条，不一致 ${bad.length} 条`);
bad.slice(0, 10).forEach(line => console.log('  ' + line));
process.exit(bad.length === 0 ? 0 : 1);
