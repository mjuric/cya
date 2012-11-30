#!/usr/bin/env python
#
#	mbackup.py <source_url_url> <base_dest_dir>
#
#	Example: mbackup.py root@moya.dev.lsstcorp.org:/etc mjuric@archive.lsstcorp.org:/data/backups/moya
#

import time, os, os.path, glob, datetime, subprocess, itertools, argparse

def hardlink_files(files, dest, base):
	new_files = [ os.path.join(base, dest, os.path.basename(fn)) for fn in files ]
	print '===', os.path.join(base, dest)
	for src, new in itertools.izip(files, new_files):
		print 'hardlink: ', new, '->', src
		os.link(src, new)
	return new_files

def full_backup(source_url, dest_dir):
	return incremental_backup(source_url, dest_dir)

def incremental_backup(source_url, dest_dir):
	# run the backup
	(host, dir) = source_url.split(":")
	backup_host = 'mjuric@moya.dev.lsstcorp.org'

	# Run backup
	## duplicity /usr/local file://$(pwd)/backups --volsize 25 --no-encryption --log-file log.log
	## sudo -E duplicity '/etc' 'scp://mjuric@moya.dev.lsstcorp.org//data/backups/moya/2000' --volsize 100 --no-encryption
	##cmd = "ssh -CA %(host)s duplicity '%(from)s' 'scp://%(backup)s/%(dest_dir)s' --volsize 100 --no-encryption" % \
	##	{'host': host, 'from': dir, 'backup': backup_host, 'dest_dir': dest_dir}
	cmd = "ssh -CA %(host)s duplicity-extended-backup '%(from)s' 'scp://%(backup)s/%(dest_dir)s' --volsize 100 --no-encryption" % \
		{'host': host, 'from': dir, 'backup': backup_host, 'dest_dir': dest_dir}
	print cmd
	subprocess.check_call(cmd, shell=True)

	# return all files existing in the backup set directory (full path)
	files = [ fn for fn in (os.path.join(dest_dir, f) for f in os.listdir(dest_dir)) if os.path.isfile(fn) ]
	return files

def no_backups_exist(dir):
	# Check if any backups exist in the directory
	for fn in glob.iglob(os.path.join(dir, '*.manifest')):
		return False
	return True

def mkbackup(source_url, dest, base):
	print 'mkbackup:', source_url, dest, base
	full_path = os.path.join(base, dest)

	if not os.path.exists(full_path):
		os.makedirs(full_path)

	if no_backups_exist(full_path):
		if dest.find('/') == -1:
			return full_backup(source_url, full_path)
		dest_up = dest[:dest.rfind('/')]
		files = mkbackup(source_url, dest_up, base)
		local_files = hardlink_files(files, dest, base)
		return local_files
	else:
		files = incremental_backup(source_url, full_path)
		return files

def date2dir(t):
	# Round down to the start of the week (weeks begin on Sunday)
	d = t.date()
	d -= datetime.timedelta((d.weekday() + 1) % 7)

	# Extract info, construct path
	dir = os.path.join(
		"%04d" % (d.year - d.year % 100),	# century
		"%04d" % (d.year - d.year % 10), 	# decade
		"%04d" % (d.year),			# year
		d.strftime("%Y-%m"),			# year-month
		d.isoformat()				# year-month-week
		)

	return dir

#base = '/data/backups/moya'
#source_url = 'mjuric@moya.dev.lsstcorp.org:/data/backups/moya_test'

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Multi-timescale backup driver')
	parser.add_argument('source_url', type=str, help='Backup source URL')
	parser.add_argument('dest_dir', type=str, help='Backup destination directory')
	parser.add_argument('--force-date', dest='now', default=str(datetime.datetime.today()), metavar='T', help='Force the current time to be T')
	args = parser.parse_args()

	base = args.dest_dir
	source_url = args.source_url

	now = datetime.datetime.strptime(args.now, '%Y-%m-%d %H:%M:%S.%f')
	dest = date2dir(now)

	print "Creating backup for: %s [%s]" % (now, dest)

	mkbackup(source_url, dest, base)
