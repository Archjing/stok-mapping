/**
 * 把 vite build 产出的 dist/index.html 中引用的 JS/CSS 内联进 HTML，
 * 生成单文件自包含的 dist/index.html：双击即可打开（file://），无需服务器。
 *
 * 由 npm run build 在 vite build 之后自动执行。
 */
import { readFileSync, writeFileSync, rmSync } from 'node:fs';
import { resolve } from 'node:path';

const dist = resolve('dist');
let html = readFileSync(resolve(dist, 'index.html'), 'utf8');

const jsTag = html.match(/<script[^>]*src="([^"]+)"[^>]*><\/script>/);
if (jsTag) {
  const js = readFileSync(resolve(dist, jsTag[1]), 'utf8').replace(
    /<\/script>/g,
    '<\\/script>',
  );
  html = html.replace(jsTag[0], `<script>${js}</script>`);
  rmSync(resolve(dist, jsTag[1]), { force: true });
} else {
  console.warn('[inline] 未找到 JS 引用，跳过 JS 内联');
}

const cssTag = html.match(
  /<link[^>]*rel="stylesheet"[^>]*href="([^"]+)"[^>]*>/,
);
if (cssTag) {
  const css = readFileSync(resolve(dist, cssTag[1]), 'utf8');
  html = html.replace(cssTag[0], `<style>${css}</style>`);
} else {
  console.warn('[inline] 未找到 CSS 引用，跳过 CSS 内联');
}

writeFileSync(resolve(dist, 'index.html'), html);
rmSync(resolve(dist, 'assets'), { recursive: true, force: true });
console.log(
  `[inline] dist/index.html 已内联为单文件（${(html.length / 1024 / 1024).toFixed(2)} MB），可直接双击打开`,
);
