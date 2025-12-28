# ArmorIQ-Assignment
# 🏦 FastAPI Banking System (with RAG Features)

A robust, lightweight banking MCP Server built with **FastAPI** and **SQLite**.

This project simulates core banking operations including atomic fund transfers, account management, and an AI-powered "Policy Search" feature that demonstrates Retrieval-Augmented Generation (RAG) concepts.

Live Link - armoriq-assignment.onrender.com
---

## 🚀 Features

### Core Banking Operations
* **Account Management:** Create accounts with initial deposits.
* **Transactions:** Deposit and withdraw funds with real-time validation.
* **Atomic Fund Transfers:** Securely move money between accounts using database transactions (ACID compliant).
* **Transaction History:** View detailed logs of all actions for any account.

### Advanced Features
* **🛡️ Atomic Safety:** Uses `commit()` and `rollback()` to ensure money is never lost during failed transfers.
* **🤖 Policy Knowledge Base (RAG):** A dedicated endpoint (`/policies`) that allows users (or AI agents) to search the bank's official handbook for rules on fees, limits, and hours.
* **✅ Data Validation:** Powered by **Pydantic** models to ensure strict input type checking and clear error messages.

---

## 🛠️ Tech Stack

* **Framework:** [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11+)
* **Server:** Uvicorn (ASGI)
* **Database:** SQLite (Embedded, lightweight)
* **Validation:** Pydantic

---

## 📦 Installation & Local Run

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yugborana/ArmorIQ-Assignment.git
    cd ArmorIQ-Assignment
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the server:**
    ```bash
    python server.py
    ```

4.  **Access the API:**
    * **Dashboard (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
    * **Health Check:** [http://localhost:8000/](http://localhost:8000/)

---

## 📖 API Documentation

Once the server is running, visit **`/docs`** for the interactive dashboard.

### Key Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/accounts/` | Create a new account |
| `GET` | `/accounts/{id}` | Check account balance |
| `POST` | `/transfer` | **Securely transfer funds** between accounts |
| `GET` | `/policies` | **Search bank rules** (e.g., `?query=overdraft`) |
| `GET` | `/accounts/{id}/history` | View transaction logs |

---

## ☁️ Deployment (Render.com)

This project is configured for seamless deployment on **Render** using Docker.

1.  Ensure `Dockerfile` and `requirements.txt` are in the root directory.
2.  Push your code to GitHub.
3.  Create a **New Web Service** on Render and connect your repository.
4.  Render will automatically detect the Docker configuration and deploy.

### ⚠️ Engineering Note: Data Persistence
> **Important limitation regarding the Render Free Tier:**
>
> This application uses **SQLite** (`bank.db`) for simplicity and portability. On the Render Free Tier, the file system is **ephemeral**. This means that whenever the application is redeployed or restarts (after a period of inactivity), **the database file will be reset**, and all created accounts/transactions will be lost.
>
> **Production Recommendation:** For a production-grade deployment, I would replace the SQLite connection with a managed **PostgreSQL** database (e.g., via `psycopg2` or SQLAlchemy) to ensure persistent storage independent of the application lifecycle.

---

## 📂 Project Structure

```text
.
├── server.py           # Main application logic & endpoints
├── bank.db             # Local SQLite database (auto-generated)
├── requirements.txt    # Python dependencies
├── Dockerfile          # Cloud deployment configuration
└── README.md           # Project documentation
