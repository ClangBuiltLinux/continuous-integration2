#!/bin/bash
set -e

BASE="/var/www/html/cbl/badges"
cd "$BASE"

rm fetched.stamp

# CBL.github.io
#wget -q -N https://clangbuiltlinux.github.io/ -Odump.txt
#for svg in $(sed -e 's/"/\n/g' dump.txt | grep 'actions/workflows.*yml$' | sort -u); do

# README.md
wget -q -N https://raw.githubusercontent.com/ClangBuiltLinux/continuous-integration2/main/README.md -Odump.txt
for svg in $(sed -e 's/[()]/\n/g' dump.txt | grep 'yml$' | sort -u); do
	url="$svg"/badge.svg
	echo "$url" >> fetched.stamp
	# Ignore fetch errors.
	wget -nv -N -r "$url" 2>> fetched.stamp || true
	sleep 1
done

BUILDS="github.com/clangbuiltlinux/continuous-integration2/actions/workflows"
for yml in $(cd "$BUILDS" && echo *); do
	build=$(basename $yml .yml)
	badge="$BUILDS/$yml/badge.svg"
	if grep -q passing "$badge"; then
		ln -sf passing.svg $build.svg
	else
		if grep -q failing "$badge"; then
			ln -sf failing.svg $build.svg
		else
			ln -sf unknown.svg $build.svg
		fi
	fi
done

touch parsed.stamp
