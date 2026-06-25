# add-doctors

Seed the three founding doctors into the NeoCortex SQLite database.

## What this skill does

Runs `scripts/seed_doctors.py` from the project root, which:
1. Creates the `doctors` table if it does not exist.
2. Inserts Dr. Sarah Levi (Neurology), Dr. Alex Goren (Internal Medicine), and Dr. Dana Cohen (Cardiology) — skipping any that are already present.
3. Prints a confirmation table of every doctor now in the database.

## Steps

1. Run the seed script:
   ```
   python scripts/seed_doctors.py
   ```
2. Confirm the output lists all three doctors with their IDs, specialties, and emails.
3. If any doctor is reported as skipped, verify the existing record is correct and report back.
