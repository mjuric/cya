#!/usr/bin/env python
#
#	mbackup.py <source_url_url> <base_dest_dir>
#
#	Example: mbackup.py root@moya.dev.lsstcorp.org:/etc mjuric@archive.lsstcorp.org:/data/backups/moya
#

import time, os, os.path, glob, datetime, subprocess, itertools, argparse, socket, getpass

class Backup(object):
	dest_base = None	# Backup directory tree base (path)
	dest_host = None	# Host name for Duplicity the destination machine to use
				# to connect from the destination machine (may include the username)
				# Will be passed to duplicity using scp:// protocol.
	src_url = None		# URL to the machine to be backed up
	src_host = None		# Host part of src_url (may include the username). Will be passed to ssh.
	src_dir = None		# Directory part of src_dest.

	backup_cmd = 'duplicity'# Backup command to use on the remote end
	backup_cmd_opts = None	# Duplicity options

	def hardlink(self, files, dest_dir):
		new_files = [ os.path.join(dest_dir, os.path.basename(fn)) for fn in files ]
		print '===', dest_dir
		for src, new in itertools.izip(files, new_files):
			print 'hardlink: ', new, '->', src
			os.link(src, new)
		return new_files

	def full_backup(self, dest_dir):
		return self.incremental_backup(dest_dir)

	def incremental_backup(self, dest_dir):
		# run the backup

		# Run backup
		## duplicity /usr/local file://$(pwd)/backups --volsize 25 --no-encryption --log-file log.log
		## sudo -E duplicity '/etc' 'scp://mjuric@moya.dev.lsstcorp.org//data/backups/moya/2000' --volsize 100 --no-encryption
		##cmd = "ssh -CA %(host)s duplicity '%(from)s' 'scp://%(backup)s/%(dest_dir)s' --volsize 100 --no-encryption" % \
		##	{'host': host, 'from': dir, 'backup': dest_host, 'dest_dir': dest_dir}
		cmd = "ssh -CA %(host)s '%(backup_cmd)s' '%(from)s' '%(dest_host)s/%(dest_dir)s' %(backup_cmd_opts)s" % \
			{'backup_cmd' : self.backup_cmd,
			 'host': self.src_host, 'from': self.src_dir, 'dest_host': self.dest_host, 'dest_dir': dest_dir,
			 'backup_cmd_opts': self.backup_cmd_opts}
		print cmd
		subprocess.check_call(cmd, shell=True)

		# return the full path to all files existing in the backup set directory
		files = [ fn for fn in (os.path.join(dest_dir, f) for f in os.listdir(dest_dir)) if os.path.isfile(fn) ]
		return files

	def no_backups_exist(self, dir):
		# Check if any backups exist in the directory
		for fn in glob.iglob(os.path.join(dir, '*.manifest')):
			return False
		return True

	def mkbackup(self, dest_dir):
		print 'mkbackup:', self.src_url, dest_dir

		if not os.path.exists(dest_dir):
			os.makedirs(dest_dir)


		if self.no_backups_exist(dest_dir):
			up_dir = os.path.dirname(dest_dir)
			print up_dir
			if up_dir == self.dest_base:
				return self.full_backup(dest_dir)

			files = self.mkbackup(up_dir)
			files = self.hardlink(files, dest_dir)
		else:
			files = self.incremental_backup(dest_dir)

		return files

	def date2dir(self, t):
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

	def __init__(self, **kwargs):
		self.dest_base = kwargs['dest_base']
		self.src_url = kwargs['src_url']
		self.src_host, self.src_dir = self.src_url.split(":")

		now = datetime.datetime.strptime(kwargs["now"], '%Y-%m-%d %H:%M:%S.%f')
		self.dest_dir = os.path.join(self.dest_base, self.date2dir(now))

		self.dest_host = kwargs['dest_host']
		self.backup_cmd = kwargs['backup_cmd']
		self.backup_cmd_opts = kwargs['backup_cmd_opts']

		print "Creating backup for: %s [%s]" % (now, self.dest_dir)
		#print vars(self)

		self.mkbackup(self.dest_dir)

#./mbackup.py mjuric@moya.dev.lsstcorp.org:/data/backups/moya_test /data/backups/moya \
#             --backup-cmd-opts="--volsize 100 --no-encryption" --backup-cmd=duplicity-extended-backup

if __name__ == "__main__":
	# autodetect dest_host URL
	dest_host = socket.gethostbyname(socket.getfqdn())
	if dest_host == '127.0.0.1':
		dest_host = None
	else:
		dest_host = 'scp://' + dest_host

	parser = argparse.ArgumentParser(description='Multi-timescale backup driver')
	parser.add_argument('src_url', type=str, help='Backup source URL')
	parser.add_argument('dest_base', type=str, help='Backup destination directory')

	parser.add_argument('--dest-host', dest='dest_host', default=dest_host, required=dest_host is None, help='Host part of the backup destination server. Must be in Duplicity URI format.')
	parser.add_argument('--backup-cmd', dest='backup_cmd', default='duplicity', help='The command to run on the backup target to have it backed up.')
	parser.add_argument('--backup-cmd-opts', dest='backup_cmd_opts', default='', help='Options to pass to the backup command.')

	parser.add_argument('--force-date', dest='now', default=str(datetime.datetime.today()), metavar='T', help='Force the current time to be T.')

	args = parser.parse_args()

	bkp = Backup(**vars(args))

