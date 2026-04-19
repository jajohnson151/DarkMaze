# Dark Maze — Plan v2 (Updated with GM State Model)

---

# 1. Goal

Build a client-server dungeon exploration system where:

* The **player explores blindfolded**
* The **server is authoritative**
* The **GM designs, edits, and runs the maze**
* The system cleanly separates:

  * design-time state
  * runtime play state

---

# 2. Core System Model

(unchanged — omitted here for brevity)

---

# 3. Architecture

(unchanged — omitted here for brevity)

---

# 4. GM Interface Architecture

## 4.1 Core Principle

The GM interface is driven by a **single authoritative maze lifecycle**.

At all times:

* The UI displays the **current maze if one exists**
* The system distinguishes between:

  * **Working Maze** (temporary)
  * **Active Maze** (committed, valid)

---

## 4.2 Maze States

### No Maze

* No maze exists in session

### Working Maze (Uncommitted)

* Temporary maze under construction or generation
* Can be modified freely
* Not valid for play

### Active Maze (Committed)

* Fully defined maze
* Valid for play
* Immutable during play mode

---

## 4.3 State Transitions

```text
No Maze
  → Create Maze → Working Maze
  → Load Maze → Active Maze

Working Maze
  → Generate → Working Maze
  → Re-do → Working Maze
  → Accept → Active Maze
  → Discard → No Maze

Active Maze
  → Edit Maze → Working Maze (copy)
  → Start Play Mode → Play Mode
  → Load Maze → Active Maze (replace)
```

---

## 4.4 Top-Level GM Actions

### When No Maze Exists

* Load Maze (file)
* Create Maze

---

### When Working Maze Exists

* Generate Maze (algorithm)
* Re-do (same parameters)
* Accept (commit to Active Maze)
* Discard (clear working state)

---

### When Active Maze Exists

* Edit Maze (creates Working Maze copy)
* Start Play Mode (if valid)
* Load Maze (replace)
* Create Maze (reset)

---

## 4.5 Create Maze Workflow

1. User inputs:

   * width
   * height

2. System creates:

   * Working Maze initialized as **all walls**

3. UI enters Working Maze state

---

## 4.6 Generation Workflow

### Generate

* Input:

  * algorithm
  * parameters (seed, etc.)

* Server generates maze topology

* Replaces Working Maze grid

---

### Re-do

* Re-run generation with same parameters
* Replaces Working Maze

---

### Accept

* Promote Working Maze → Active Maze
* Active Maze becomes authoritative

---

## 4.7 Edit Workflow

* Edit Maze clones Active Maze → Working Maze

* User modifies:

  * walls
  * placements
  * features

* Accept commits back to Active Maze

---

## 4.8 Play Mode

### Preconditions

* Active Maze exists
* Active Maze is valid:

  * has spawn
  * has exit
  * valid grid

### Behavior

* Maze becomes immutable
* Session mode = "play"

---

## 4.9 Display Rules

* Maze is always displayed if present
* Visual indicators:

  * Working Maze → "Preview / Uncommitted"
  * Active Maze → "Ready"
  * Play Mode → runtime overlays

---

## 4.10 UI Layout (Simplified)

### Top Menu (Always Visible)

* Load Maze
* Create Maze
* Edit Maze (if Active exists)
* Start Play Mode (if valid)

---

### Contextual Controls

#### Working Maze

* Algorithm selection
* Parameter inputs
* Generate
* Re-do
* Accept / Discard

#### Active Maze

* Start Play Mode
* Edit Maze

---

### Main Canvas

* Maze visualization (always visible if maze exists)

---

## 4.11 Design Rules

* Working Maze is never used for play
* Generation never modifies Active Maze directly
* Editing always operates on a copy
* Accept is the only way to commit changes
* Play Mode uses Active Maze only

---

# 5. Design System (Merged)

## 5.1 Editing

* Drag between cells:

  * normal drag → open wall
  * shift + drag → close wall

* Placement tools:

  * player spawn
  * exit
  * monster
  * item
  * hazard

---

## 5.2 Generation

* Algorithm registry:

  * recursive_backtracker (MVP)

* Parameters:

  * seed

---

## 5.3 Data Model (Template)

* width / height
* grid (walls + features)
* player_spawn
* exit
* monsters
* monster_types

---

# 6. Play Mode

(unchanged — resolver, hearing, etc.)

---

# 7. Execution Phases

(unchanged)

---

# 8. Non-Goals

(unchanged)

---

# 9. Key Principles

* clear separation of working vs active maze
* explicit commit model (Accept)
* deterministic state transitions
* no implicit mutation of authoritative data

---
