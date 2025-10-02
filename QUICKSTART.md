# DCAMOON Quick Start Guide

Get your trading system up and running in 5 minutes.

---

## 1. Initial Setup (One-Time)

### Copy Environment Template
```bash
cd /Users/clive/Desktop/DCA/DCAMOON
cp .env.example .env
```

### Edit Your Configuration
Open `.env` in a text editor and set:

```bash
# REQUIRED: Your OpenAI API key
OPENAI_API_KEY=sk-your-actual-key-here

# OPTIONAL: Everything else has sensible defaults
# But you may want to customize:
DCAMOON_PORTFOLIO_ID=       # Leave blank to auto-detect
DATABASE_URL=sqlite:///dcamoon.db
FLASK_DEBUG=false            # NEVER set to true in production
```

### Generate Secure Keys (Recommended)
```bash
# Generate Flask secret key
python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))" >> .env

# Optional: Generate encryption key (auto-created if not set)
python -c "from cryptography.fernet import Fernet; print('DCAMOON_MASTER_KEY=' + Fernet.generate_key().decode())" >> .env
```

---

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 3. Initialize Database

```bash
# The database will auto-initialize on first run
# Or manually initialize:
python -c "from database.database import initialize_database; initialize_database()"
```

---

## 4. Run the Application

### Option A: Main Dashboard (Port 5001)
```bash
python app.py
```

Then open: http://localhost:5001

### Option B: Autonomous Trading (Port 5004)
```bash
python simple_app.py
```

Then open: http://localhost:5004

### Option C: Automated Trading (CLI)
```bash
# Dry run (simulation only)
python simple_automation.py --dry-run

# Real trades (CAUTION!)
python simple_automation.py --execute-real-trades
```

---

## 5. Verify Installation

### Check Startup Messages
You should see:
```
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║                   DCAMOON Dashboard                       ║
║               Trading System v1.0.0                       ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

Environment: production
Database: sqlite:///dcamoon.db
Log Level: INFO

Starting up...
✓ Startup validation complete
✓ Server starting on http://0.0.0.0:5001
```

### Check for Errors
If you see errors, they will be clear and specific:
- Missing API key → Set `OPENAI_API_KEY` in `.env`
- Database issues → Check `DATABASE_URL` and permissions
- Configuration errors → Review the error message for guidance

---

## Common Issues & Solutions

### Issue: "Missing required environment variables: OPENAI_API_KEY"
**Solution:** Add your OpenAI API key to `.env`:
```bash
OPENAI_API_KEY=sk-your-actual-key-here
```

### Issue: "Portfolio not found"
**Solution:** Set your portfolio ID in `.env`:
```bash
# Find your portfolio ID from the database or logs
DCAMOON_PORTFOLIO_ID=c49d9e6f-a4c2-4524-81d1-96a8e5672d52
```

### Issue: Database errors
**Solution:** Check database file permissions:
```bash
# For SQLite
ls -la dcamoon.db
chmod 644 dcamoon.db
```

### Issue: "Insufficient permissions for ~/.dcamoon"
**Solution:** Fix directory permissions:
```bash
chmod 700 ~/.dcamoon
chmod 600 ~/.dcamoon/*.key
```

---

## Configuration Tips

### Minimal Configuration (Just to Test)
```bash
# .env file with minimal settings
OPENAI_API_KEY=sk-your-key-here
DATABASE_URL=sqlite:///dcamoon.db
FLASK_DEBUG=false
SECRET_KEY=change-this-to-a-random-string
```

### Recommended Configuration (For Regular Use)
```bash
# .env file with recommended settings
OPENAI_API_KEY=sk-your-key-here
DATABASE_URL=sqlite:///dcamoon.db
DCAMOON_PORTFOLIO_ID=your-portfolio-uuid
FLASK_DEBUG=false
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">

# Trading settings
MAX_POSITION_SIZE=0.10  # 10% max position
STOP_LOSS_PCT=0.20      # 20% stop loss

# Logging
LOG_LEVEL=INFO
```

---

## Security Checklist

Before running in production:

- [ ] `FLASK_DEBUG=false` ✅
- [ ] Strong `SECRET_KEY` generated ✅
- [ ] Real `OPENAI_API_KEY` (not placeholder) ✅
- [ ] Database file has appropriate permissions ✅
- [ ] `.env` file not committed to version control ✅
- [ ] `~/.dcamoon/` directory backed up ✅

---

## Daily Usage

### Start the Dashboard
```bash
python app.py
```

### View Portfolio
Navigate to: http://localhost:5001/api/portfolio

### Execute Manual Trade
```bash
curl -X POST http://localhost:5001/api/execute-trade \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "trade_type": "BUY",
    "shares": 10,
    "price": 150.00,
    "reason": "Manual purchase"
  }'
```

### Run Automated Analysis (Dry Run)
```bash
python simple_automation.py --dry-run
```

---

## Backup & Recovery

### Backup Your Data
```bash
# Backup database
cp dcamoon.db dcamoon.db.backup

# Backup encryption keys
cp -r ~/.dcamoon ~/.dcamoon.backup

# Backup CSV files (if used)
tar -czf data-backup.tar.gz "Scripts and CSV Files/"
```

### Restore from Backup
```bash
# Restore database
cp dcamoon.db.backup dcamoon.db

# Restore encryption keys
cp -r ~/.dcamoon.backup ~/.dcamoon
```

---

## Next Steps

1. ✅ **Review** [IMPROVEMENTS_SUMMARY.md](IMPROVEMENTS_SUMMARY.md) for all features
2. ✅ **Configure** trading parameters in `.env`
3. ✅ **Test** with dry-run mode first
4. ✅ **Monitor** logs for any issues
5. ✅ **Backup** your data regularly

---

## Getting Help

### Check Logs
The application outputs detailed logs to the console. Watch for:
- `ERROR` - Something went wrong
- `WARNING` - Potential issue
- `INFO` - Normal operation
- `DEBUG` - Detailed troubleshooting info

### Review Documentation
- `.env.example` - All configuration options explained
- `IMPROVEMENTS_SUMMARY.md` - Complete feature list
- Code comments - Inline documentation

### Common Commands
```bash
# Check Python version
python --version  # Should be 3.8+

# List installed packages
pip list

# Verify dependencies
pip check

# Run with debug logging
LOG_LEVEL=DEBUG python app.py
```

---

**You're all set! The system is optimized and ready for use. 🚀**
