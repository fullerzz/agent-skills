// Run in the browser console on /guide/visual-guide, or pass to a browser evaluation tool.
(async () => {
  const assert = (condition, message) => { if (!condition) throw new Error(message) }
  const map = document.querySelector('figure[aria-label="zstack component relationships"]')
  const route = document.querySelector('figure[aria-label="Interactive z-mode routing examples"]')
  const install = document.querySelector('figure[aria-label="Installation source and destination map"]')
  assert(map && route && install, 'Open the visual guide before running this check')
  const links = new Set([...document.querySelectorAll('.z-visual a')].map(link => link.href))
  for (const detail of map.querySelectorAll('details')) {
    detail.open = false
    detail.querySelector('summary').click()
    assert(detail.open, 'Component details must expand')
    detail.querySelector('summary').click()
    assert(!detail.open, 'Component details must collapse')
  }
  const playbooks = ['investigation', 'bug-fix', 'feature', 'pause-safely']
  const buttons = [...route.querySelectorAll('button')]
  for (const [index, button] of buttons.entries()) {
    button.click()
    await Promise.resolve()
    assert(button.getAttribute('aria-pressed') === 'true', 'Selected route must be announced')
    assert(route.querySelectorAll('[aria-pressed="true"]').length === 1, 'Exactly one selected route')
    assert(route.querySelector('.z-connector a').hash === '#playbook-' + playbooks[index], 'Route must link to its playbook')
    assert(route.querySelectorAll('ol li').length === 3, 'Route must display its three stages')
    route.querySelectorAll('a').forEach(link => links.add(link.href))
  }
  const [host, scope] = install.querySelectorAll('select')
  for (const [hostValue, scopeValue, skills, agents] of [
    ['codex', 'personal', '~/.agents/skills/<name>', '~/.codex/agents/'],
    ['codex', 'project', '<project>/.agents/skills/<name>', '<project>/.codex/agents/'],
    ['claude', 'personal', '~/.claude/skills/<name>', '~/.claude/agents/'],
    ['claude', 'project', '<project>/.claude/skills/<name>', '<project>/.claude/agents/'],
  ]) {
    host.value = hostValue
    host.dispatchEvent(new Event('change', { bubbles: true }))
    scope.value = scopeValue
    scope.dispatchEvent(new Event('change', { bubbles: true }))
    await Promise.resolve()
    const text = install.textContent
    assert(text.includes(skills) && text.includes(agents), 'Wrong installation destinations')
    assert(text.includes(agents.replace('agents/', 'zstack-install.json')), 'Wrong receipt location')
    const command = install.querySelector('.z-command > code').textContent
    assert(command.includes('--host ' + hostValue), 'Wrong command host')
    assert(command.includes('--project') === (scopeValue === 'project'), 'Wrong command scope')
  }
  for (const href of links) {
    const link = new URL(href)
    const response = await fetch(link.href)
    assert(response.ok, 'Broken visual link: ' + link.href)
    const page = new DOMParser().parseFromString(await response.text(), 'text/html')
    assert(!link.hash || page.getElementById(decodeURIComponent(link.hash.slice(1))), 'Missing reference anchor: ' + link.href)
  }
  assert(document.documentElement.scrollWidth <= innerWidth, 'Page overflows the viewport')
  return 'PASS: component expansion, four task routes, four install destinations, reference links, viewport overflow'
})()
