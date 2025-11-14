# Quick Start Guide - Database Metadata Population

## 🎯 Goal
Populate your PostgreSQL database with case and document metadata from the Excel file.

---

## ⚡ Quick Commands

### Step 1: Copy Script to Your Project
```bash
# 🔹 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley

# Create directory if it doesn't exist
mkdir -p scripts/phase1

# Copy the script (download it from Claude first)
# Then move it to the correct location
mv ~/Downloads/populate_metadata.py scripts/phase1/
```

### Step 2: Run Test Mode (First Time)
```bash
# 🔹 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
source venv/bin/activate
python scripts/phase1/populate_metadata.py
```

**Expected output**: Processes 15 rows, shows validation results

### Step 3: Verify Test Results
```bash
# Check the log file
cat logs/metadata_population.log

# Or run a quick SQL check
psql -U your_username -d climate_litigation -c "SELECT COUNT(*) FROM cases;"
psql -U your_username -d climate_litigation -c "SELECT COUNT(*) FROM documents;"
```

**Expected counts**: 15 cases, 15 documents

### Step 4: Run Full Population
```bash
# Edit the script to disable test mode
nano scripts/phase1/populate_metadata.py

# Find line ~68 and change:
# TEST_MODE = False  # Changed from True

# Save and exit (Ctrl+X, Y, Enter)

# Run again
python scripts/phase1/populate_metadata.py
```

**Expected output**: Processes all 2,924 rows

---

## ✅ Success Checklist

After running the script, you should see:

- [ ] **Console shows**: "Success rate: 100.0%"
- [ ] **Cases created**: ~2,924 (or fewer if some updated)
- [ ] **Documents created**: ~2,924 (or fewer if some updated)
- [ ] **Errors**: 0 (or very few)
- [ ] **Validation shows**: No missing required fields
- [ ] **Sample records**: Look correct and complete

---

## 🔍 Quick Validation (PostgreSQL)

```sql
-- Connect to database
psql -U your_username -d climate_litigation

-- Check counts
SELECT COUNT(*) FROM cases;
-- Expected: ~2,924

SELECT COUNT(*) FROM documents;
-- Expected: ~2,924

-- Check region distribution
SELECT region, COUNT(*) 
FROM cases 
GROUP BY region;
-- Expected: Mostly "Global North", some "Global South"

-- Check sample case
SELECT case_name, court_name, country, region, case_status 
FROM cases 
LIMIT 3;
-- Expected: Full, readable data

-- Check document URLs
SELECT COUNT(*) 
FROM documents 
WHERE document_url IS NOT NULL;
-- Expected: ~2,920+ (very high percentage)

-- Exit
\q
```

---

## 🚨 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| "File not found" | Run from `/home/gusrodgs/Gus/cienciaDeDados/phdMutley` |
| "Cannot import models" | Check `scripts/phase0/init_database_pg18.py` exists |
| "Database connection failed" | Check PostgreSQL is running: `sudo systemctl status postgresql` |
| "Permission denied" | Check file permissions: `chmod +x scripts/phase1/populate_metadata.py` |
| Many errors in output | Check `logs/metadata_population.log` for details |

---

## 📊 What You Get

After successful run:

```
✅ Cases Table
   - 2,924 cases with full metadata
   - Case names, numbers, courts, locations
   - Filing dates, decision dates, status
   - Rich JSON metadata (summaries, categories, laws)

✅ Documents Table
   - 2,924 documents linked to cases
   - Document types, URLs
   - Ready for PDF download
   - pdf_downloaded = false (not yet downloaded)

✅ Ready for Next Phase
   - Text extraction script can now run
   - All metadata relationships established
   - UUIDs are deterministic and consistent
```

---

## 🔄 What's Next?

After successful metadata population:

1. **Verify your existing extraction test**: Re-run your 8-PDF test to see if metadata is now complete
2. **Plan full extraction**: Your `extract_text.py` should now populate all fields correctly
3. **Consider PDF download**: You may need to download remaining PDFs first

---

## 💡 Pro Tips

- **Always test first**: The TEST_MODE exists for a reason
- **Check logs**: `logs/metadata_population.log` has detailed information
- **Safe to re-run**: The script won't duplicate data
- **Preserve PDFs**: If you already extracted some PDFs, those records won't be overwritten
- **Version control**: Commit after successful population: `git commit -am "Populated database metadata"`

---

## 🎓 For Your Thesis

This script is methodologically important because:
- **Reproducible**: Same input always produces same output (deterministic UUIDs)
- **Documented**: Every decision is logged
- **Transparent**: All field mappings are explicit
- **Auditable**: Can verify any record against source Excel
- **Separation of concerns**: Metadata loading ≠ text extraction

Document this as **Phase 1, Step 1: Database Population** in your methodology section.

---

## Time Estimate

- **Test run**: 5 seconds
- **Verification**: 2 minutes
- **Full run**: 3-5 minutes
- **Total**: ~10 minutes to complete

---

**Ready to start? Run Step 1 above!** 🚀
