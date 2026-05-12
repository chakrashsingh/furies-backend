#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Furies Platform — Mac Setup Script
# Run this once from inside the furies folder:
#   chmod +x setup.sh
#   ./setup.sh
# ─────────────────────────────────────────────────────────────

set -e
echo ""
echo "🔥 Setting up Furies Platform..."
echo ""

# ── 1. Python check ───────────────────────────────────────────
if ! command -v python3.11 &>/dev/null; then
  echo "📦 Installing Python 3.11..."
  brew install python@3.11
else
  echo "✅ Python 3.11 found"
fi

# ── 2. PostgreSQL check ───────────────────────────────────────
if ! command -v psql &>/dev/null; then
  echo "📦 Installing PostgreSQL 15..."
  brew install postgresql@15
  echo 'export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"' >> ~/.zshrc
  export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"
else
  echo "✅ PostgreSQL found"
fi

# ── 3. Start PostgreSQL ───────────────────────────────────────
echo "▶️  Starting PostgreSQL..."
brew services start postgresql@15
sleep 2

# ── 4. Create database ────────────────────────────────────────
echo "🗄️  Creating database..."
psql postgres -c "CREATE USER furies_user WITH PASSWORD 'furies2025';" 2>/dev/null || echo "   (user already exists)"
psql postgres -c "CREATE DATABASE furies_db OWNER furies_user;" 2>/dev/null || echo "   (database already exists)"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE furies_db TO furies_user;" 2>/dev/null

# ── 5. Virtual environment ────────────────────────────────────
echo "🐍 Creating virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

# ── 6. Install packages ───────────────────────────────────────
echo "📦 Installing packages..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ── 7. Create .env ────────────────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  sed -i '' "s/replace_this_with_generated_key/$SECRET/" .env
  echo "✅ .env file created with secure secret key"
else
  echo "✅ .env already exists"
fi

# ── 8. Run migrations ─────────────────────────────────────────
echo "🔄 Running database migrations..."
alembic revision --autogenerate -m "initial_schema" 2>/dev/null || true
alembic upgrade head

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start Furies, run:"
echo "   source venv/bin/activate"
echo "   uvicorn main:app --reload --port 8000"
echo ""
echo "Then open: http://localhost:8000/docs"
