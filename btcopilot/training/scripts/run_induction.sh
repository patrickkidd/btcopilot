#!/usr/bin/env bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Change to project root
cd "$(dirname "$0")/../../../.."

echo ""
echo -e "${BLUE}🚀 Starting Automated Prompt Induction${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. Export GT
echo -e "${BLUE}📊 Step 1/4: Exporting ground truth...${NC}"
uv run python -m btcopilot.training.export_gt

if [ ! -f "instance/gt_export.json" ]; then
    echo -e "${RED}❌ GT export failed - instance/gt_export.json not found${NC}"
    exit 1
fi

GT_COUNT=$(python3 -c "import json; print(len(json.load(open('instance/gt_export.json'))))")
echo -e "${GREEN}✅ Exported $GT_COUNT GT cases${NC}"
echo ""

# 2. Create checkpoint
echo -e "${BLUE}💾 Step 2/4: Creating checkpoint...${NC}"

# Stage current prompts.py if it has changes
if git diff --quiet btcopilot/btcopilot/personal/prompts.py 2>/dev/null; then
    echo "No uncommitted changes in prompts.py"
else
    echo "Uncommitted changes detected - creating stash"
    git stash push -m "Pre-induction checkpoint ($(date +%Y-%m-%d_%H-%M-%S))" btcopilot/btcopilot/personal/prompts.py 2>/dev/null || true
fi

CHECKPOINT_SHA=$(git rev-parse --short HEAD)
echo -e "${GREEN}✅ Checkpoint: $CHECKPOINT_SHA${NC}"
echo ""

# 3. Run Claude Code agent
echo -e "${BLUE}🤖 Step 3/4: Running Claude Code induction agent...${NC}"
echo -e "${YELLOW}This will take 5-15 minutes depending on dataset size${NC}"
echo ""
echo "The agent will:"
echo "  • Analyze error patterns in GT cases"
echo "  • Propose targeted prompt improvements"
echo "  • Test each change iteratively"
echo "  • Generate detailed report"
echo ""
echo -e "${YELLOW}Starting Claude Code...${NC}"
echo ""

# Run Claude Code with the meta-prompt
# Use env var to avoid shell quote interpretation issues with complex markdown
# --dangerously-skip-permissions allows autonomous file edits without prompts
PROMPT=$(cat btcopilot/btcopilot/training/prompts/induction_agent.md)
claude -p --dangerously-skip-permissions "$PROMPT"

# 4. Check results
echo ""
echo -e "${BLUE}📋 Step 4/4: Checking results...${NC}"

if [ ! -f "instance/induction_report.md" ]; then
    echo ""
    echo -e "${RED}❌ No report generated - something went wrong${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  • Check if Claude Code completed successfully"
    echo "  • Look for error messages above"
    echo "  • Verify instance/gt_export.json is valid"
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ Induction complete!${NC}"
echo ""

# Extract and display key results from report
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}📊 Results Summary:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
grep "| Aggregate F1" instance/induction_report.md | head -1 || echo "Results table not found in report"
echo ""

# Check if there are uncommitted changes
if git diff --quiet btcopilot/btcopilot/personal/prompts.py; then
    echo -e "${YELLOW}⚠️  No changes made to prompts.py${NC}"
    echo "   The agent may have determined current prompts are optimal"
else
    echo -e "${GREEN}✅ Changes made to prompts.py${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}📄 Generated Files:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  • Full report: instance/induction_report.md"
echo "  • Changes: git diff btcopilot/btcopilot/personal/prompts.py"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}🎯 Next Steps:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Review the report:"
echo "   ${YELLOW}cat instance/induction_report.md${NC}"
echo ""
echo "2. Review the changes:"
echo "   ${YELLOW}git diff btcopilot/btcopilot/personal/prompts.py${NC}"
echo ""
echo "3a. If improved, commit:"
echo "    ${GREEN}git add btcopilot/btcopilot/personal/prompts.py instance/induction_report.md${NC}"
echo "    ${GREEN}git commit -m 'Automated prompt induction (F1: X.XX → Y.YY)'${NC}"
echo ""
echo "3b. If not improved, revert:"
echo "    ${RED}git checkout btcopilot/btcopilot/personal/prompts.py${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
