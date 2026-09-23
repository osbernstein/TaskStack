# TaskStack
Task tracker for school assignments, daily tasks, and other to-do lists

A lightweight, local REST API built with Python, FastAPI, and SQLite to manage and filter coursework assignments on macOS.

---

## 1. Project Overview

* **Runtime:** Python 3.10+
* **Framework:** FastAPI
* **Server:** Uvicorn
* **Database:** SQLite (file-based: `assignments.db`, zero setup required)
* **Interactive UI:** Swagger UI served automatically at `http://127.0.0.1:8000/docs`

---

## 2. Data Model

Each assignment record contains:

| Field      | Type    | Description                                   | 
| :---       | :---    | :---                                          | 
| `id`       | Integer | Unique identifier (auto-generated)            | 
| `title`    | String  | Assignment name or topic                      | 
| `course`   | String  | Course code or name                           |
| `due_date` | String  | Due date (`YYYY-MM-DD`)                       |
| `due_time` | String  | Due time (`HH:MM`, 24-hr format)              | 
| `status`   | String  | `"not_started"`, `"in_progress"`, or `"done"` | 
| `link`     | String | URL to LMS or assignment details (optional)    |

---

## 3. API Endpoints & Filter Specs

*GET /assignments*
Query Filters / Body: ?course=CS101&status=not_started&due_date=2026-10-15
Purpose: List assignments with optional filters
*POST /assignments*
Query Filters / Body: JSON Body (all fields except id)
Purpose: Create a new assignment
*GET /assignments/{id}*
Query Filters / Body: —
Purpose: Get single assignment details
*PATCH /assignments/{id}*
Query Filters / Body: JSON Body (partial updates like {"status": "done"})
Purpose: Update an assignment
*DELETE /assignments/{id}*
Query Filters / Body: —
Purpose: Delete an assignment

---

## 4. Initial Setup (Terminal)

Open the **Terminal** app on your Mac and navigate to this folder:

```bash
cd path/to/assignment-tracker
