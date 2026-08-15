import {
  aggregateDaily,
  tfForDays,
  timeframeForVisibleDays,
} from '../src/aggregate';
import type { IndexBar } from '../src/aggregate';

function bar(d: string, o: number, h: number, l: number, c: number): IndexBar {
  return { d, o, h, l, c };
}

const days = [
  // 2024-12-30(周一) 开始的一周
  bar('2024-12-30', 10, 12, 9, 11),
  bar('2024-12-31', 11, 13, 10, 12),
  bar('2025-01-02', 12, 14, 11, 13),
  bar('2025-01-03', 13, 15, 12, 14),
  // 下一周 2025-01-06(周一)
  bar('2025-01-06', 14, 16, 13, 15),
  bar('2025-01-07', 15, 17, 14, 16),
  // 2025-02 第一周
  bar('2025-02-03', 20, 25, 18, 24),
];

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) {
    failures++;
    console.log(`FAIL ${name} ${detail}`);
  } else {
    console.log(`ok   ${name}`);
  }
}

// --- 周线聚合 ---
const w = aggregateDaily(days, '1W');
check('weekly bars=3', w.bars.length === 3, `got ${w.bars.length}`);
check('week1 d=2024-12-30', w.bars[0].d === '2024-12-30', w.bars[0].d);
check('week1 o=10 h=15 l=9 c=14', w.bars[0].o === 10 && w.bars[0].h === 15 && w.bars[0].l === 9 && w.bars[0].c === 14, JSON.stringify(w.bars[0]));
check('week1 span=[0,3]', JSON.stringify(w.spans[0]) === '[0,3]', JSON.stringify(w.spans[0]));
check('week2 span=[4,5]', JSON.stringify(w.spans[1]) === '[4,5]');
check('week3 d=2025-02-03 span=[6,6]', w.bars[2].d === '2025-02-03' && JSON.stringify(w.spans[2]) === '[6,6]');

// --- 月线聚合 ---
const m = aggregateDaily(days, '1M');
check('monthly bars=3', m.bars.length === 3, `got ${m.bars.length}`);
check('month1 d=2024-12-01', m.bars[0].d === '2024-12-01', m.bars[0].d);
check('month2 d=2025-01-01', m.bars[1].d === '2025-01-01', m.bars[1].d);
check('month2 o=12 h=17 l=11 c=16', m.bars[1].o === 12 && m.bars[1].h === 17 && m.bars[1].l === 11 && m.bars[1].c === 16, JSON.stringify(m.bars[1]));
check('month3 d=2025-02-01 span=[6,6]', m.bars[2].d === '2025-02-01' && JSON.stringify(m.spans[2]) === '[6,6]');

// --- 年线聚合 ---
const y = aggregateDaily(days, '1Y');
check('yearly bars=2', y.bars.length === 2, `got ${y.bars.length}`);
check('year1 d=2024-01-01 span=[0,1]', y.bars[0].d === '2024-01-01' && JSON.stringify(y.spans[0]) === '[0,1]', `${y.bars[0].d} ${JSON.stringify(y.spans[0])}`);
check('year2 d=2025-01-01 o=12 h=25 l=11 c=24', y.bars[1].d === '2025-01-01' && y.bars[1].o === 12 && y.bars[1].h === 25 && y.bars[1].l === 11 && y.bars[1].c === 24, JSON.stringify(y.bars[1]));

// --- 1D 原样 ---
const d1 = aggregateDaily(days, '1D');
check('daily same length+identity', d1.bars === days && d1.spans.length === days.length);

// --- 阈值 ---
check('tfForDays(250)=1D', tfForDays(250) === '1D');
check('tfForDays(1000)=1W', tfForDays(1000) === '1W');
check('tfForDays(3000)=1M', tfForDays(3000) === '1M');
check('tfForDays(6000)=1Y', tfForDays(6000) === '1Y');
check('hysteresis 1D: 500→1W', timeframeForVisibleDays(500, '1D') === '1W');
check('hysteresis 1W: 300→1D', timeframeForVisibleDays(300, '1W') === '1D');
check('hysteresis 1W: 1000→1W', timeframeForVisibleDays(1000, '1W') === '1W');
check('hysteresis 1Y: 4000→1M', timeframeForVisibleDays(4000, '1Y') === '1M');
check('hysteresis 1Y: 6000→1Y', timeframeForVisibleDays(6000, '1Y') === '1Y');

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURES`);
process.exit(failures === 0 ? 0 : 1);
