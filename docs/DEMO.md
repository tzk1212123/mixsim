# Presentation and live demonstration guide

Use a 4-6 minute sequence around one experiment: two pumps approach a target color while the device layer enforces limits. The semester demonstration does not require chemical yield or the optional summer droplet task.

## Before presenting

1. Start MixSim and open http://127.0.0.1:8765 in a wide browser window. Narrow side panels use a stacked layout.
2. Set seed 42, target recipe 68%, total flow 400 uL/min, settling time 60 s and 10 trials, then start a new session.
3. State that this is simulation. Some device specifications are sourced; geometry, dye optics and sensor calibration remain assumptions.

## Slides and live actions

| Topic | Live action | Evidence to point out |
|---|---|---|
| Research question | Show the target and two pumps | Inputs are two flow commands; outputs are color and pressure. |
| Architecture | Explain shared Python/CLI/MCP drivers | Limits are enforced below the planner, which can issue invalid commands. |
| Normal closed loop | Run the built-in demonstration | Every trial, camera reading and error is retained. Label this a feedback baseline. |
| Delivered performance | Show the final replicate card and orange point | Best observation and independent replicate are separate records. |
| Fault handling | New session, inject x6 clog, run manual trial | Overpressure event, stopped pumps and latched interlock. |
| Recovery | Attempt a rejected flow write; clear clog, advance 10 s, reset | Repeated writes cannot bypass the device layer. |
| LLM integration | If connected, let a real model execute a short MCP campaign | Tool calls and the same experiment records appear in the dashboard. |
| Verification | Show your own pytest cases and output | Distinguish passed software checks from unperformed bench validation. |

Only call an experiment an LLM campaign when an actual model chose the parameters through MCP. Without a connected model, demonstrate prepared tools and the baseline without claiming real-model results.

## Preserve evidence

Export JSON after each campaign for complete configuration, seed, action audit, trials and final replicate. CSV is convenient for later slide plots. Export before resetting or shutting down: sessions are in memory.

Keep a normal campaign, a fault-handling log, your pytest results and, for real-model experiments, the client/model version, prompt and tool-call record. A PowerPoint deck has not been created as part of this implementation.
