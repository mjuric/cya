cya -- a multi-level backup driver for Duplicity
================================================

Mario Juric <mjuric@lsst.org>

cya (pronnounced see-ya) is a driver for the Duplicity backup tool
(http://duplicity.nongnu.org) that enables:

* multi-level incremental backups on varying time-scales (decade, year,
  month, week), with the ability to keep only the latest few backups on each
  time scale.

* handling of hard links, access control lists, and extended attributes. This
  allows whole-system backups to be performed with cya.

* unattended backups while maintaining security and space efficiency.


Quick Start
===========

How it works
------------

Every day each client adds an incremental backup to a client-specific
'incoming' directory on the archive server (typically,
~archive/$CLIENT/incoming). The backups are usually encrypted for added
security.

The archive server then moves the new increment to its correct place in the
multi-level hierarchy (see 'Multi-level Backups' below), and prepares the
'incoming' directory for the next (incremental) backup.

In time, at each level in the directory tree (typically,
~archive/$CLIENT/backups) a backup chain forms, with increments taken at
different scales.

Quick start
-----------

### Setting up the server (run as root)
```
# install
yum install duplicity
git clone git@github.com:mjuric/cya /opt/cya
ln -s /opt/cya/bin/cya-server /usr/local/bin
mkdir -p /var/lib/cya/backups

# install the backup collector
cp /opt/cya/templates/99-cya-collect /etc/cron.d
```

### Setting up the client (full backup of `/home` on client1.example.com)

#### On the server (run as root)
```
# write down the temporary password this command outputs
cya-server new-backup client1.example.com-home drop-client1
```

#### On the client (run as root)
```
# install
yum install duplicity
git clone git@github.com:mjuric/cya /opt/cya
ln -s /opt/cya/bin/cya-client /usr/local/bin
cp /opt/cya/templates/99-cya-backup /etc/cron.d

# when prompted, use the temporary password from the server
# edit the config file, as instructed, to set up the EXCLUDEs
cya-client new-backup drop-client1@server.example.com client1.example.com-home /home
```

Setting up unattended backups
-----------------------------

Preparing the archive server:

	* install cya
	* install duplicity 0.6.20 or higher

	* copy templates/collect.sample to /etc/cya/server.conf. Customize it
	  as necessary. The most important variable to customize will be
	  `ARCHIVE`, the directory (owned by root) in which the backup
	  sets will be stored. You need to create this directory.

	* add a crontab entry to run `cya-server-collect` daily

Preparing a client to be backed up:

	* On the archive server:
	  + run:
	  
	       `cya-server-init <backup-name> <dropbox-user>'

	    This will create a user `dropbox-user` and directories
	    `~dropbox-user/backup-name` and `$ARCHIVE/backup-name`.  The
	    client will log in as `dropbox-user` to add backup increments,
	    and the server will periodically move them into
	    `$ARCHIVE/backup-name` (whenever `cya-server-collect` is run).

	    By convention, `backup-name` is usually the fully qualified
	    domain name of the client (if this is a full client backup)

	    This command will also create an SSH key pair for
	    `dropbox-user`; you will want to copy the *private* key to the
	    client (the client will use it to log in).

	* On the client:
	  + install cya
	  + install duplicity 0.6.20 or higher
	  
	  + copy the private ssh key from `~dropbox-user/.ssh/id_rsa` on the archive
	    server.

	  + initialize a new backupset by running

	       `cya-client-init <source-dir> <backup-conf> <dropbox-ssh-uri> <key-file>`

	    This will generate the backup configuration files in the `backup-conf`
	    directory, to back up `source-dir` directory via `scp` to
	    `dropbox-ssh-uri`. The `dropbox-ssh-uri` will be of the
	    form `dropbox-user@archive:backup-name`.
	    
	    Note the backup encryption key this command will output.  This
	    passphrase will be used to encrypt the backup set, and should
	    not be shared with anyone (including the archive server!).  Keep
	    it in a safe place -- you will need it to restore the system
	    from backups.

	  + add `cya-client-backup` to crontab on the client. An example
	    file will be in `backup-conf/99-cya-cron`. For optimal
	    performance, have it run ~10-15 minutes after cya-collect runs on
	    the server.

	    WARNING: Some distros (notably, RHEL) set HOME=/ in /etc/crontab.
	    If your distro does this, make sure you run /etc/cya/backup with
	    HOME=/root envvar set. Otherwise, cache directories will be
	    created in /.


Multi-level backups
===================

cya enables multi-level incremental Duplicity backups on varying time-scales
(decade, year, month, week), by organizing Duplicity backups in a directory
tree, where each level in the tree corresponds to the timescale of a backup
stored at that level. Increments that are shared between different levels
are hardlinked to the correct places in the hierarchy (thus the space
efficiency).

For example, a backup made on 2012-12-04 would be placed in a subdirectory
of:

	2000/2010/2012/2012-12/2012-12-02

where the levels correspond to century, decade, year, month and week,
each holding backups for decades, years, months, weeks and days,
respectively.

If the 2012-12-04 backup was the first one ever made, the files in the leaf
directory 2000/2010/2012/2012-12/2012-12-02 would also get hardlinked to
2000/2010/2012/2012-12 (because it's the first weekly backup), and to
2000/2010/2012 (because it's the first montly backup), and so on.

When a backup is made on the next day, 2012-12-05, that day is still in the
week of 2012-12-02, so an incremental backup would be made in
2000/2010/2012/2012-12/2012-12-02. Equally so for all days through
2012-12-08.

On 2012-12-09, the destination directory will change to:

	2000/2010/2012/2012-12/2012-12-09

As it is empty, cya will look into one directory up the hierarchy to use as
a basis for this (incremental) backup.  It will first hardlink files from
2000/2010/2012/2012-12 to 2000/2010/2012/2012-12/2012-12-09, and make this
the 'incoming' directory for the next incremental backup.  The procedure is
repeated when the month/year/decade boundaries are crossed. In time, at each
level in the directory tree a backup chain forms, with increments taken at
different scales.

It's likely desirable to keep this tree pruned, deleting all but two newest
leaf directories at every level of the hierarchy. Right now, cya won't do it
for you (it has to be done manually).


Security model
==============

Definitions:

* archive: the host which holds the backups
* client: a host being backed up
* $ROOT: base directory of backup sets on archive
* Committed backup files: files residing in $ROOT/backups
* Uncommited backup files: files residing in $ROOT/incoming/finished


Design summary:

Client host attempts to back itself up daily to archive:$ROOT/incoming/next
directory, if that directory exists. When it succeeds, it renames that
directory to 'finished'.

The archive host periodically checks for existence of
archive:$ROOT/incoming/finished. If it exists, the increment is moved to the
correct level in the backup hierarchy, and a new $ROOT/incoming/next
directory is prepared.


Design consequences:

* If archive@archive is breached, no committed backup files can be accessed.
  Uncommitted backup files can be accessed, read, deleted, but not decrypted.

* If root@archive is breached all backup files can be accessed, read,
  deleted, but not decrypted.

* If root@client is breached, no committed backups on the archive can be
  accessed.  Uncommitted backup files can be accessed, read, deleted, and
  decrypted.

* If both root@archive and root@client are breached, the backups can be
  read, deleted and decrypted (full compromise).


Implementation details
======================

There are three parts to cya:

* A wrapper for duplicity, `duplicity-ex', that records in the backup the
  ACLs and extended attributes of the files being backed up, and efficiently
  backs up multiply hard-linked files.

* A scheme for organizing Duplicity incremental backups that results in
  multi-level backup chains while being space efficient.

* A scheme and a utility, `cya-collect`, for performing unattended,
  multi-level backups with Duplicity.


Clients periodically (typically, daily) create and upload backups to an
"incoming" directory at the archive server. The archive server collects
these, placing them in apropriate directories in the multi-level backup
hierarchy.

In more detail, on the archive server:

	1) For each client that is backed up, cya-collect is called daily
	   via cron.

	2) It checks if $ROOT/incoming/finished directory exists. If yes,
	   that means a new backup has been uploaded. If no, it exits.

	3) If 'finished' exists, cya-collect uses the information from
	   $ROOT/next_info to hardlink the backup files to apropriate backup
	   sets in $ROOT/backups.  Once done, it removes the 'finished'
	   directory, and creates $ROOT/incomin/next.  It hardlinks the
	   apropriate backup set files (based on current time) into this
	   directory.  It stores which backup set has been hardlinked to
	   $ROOT/next_info.

On the client:

	1) /etc/cya/backup script is run daily via cron. It checks if
	   $ROOT/incoming/next exists on the archive server. If not, it
	   exits, as this means that cya-collect hasn't ran yet and moved a
	   previously created backup to its right place.

	2) Otherwise, it runs duplicity, uploading the result to
	   $ROOT/incoming/next. How duplicity is run can be customized by
	   creating a shell function named 'duplicity' in /etc/cya/backup

	3) Once the backup has finished, $ROOT/incoming/next is moved to
	   $ROOT/incoming/finished. This signals cya-collect that a new
	   backup is ready.



Features to be documented
=========================

These are all in the code (duplicity-ex and duplicity-ex-snap utilities in
lib/), but so far undocumented beyond the actual code:

These do:
* extending duplicity to efficiently store hardlinks
* extending duplicity to store ACLs and xattrs
* self-consistent backups using LVM snapshots
* how to restore using the restore scripts
