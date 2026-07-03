import { readFileSync } from 'node:fs';
import { liteAdaptor } from 'mathjax-full/js/adaptors/liteAdaptor.js';
import { RegisterHTMLHandler } from 'mathjax-full/js/handlers/html.js';
import { mathjax } from 'mathjax-full/js/mathjax.js';
import { TeX } from 'mathjax-full/js/input/tex.js';
import { AllPackages } from 'mathjax-full/js/input/tex/AllPackages.js';
import { SVG } from 'mathjax-full/js/output/svg.js';

const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);

const texInput = new TeX({
  packages: AllPackages,
  formatError(_jax, error) {
    throw error;
  },
});
const svgOutput = new SVG({ fontCache: 'none' });
const document = mathjax.document('', {
  InputJax: texInput,
  OutputJax: svgOutput,
});

const payload = JSON.parse(readFileSync(0, 'utf8') || '{}');
const formula = String(payload.formula ?? '');
const display = payload.display !== false;
const node = document.convert(formula, { display });
const html = adaptor.outerHTML(node);
const match = html.match(/<svg[\s\S]*<\/svg>/);

if (!match) {
  throw new Error('MathJax did not return an SVG element');
}

process.stdout.write(JSON.stringify({ svg: match[0] }));
