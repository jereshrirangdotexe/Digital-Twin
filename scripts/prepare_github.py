"""Verify and export a complete public source package without local runtime state."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIRS = {'.github', 'backend', 'frontend', 'ml', 'data', 'docs', 'examples', 'scripts', 'tests', 'reports'}
FILES = {'.gitignore', '.gitattributes', '.env.example', 'LICENSE', 'README.md', 'START_HERE.md',
         'CONTRIBUTING.md', 'SECURITY.md', 'THIRD_PARTY_NOTICES.md', 'requirements.txt',
         'requirements-dev.txt', 'install_voltmind.bat', 'start_voltmind.bat',
         'stop_voltmind.bat', 'test_voltmind.bat'}
SKIP_DIRS = {'.git', '.venv', 'venv', 'node_modules', 'target', 'dist', 'build', '__pycache__',
             '.pytest_cache', '.state', '.idea', '.vscode', 'uploads', 'htmlcov'}
SKIP_SUFFIX = {'.zip', '.log', '.pyc', '.pyo', '.sqlite', '.sqlite3', '.db', '.pem', '.key', '.p12', '.pfx'}
REPORTS = {'.gitkeep', 'FINAL_INTEGRATION_VALIDATION.md', 'FINAL_VALIDATION.md'}
OMIT = {'docs/VoltMind_Hackathon_Demo.pptx', 'docs/HISTORICAL_START_HERE_20261008.md'}
TEXT = {'.py', '.java', '.js', '.jsx', '.mjs', '.json', '.md', '.txt', '.yml', '.yaml', '.xml', '.properties', '.bat', '.cmd', '.html'}
PATTERNS = {
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'GitHub token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
    'AWS access key': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'OpenAI key': re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b'),
    'credential-bearing URL': re.compile(r'https?://[^\s/:@]+:[^\s/@]+@'),
    'assigned credential': re.compile(r'''(?im)^\s*(?:["']?(?:api_key|secret_key|access_token|password|client_secret)["']?)\s*[:=]\s*["']([^"'\n]{12,})["']'''),
}

def selected(root):
    for directory, dirs, names in os.walk(root):
        relative = Path(directory).relative_to(root)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not Path(directory, d).is_symlink()
                         and (relative.parts or d in DIRS))
        for name in sorted(names):
            path = Path(directory, name)
            rel = path.relative_to(root)
            if path.is_symlink() or (not rel.parent.parts and name not in FILES): continue
            if rel.as_posix() in OMIT or path.suffix.lower() in SKIP_SUFFIX: continue
            if name.startswith('.env') and name != '.env.example': continue
            if name in {'credentials.json', 'Thumbs.db', '.DS_Store'} or name.startswith('service-account'): continue
            if rel.parts[0] == 'reports' and (len(rel.parts) != 2 or name not in REPORTS): continue
            yield path, rel

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def audit(root):
    manifest = json.loads((root/'docs/ARTIFACT_CHECKSUMS.json').read_text(encoding='utf-8'))
    mismatches = [p for p, value in manifest['sha256'].items()
                  if not (root/p).is_file() or sha(root/p) != value]
    findings = []
    files = list(selected(root))
    for path, rel in files:
        if path.stat().st_size > 100*1024*1024:
            findings.append({'file': rel.as_posix(), 'issue': 'Above regular Git 100 MiB limit; review LFS rules'})
        if path.suffix.lower() not in TEXT or path.stat().st_size > 5*1024*1024: continue
        text = path.read_text(encoding='utf-8-sig', errors='replace')
        for label, pattern in PATTERNS.items():
            if pattern.search(text): findings.append({'file': rel.as_posix(), 'issue': label})
    result = {'status': 'PASS' if not mismatches and not findings else 'FAIL',
              'selectedFiles': len(files), 'protectedArtifacts': len(manifest['sha256']),
              'artifactMismatches': mismatches, 'credentialOrSizeFindings': findings,
              'scope': 'Common credential patterns in selected text files up to 5 MiB; not a universal secret detector.'}
    return result, files

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result, files = audit(ROOT)
    print(json.dumps(result, indent=2))
    if result['status'] != 'PASS': raise SystemExit(1)
    if not args.output: return
    output = args.output.resolve()
    if output.exists() or output == ROOT or ROOT in output.parents:
        raise SystemExit('Choose a new destination outside the working project; existing folders are never overwritten.')
    archive = output.with_suffix('.zip')
    if archive.exists(): raise SystemExit('Archive already exists; choose a new destination.')
    output.mkdir(parents=True)
    for source, rel in files:
        dest = output/rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        # Remove workstation-only paths from prose; frozen data/models are never rewritten.
        if (rel.parts[0] == 'docs' and source.suffix == '.md') or rel.as_posix() == 'START_HERE.md':
            text = dest.read_text(encoding='utf-8-sig')
            text = text.replace('C:/Users/Shriii/Desktop/t/DT/', '').replace('C:/Users/Shriii/Desktop/t/DT', '<project>')
            text = text.replace('C:\\Users\\Shriii\\Desktop\\t\\DT', '<project>').replace('C:\\Users\\Shriii\\Desktop\\VoltMind', 'C:\\Projects\\VoltMind')
            dest.write_text(text, encoding='utf-8')
    final, exported = audit(output)
    if final['status'] != 'PASS': raise SystemExit('Export validation failed: '+json.dumps(final))
    checksums = {rel.as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)} for p, rel in exported}
    (output/'PUBLIC_PACKAGE_MANIFEST.json').write_text(json.dumps({'audit': final, 'files': checksums}, indent=2), encoding='utf-8')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(output.rglob('*')):
            if path.is_file(): z.write(path, output.name+'/'+path.relative_to(output).as_posix())
    print('Ready: '+str(output))
    print('Full source ZIP: '+str(archive))

if __name__ == '__main__': main()
