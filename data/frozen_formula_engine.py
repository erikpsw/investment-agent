"""Archive sealed research sources and run them in an isolated Python process."""
import hashlib
from importlib import metadata
import json
from pathlib import Path,PurePosixPath
import platform
import subprocess
import sys
import tempfile


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(",",":")).encode()).hexdigest()


def runtime():
    try:tzdata=metadata.version("tzdata")
    except metadata.PackageNotFoundError:tzdata=None
    return {"python":sys.version,"implementation":platform.python_implementation(),"tzdata":tzdata}


def validate_protocol(protocol):
    if digest({k:v for k,v in protocol.items() if k!="seal"})!=protocol.get("seal"):
        raise ValueError("Protocol seal mismatch")
    for name in protocol["engine_source_hashes"]:
        path=PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name or path.suffix!=".py" or path.parts[0] not in ("data","scripts"):
            raise ValueError("Invalid source path")


def verify_archive(protocol,archive_root):
    validate_protocol(protocol)
    folder=Path(archive_root)/protocol["seal"]
    manifest=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    saved=json.loads((folder/"protocol.json").read_text(encoding="utf-8"))
    if saved!=protocol or manifest["seal"]!=protocol["seal"] or manifest["source_files"]!=protocol["engine_source_hashes"]:
        raise ValueError("Archive protocol mismatch")
    if manifest.get("bootstrap_hash")!=hashlib.sha256(BOOTSTRAP.encode()).hexdigest():
        raise ValueError("Archive bootstrap hash mismatch")
    for name,expected in protocol["engine_source_hashes"].items():
        path=folder/name
        if not path.resolve().is_relative_to(folder.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError("Archive source hash mismatch")
    return folder


def archive_engine(protocol,source_root,archive_root):
    validate_protocol(protocol)
    folder=Path(archive_root)/protocol["seal"]
    if (folder/"manifest.json").exists():return verify_archive(protocol,archive_root)
    source_root=Path(source_root).resolve()
    # Verify every live source before creating the snapshot; partial archives
    # can be resumed only when every existing file has the expected contents.
    sources={}
    for name,expected in protocol["engine_source_hashes"].items():
        source=(source_root/name).resolve()
        if not source.is_relative_to(source_root):raise ValueError("Source outside workspace")
        blob=source.read_bytes()
        if hashlib.sha256(blob).hexdigest()!=expected:raise ValueError("Source hash changed")
        sources[name]=blob
    folder.mkdir(parents=True,exist_ok=True)
    sources["protocol.json"]=json.dumps(protocol,ensure_ascii=False,indent=2,allow_nan=False).encode()
    for name,blob in sources.items():
        destination=folder/name
        if not destination.resolve().is_relative_to(folder.resolve()):raise ValueError("Archive destination outside root")
        destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():
            if destination.read_bytes()!=blob:raise ValueError("Partial archive hash mismatch")
        else:
            with destination.open("xb") as target:target.write(blob)
    manifest={"version":1,"seal":protocol["seal"],"runtime":runtime(),"source_files":protocol["engine_source_hashes"],"bootstrap_hash":hashlib.sha256(BOOTSTRAP.encode()).hexdigest()}
    with (folder/"manifest.json").open("x",encoding="utf-8") as target:json.dump(manifest,target,ensure_ascii=False,indent=2)
    return verify_archive(protocol,archive_root)


BOOTSTRAP="""
import json,sys,types
from pathlib import Path
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
root=Path(sys.argv[1]).resolve()
# Pure research modules use only the archived namespace; eager application
# package initializers and the live checkout never enter this process.
pkg=types.ModuleType('investment');pkg.__path__=[str(root)]
sys.modules['investment']=pkg
sub=types.ModuleType('investment.data');sub.__path__=[str(root/'data')]
sys.modules['investment.data']=sub
from investment.data.formula_holdout import evaluate_protocol
request=json.load(sys.stdin)
result=evaluate_protocol(request['protocol'],request['series'])
json.dump(result,sys.stdout,ensure_ascii=False,allow_nan=False)
"""


def run_archived(protocol,series,archive_root):
    folder=verify_archive(protocol,archive_root)
    manifest=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    if manifest["runtime"]!=runtime():raise ValueError("Frozen runtime changed; verify a separate environment")
    # A fresh cache prefix plus -B ensures imports compile the verified source
    # rather than reading bytecode from a previous snapshot run.
    with tempfile.TemporaryDirectory(prefix="formula-frozen-cache-") as cache:
        result=subprocess.run([sys.executable,"-I","-B","-X",f"pycache_prefix={cache}","-c",BOOTSTRAP,str(folder.resolve())],input=json.dumps({"protocol":protocol,"series":series},ensure_ascii=False,allow_nan=False),capture_output=True,text=True,encoding="utf-8",timeout=300)
    if result.returncode:raise ValueError("Archived evaluation failed: "+result.stderr.strip()[-2000:])
    return json.loads(result.stdout)
