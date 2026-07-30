# TODO: Comments Analysis - payu/ Subdirectory

**Total TODO: Comments Found: 38**

---

## 1. SCHEDULER & CROSS-PLATFORM SUPPORT
**Category:** Infrastructure / High Priority  
**Impact:** Blocks scheduler portability (PBS, Slurm, other HPC systems)

| File | Line | TODO | Status |
|------|------|------|--------|
| `schedulers/pbs.py` | 142 | PBS class is a stub acting as a minimal port to Scheduler class | Stub implementation |
| `schedulers/pbs.py` | 381 | Need to pass lab.config_path somehow | Unresolved parameter |
| `schedulers/pbs.py` | 401 | Support full export of environment variables: `qsub -V` | Feature gap |
| `schedulers/scheduler.py` | 7 | Scheduler class is currently just a stub | Stub implementation |
| `subcommands/run_cmd.py` | 92 | Incorporate mask_table logic into Model driver | Refactoring needed |
| `subcommands/run_cmd.py` | 97 | Is control_path defined at this stage? | Uncertain state |

**Related GitHub Issues:**
- ✅ #182 "Create a Scheduler Class" (CLOSED 2026-05-19) - base infrastructure complete, but stubs remain
- 🔵 #323 "Porting payu to non-NCI machinery" (OPEN) - Pawsey/Slurm support request

---

## 2. CODE ARCHITECTURE & REFACTORING
**Category:** Technical Debt / Code Quality  
**Impact:** Maintainability, modularity, testing

| File | Line | TODO | Issue |
|------|------|------|-------|
| `experiment.py` | 95 | `__init__` should not be a config dumping ground! | Design violation |
| `experiment.py` | 141 | Move this stuff somewhere else | Miscellaneous config bloat |
| `experiment.py` | 120 | Move to run/collate/sweep? | Unclear ownership |
| `experiment.py` | 442 | Move function to setup file if setup is moved | Conditional refactor |
| `experiment.py` | 201 | Rename `self.models` to `self.submodels` | Semantic clarity |
| `cli.py` | 215 | Temporary stub to replicate the old approach | Deprecated pattern |

**Impact:** experiment.py has 4 architecture TODOs - suggests need for major refactor

---

## 3. MODULE SYSTEM & ENVIRONMENT MANAGEMENT
**Category:** System Integration / Dependencies  
**Impact:** Environment setup, version tracking

| File | Line | TODO | Details |
|------|------|------|---------|
| `experiment.py` | 53 | Core modules to be removed (Vayu-specific) | Deprecation needed |
| `experiment.py` | 92 | Replace modules set with dict, check versions via key-value pairs | Data structure upgrade |
| `envmod.py` | 113 | Bad design, fixme! (local import to avoid reversion) | Technical debt |

**Context:** Vayu HPC-specific code being phased out; module tracking needs modernization

---

## 4. CONFIGURATION & RUNTIME OPTIONS
**Category:** Features / Configurability  
**Impact:** User customization

| File | Line | TODO | Type |
|------|------|------|------|
| `experiment.py` | 104 | `expand_shell_vars` should be configurable | Feature request |
| `experiment.py` | 518 | Make `stripedio` more configurable | Configuration flexibility |

---

## 5. DATE & CALENDAR HANDLING
**Category:** Domain Logic / Correctness  
**Impact:** Model time integration accuracy

| File | Line | TODO | Severity |
|------|------|------|----------|
| `calendar.py` | 88 | Internal date correction (init_date on/after 1-March) | Edge case |
| `calendar.py` | 93 | Caltype logic could be simplified (use string instead of int) | Refactoring |
| `calendar.py` | 114 | Is GREGORIAN=proleptic_gregorian confusing? | UX/clarity |

**Note:** Potential correctness issue with date calculations

---

## 6. MODEL EXECUTION & MPI SUPPORT
**Category:** Core Functionality / Features  
**Impact:** Model runtime configuration, parallelization

| File | Line | TODO | Details |
|------|------|------|---------|
| `experiment.py` | 599 | More uniform support needed (scalasca profiler) | Feature parity |
| `experiment.py` | 621 | Check for MPI library mismatch across multiple binaries | Error detection |
| `experiment.py` | 652 | New Open MPI format? | Compatibility check |
| `experiment.py` | 328 | Consolidate profiling stuff | Code organization |

**Related Issue:**
- 🔵 #718 "Running models without MPI" (OPEN) - Request for serial/non-MPI support

---

## 7. EXECUTION & ENVIRONMENT
**Category:** Runtime Behavior / Debugging  
**Impact:** Process execution, error handling

| File | Line | TODO | Issue |
|------|------|------|-------|
| `experiment.py` | 719 | Replace with mpirun -x flag inputs | MPI flag modernization |
| `experiment.py` | 689 | Consider making coredump default | Configuration default |

---

## 8. OUTPUT & FILE HANDLING
**Category:** Data Management / I/O  
**Impact:** File organization, output streams

| File | Line | TODO | Type |
|------|------|------|------|
| `experiment.py` | 370 | Per-model output streams? | Architecture question |
| `experiment.py` | 392 | Check case counter == 0 | Edge case validation |
| `experiment.py` | 511 | Reconstruct config.yaml with default values | Enhancement |
| `status.py` | 62 | Support non-default stderr and stdout file names | Feature gap |
| `status.py` | 271 | Parse stdout files to get exit status | Feature enhancement |

