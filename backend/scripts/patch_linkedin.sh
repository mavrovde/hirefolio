#!/bin/bash
set -e

# patch_linkedin.sh
# Patches linkedin-api to remove entry_points.txt which causes conflicts

pip download linkedin-api==2.2.1 --no-deps -d /tmp/wheels
mkdir -p /tmp/patched
python -c "import zipfile; zin=zipfile.ZipFile('/tmp/wheels/linkedin_api-2.2.1-py3-none-any.whl','r'); zout=zipfile.ZipFile('/tmp/patched/linkedin_api-2.2.1-py3-none-any.whl','w'); [zout.writestr(i, b'') if i.filename.endswith('entry_points.txt') else zout.writestr(i, zin.read(i.filename)) for i in zin.infolist()]; zin.close(); zout.close()"
pip install /tmp/patched/linkedin_api-2.2.1-py3-none-any.whl && rm -rf /tmp/wheels /tmp/patched
