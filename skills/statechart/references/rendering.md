# Render statecharts

The pipeline always writes Mermaid sources, stories, counts, and TLC evidence. Rendering is optional and local; it does not send models to a hosted service. Run commands from an owned scratch directory, with an absolute `STATECHART_DIR` resolved from the loaded skill.

## Mermaid PNG

`--png` uses `npx -y @mermaid-js/mermaid-cli`; it needs npm and a working Chromium installation. Use a project-pinned Mermaid CLI where reproducibility matters. Package execution may download dependencies; follow the target environment's installation policy.

```sh
node "$STATECHART_DIR/scripts/statechart.mjs" from-spec Code.tla --png
```

## Pele SVG

[Pele](https://pele.run/) renders the same Mermaid source into standalone SVG without a browser. Install `pele` locally in the working directory using its package manager and record the locked version. Do not install it into the plugin cache or globally. For a new scratch project:

```sh
npm install --save-exact pele
node "$STATECHART_DIR/scripts/statechart.mjs" from-chart flow.mmd --pele
```

The helper resolves `pele` from the working directory, so linked and packaged skill paths behave alike. It calls the [render API](https://pele.run/api) with fixed dimensions and disabled links and images. No renderer is downloaded by `--pele`. A missing dependency, rejected chart, or failed render exits 2 while preserving the current run's model evidence and successfully rendered files. Both `--png` and `--pele` can be requested in one run; either renderer's failure makes the run incomplete.

Pele's [layout and themes differ from Mermaid](https://pele.run/compatibility). Inspect every overview and trace, including nested states, parallel regions, status borders, legends, and numbered steps. Keep the Mermaid source with the SVG so readers can inspect the same graph. Use Mermaid PNG when that output format is required; Pele does not provide PNG conversion here.

Output directories belong to the generator: rerunning without a rendering flag removes that format's old images. Keep annotations and other user files elsewhere. The color statuses and `bug-N` names describe model results; report implementation bugs or fixes only after real-code reproduction.
