#!/usr/bin/env bash
# Rebuild AirNode S3 from design.py: libraries -> schematic -> netlist check -> PCB -> route -> pours/DRC
set -euo pipefail
T="$(cd "$(dirname "$0")" && pwd)"
P="$T/../project"
PY=/usr/bin/python3.12

python3 "$T/make_libs.py" "$P"
python3 "$T/gen_sch.py" "$P/airnode.kicad_sch"
(cd "$P" && kicad-cli sch export netlist -o airnode.net airnode.kicad_sch >/dev/null)
python3 "$T/check_net.py" "$P/airnode.net"
(cd "$T" && $PY build_pcb.py "$P/airnode")
$PY "$T/router.py" "$P/airnode.kicad_pcb" | grep -E "!!|total fails|SAVED"
$PY "$T/finish_pcb.py" "$P/airnode.kicad_pcb" "$P/airnode-drc.rpt"
grep -E "Found" "$P/airnode-drc.rpt"
grep -oE "^\[[a-z_]+\]" "$P/airnode-drc.rpt" | sort | uniq -c || true
