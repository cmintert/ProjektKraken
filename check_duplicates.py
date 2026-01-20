import sqlite3

conn = sqlite3.connect("worlds/Default World/Default World.kraken")
cursor = conn.cursor()

# Count total relations
cursor.execute("SELECT COUNT(*) FROM relations")
total = cursor.fetchone()[0]
print(f"Total relations: {total}")

# Check for duplicates
cursor.execute(
    """
    SELECT source_id, target_id, rel_type, COUNT(*) as count 
    FROM relations 
    GROUP BY source_id, target_id, rel_type 
    HAVING count > 1
"""
)
duplicates = cursor.fetchall()
print(f"\nDuplicates found: {len(duplicates)}")
for dup in duplicates:
    print(
        f"  Source: {dup[0][:12]}... -> Target: {dup[1][:12]}... Type: {dup[2]} (Count: {dup[3]})"
    )

# Show recent relations
cursor.execute(
    "SELECT id, source_id, target_id, rel_type, created_at FROM relations ORDER BY created_at DESC LIMIT 10"
)
print(f"\nMost recent 10 relations:")
for row in cursor.fetchall():
    print(f"  {row[3]}: {row[1][:12]}... -> {row[2][:12]}...")

conn.close()
