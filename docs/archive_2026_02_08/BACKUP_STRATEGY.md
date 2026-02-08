# Backup Strategy Guide

## Overview

ProjektKraken includes a comprehensive automated backup system to protect your worldbuilding data. This guide explains how backups work, how to configure them, and how to restore your data when needed.

## Backup Types

The system supports four types of backups:

### 1. Auto-Save Backups
- **Frequency**: Every 5 minutes (configurable)
- **Retention**: Last 12 backups (1 hour of history)
- **Purpose**: Protect against accidental data loss during active editing
- **Location**: `backups/auto/`
- **Naming**: `{database}_autosave_{timestamp}.kraken`

### 2. Daily Backups
- **Frequency**: Once per day
- **Retention**: Last 7 days
- **Purpose**: Daily snapshots for short-term recovery
- **Location**: `backups/daily/`
- **Naming**: `{database}_daily_{date}.kraken`

### 3. Weekly Backups
- **Frequency**: Once per week
- **Retention**: Last 4 weeks
- **Purpose**: Long-term archival and version history
- **Location**: `backups/weekly/`
- **Naming**: `{database}_weekly_{year}_W{week}.kraken`

### 4. Manual Backups
- **Frequency**: On-demand (user-initiated)
- **Retention**: Unlimited (never auto-deleted)
- **Purpose**: Important milestones, before major changes
- **Location**: `backups/manual/`
- **Naming**: `{database}_manual_{timestamp}_{description}.kraken`

## Backup Location

### Default Location

Backups are stored in your application data directory:

