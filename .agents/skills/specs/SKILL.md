---
name: specs
description: |
  Designs and authors detailed technical specifications from PROJECT_PLAN.md on major Phase feature branches.
  Usage: /specs <task_number> <task_name> (e.g., /specs 1 DATABASE_SETUP or /specs 2.3 USDA_TOOL_NODE).
  Enforces a clean git status, manages major Phase feature branches (Phase 0, Phase 1, Phase 2), and creates detailed specs in specs/<task_number>_<TASK_NAME>.md without auto-executing code.
---

# Specs Workflow & Task Execution

This skill handles task design, phase branch management, and specification authoring from `PROJECT_PLAN.md`.

---

## Command Usage

Invoke in chat:
```text
/specs <task_number> <task_name>
```
* **Examples**:
  * `/specs 1 DATABASE_SETUP`
  * `/specs 2.3 USDA_TOOL_NODE`

---

## Mandatory Execution Steps

### Step 1: Strict Git Status Purity Check

Before performing ANY file edits, branch creation, or work:
1. Check if git is initialized (`git rev-parse --is-inside-work-tree`). If git is initialized, run `git status --porcelain`.
2. **If `git status --porcelain` is NOT empty** (uncommitted changes, untracked files, or staged changes exist):
   > [!CAUTION]
   > **ABORT EXECUTION IMMEDIATELY.** Do NOT create or switch branches. Do NOT write spec files. Do NOT write code.
   > Display the following error message to the user:
   > 
   > **`GIT STATUS IS NOT CLEAN!`**
   > *Please commit, stash, or clean working tree changes before starting a new task.*

3. **If git status IS clean** (or if git repo initialization is the task itself): Proceed to Step 2.

---

### Step 2: Major Phase Feature Branch Management

> [!IMPORTANT]
> Feature branches are ONLY created for major Phase jumps (e.g., Phase `0`, `1`, `2`, `3`, `4`), **NOT** for individual subtasks like `0.1`, `0.2`, `1.2`, or `2.3`.

1. **Extract Major Phase Number**:
   - Extract the root phase number from `<task_number>` (e.g., for `0.1` or `0` $\rightarrow$ Phase `0`; for `1.2` or `1` $\rightarrow$ Phase `1`; for `2.3` or `2` $\rightarrow$ Phase `2`).
2. **Branch Management Rules**:
   - **For Major Phase Entry** (e.g., `/specs 1 DATABASE_SETUP`):
     Create and checkout a new major branch: `feature/phase-<phase_number>-<formatted_task_name>` (e.g., `feature/phase-1-database-setup`).
   - **For Subtasks** (e.g., `/specs 1.2 EXECUTE_DDL_MIGRATION`):
     Check out or remain on the parent phase branch `feature/phase-<phase_number>` (or `feature/phase-1-database-setup`). **Do NOT create a separate sub-branch for subtasks (`1.1`, `1.2`, `2.3`).**

---

### Step 3: Read Project Plan & Author Detailed Spec

1. Read `PROJECT_PLAN.md` from the workspace root (`file:///home/jiggra/bite-backend/PROJECT_PLAN.md`).
2. Locate the specific section for `<task_number>`.
3. Ensure the `specs/` directory exists.
4. Construct spec file path: `specs/<task_number>_<UPPERCASE_TASK_NAME>.md` (e.g., `specs/1.0_DATABASE_SETUP.md`).
5. Write a highly detailed, comprehensive, production-grade technical specification containing:
   - **Task Metadata**: Task ID, Title, Major Phase Branch, Status.
   - **Goal & Architectural Overview**
   - **Technical Requirements & Data Structures**
   - **Security & Performance Standards** (complying strictly with `backend-engineering-security-performance` guidelines).
   - **Step-by-Step Implementation Blueprint**
   - **Verification & Acceptance Criteria**

> [!IMPORTANT]
> `/specs` ONLY authors the specification file inside `specs/`. Do NOT write implementation code or execute tasks during `/specs`. Provide a summary with a clickable link to the generated spec file when finished.

