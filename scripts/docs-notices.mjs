import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));

function packageRoot(id) {
  let directory = path.dirname(id.split('?')[0]);
  while (directory !== path.dirname(directory)) {
    const manifest = path.join(directory, 'package.json');
    if (fs.existsSync(manifest) && JSON.parse(fs.readFileSync(manifest, 'utf8')).name) return directory;
    directory = path.dirname(directory);
  }
  throw new Error(`Cannot locate dependency notice for ${id}`);
}

export function docsNotices() {
  let ssr = false;
  return {
    name: 'docs-license-notices',
    apply: 'build',
    configResolved(config) { ssr = Boolean(config.build.ssr); },
    generateBundle() {
      if (ssr) return;
      // Include loaded CSS as well as JavaScript so font-package notices ship too.
      const packages = new Map();
      for (const id of this.getModuleIds()) {
        if (!path.isAbsolute(id) || !id.replaceAll('\\', '/').includes('/node_modules/')) continue;
        if (!this.getModuleInfo(id)?.isIncluded && !id.split('?')[0].endsWith('.css')) continue;
        const directory = packageRoot(id);
        const metadata = JSON.parse(fs.readFileSync(path.join(directory, 'package.json'), 'utf8'));
        packages.set(`${metadata.name}@${metadata.version}`, directory);
      }
      const sections = [`zstack / upstream pstack (MIT)\n\n${fs.readFileSync(path.join(root, 'LICENSE'), 'utf8').trim()}`];
      for (const [name, directory] of [...packages].sort(([a], [b]) => a.localeCompare(b))) {
        const files = fs.readdirSync(directory)
          .filter(file => /^(licen[cs]e|notice|copying)([.-]|$)/i.test(file)).sort()
          .map(file => path.join(directory, file));
        // DocSearch CSS 3.8.2 omits https://github.com/algolia/docsearch/blob/v3.8.2/LICENSE.
        if (!files.length && name === '@docsearch/css@3.8.2') {
          files.push(path.join(root, 'docs/.vitepress/licenses/docsearch-3.8.2.txt'));
        }
        if (!files.length) throw new Error(`Missing license text for ${name}`);
        for (const file of files) {
          const text = fs.readFileSync(file, 'utf8').trim();
          if (!text) throw new Error(`Empty license text for ${name}: ${path.basename(file)}`);
          sections.push(`${name} — ${path.basename(file)}\n\n${text}`);
        }
      }
      this.emitFile({
        type: 'asset',
        fileName: 'third-party-notices.txt',
        source: sections.join('\n\n' + '='.repeat(72) + '\n\n') + '\n',
      });
    },
  };
}
