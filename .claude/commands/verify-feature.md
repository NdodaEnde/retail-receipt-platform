Verify a feature works before committing. This is MANDATORY before any git push.

Usage: /verify-feature [description of what to test]

## Verification Steps (ALL required)

### 1. Backend API Check
- Start backend locally if not running: `cd backend && uvicorn server:app --reload --port 8000`
- Hit the relevant endpoint(s) with `curl` and verify the response is correct
- Check for error logs in the terminal

### 2. Frontend Render Check
- If frontend changes were made, verify the dev server compiles without errors
- Check that new imports resolve (e.g., icons exist in lucide-react, components exist)
- If Recharts/charts are involved, verify data flows through: API → state → chart props

### 3. Data Format Check
- Verify phone number format matches what's in the DB (with/without + prefix)
- Verify numeric fields parse correctly (string vs number from PostgreSQL)
- Test with real data, not just empty states

### 4. Edge Cases
- Test with the user's phone number: 0769695462 (should normalize to 27769695462)
- Test empty states (no receipts, new customer)
- Test with invalid input (empty phone, garbage text)

## Only after ALL steps pass:
- Stage specific files (never `git add -A`)
- Commit with descriptive message
- Push to remote

## If verification fails:
- Fix the issue
- Re-verify from step 1
- Do NOT push broken code hoping to fix it in the next commit
