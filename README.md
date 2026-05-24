# Development Status

# DEVELOPMENT IN PROGRESS

> Project ini masih dalam tahap pengembangan aktif dan belum production-ready.
> Arsitektur masih terus berubah dan beberapa fitur masih dalam tahap stabilisasi.

---

# AI Agent Platform

Sebuah platform AI Agent modular berbasis:

* React + Vite frontend
* Python FastAPI orchestration backend
* Node.js runtime sandbox
* Workspace generator system
* Real-time execution streaming
* Multi-stage AI orchestration architecture

Project ini dirancang sebagai fondasi:

* AI App Generator
* AI Coding Agent
* Runtime Sandbox
* Visual AI Workspace
* Multi-provider orchestration system

---

# Features

* AI orchestration backend
* Runtime sandbox execution
* Real-time terminal streaming
* Workspace isolation system
* Frontend IDE shell
* SSE event streaming
* Multi-process execution
* Generated app preview system
* Architecture-first modular design
* AI repair/recovery pipeline foundation

---

# Architecture Overview

```text
Frontend (React/Vite)
        │
        ▼
Python Backend (FastAPI)
        │
        ▼
Node Runtime Sandbox
        │
        ▼
Generated Workspace Apps
```

---

# Project Structure

```text
ai-agent/
│
├── backend/              # FastAPI AI orchestration core
├── frontend/             # React frontend shell
├── runtime/              # Node.js runtime sandbox
├── workspaces/           # Generated applications
│
├── .gitignore
├── package-lock.json
├── requirements.txt
└── README.md
```

---

# Core Responsibilities

## frontend/

Frontend hanya bertugas sebagai:

* IDE shell
* terminal display
* preview UI
* event visualization

Frontend tidak memiliki:

* orchestration logic
* process management
* AI reasoning

---

## backend/

Backend adalah pusat sistem AI:

* orchestration
* planning
* generation
* repair
* streaming
* workflow execution

Menggunakan:

* FastAPI
* SSE/WebSocket
* Python orchestration pipeline

---

## runtime/

Runtime adalah sandbox executor:

* menjalankan proses
* streaming log
* menjalankan generated app
* isolated execution

Menggunakan:

* Node.js
* execa
* PTY process management

---

## workspaces/

Workspace adalah output generated app.

Contoh:

* todo app
* calendar app
* dashboard
* generated frontend/backend

Folder ini tidak masuk GitHub karena bersifat temporary/generated.

---

# Requirements

## Software

Wajib install:

* Node.js 20+
* Python 3.11+
* Git

Disarankan:

* VSCode
* pnpm atau npm

---

# Installation

## 1. Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd ai-agent
```

---

## 2. Install Frontend Dependencies

```bash
cd frontend
npm install
```

---

## 3. Install Runtime Dependencies

```bash
cd ../runtime
npm install
```

---

## 4. Setup Python Backend

```bash
cd ../backend
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

Install dependency:

```bash
pip install -r ../requirements.txt
```

---

# Environment Setup

Buat file:

```text
.env
```

Contoh:

```env
OPENAI_API_KEY=your_api_key
ANTHROPIC_API_KEY=your_api_key

BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000

RUNTIME_PORT=3001
```

---

# Running The System

Sistem memiliki 3 service utama yang harus berjalan.

---

# 1. Start Backend

Masuk ke root project:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Expected output:

```text
Application startup complete.
Uvicorn running on http://127.0.0.1:8000
```

---

# 2. Start Runtime

```bash
cd runtime
npm run dev
```

Expected output:

```text
Runtime listening on port 3001
```

---

# 3. Start Frontend

```bash
cd frontend
npm run dev
```

Expected output:

```text
VITE ready in xxx ms
Local: http://localhost:5173
```

---

# Application Flow

```text
User Prompt
    │
    ▼
Frontend UI
    │
    ▼
Python Backend
    │
    ▼
Runtime Sandbox
    │
    ▼
Workspace Generation
    │
    ▼
Preview + Logs
```

---

# Input and Output

# Input

Input utama sistem:

```text
Natural language prompt
```

Contoh:

```text
Create a todo app with dark mode and local storage
```

Atau:

```text
Build a calendar app with drag and drop support
```

---

# Output

Output sistem:

## 1. Generated Application

Disimpan di:

```text
workspaces/
```

---

## 2. Real-time Logs

Contoh:

```text
Installing dependencies...
Generating files...
Starting preview server...
Preview ready.
```

---

## 3. Preview URL

Contoh:

```text
http://localhost:xxxx
```

---

# Current Development Status

## Working

* frontend shell
* runtime communication
* SSE streaming
* basic generation pipeline
* workspace isolation
* process spawning
* log streaming

---

## In Progress

* dependency stabilization
* runtime recovery
* advanced orchestration
* automatic repair pipeline
* complex app generation
* multi-provider routing

---

# Known Limitations

Saat ini:

* aplikasi sederhana berjalan lebih stabil
* aplikasi dengan dependency kompleks masih dalam tahap stabilisasi
* beberapa generated app dapat stuck pada UI preview
* runtime recovery belum sepenuhnya otomatis

---

# Security Notes

Jangan upload:

* `.env`
* API keys
* generated workspaces
* logs
* private docs

Pastikan `.gitignore` aktif sebelum push repository.

---

# Development Philosophy

Project ini menggunakan pendekatan:

```text
Architecture First
```

Artinya:

* boundary harus jelas
* ownership harus jelas
* orchestration centralized
* runtime isolated
* frontend dumb shell

---

# Example Workflow

## Prompt

```text
Create a weather dashboard with charts
```

## System Execution

```text
Frontend -> Backend -> Runtime -> Workspace
```

## Result

```text
Generated React application
+
Preview URL
+
Terminal logs
```

---

# Future Goals

* AI self-repair
* visual node orchestration
* multi-agent collaboration
* plugin system
* offline runtime mode
* VSCode-like editor integration
* deployment automation
* template marketplace

---

# Contributing

Project masih dalam tahap active development.

Gunakan branch terpisah untuk eksperimen besar.

---


# MIT License
MIT License
Copyright (c) 2026 gazeX69

---
# Support Development

Jika project ini membantu atau menarik untukmu, kamu bisa mendukung pengembangan project ini melalui Trakteer:

☕ https://trakteer.id/gazeX69

Support akan membantu:
- pengembangan fitur baru
- biaya AI/API experimentation
- runtime infrastructure
- maintenance dan stabilisasi project