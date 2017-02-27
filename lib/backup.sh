#
# backup function library. The backup script (usually /etc/cya/backup) may
# want to override duplicity() and retarget it to one of the duplicity-ex
# variants, or a different backup program alltogether.
#

CYA_LIB_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

type -t duplicity-ex-snap >/dev/null || duplicity-ex-snap() { "$CYA_LIB_DIR/duplicity-ex-snap" "$@"; }
type -t duplicity-ex      >/dev/null || duplicity-ex()      { "$CYA_LIB_DIR/duplicity-ex" "$@"; }

backup()
{
	(
		set -e

		# don't let two backups run at the same time
		flock --nonblock 200 || { echo "Backup already in progress. Exiting."; exit 1; }


		# save the users from themselves; check that /etc/cya, /etc/cya/backup and the private SSH keys are
		# not group or world accessible
		GOPERMS=$(stat -c'%A' "$0" | cut -b 5-10)
		[[ $GOPERMS != "------" ]] && { echo "Permissions to $0 incorrect (run 'chmod go-rwx $0')"; exit -1; }
		ETC_CYA_DIR=$(dirname "$0")
		GOPERMS=$(stat -c'%A' "$ETC_CYA_DIR" | cut -b 5-10)
		[[ $GOPERMS != "------" ]] && { echo "Permissions to $ETC_CYA_DIR incorrect (run 'chmod go-rwx $ETC_CYA_DIR')"; exit -1; }
		GOPERMS=$(stat -c'%A' "$SSHKEY" | cut -b 5-10)
		[[ $GOPERMS != "------" ]] && { echo "Permissions to $SSHKEY incorrect (run 'chmod go-rwx $SSHKEY')"; exit -1; }

		# Test if it's OK to start
		START=$(ssh -i "$SSHKEY" "$DESTHOST" "test -d $DESTDIR/incoming/next && echo Y")
		[[ $START != "Y" ]] && exit 2;

		# Backup
		(
			# Close the lock file descriptor. Otherwise, if LVM is 
			# called by duplicity, it will complain about open descriptors.
			# Do it from a subshell so we don't release the lock
			exec 200>&-

			# Make sure cache directory isn't readable to anyone.
			# This is really a bug in duplicity.
			mkdir -p "$HOME/.cache/duplicity"
			chmod 700 "$HOME/.cache/duplicity"

			# Construct the --exclude line
			EXCLUSIONS=()
			for DIR in "${EXCLUDE[@]}"; do EXCLUSIONS+=("--exclude" "$DIR"); done

			export PASSPHRASE="$BACKUP_ENCRYPTION_KEY"
			"$DUPLICITYCMD" \
				"$SOURCEDIR" \
				scp://"$DESTHOST"/"$DESTDIR"/incoming/next \
				--verbosity=error \
				--ssh-options="-oIdentityFile=$SSHKEY" \
				--asynchronous-upload --volsize=100 \
				--ssh-backend pexpect \
				"${EXCLUSIONS[@]}"

			# Mark as finished
			ssh -i "$SSHKEY" "$DESTHOST" \
				mv "$DESTDIR"/incoming/next "$DESTDIR"/incoming/finished
		)

	) 200>/var/run/cya-backup
}
