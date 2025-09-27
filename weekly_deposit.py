import pandas as pd
from datetime import datetime

CSV = "Scripts and CSV Files/chatgpt_portfolio_update.csv"
df = pd.read_csv(CSV)
today = pd.to_datetime(datetime.today().date()).strftime("%Y-%m-%d")

# Ensure today's CASH and TOTAL rows exist
cols = ["Date","Ticker","Shares","Buy Price","Cost Basis","Stop Loss","Action",
        "Current Price","Total Value","PnL","Cash Balance","Total Equity"]

def ensure_row(ticker):
    mask = (df["Date"] == today) & (df["Ticker"] == ticker)
    if not mask.any():
        new = {c:"" for c in cols}
        new.update({"Date":today,"Ticker":ticker})
        df.loc[len(df)] = new

ensure_row("CASH")
ensure_row("TOTAL")

# +£10 to today's CASH and TOTAL Cash Balance
for t in ["CASH","TOTAL"]:
    m = (df["Date"]==today) & (df["Ticker"]==t)
    df.loc[m,"Cash Balance"] = pd.to_numeric(df.loc[m,"Cash Balance"], errors="coerce").fillna(0) + 10

df.to_csv(CSV, index=False)
print(f"💷 Added £10 on {today}")