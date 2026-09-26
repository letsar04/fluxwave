# FluxWave

**Adaptive data transfer engine for large-scale file sharing.**

FluxWave explores a different model for heavy data transfer: instead of treating a file as an indivisible object, it models the data as reconstructible fragments and dynamically chooses what to transfer, from which peers, and with what redundancy.

> Research/engineering prototype — not production-ready.

## Core hypothesis

A large transfer should optimize **reconstruction cost**, not merely raw throughput.

FluxWave's experimental planner, **WARP (Weighted Adaptive Reconstruction Planner)**, evaluates candidate actions using estimated transfer cost, latency, failure risk, and reconstruction gain.

## The key idea: transfer vs reconstruction

The destination does not necessarily need the missing fragment itself.

A target fragment can have one or more **logical reconstruction rules**, for example:

```text
F3 = reconstruct(F1, F2)
```

WARP can then compare:

```text
direct cost      = cost(fetch F3)
reconstruction   = cost(fetch missing prerequisites) + CPU cost
```

If prerequisites already exist at the destination, their transfer cost is zero. If prerequisites are themselves reconstructible, FluxWave can recursively evaluate that dependency chain.

This is currently a **planning abstraction**, not a claim that FluxWave has invented a new codec. Actual byte-level codecs will be implemented later as replaceable backends.

## Current architecture

```text
File
  |
  v
Fragments + fingerprints
  |
  v
Availability graph
  |
  +------> Destination state
  |
  +------> Reconstruction rules
  |
  v
WARP
  |
  +--> direct transfer
  |
  +--> recursive reconstruction
  |
  v
Source-aware scheduler
  |
  v
Transport simulation
```

## Project goals

- Content-aware chunking and fingerprints
- Fragment/data availability graph
- Dependency-aware reconstruction planning
- Partial-state awareness and deduplication
- Adaptive peer scheduling
- Adaptive redundancy
- Reproducible network simulation
- Benchmarks against simple transfer strategies
- Pluggable reconstruction codecs

## Repository layout

```text
fluxwave/
├── fluxwave/
│   ├── core/
│   │   ├── chunking.py
│   │   ├── graph.py
│   │   ├── planner.py
│   │   ├── reconstruction.py
│   │   ├── scheduler.py
│   │   └── state.py
│   └── network/
├── tests/
├── benchmarks/
├── docs/
└── pyproject.toml
```

## Development principles

1. No claims of novelty without evidence.
2. Every optimization must be measurable.
3. Baselines are mandatory.
4. Failure cases are documented, not hidden.
5. The prototype must remain reproducible on a normal development machine.
6. A logical reconstruction rule must never be confused with a working byte-level codec.

## Current experimental milestone

**Phase 1 — dependency-aware reconstruction planning**

The prototype now models:

- fragments available at the destination;
- fragments available from specific peers;
- multiple reconstruction rules per target;
- recursive dependency chains;
- cycle detection;
- direct-transfer versus reconstruction cost;
- source-aware scheduling.

The next experimental step is to implement a small real codec backend, such as XOR parity, and measure whether the planner's predicted strategy matches actual reconstruction time and transferred bytes.
