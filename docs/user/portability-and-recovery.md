# Understand world portability and recovery

A portable world keeps its manifest, saved lore and assets in one folder.
Application preferences, backups and search caches have separate purposes and
locations. Saving lore is not the same as creating a complete transferable copy.

## Three kinds of output

| Output | Purpose and boundary |
| --- | --- |
| Lore export | Exchange selected records in supported formats. It is not a complete world backup. |
| Database backup | Recover saved world data. It does not contain image/map asset files. |
| Portable world package | Transfer the manifest, saved data and assets together as a `.krakenworld` file. Local preferences, caches, external-path approvals and old backups do not travel. |

The [transfer guide](import-export-and-backups.md) is the canonical procedure
and format reference. Publishing a readable Longform document has a different
goal from exporting records that can be imported again.

## External databases reduce portability

**Link External DB** deliberately links a world to a database outside its folder.
Approval belongs to local application settings; a received manifest does not
grant that trust. A missing external database is not automatically recreated.
Keeping the manifest and assets together does not make an external database
part of that folder. Network or synchronized storage also does not provide
simultaneous multi-user editing safety.

## Undo, restore and upgrade recovery

Undo reverses supported content operations. Removing an entry from one Longform
document is distinct from deleting it from the world. Restoring a database
backup replaces saved world data and requires a restart after shutdown; it is
not an ordinary undoable edit. An upgrade recovery copy serves a different
purpose again: it preserves the pre-migration data for the compatible version.

Use {ref}`backup and restore <help-backup-restore>` for the full procedure and
its safety-snapshot behavior. Keep upgrade recovery instructions with their
recovery directory. A successful restore of lore cannot recover an image file
that was never included in that backup.
