#!/bin/bash
# MLF Presentation Build Pipeline
# Usage: ./build.sh
set -e
cd /home/claude

echo "═══════════════════════════════════════"
echo "  MLF BUILD PIPELINE"
echo "═══════════════════════════════════════"

echo ""
echo "1. Generating HTML..."
python3 gen.py

echo ""
echo "2. Running layout simulation..."
python3 simulate.py
SIM_EXIT=$?

echo ""
echo "3. Running order & dependency check..."
python3 order_check.py
ORDER_EXIT=$?

echo ""
echo "4. Running comprehensive audit..."
python3 audit.py
AUDIT_EXIT=$?

echo ""
if [ $SIM_EXIT -eq 0 ] && [ $ORDER_EXIT -eq 0 ] && [ $AUDIT_EXIT -eq 0 ]; then
  echo "✓ All checks passed — deploying..."
  cp mlf-final.html /mnt/user-data/outputs/mlf-presentation.html
  cp gen.py /mnt/user-data/outputs/gen.py
  cp simulate.py /mnt/user-data/outputs/simulate.py
  cp audit.py /mnt/user-data/outputs/audit.py
  echo "✓ Deployed to outputs/"
else
  echo "✗ Checks failed — NOT deploying. Fix issues above first."
  exit 1
fi
