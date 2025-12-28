import sqlite3
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import uvicorn

DB_NAME = "bank.db"

# --- 1. RAG / Policy Knowledge Base ---
# Simulated secure policy handbook
BANK_POLICIES = {
    "withdrawal_limit": "Daily withdrawal limit is $500 for Basic accounts and $2,000 for Premium accounts.",
    "overdraft_fees": "Overdraft fee is $35 per transaction. Interest is charged at 15% APR on negative balances.",
    "international_transfer": "International transfers cost $25 fixed fee plus 1% currency conversion margin. Takes 3-5 business days.",
    "fraud_protection": "We monitor all transactions. If you suspect fraud, use the 'freeze_account' tool immediately. Liability is $0 if reported within 24 hours.",
    "support_hours": "Live support is available 9 AM - 5 PM EST, Monday to Friday. Automated support is 24/7."
}

# --- 2. Database Helpers ---
def init_db():
    """Initialize the database with tables for accounts and transactions."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                balance REAL DEFAULT 0.0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                type TEXT,
                amount REAL,
                timestamp TEXT,
                FOREIGN KEY(account_id) REFERENCES accounts(id)
            )
        """)
        conn.commit()

def log_transaction(cursor, account_id, trans_type, amount):
    """Helper to log transactions within an existing cursor context."""
    cursor.execute(
        "INSERT INTO transactions (account_id, type, amount, timestamp) VALUES (?, ?, ?, ?)",
        (account_id, trans_type, amount, datetime.now().isoformat())
    )

# --- 3. Pydantic Models ---
class AccountCreate(BaseModel):
    name: str
    initial_deposit: float = 0.0

class TransactionRequest(BaseModel):
    amount: float

class TransferRequest(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: float

# --- 4. FastAPI App Setup ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan, title="Banking API Service (with RAG)")

# --- 5. API Endpoints ---

@app.get("/")
def health_check():
    return {"status": "running", "docs_url": "http://localhost:8000/docs"}

# --- Account Management ---

@app.post("/accounts/")
def create_account(account: AccountCreate):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO accounts (name, balance) VALUES (?, ?)", 
                       (account.name, account.initial_deposit))
        account_id = cursor.lastrowid
        
        if account.initial_deposit > 0:
            log_transaction(cursor, account_id, "DEPOSIT", account.initial_deposit)
            
        conn.commit()
    return {"message": "Account created successfully", "account_id": account_id}

@app.get("/accounts/{account_id}")
def get_balance(account_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, balance FROM accounts WHERE id = ?", (account_id,))
        result = cursor.fetchone()
        
    if not result:
        raise HTTPException(status_code=404, detail="Account not found")
        
    return {"account": result[0], "balance": result[1]}

# --- Basic Transactions ---

@app.post("/accounts/{account_id}/deposit")
def deposit(account_id: int, request: TransactionRequest):
    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive.")

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Account not found")
        
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (request.amount, account_id))
        log_transaction(cursor, account_id, "DEPOSIT", request.amount)
        conn.commit()
        
    return {"message": "Deposit successful"}

@app.post("/accounts/{account_id}/withdraw")
def withdraw(account_id: int, request: TransactionRequest):
    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive.")

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Account not found.")
        
        current_balance = result[0]
        if current_balance < request.amount:
            raise HTTPException(status_code=400, detail="Insufficient funds.")
        
        cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (request.amount, account_id))
        log_transaction(cursor, account_id, "WITHDRAWAL", request.amount)
        conn.commit()

    return {"message": "Withdrawal successful"}

# --- NEW FEATURE: Secure Fund Transfer ---

@app.post("/transfer")
def transfer_funds(request: TransferRequest):
    print(f"--- 🟢 Received Transfer Request: ${request.amount} from Acc {request.from_account_id} ---")
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        try:
            # 1. Check Sender
            cursor.execute("SELECT balance FROM accounts WHERE id = ?", (request.from_account_id,))
            sender = cursor.fetchone()
            
            if not sender:
                print("❌ Sender not found")
                raise HTTPException(status_code=404, detail="Sender account not found.")
            
            current_balance = sender[0]
            print(f"   💰 Current Balance: ${current_balance}")
            
            if current_balance < request.amount:
                print(f"   ❌ Insufficient Funds! (Has {current_balance}, needs {request.amount})")
                raise HTTPException(status_code=400, detail="Insufficient funds.")

            # 2. Execute Transfer
            print("   ✅ Funds Sufficient. Executing Transfer...")
            cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (request.amount, request.from_account_id))
            cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (request.amount, request.to_account_id))
            
            # Log
            log_transaction(cursor, request.from_account_id, "TRANSFER_OUT", request.amount)
            log_transaction(cursor, request.to_account_id, "TRANSFER_IN", request.amount)
            
            conn.commit()
            print("   💾 Transaction Committed Successfully.")
            
        except HTTPException as he:
            conn.rollback()
            print("   ↩️ Rolled Back due to Error.")
            raise he
        except Exception as e:
            conn.rollback()
            print(f"   ⚠️ Unexpected Error: {e}")
            raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")

    return {"message": "Transfer Successful"}

# --- NEW FEATURE: Policy Knowledge Base (RAG) ---

@app.get("/policies")
def consult_bank_policy(query: str = Query(..., description="Topic to search for (e.g., 'fees', 'limit')")):
    """
    Search the official Bank Policy Handbook.
    """
    query = query.lower()
    results = []
    
    for topic, content in BANK_POLICIES.items():
        if query in topic.replace("_", " ") or query in content.lower():
            results.append({"topic": topic.upper(), "content": content})
            
    if not results:
        return {"message": "No specific policy found.", "results": []}
        
    return {"message": "Policy found", "results": results}

@app.get("/accounts/{account_id}/history")
def get_transaction_history(account_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT type, amount, timestamp FROM transactions WHERE account_id = ? ORDER BY id DESC LIMIT 10", (account_id,))
        rows = cursor.fetchall()
        
    formatted_history = [
        {"type": row[0], "amount": row[1], "timestamp": row[2]} 
        for row in rows
    ]
    return {"history": formatted_history}

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)