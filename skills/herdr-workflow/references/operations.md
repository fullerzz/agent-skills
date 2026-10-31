# Native Herdr operations

Native `hc` operations live in the installed **herdr-zstack:hc-workflow** companion. Resolve it through the current host catalog or the path supplied by zstack’s session hook and read it before operating. A missing or ambiguous installation is a capability gap; do not use legacy `herdr pane` / `herdr agent` commands as a fallback. See the [companion repository](https://github.com/fullerzz/herdr-zstack).

Native detection requires `HC_TERMINAL_ID`, a live caller resolved by `hc get "$HC_TERMINAL_ID"`, and an answering `hc server status` on the same core. `HERDR_ENV` alone proves neither native identity nor availability. Use the companion’s read-only preflight: hc discovery commands can start a core, so do not probe an absent core through the CLI.

## Pickup, pause and cleanup

Use the companion’s native reconciliation steps. Verify the recorded endpoint, terminal occupant, checkout, revision, assignment and evidence before sending anything. Never automatically replay a prompt. Drain or interrupt previous writers before replacement; preserve task artifacts and unrelated terminals. Preference controls change no processes, and no parent controls or plugin state paths belong in child briefs.

The selected zstack playbook still owns scope, authorization and acceptance under the [shared execution contract](../../z-mode/references/native-hosts.md#execution-selection). Enabling Herdr supplies no extra delegation, installation, publication, remote-access or cleanup authority.
