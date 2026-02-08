# Tasks Manifest

**Project:** workflow-as-models
**Created:** 2026-02-07

## Phases

| Phase | Status | Spec File |
|-------|--------|-----------|
| 1: Clean Slate | pending | spec-phase-1.md |
| 2: Workflow Engine | blocked (by Phase 1) | spec-phase-2.md |
| 3: Hardening | blocked (by Phase 2) | spec-phase-3.md |

## Quick Start

Start execution with:

```
/execute-spec docs/ideation/workflow-as-models/spec-phase-1.md
```

After Phase 1 completes, review and commit, then:

```
/execute-spec docs/ideation/workflow-as-models/spec-phase-2.md
```

After Phase 2 completes, review and commit, then:

```
/execute-spec docs/ideation/workflow-as-models/spec-phase-3.md
```

## Artifacts

```
docs/ideation/workflow-as-models/
├── contract.md          # Approved contract
├── prd-phase-1.md       # Phase 1: Strip & rename
├── prd-phase-2.md       # Phase 2: Workflow engine
├── prd-phase-3.md       # Phase 3: Tests & hardening
├── spec-phase-1.md      # Phase 1 implementation spec
├── spec-phase-2.md      # Phase 2 implementation spec
├── spec-phase-3.md      # Phase 3 implementation spec
└── tasks-manifest.md    # This file
```
