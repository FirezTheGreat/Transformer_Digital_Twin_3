#!/usr/bin/env python3
"""Finalize inventory and create a deterministic, verified ZIP; no app mutation."""
import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path
from validate import validate

def sha(data):return hashlib.sha256(data).hexdigest()

def make_zip(bundle,members):
    result=io.BytesIO()
    with zipfile.ZipFile(result,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in members:
            relative=path.relative_to(bundle).as_posix()
            info=zipfile.ZipInfo('gridpulse_backup_v1/'+relative,date_time=(2025,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.create_system=3;info.external_attr=0o100644<<16
            archive.writestr(info,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    return result.getvalue()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--zip',type=Path,required=True)
    args=p.parse_args();bundle=args.bundle.resolve();dest=args.zip.resolve()
    if dest.is_relative_to(bundle):raise SystemExit('ZIP must be outside the bundle to avoid self-inclusion')
    if not (bundle/'validation_report.md').exists():raise SystemExit('Run validate.py --write-report first')
    manifest=json.loads((bundle/'dataset_manifest.json').read_text())
    members=sorted(x for x in bundle.rglob('*') if x.is_file() and '__pycache__' not in x.parts)
    manifest['file_inventory']=[{'path':x.relative_to(bundle).as_posix(),'size_bytes':x.stat().st_size,'sha256':sha(x.read_bytes())} for x in members if x.name!='dataset_manifest.json']
    manifest['file_validation_status']='FILE-VALIDATED'
    (bundle/'dataset_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    validation=validate(bundle)
    if validation['failed']:raise SystemExit('Refusing package with failed file validation')
    data=make_zip(bundle,members);again=make_zip(bundle,members)
    if data!=again:raise SystemExit('ZIP regeneration was not byte-identical')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.testzip() is not None:raise SystemExit('Archive CRC failed')
        if len(archive.namelist())!=len(members):raise SystemExit('Wrong archive member count')
        for path in members:
            if archive.read('gridpulse_backup_v1/'+path.relative_to(bundle).as_posix())!=path.read_bytes():raise SystemExit('Archive round-trip byte mismatch')
    dest.write_bytes(data)
    result={'zip':dest.name,'zip_sha256':sha(data),'zip_bytes':len(data),'member_count':len(members),
            'archive_crc':'PASS','all_member_bytes_roundtrip':'PASS','zip_byte_reproducibility':'PASS',
            'final_manifest_checks_passed':validation['passed'],'final_manifest_checks_failed':validation['failed']}
    (dest.parent/'package_verification.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2))