---

## 9. PROCESS CLEANUP & ERROR RECOVERY
**Category:** Reliability / Error Handling  
**Impact:** Job cleanup, error detection, state management

| File | Line | TODO | Severity |
|------|------|------|----------|
| `experiment.py` | 746 | Need model-specific cleanup method call | Missing feature |
| `experiment.py` | 1072 | Fix the IO race conditions! | **Critical** |
| `experiment.py` | 1074 | Model outstreams and PBS logs need separate handling | Architecture |
| `experiment.py` | 1096 | New path may still exist! (assertion issue) | Potential bug |

**Critical:** IO race conditions in sweep process need resolution

---

## 10. RESTART & STATE MANAGEMENT
**Category:** Experiment Flow  
**Impact:** Restart handling, experiment continuity

| File | Line | TODO | Details |
|------|------|------|---------|
| `experiment.py` | 1150 | Figure out restart pruning logic with repeat_run | Undefined behavior |

---

## 11. FMS MODEL DRIVER
**Category:** Model-Specific / Data Processing  
**Impact:** Collation, output validation

| File | Line | TODO | Type |
|------|------|------|------|
| `models/fms.py` | 309 | Validate collated file somehow | QA/validation |
| `models/fms.py` | 330 | Categorise the return codes | Error handling |

---

## 12. OASIS COUPLER
**Category:** Model Integration  
**Impact:** Coupled model configuration

| File | Line | TODO | Status |
|------|------|------|--------|
| `models/oasis.py` | 40 | Parse namcouple to determine filelist | Enhancement |
| `models/oasis.py` | 41 | Let users map files to models | Feature request |

**Related Issue:**
- ✅ #168 "oasis driver: namcouple copied from restart" (CLOSED 2019-02-27)

---

## 13. WW3 & CICE MODELS
**Category:** Model-Specific Setup  
**Impact:** Model initialization

| File | Line | TODO | Status |
|------|------|------|--------|
| `models/ww3.py` | 30 | Construct grid files | Stub/incomplete |
| `models/cice5.py` | 105 | Move to ACCESS driver | Refactoring |

---

## 14. COLLATION COMMAND
**Category:** Post-processing / Job Submission  
**Impact:** Job resource estimation

| File | Line | TODO | Type |
|------|------|------|------|
| `subcommands/collate_cmd.py` | 72 | Calculate default memory based on ncpus and platform | Dynamic estimation |
| `subcommands/collate_cmd.py` | 85 | Test the sequence, not just string characters | Validation improvement |

**Related Issues:**
- 🔵 #566 "Using the iointensive queue feature" (OPEN) - I/O intensive resources
- ✅ #756 "payu status shows incorrect queue status for collate job" (CLOSED 2026-06-10)

---

## SUMMARY BY PRIORITY & IMPACT

### 🔴 Critical (Must Address)
1. **experiment.py:1072** - Fix IO race conditions in sweep
2. **experiment.py:1096** - Path may still exist assertion bug

### 🟠 High Priority (Blocks Features/Portability)
1. **Scheduler stubs** (pbs.py:142, scheduler.py:7) - Blocks Slurm/cross-platform support (#323)
2. **experiment.py:95** - `__init__` bloat affects testability
3. **experiment.py:621** - MPI library mismatch detection missing
4. **MPI support** (experiment.py:652, 719) - Open MPI format compatibility

### 🟡 Medium Priority (Code Quality/Features)
1. **Calendar logic** (calendar.py:88, 93, 114) - Potential correctness issues
2. **Profiling consolidation** (experiment.py:328)
3. **Output streams** (experiment.py:370)
4. **Model-specific cleanup** (experiment.py:746)

### 🟢 Low Priority (Nice-to-Have)
1. Configuration defaults (experiment.py:689, 104)
2. Deprecation cleanup (experiment.py:53)
3. Validation/error handling improvements

---

## CROSS-REFERENCE: TODOs vs GitHub Issues

**Issues with Related TODOs:**
- #182 ✅ CLOSED - Scheduler class (still has stubs in code)
- #168 ✅ CLOSED - OASIS namcouple handling
- #323 🔵 OPEN - Slurm/non-NCI support (blocked by scheduler TODOs)
- #566 🔵 OPEN - iointensive queue feature (relates to collation)
- #718 🔵 OPEN - Non-MPI model support (relates to MPI TODOs)
- #756 ✅ CLOSED - Collate status reporting

**Orphaned TODOs (No Matching Issue):**
- IO race conditions (experiment.py:1072)
- Config/architecture refactoring (experiment.py:95, 141, 120)
- Calendar edge cases (calendar.py:88)
- 20+ other technical items

---

## RECOMMENDATIONS

1. **Create issue for IO race conditions** - Critical blocker for reliability
2. **Track scheduler TODO removal** - Link to #323 for Slurm support
3. **Batch architecture refactoring** - experiment.py needs comprehensive restructure
4. **Document calendar behavior** - Clarify date handling edge cases
5. **MPI modernization** - Address compatibility with newer MPI versions