- **Windows**: `C:\Users\{username}\AppData\Roaming\ProjektKraken\backups\`
- **macOS**: `~/Library/Application Support/ProjektKraken/backups/`
- **Linux**: `~/.local/share/ProjektKraken/backups/`

### Accessing Backups

To open the backup directory:
1. Open ProjektKraken
2. Go to **File → Backup & Restore → Show Backup Location**
3. Your file explorer will open to the backups folder

## Creating Backups

### Manual Backup

To create a manual backup:

1. Go to **File → Backup & Restore → Create Backup...**
2. (Optional) Enter a description for the backup
3. Click **OK**
4. A confirmation dialog will show the backup location and size

**When to create manual backups:**
- Before making major structural changes
- After completing a significant milestone
- Before experimenting with new features
- When you want a named checkpoint

### Automatic Backups

Auto-save backups run automatically in the background every 5 minutes by default. You'll see a brief status message when a backup is created, but it won't interrupt your work.

**Note**: Daily and weekly backups are planned for future releases.

## Restoring from Backup

### Restore Process

To restore from a backup:

1. Go to **File → Backup & Restore → Restore from Backup...**
2. Select the backup file you want to restore
3. Confirm the restoration (a safety backup of your current database will be created first)
4. The application will close - restart to use the restored database

**Important**: Restoring replaces your current database. Make sure you select the correct backup file!

### Safety Features

- **Pre-restore backup**: Before restoring, the system creates a safety backup of your current database (named `pre_restore_{timestamp}.kraken`)
- **Integrity verification**: All backups are verified before restoration to ensure they're not corrupted
- **Application restart**: The app closes after restoration to ensure a clean state

## Configuration

### Backup Settings

Currently, backup settings use sensible defaults:

- **Auto-save**: Enabled, 5-minute interval, keeps 12 backups
- **Verification**: All backups are verified after creation
- **External backup**: Optional (see below)

Future releases will include a settings dialog to customize these options.

### External Backup Location

For additional safety, you can configure backups to be copied to an external location (like a cloud-synced folder). This is currently done via configuration file but will have a UI in future releases.

## Best Practices

### 1. Verify Backups Periodically

Occasionally test restoring from a backup to ensure the process works:

1. Note your current data state
2. Restore from a recent backup
3. Verify the data is correct
4. Close and restart to return to your current database

### 2. Keep Important Manual Backups Safe

Manual backups are never auto-deleted. Create them at important milestones:

- Project inception
- Major story arcs completed
- Before large refactoring efforts
- Before installing ProjektKraken updates

### 3. Use Cloud Storage for Off-Site Backups

Consider copying important backups to cloud storage:

1. Open the backup location (File → Backup & Restore → Show Backup Location)
2. Copy manual backups to Dropbox, OneDrive, Google Drive, etc.
3. Keep backups of different projects separate

### 4. Monitor Backup Health

Check the backup location occasionally to ensure:

- Backups are being created regularly
- Backup files aren't corrupted (system verifies on creation)
- You have recent backups before making major changes

## Disaster Recovery

### Database Corruption

If your database becomes corrupted:

1. Open ProjektKraken
2. Go to File → Backup & Restore → Restore from Backup...
3. Select the most recent backup before corruption occurred
4. Restart the application

### Accidental Deletion

If you accidentally deleted important data:

1. **Don't save!** The auto-save system may have a backup from before deletion
2. Check auto-save backups (most recent ones)
3. Restore from the backup immediately before the deletion
4. Restart the application

### Complete Data Loss

If your entire database is lost:

1. Check your backup folder for the most recent backup
2. If you enabled external backups, check your cloud storage
3. Restore from the most recent available backup
4. Consider your disaster recovery practices going forward

### Hardware Failure

**Prevention**: 
- Enable external backups to cloud storage
- Regularly copy manual backups to external drives
- Use cloud-synced backup locations (Dropbox folder, etc.)

**Recovery**:
1. Install ProjektKraken on new hardware
2. Copy backups from cloud storage to local machine
3. Use File → Backup & Restore → Restore from Backup...

## Troubleshooting

### Backup Creation Fails

**Symptoms**: Error message when creating backup

**Possible causes**:
- Insufficient disk space
- Write permissions issues
- Database is corrupted

**Solutions**:
1. Check available disk space
2. Verify backup directory permissions
3. Try running ProjektKraken as administrator (Windows) or with appropriate permissions
4. Check application logs for detailed error messages

### Restore Fails

**Symptoms**: Error during restoration, database not restored

**Possible causes**:
- Corrupted backup file
- Insufficient disk space
- Permission issues

**Solutions**:
1. Try a different backup file
2. Check if the backup file is corrupted (try opening with SQLite browser)
3. Verify sufficient disk space
4. Check application logs for detailed error messages

### Auto-Backup Not Working

**Symptoms**: No recent auto-save backups in backup folder

**Possible causes**:
- Auto-backup disabled in configuration
- Application not running long enough
- Permission issues writing to backup directory

**Solutions**:
1. Verify auto-save is enabled (check logs on startup)
2. Keep application running for at least 5 minutes to trigger first auto-save
3. Check backup directory permissions
4. Review application logs for errors

### Backup File Too Large

**Symptoms**: Backup files taking up too much disk space

**Solutions**:
1. This is normal - SQLite databases grow with data
2. Use the retention policies to limit backup count
3. Delete old manual backups you no longer need
4. Consider enabling database VACUUM (future feature) to compress database

## Technical Details

### Backup Algorithm

The backup system uses a robust atomic copy process:

1. **Preparation**: Verify database is not in transaction
2. **Copy**: Copy database file to temporary location
3. **Verify**: Check integrity using SQLite PRAGMA commands
4. **Checksum**: Calculate SHA256 hash for corruption detection
5. **Atomic Rename**: Move temporary file to final backup location
6. **Metadata**: Record backup metadata (size, timestamp, checksum)
7. **Cleanup**: Enforce retention policies, delete old backups

### File Format

Backups are standard SQLite database files with `.kraken` extension. They can be:

- Opened with SQLite browsers for inspection
- Copied manually for additional backups
- Shared with other ProjektKraken users
- Restored on any platform (Windows, macOS, Linux)

### Performance Impact

- **Backup creation**: Minimal impact, runs in background
- **Auto-save**: Brief pause (<1 second for typical databases)
- **Restoration**: Requires application restart
- **Storage**: Each backup is ~200KB (grows with your data)

### Security Considerations

- **Encryption**: Backups are not encrypted (planned feature)
- **Permissions**: Use operating system file permissions to protect backups
- **Cloud storage**: If using cloud sync, ensure your cloud provider uses encryption
- **Sensitive data**: Consider using encrypted folders for backup storage

## FAQ

**Q: Can I disable auto-backup?**
A: Yes, through configuration file (UI coming in future release). Not recommended.

**Q: How much disk space do backups use?**
A: Each backup is roughly the size of your database (~200KB base + your data). With default settings, auto-saves use ~2.4 MB maximum.

**Q: Can I backup to a network drive?**
A: Yes, but network reliability may affect backup success. Local backups are recommended.

**Q: What happens if backup fails?**
A: The system logs the error and continues running. Your data remains safe, just that particular backup won't be created.

**Q: Can I restore to a different computer?**
A: Yes! Copy the backup file to the new computer and use Restore from Backup.

**Q: Are backups cross-platform?**
A: Yes, SQLite databases work on all platforms (Windows, macOS, Linux).

**Q: How do I export my data to another format?**
A: Backup files are SQLite databases. You can export to JSON, CSV, or other formats using SQLite tools or future ProjektKraken export features.

## Future Enhancements

Planned features for future releases:

- **Settings dialog** for backup configuration
- **Backup browser** to preview and compare backups
- **Incremental backups** for larger databases
- **Compression** for long-term archives
- **Encryption** for sensitive projects
- **Cloud integration** for seamless off-site backups
- **Backup scheduling** for daily and weekly backups
- **Multi-database backup** for backing up all projects at once

## Support

If you encounter issues with the backup system:

1. Check application logs (Help → View Logs)
2. Review this documentation
3. Check GitHub issues for known problems
4. Open a new issue with detailed error information

## See Also

- [Database Schema Documentation](DATABASE.md)
- [User Guide](README.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)
