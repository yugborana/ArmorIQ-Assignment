import sqlite3
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import uvicorn
from fastmcp import FastMCP

# --- Configuration ---
DB_NAME = "bank.db"

# --- 1. Database Helpers ---
def init_db():
    """Initialize the database tables."""
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
    """Helper to log transactions (must be called inside an existing transaction)."""
    cursor.execute(
        "INSERT INTO transactions (account_id, type, amount, timestamp) VALUES (?, ?, ?, ?)",
        (account_id, trans_type, amount, datetime.now().isoformat())
    )

# --- 2. Initialize FastMCP ---
# This object holds all our "AI Tools"
mcp = FastMCP("Banking Service")

# --- 3. Define Logic as MCP Tools ---

@mcp.tool()
def create_account_tool(name: str, initial_deposit: float = 0.0) -> dict:
    """Create a new account and return the ID."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO accounts (name, balance) VALUES (?, ?)", (name, initial_deposit))
        account_id = cursor.lastrowid
        if initial_deposit > 0:
            log_transaction(cursor, account_id, "DEPOSIT", initial_deposit)
        conn.commit()
    return {"message": "Account created", "account_id": account_id}

@mcp.tool()
def deposit_tool(account_id: int, amount: float) -> str:
    """Add funds to an account."""
    if amount <= 0:
        raise ValueError("Amount must be positive.")
        
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM accounts WHERE id = ?", (account_id,))
        if not cursor.fetchone():
            raise ValueError("Account not found.")
            
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, account_id))
        log_transaction(cursor, account_id, "DEPOSIT", amount)
        conn.commit()
    return f"Deposited ${amount} successfully."

@mcp.tool()
def withdraw_tool(account_id: int, amount: float) -> str:
    """Deduct funds from an account."""
    if amount <= 0:
        raise ValueError("Amount must be positive.")

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,))
        res = cursor.fetchone()
        if not res:
            raise ValueError("Account not found.")
        if res[0] < amount:
            raise ValueError("Insufficient funds.")
            
        cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, account_id))
        log_transaction(cursor, account_id, "WITHDRAWAL", amount)
        conn.commit()
    return f"Withdrew ${amount} successfully."

@mcp.tool()
def transfer_tool(from_id: int, to_id: int, amount: float) -> str:
    """Securely transfer funds between accounts."""
    if amount <= 0:
        raise ValueError("Amount must be positive.")

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        try:
            # Check Sender
            cursor.execute("SELECT balance FROM accounts WHERE id = ?", (from_id,))
            sender = cursor.fetchone()
            if not sender: raise ValueError("Sender account not found.")
            if sender[0] < amount: raise ValueError("Insufficient funds.")

            # Check Receiver
            cursor.execute("SELECT id FROM accounts WHERE id = ?", (to_id,))
            if not cursor.fetchone(): raise ValueError("Receiver account not found.")

            # Execute
            cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_id))
            cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))
            
            log_transaction(cursor, from_id, "TRANSFER_OUT", amount)
            log_transaction(cursor, to_id, "TRANSFER_IN", amount)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
            
    return f"Transferred ${amount} from {from_id} to {to_id}."

@mcp.tool()
def get_balance_tool(account_id: int) -> dict:
    """Get the current balance."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, balance FROM accounts WHERE id = ?", (account_id,))
        res = cursor.fetchone()
        
    if not res:
        raise ValueError("Account not found.")
    return {"account": res[0], "balance": res[1]}

@mcp.tool()
def get_policy_tool(query: str) -> list:
    """Search the banking policy handbook."""
    policies = {
        "withdrawal_limit": "Daily limit is $500 (Basic) / $2,000 (Premium).",
        "overdraft_fees": "Fee is $35 per transaction.",
        "international": "Cost is $25 + 1% fee. Takes 3-5 days.",
        "fraud": "Liability is $0 if reported in 24h.",
        "support": "Live support 9-5 EST Mon-Fri."
    }
    query = query.lower()
    results = []
    for k, v in policies.items():
        if query in k or query in v.lower():
            results.append({"topic": k.upper(), "content": v})
    return results

# --- 4. FastAPI Setup ---

class AccountCreate(BaseModel):
    name: str
    initial_deposit: float = 0.0

class TransactionRequest(BaseModel):
    amount: float

class TransferRequest(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: float

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan, title="Banking MCP Server")

app.mount("/sse", mcp.http_app())

# --- 5. FastAPI Endpoints ---

@app.get("/")
def home():
    return {"status": "running", "mcp_endpoint": "/sse"}

@app.post("/accounts/")
def create_account(data: AccountCreate):
    # Call the tool logic directly
    return create_account_tool(data.name, data.initial_deposit)

@app.get("/accounts/{account_id}")
def get_balance(account_id: int):
    try:
        return get_balance_tool(account_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/accounts/{account_id}/deposit")
def deposit(account_id: int, data: TransactionRequest):
    try:
        return {"message": deposit_tool(account_id, data.amount)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/accounts/{account_id}/withdraw")
def withdraw(account_id: int, data: TransactionRequest):
    try:
        return {"message": withdraw_tool(account_id, data.amount)}
    except ValueError as e:
        status = 404 if "not found" in str(e) else 400
        raise HTTPException(status_code=status, detail=str(e))

@app.post("/transfer")
def transfer(data: TransferRequest):
    try:
        msg = transfer_tool(data.from_account_id, data.to_account_id, data.amount)
        return {"message": msg}
    except ValueError as e:
        status = 404 if "not found" in str(e) else 400
        raise HTTPException(status_code=status, detail=str(e))

@app.get("/policies")
def search_policy(query: str):
    results = get_policy_tool(query)
    if not results:
        return {"message": "No policy found", "results": []}
    return {"results": results}

if __name__ == "__main__":
    print("🚀 Server running. Web API at port 8000.")

    uvicorn.run(app, host="0.0.0.0", port=8000)
