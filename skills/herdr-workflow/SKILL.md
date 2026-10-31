---
name: herdr-workflow
description: "Compatibility entrypoint for selecting Herdr execution and loading the installed herdr-zstack hc-workflow companion."
disable-model-invocation: true
---

# Herdr workflow

Native Herdr execution lives in the installed **herdr-zstack:hc-workflow** companion. Resolve it through the current host's skill catalog or the absolute path supplied by zstack's session hook, then read it alongside the selected playbook. See [herdr-zstack](https://github.com/fullerzz/herdr-zstack/blob/main/skills/hc-workflow/SKILL.md) for installation and operations. A missing or ambiguous companion is a capability gap: stop dependent Herdr work, with no legacy fallback.

This compatibility entrypoint preserves existing invocations. Loading it alone does not select execution or authorize workers. On an explicit request, use only the current session's trusted Herdr/Native controls; use Enable separately if z-mode is also requested. Disable clears both preferences. Without controls, preserve selection conversationally and in handoffs. Never copy controls into children. Controls change preferences, not processes; reconcile assigned workers before changing execution methods.

The selected playbook and [shared execution contract](../z-mode/references/native-hosts.md#execution-selection) retain scope, authority, ownership and acceptance. The installed companion owns preflight, launch, collection, pause, pickup and cleanup.
