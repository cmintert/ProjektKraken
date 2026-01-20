"""Script to clean up duplicate relations in the database."""

import sqlite3


def clean_duplicates():
    conn = sqlite3.connect("worlds/Default World/Default World.kraken")
    cursor = conn.cursor()

    # Find all duplicate groups
    cursor.execute(
        """
        SELECT source_id, target_id, rel_type, GROUP_CONCAT(id) as ids, COUNT(*) as count
        FROM relations
        GROUP BY source_id, target_id, rel_type
        HAVING count > 1
    """
    )

    duplicates = cursor.fetchall()
    print(f"Found {len(duplicates)} duplicate relation groups")

    total_deleted = 0
    for source_id, target_id, rel_type, ids_str, count in duplicates:
        # Keep the first ID, delete the rest
        ids = ids_str.split(",")
        keep_id = ids[0]
        delete_ids = ids[1:]

        print(
            f"Keeping {keep_id}, deleting {len(delete_ids)} duplicates for {rel_type}: {source_id[:12]}... -> {target_id[:12]}..."
        )

        for delete_id in delete_ids:
            cursor.execute("DELETE FROM relations WHERE id = ?", (delete_id,))
            total_deleted += 1

    conn.commit()

    # Verify
    cursor.execute(
        """
        SELECT COUNT(*) 
        FROM (
            SELECT source_id, target_id, rel_type, COUNT(*) as count
            FROM relations
            GROUP BY source_id, target_id, rel_type
            HAVING count > 1
        )
    """
    )
    remaining_dupes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM relations")
    total_relations = cursor.fetchone()[0]

    print(f"\nDeleted {total_deleted} duplicate relations")
    print(f"Total relations remaining: {total_relations}")
    print(f"Duplicate groups remaining: {remaining_dupes}")

    conn.close()


if __name__ == "__main__":
    clean_duplicates()
