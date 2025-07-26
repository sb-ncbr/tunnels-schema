#!/usr/bin/env bash
# utils/generate_images.sh
# Regenerate ER‑diagram images from the current dictionary.
# Needs: utils/summarise.py  +  graphviz `dot`  +  gemmi (for summarise.py)

set -e

# ---- paths -----------------------------------------------------------------
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SELF_DIR}/.."

DICT="${ROOT_DIR}/schemas/mmcif_tunnels_v10.dic"
SUMMARISE="${SELF_DIR}/summarise.py"
IMAGES="${ROOT_DIR}/images"

mkdir -p "${IMAGES}"

# ---- concise diagram -------------------------------------------------------
python "${SUMMARISE}" "${DICT}" --dot "${IMAGES}/schema.gv"
dot -Tpng "${IMAGES}/schema.gv" -o "${IMAGES}/schema.png"
dot -Tpdf "${IMAGES}/schema.gv" -o "${IMAGES}/schema.pdf"
rm "${IMAGES}/schema.gv"

# ---- full diagram (with descriptions) --------------------------------------
python "${SUMMARISE}" "${DICT}" --dot "${IMAGES}/schema_full.gv" --desc
dot -Tpng "${IMAGES}/schema_full.gv" -o "${IMAGES}/schema_full.png"
dot -Tpdf "${IMAGES}/schema_full.gv" -o "${IMAGES}/schema_full.pdf"
rm "${IMAGES}/schema_full.gv"

echo "Diagrams regenerated in ${IMAGES}"

