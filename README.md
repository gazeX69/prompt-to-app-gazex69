# AI Agent Platform

[![Development Status](https://img.shields.io/badge/Status-Development%20In%20Progress-orange.svg)](#development-status)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](#mit-license)

Sebuah platform AI Agent modular berbasis arsitektur terdistribusi untuk pembuatan dan perbaikan aplikasi secara otomatis (*autonomous code generation & self-repair*). 

---

## 🛠️ Status Pengembangan (Development Status)

> [!IMPORTANT]
> **DEVELOPMENT IN PROGRESS**
> Project ini masih dalam tahap pengembangan aktif dan belum siap untuk production (non-production ready).
> Arsitektur inti dan boundary komunikasi antar-layanan masih terus diperbarui secara berkala. Beberapa fitur masih dalam tahap stabilisasi.

---

## 🏗️ Gambaran Umum Arsitektur (Architecture Overview)

Platform ini mengadopsi prinsip **Architecture First** dengan pembagian tanggung jawab yang jelas (*clear boundaries*):

```text
       ┌──────────────────────────────┐
       │     Frontend (React/Vite)    │  <- IDE Shell, Terminal, Preview & Event Display
       └──────────────┬───────────────┘
                      │ HTTP / WebSocket (Socket.IO)
                      ▼
       ┌──────────────────────────────┐
       │   Python Backend (FastAPI)   │  <- Orchestration, Planning, Patching & AI Reasoning
       └──────────────┬───────────────┘
                      │ HTTP / SSE Events
                      ▼
       ┌──────────────────────────────┐
       │  Node.js Runtime Sandbox     │  <- Isolated Execution, PTY Terminal, DevServer Spawner
       └──────────────┬───────────────┘
                      ▼
       ┌──────────────────────────────┐
       │   Generated Workspaces       │  <- Output Aplikasi yang Dihasilkan
       └──────────────────────────────┘
```

---

## 📂 Struktur Proyek (Project Structure)

```text
ai-agent/
├── backend/              # Inti orkestrasi AI (FastAPI, agent planning, prompt templates)
├── frontend/             # Antarmuka pengguna berbentuk IDE shell & viewer
├── runtime/              # Node.js sandbox executor (execa, PTY process streams)
└── workspaces/           # Folder penyimpanan aplikasi hasil generate (diabaikan dari Git)
```

---

## ⚙️ Persyaratan Sistem (Requirements)

* **Node.js:** Versi 20 atau lebih baru
* **Python:** Versi 3.11 atau lebih baru (disarankan menggunakan Virtual Environment)
* **Git:** Versi terbaru untuk manajemen repositori

---

## 🚀 Panduan Instalasi (Installation Guide)

### 1. Clone Repositori
```bash
git clone https://github.com/gazeX69/ai-agent.git
cd ai-agent
```

### 2. Instalasi Dependensi Frontend
```bash
cd frontend
npm install
```

### 3. Instalasi Dependensi Runtime
```bash
cd ../runtime
npm install
```

### 4. Setup Python Backend & Virtual Environment
```bash
cd ../backend
python -m venv venv
```
* **Mengaktifkan venv (Windows):**
  ```bash
  venv\Scripts\activate
  ```
* **Mengaktifkan venv (Linux/macOS):**
  ```bash
  source venv/bin/activate
  ```
* **Instalasi Dependensi Python:**
  ```bash
  pip install -r ../requirements.txt
  ```

---

## 📝 Setup Environment (`.env`)

Buat file bernama `.env` pada root directory proyek dengan konfigurasi sebagai berikut:

```env
# AI Model Provider API Key (Qwen/Dashscope adalah default utama)
DASHSCOPE_API_KEY=your_dashscope_api_key

# Opsional: Provider Lainnya
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Konfigurasi Port Default
API_HOST=127.0.0.1
API_PORT=8000
RUNTIME_PORT=3001
CORS_ORIGINS=http://localhost:5173
```

---

## 🖥️ Menjalankan Sistem (Running The System)

### Cara A: Menggunakan Single Command (Sangat Direkomendasikan)
Metode ini akan secara otomatis memindai port yang kosong dan menjalankan ketiga layanan (Backend, Runtime, Frontend) secara bersamaan dalam satu terminal shell.
1. Buka terminal pada root folder `ai-agent`.
2. Jalankan perintah:
   ```bash
   npm run dev:all
   ```
3. Buka halaman frontend di browser pada alamat yang tertera (biasanya `http://127.0.0.1:5173`).

### Cara B: Menjalankan Secara Manual di Terminal Terpisah
Jika Anda ingin memantau log per-layanan secara terpisah:

1. **Jalankan Backend:**
   ```bash
   cd backend
   venv\Scripts\activate  # Windows
   uvicorn backend.main:app --host 127.0.0.1 --port 8000
   ```
2. **Jalankan Runtime Sandbox:**
   ```bash
   cd runtime
   npm run dev
   ```
3. **Jalankan Frontend:**
   ```bash
   cd frontend
   npm run dev
   ```

---

## 🔍 Kebijakan Berkas Git (.gitignore Policy)

Repositori ini menerapkan manajemen berkas bersih (*clean repository policy*):
* **Format Markdown (`*.md`):** Semua berkas markdown diabaikan secara otomatis kecuali berkas dokumentasi utama `README.md` dan `readme.md`.
* **Kredensial & Kunci API:** Berkas konfigurasi seperti `.env` dan `backend/brain/memory/providers.json` diabaikan sepenuhnya agar tidak bocor ke publik.
* **Proyek Hasil Generate:** Seluruh isi folder `workspaces/` dan `scratch/` tidak akan masuk pelacakan Git.

---

## ☕ Support Development

Jika project ini membantu atau menarik untukmu, kamu bisa mendukung pengembangan project ini melalui Trakteer:

☕ https://trakteer.id/gazeX69

Support akan membantu:
* pengembangan fitur baru
* biaya AI/API experimentation
* runtime infrastructure
* maintenance dan stabilisasi project

---

## 📄 MIT License
MIT License - Copyright (c) 2026 gazeX69.
Selengkapnya dapat dilihat pada berkas `License`.