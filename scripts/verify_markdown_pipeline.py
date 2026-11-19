#!/usr/bin/env python3
"""
Automated Markdown Verification Script for MovieAIProducer.
Verifies:
1. Exactly 67 markdown files are present.
2. Balanced code fences across all files.
3. 0 broken internal markdown relative links.
4. Mermaid diagram syntax and validity.
"""

import glob
import os
import re
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_markdown_files():
    pattern = os.path.join(REPO_ROOT, "**/*.md")
    files = glob.glob(pattern, recursive=True)
    # Exclude hidden directories, virtualenvs, caches
    filtered = [
        f for f in sorted(files)
        if "/." not in os.path.relpath(f, REPO_ROOT)
    ]
    return filtered


def verify_balanced_fences(md_files):
    errors = []
    for f in md_files:
        rel = os.path.relpath(f, REPO_ROOT)
        with open(f, "r", encoding="utf-8") as fp:
            lines = fp.readlines()
        fences = [l for l in lines if l.strip().startswith("```")]
        if len(fences) % 2 != 0:
            errors.append((rel, len(fences)))
    return errors


def verify_relative_links(md_files):
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    broken = []
    total_links = 0

    for f in md_files:
        rel_file = os.path.relpath(f, REPO_ROOT)
        file_dir = os.path.dirname(f)
        with open(f, "r", encoding="utf-8") as fp:
            content = fp.read()

        for text, url in link_pattern.findall(content):
            # Ignore web links, mailto, anchor only
            if url.startswith(("http://", "https://", "mailto:", "#")):
                continue
            # Strip query / anchor
            clean_url = url.split("#")[0].split("?")[0]
            if not clean_url:
                continue

            total_links += 1
            target_path = os.path.normpath(os.path.join(file_dir, clean_url))
            if not os.path.exists(target_path):
                broken.append((rel_file, text, url, target_path))

    return total_links, broken


def verify_mermaid_diagrams(md_files):
    diagram_blocks = []
    unique_diagrams = {}

    for f in md_files:
        rel_file = os.path.relpath(f, REPO_ROOT)
        with open(f, "r", encoding="utf-8") as fp:
            content = fp.read()
        matches = re.findall(r"```mermaid\n(.*?)\n```", content, re.DOTALL)
        for idx, m in enumerate(matches):
            diag = m.strip()
            diagram_blocks.append((rel_file, idx + 1, diag))
            if diag not in unique_diagrams:
                unique_diagrams[diag] = []
            unique_diagrams[diag].append((rel_file, idx + 1))

    # Validate unique diagrams using mmdc
    puppeteer_cfg = "/tmp/puppeteerConfig.json"
    if not os.path.exists(puppeteer_cfg):
        with open(puppeteer_cfg, "w", encoding="utf-8") as fp:
            fp.write('{"args": ["--no-sandbox", "--disable-setuid-sandbox"]}')

    failed = []
    for diag, occurrences in unique_diagrams.items():
        with tempfile.NamedTemporaryFile("w", suffix=".mmd", delete=False) as tf:
            tf.write(diag)
            tname = tf.name
        svg_name = tname + ".svg"
        try:
            res = subprocess.run(
                ["bun", "x", "@mermaid-js/mermaid-cli", "-i", tname, "-o", svg_name, "-p", puppeteer_cfg],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if res.returncode != 0:
                failed.append((occurrences, diag, res.stderr.strip()))
        except Exception as e:
            failed.append((occurrences, diag, str(e)))
        finally:
            if os.path.exists(tname):
                os.remove(tname)
            if os.path.exists(svg_name):
                os.remove(svg_name)

    return len(diagram_blocks), len(unique_diagrams), failed


def main():
    print("=" * 60)
    print("MOVIEAIPRODUCER MARKDOWN QUALITY PIPELINE VERIFICATION")
    print("=" * 60)

    # 1. File Count Check
    files = find_markdown_files()
    print(f"[*] Total markdown files discovered: {len(files)}")
    if len(files) != 67:
        print(f"[!] ERROR: Expected exactly 67 markdown files, found {len(files)}.")
        return 1

    # 2. Balanced Fences Check
    fence_errors = verify_balanced_fences(files)
    if fence_errors:
        print(f"[!] ERROR: Unbalanced code fences found in {len(fence_errors)} files:")
        for rel, count in fence_errors:
            print(f"    - {rel} (total fence lines: {count})")
        return 1
    print("[+] All code fences are balanced.")

    # 3. Relative Link Check
    total_links, broken_links = verify_relative_links(files)
    print(f"[*] Checked {total_links} internal relative links across {len(files)} files.")
    if broken_links:
        print(f"[!] ERROR: Found {len(broken_links)} broken relative links:")
        for rel, text, url, target in broken_links:
            print(f"    - {rel}: [{text}]({url}) -> unresolved: {target}")
        return 1
    print("[+] 0 broken internal markdown relative links.")

    # 4. Mermaid Syntax Check
    total_diags, unique_diags, failed_diags = verify_mermaid_diagrams(files)
    print(f"[*] Found {total_diags} Mermaid diagram blocks ({unique_diags} unique).")
    if failed_diags:
        print(f"[!] ERROR: {len(failed_diags)} Mermaid diagrams failed compilation:")
        for occ, diag, err in failed_diags:
            print(f"    - In {occ[0]}: {err[:120]}")
        return 1
    print(f"[+] All {total_diags} Mermaid diagrams ({unique_diags} unique) validated successfully!")

    print("=" * 60)
    print("ALL QUALITY PIPELINE VERIFICATIONS PASSED (67/67 FILES VALIDATED)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
