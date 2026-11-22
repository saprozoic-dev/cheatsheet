#!/bin/sh
# Full rebuild from one tracker pull.  Usage: sh run_all.sh pull.json [prev_state.json]
set -e
PULL=$1; PREV=${2:-}
rm -f part_*.pkl
python3 site2db.py "$PULL"
python3 -c "
import sweep2
n=[m[0] for m in sweep2.MACH]; h=len(n)//2
open('names_a.txt','w').write('|'.join(n[:h])); open('names_b.txt','w').write('|'.join(n[h:]))"
A=$(cat names_a.txt); B=$(cat names_b.txt)
( python3 run_sel.py a "$A" && python3 run_hi.py a "$A" ) > sim_a.log 2>&1 &
PA=$!
( python3 run_sel.py b "$B" && python3 run_hi.py b "$B" ) > sim_b.log 2>&1 &
PB=$!
python3 epicsim.py 2> epic.log
wait $PA; wait $PB
python3 sweep2.py merge > merge.log 2>&1 || { cat merge.log; exit 1; }
python3 hitstats.py
python3 auto_page.py "$PULL" $PREV
