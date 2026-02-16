# Speed Friending App - Deployment Guide

## Local Development

### Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start server
uvicorn main:app --reload
```

The app will be available at `http://localhost:8000`

## Production Deployment (Railway)

### Prerequisites
- GitHub account (code stored there)
- Railway account (free at railway.app)

### Step 1: Prepare Code
All deployment files are ready:
- ✅ `.env.example` - Template for environment variables
- ✅ `requirements.txt` - Python dependencies
- ✅ `Procfile` - Instructions for Railway
- ✅ `railway.json` - Railway configuration
- ✅ `.gitignore` - Prevent secrets from leaking

### Step 2: Deploy to Railway

1. **Sign up** at https://railway.app (free)

2. **Connect GitHub**:
   - Click "New Project"
   - Select "Deploy from GitHub"
   - Authorize Railway to access your GitHub

3. **Create application**:
   - Select your `speedfriending_app` repository
   - Railway auto-detects it's a Python app

4. **Add PostgreSQL**:
   - Click "+ Add Service"
   - Select "PostgreSQL"
   - Railway creates `DATABASE_URL` automatically

5. **Configure Environment Variables**:
   - Click on your app → "Variables"
   - Add these variables:
     ```
     ENVIRONMENT=production
     SECRET_KEY=[generate-strong-key]
     BREAK_DURATION_SECONDS=60
     ```
   
   To generate a strong SECRET_KEY:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

6. **Deploy**:
   - Railway auto-deploys when you push to GitHub
   - Check the "Logs" tab for deployment status
   - Your app will be live at `https://speedfriending-xxxx.railway.app`

### Step 3: Verify Deployment

```bash
# Test API endpoints
curl https://speedfriending-xxxx.railway.app/
curl https://speedfriending-xxxx.railway.app/docs

# Check database connection
# (If you see "Event not found" errors, DB is connected)
```

### Step 4: Database Setup

Database tables are created automatically:
- On first app startup, SQLModel creates all tables
- PostgreSQL is initialized from migrations

### Custom Domain (Optional)

1. Buy domain (Namecheap, GoDaddy, etc.)
2. In Railway dashboard:
   - Click app → Deployments
   - Go to "Settings" → "Domains"
   - Add your custom domain
   - Update DNS records (Railway shows instructions)

## Troubleshooting

### Error: "DATABASE_URL not set"
- Add `DATABASE_URL` in Railway variables
- Railway PostgreSQL creates it automatically

### Error: "SECRET_KEY must be set in production"
- Set `SECRET_KEY` environment variable in Railway
- Generate one: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

### Database Connection Failed
- Ensure PostgreSQL service is running
- Check `DATABASE_URL` format: `postgresql://user:password@host:port/db`
- Verify firewall allows connections

### App Won't Deploy
- Check "Logs" in Railway dashboard
- Ensure Python 3.8+ is available
- Verify all dependencies in `requirements.txt`

## Environment Variables Reference

| Variable | Required | Example | Notes |
|----------|----------|---------|-------|
| `ENVIRONMENT` | Yes | `production` | Set to `development` locally |
| `DATABASE_URL` | Yes | `postgresql://...` | Auto-set by Railway PostgreSQL |
| `SECRET_KEY` | Yes | Long random string | Generate with secrets module |
| `BREAK_DURATION_SECONDS` | No | `60` | Break time between rounds |
| `ALLOWED_HOSTS` | No | `localhost,127.0.0.1` | Comma-separated list |

## Deployment Checklist

- [ ] Create `.env` file with secrets (never commit)
- [ ] Add `.env` to `.gitignore` ✓
- [ ] Install all dependencies: `pip install -r requirements.txt` ✓
- [ ] Test locally: `uvicorn main:app --reload`
- [ ] Push to GitHub
- [ ] Create Railway account
- [ ] Connect GitHub to Railway
- [ ] Add PostgreSQL service
- [ ] Set environment variables
- [ ] Deploy and verify endpoints work
- [ ] Test event creation → participant join → pairing workflow

## Support

For issues:
1. Check Railway logs: Dashboard → Deployments
2. Verify environment variables are set
3. Ensure database is running
4. Check that all endpoints respond at `/docs`
