#!/bin/bash
# One-command deployment helper
#
# Assumes the one-time Railway project setup in DEPLOY.md is already done
# (api/frontend/Postgres/Redis/Qdrant services exist, env vars are set).
# This script just builds and ships new code to the two services this repo
# owns — it can't create plugins or set variables for you.
#
# Requires: `railway login` access to the project (this script logs you in
# interactively) and `railway link` will ask you to pick the right project
# the first time you run it. For non-interactive deploys (CI), use
# .github/workflows/deploy.yml with a RAILWAY_TOKEN instead — `railway
# login` opens a browser and will just hang in a CI runner.

set -euo pipefail

echo "🚀 Career OS — Production Deployment"
echo "======================================"
echo ""

echo "Step 1: Installing Railway CLI..."
if command -v railway >/dev/null 2>&1; then
  echo "Already installed ($(railway --version))."
else
  npm install -g @railway/cli
fi
echo ""

echo "Step 2: Login to Railway..."
railway login
echo ""

echo "Step 3: Linking to your Railway project..."
railway link
echo ""

echo "Step 4: Deploying backend API..."
railway up --service api
echo ""

echo "Step 5: Deploying frontend..."
railway up --service frontend
echo ""

echo "✅ Deployment complete!"
echo "Your app is live at: $(railway domain --service frontend 2>/dev/null || echo '(run `railway domain` to generate one if this is empty)')"
