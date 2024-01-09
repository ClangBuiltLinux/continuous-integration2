#!/bin/bash
set -e

BASE="/var/www/html/cbl/badges"
cd "$BASE"

wget -q -N https://clangbuiltlinux.github.io/ -Odump.txt
for svg in $(sed -e 's/"/\n/g' dump.txt | grep 'actions/workflows.*yml$' | sort -u); do
	#break
        wget -q -N -r "$svg"/badge.svg
	sleep 1
done

BUILDS="github.com/clangbuiltlinux/continuous-integration2/actions/workflows"
for yml in $(cd "$BUILDS" && echo *); do
	build=$(basename $yml .yml)
	badge="$BUILDS/$yml/badge.svg"
	if grep -q passing "$badge"; then
		ln -sf passing.svg $build.svg
	else
		ln -sf failing.svg $build.svg
	fi
done
