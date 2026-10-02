process.env.NODE_ENV = 'development';
process.argv.splice(1, 1, 'vitepress', 'dev', 'docs');
await import('vitepress/dist/node/cli.js');
