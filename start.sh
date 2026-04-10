#!/bin/bash
set -e

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║          BROadvocacy AI Setup            ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
  echo "❌ Python 3 is required. Install from https://python3.org"
  exit 1
fi

# Create .env if missing
if [ ! -f .env ]; then
  echo "⚙️  First time setup — enter your Anthropic API key."
  echo "   (Get one free at https://console.anthropic.com)"
  echo ""
  read -p "API Key: " key
  echo "ANTHROPIC_API_KEY=$key" > .env
  echo ""
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -q -r backend/requirements.txt

echo ""
echo "✅ Ready! Opening at http://localhost:8000"
echo "   Press Ctrl+C to stop."
echo ""

# Start server
cd "$(dirname "$0")"
python3 backend/main.py
