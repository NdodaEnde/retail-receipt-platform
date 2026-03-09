Create a new SQL view for analytics and wire it through the full stack.

Usage: /add-sql-view [view_name] [description]

## Steps (in order, verify each before moving on)

### 1. Design the SQL view
- Write the CREATE OR REPLACE VIEW statement
- Test it mentally against the schema: does it reference existing columns?
- Consider: does it need to filter `WHERE status != 'rejected'`?

### 2. Add to schema.sql
- Add the view definition to `backend/schema.sql` in the appropriate section
- Provide the SQL to the user to run in Supabase SQL Editor
- Wait for user confirmation before proceeding

### 3. Add database.py method
- Add an async method to `Database` class in `backend/database.py`
- Pattern: `self.client.table('view_name').select('*').eq(...)...execute()`
- Remember: views are queried as tables via Supabase client

### 4. Add server.py endpoint
- Add a FastAPI endpoint in `backend/server.py`
- Decide: admin-protected (`Depends(require_admin)`) or public?
- Normalize phone numbers if the endpoint takes a phone parameter

### 5. Verify backend
- Start backend locally: `uvicorn server:app --reload --port 8000`
- `curl` the new endpoint and verify it returns data
- Check the Supabase query in the logs

### 6. Add frontend (if needed)
- Add the API call, state, and UI component
- Use existing patterns from BasketAnalytics.jsx or MySpending.jsx
- If using Recharts: wrap in explicit-height div + ResponsiveContainer

### 7. Update CLAUDE.md
- Add the new view to the "Current views" list in Analytics Architecture section
- Add the new endpoint if customer-facing
