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

# Display focus info if set
if [ -n "$INDUCTION_FOCUS" ]; then
    echo -e "${GREEN}Focus: $INDUCTION_FOCUS${NC}"
    echo -e "  Metric: $INDUCTION_FOCUS_METRIC"
    echo ""
fi

echo "The agent will:"
echo "  • Analyze error patterns in GT cases"
if [ -n "$INDUCTION_FOCUS" ]; then
    echo "  • Prioritize $INDUCTION_FOCUS improvements"
fi
echo "  • Propose targeted prompt improvements"
echo "  • Test each change iteratively"
echo "  • Generate detailed report and log file"
echo ""
echo -e "${YELLOW}Starting Claude Code...${NC}"
echo ""

# Build the prompt with focus context if provided
PROMPT=$(cat btcopilot/btcopilot/training/prompts/induction_agent.md)

# Build context to prepend to the prompt
CONTEXT=""

if [ -n "$INDUCTION_FOCUS" ]; then
    CONTEXT="${CONTEXT}
## Focus Configuration

- **INDUCTION_FOCUS**: $INDUCTION_FOCUS
- **INDUCTION_FOCUS_METRIC**: $INDUCTION_FOCUS_METRIC
- **INDUCTION_FOCUS_GUIDANCE**: $INDUCTION_FOCUS_GUIDANCE

**IMPORTANT**: Prioritize improving $INDUCTION_FOCUS_METRIC above aggregate F1. Make at least 2-3 iterations targeting this specific area before considering other improvements.

"
fi

if [ -n "$INDUCTION_DISCUSSION_ID" ]; then
    CONTEXT="${CONTEXT}
## Discussion Filter

**INDUCTION_DISCUSSION_ID**: $INDUCTION_DISCUSSION_ID

When running test_prompts_live, ALWAYS include: \`--discussion $INDUCTION_DISCUSSION_ID\`

Example: \`uv run python -m btcopilot.training.test_prompts_live --discussion $INDUCTION_DISCUSSION_ID\`

"
fi

if [ -n "$CONTEXT" ]; then
    PROMPT="${CONTEXT}---

${PROMPT}"
fi

# Run Claude Code with the meta-prompt
# --dangerously-skip-permissions allows autonomous file edits without prompts
#
# Interactive mode: allows user to type steering input during the run.
# The agent reads instance/steering.md at the start of each iteration.
#
# Ctrl+C will cleanly terminate Claude Code.
echo -e "${YELLOW}Interactive mode: You can type to steer the agent.${NC}"
echo -e "${YELLOW}Edit instance/steering.md to provide guidance for subsequent iterations.${NC}"
echo ""

# Write prompt to temp file, then use --prompt-file for interactive mode
# PROMPT_FILE=$(mktemp)
claude --dangerously-skip-permissions "$PROMPT"

# 4. Check results
echo ""
echo -e "${BLUE}📋 Step 4/4: Checking results...${NC}"

# Find the most recent run folder (timestamped, optionally with --focus-* suffix)
REPORT_DIR="btcopilot/induction-reports"
LATEST_FOLDER=$(ls -dt "$REPORT_DIR"/20* 2>/dev/null | head -1)
if [ -n "$LATEST_FOLDER" ]; then
    LATEST_REPORT=$(ls -t "$LATEST_FOLDER"/*.md 2>/dev/null | head -1)
    LATEST_LOG=$(ls -t "$LATEST_FOLDER"/*_log.jsonl 2>/dev/null | head -1)
else
    LATEST_REPORT=""
    LATEST_LOG=""
fi

if [ -z "$LATEST_REPORT" ] && [ -z "$LATEST_LOG" ]; then
    echo ""
    echo -e "${RED}❌ No report or log generated - something went wrong${NC}"
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
if [ -n "$LATEST_REPORT" ]; then
    grep "| Aggregate F1" "$LATEST_REPORT" | head -1 || echo "Results table not found in report"
    if [ -n "$INDUCTION_FOCUS" ]; then
        echo ""
        echo -e "${GREEN}Focused metric ($INDUCTION_FOCUS_METRIC):${NC}"
        grep "| ${INDUCTION_FOCUS_METRIC%_*}" "$LATEST_REPORT" | head -1 || echo "Focused metric not found"
    fi
else
    echo "Report not found - check log file for details"
fi
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
if [ -n "$LATEST_FOLDER" ]; then
    echo "  • Folder: $LATEST_FOLDER"
fi
if [ -n "$LATEST_REPORT" ]; then
    echo "  • Report: $LATEST_REPORT"
fi
if [ -n "$LATEST_LOG" ]; then
    echo "  • Log:    $LATEST_LOG"
fi
echo "  • Changes: git diff btcopilot/btcopilot/personal/prompts.py"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}🎯 Next Steps:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Review the report:"
echo "   ${YELLOW}cat $LATEST_REPORT${NC}"
echo ""
echo "2. Review the changes:"
echo "   ${YELLOW}git diff btcopilot/btcopilot/personal/prompts.py${NC}"
echo ""
echo "3a. If improved, commit:"
echo "    ${GREEN}git add btcopilot/btcopilot/personal/prompts.py btcopilot/induction-reports/${NC}"
echo "    ${GREEN}git commit -m 'Automated prompt induction (F1: X.XX → Y.YY)'${NC}"
echo ""
echo "3b. If not improved, revert:"
echo "    ${RED}git checkout btcopilot/btcopilot/personal/prompts.py${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
