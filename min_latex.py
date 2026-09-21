#!/usr/bin/env python3
r"""
Usage:
    python min_latex.py path/to/main.tex

What it does:
    - For dependency parsing:
        * removes \iffalse ... \fi
        * removes \begin{comment}...\end{comment}
        * strips % line comments completely
    - Recursively finds ONLY actually used files:
        * \input, \include, \subfile
        * \includegraphics, \includegraphics*
        * \includepdf, \includepdf*
        * \graphicspath
        * \addbibresource, \bibliography
        * \lstinputlisting, \pgfplotstableread
    - Creates minimal/:
        * writes .tex files where:
            - all \iffalse...\fi and \begin{comment}...\end{comment} blocks are removed
            - each line is truncated after the first unescaped % (the % is kept)
        * copies all non-.tex required files (figures, .bib, listings, …)
        * copies Makefile if present
"""

import os
import re
import sys
import shutil

GRAPHIC_EXTS = [".pdf", ".png", ".jpg", ".jpeg", ".eps"]
TEX_EXTS = [".tex"]
BIB_EXTS = [".bib"]


def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ---------- Block removers used for both parsing and output ----------

def remove_iffalse_blocks(text):
    r"""Remove \iffalse ... \fi blocks (simple nesting handled by repeated removal)."""
    pattern = re.compile(r"\\iffalse\b.*?\\fi", re.DOTALL)
    prev = None
    while prev != text:
        prev = text
        text = pattern.sub("", text)
    return text


def strip_comment_envs(text):
    r"""Remove \begin{comment} ... \end{comment} blocks (non-nesting)."""
    pattern = re.compile(r"\\begin{comment}.*?\\end{comment}", re.DOTALL)
    return pattern.sub("", text)


# ---------- Parsing-time helpers (for dependency discovery) ----------

def strip_line_comments_for_parse(text):
    r"""
    Parsing-time comment removal:
    - Remove % and everything after it on each line (except escaped \%).
    - Used ONLY for dependency parsing.
    """
    stripped_lines = []
    for line in text.splitlines():
        new_line_chars = []
        prev = ""
        for ch in line:
            if ch == "%" and prev != "\\":
                break  # start of comment, remove % and after
            new_line_chars.append(ch)
            prev = ch
        stripped_lines.append("".join(new_line_chars))
    return "\n".join(stripped_lines)


def preprocess_tex_for_parsing(text):
    r"""
    Preprocess LaTeX for dependency parsing:
        1. remove \iffalse...\fi
        2. remove comment environments
        3. strip % line comments (including %)
    """
    text = remove_iffalse_blocks(text)
    text = strip_comment_envs(text)
    text = strip_line_comments_for_parse(text)
    return text


# ---------- Output-time helpers (for final .tex) ----------

def truncate_after_percent(text):
    r"""
    Output-time comment handling:
    - Keep everything up to and including the first unescaped %.
    - Delete everything AFTER that % on each line.
    - If there is no unescaped %, keep the whole line.
    Examples:
        'a % b'     -> 'a %'
        'a \\% b'   -> 'a \\% b'
    """
    result_lines = []
    for line in text.splitlines():
        cut_pos = len(line)
        prev = ""
        for i, ch in enumerate(line):
            if ch == "%" and prev != "\\":
                cut_pos = i + 1  # keep the %
                break
            prev = ch
        result_lines.append(line[:cut_pos])
    return "\n".join(result_lines)


def strip_all_comments_for_output(text):
    r"""
    For output .tex:
        - Remove \iffalse...\fi blocks.
        - Remove \begin{comment}...\end{comment} blocks.
        - Then truncate lines after the first unescaped % (keeping the %).
    """
    text = remove_iffalse_blocks(text)
    text = strip_comment_envs(text)
    text = truncate_after_percent(text)
    return text


# ---------- Path resolution ----------

def resolve_path(base_dir, rel_path, exts=None):
    r"""Resolve LaTeX-style relative or absolute path with optional extension guessing."""
    rel_path = rel_path.strip()
    if not rel_path:
        return None

    # Absolute path
    if os.path.isabs(rel_path):
        return rel_path if os.path.exists(rel_path) else None

    candidate = os.path.join(base_dir, rel_path)
    base, ext = os.path.splitext(candidate)

    if ext:
        return candidate if os.path.exists(candidate) else None

    if exts:
        for e in exts:
            tmp = base + e
            if os.path.exists(tmp):
                return tmp

    return candidate if os.path.exists(candidate) else None


def resolve_graphic(base_dir, project_root, rel_path, graphic_paths, exts):
    r"""
    Resolve graphics file considering:
      - base_dir (current .tex file)
      - project_root
      - each absolute \graphicspath directory
    """
    # 1) relative to current file
    resolved = resolve_path(base_dir, rel_path, exts)
    if resolved:
        return resolved

    # 2) relative to project root
    resolved = resolve_path(project_root, rel_path, exts)
    if resolved:
        return resolved

    # 3) under each \graphicspath directory (absolute)
    for gp in graphic_paths:
        candidate = os.path.join(gp, rel_path)
        base, ext = os.path.splitext(candidate)

        if ext:
            if os.path.exists(candidate):
                return candidate
        else:
            if exts:
                for e in exts:
                    tmp = base + e
                    if os.path.exists(tmp):
                        return tmp
            if os.path.exists(candidate):
                return candidate

    return None


def parse_graphicspaths(content):
    r"""Parse \graphicspath{{dir1/}{dir2/}} and return list of dirs (as given)."""
    paths = []
    pattern = re.compile(r"\\graphicspath\{\s*((?:\{[^}]*\}\s*)+)\}")
    for m in pattern.finditer(content):
        inner = m.group(1)
        for d in re.findall(r"\{([^}]*)\}", inner):
            d = d.strip()
            if d:
                paths.append(d)
    return paths


# ---------- Dependency discovery ----------

def find_dependencies(tex_path, project_root, required_files, visited_tex, global_graphic_paths):
    r"""
    Recursively scan tex_path (.tex file), collect dependencies, and update
    global_graphic_paths (as absolute directories) with any \graphicspath entries found.
    Uses aggressive preprocessing only for parsing.
    """
    tex_path = os.path.abspath(tex_path)
    if tex_path in visited_tex:
        return
    visited_tex.add(tex_path)

    base_dir = os.path.dirname(tex_path)
    raw = read_text(tex_path)
    processed = preprocess_tex_for_parsing(raw)

    rel_tex = os.path.relpath(tex_path, project_root)
    required_files.add(rel_tex)

    # collect \graphicspath (store as absolute dirs from project_root)
    for gp in parse_graphicspaths(processed):
        abs_gp = os.path.abspath(os.path.join(project_root, gp))
        if abs_gp not in global_graphic_paths:
            global_graphic_paths.append(abs_gp)

    # \input, \include, \subfile
    for cmd in ["input", "include", "subfile"]:
        pattern = re.compile(rf"\\{cmd}\s*\{{([^}}]+)\}}")
        for m in pattern.finditer(processed):
            rel = m.group(1)
            resolved = resolve_path(base_dir, rel, TEX_EXTS)
            if resolved:
                find_dependencies(
                    resolved,
                    project_root,
                    required_files,
                    visited_tex,
                    global_graphic_paths,
                )

    # \includegraphics / \includegraphics*
    p_graphics = re.compile(
        r"\\includegraphics\*?(?:\[[^\]]*\])?\s*\{([^}]+)\}",
        re.MULTILINE,
    )
    for m in p_graphics.finditer(processed):
        rel = m.group(1)
        resolved = resolve_graphic(
            base_dir, project_root, rel, global_graphic_paths, GRAPHIC_EXTS)
        if resolved:
            required_files.add(os.path.relpath(resolved, project_root))

    # \includepdf / \includepdf*
    p_pdf = re.compile(
        r"\\includepdf\*?(?:\[[^\]]*\])?\s*\{([^}]+)\}",
        re.MULTILINE,
    )
    for m in p_pdf.finditer(processed):
        rel = m.group(1)
        resolved = resolve_graphic(
            base_dir, project_root, rel, global_graphic_paths, GRAPHIC_EXTS)
        if resolved:
            required_files.add(os.path.relpath(resolved, project_root))

    # \addbibresource
    p_biber = re.compile(r"\\addbibresource(?:\[[^\]]*\])?\s*\{([^}]+)\}")
    for m in p_biber.finditer(processed):
        rel = m.group(1)
        resolved = resolve_path(base_dir, rel, BIB_EXTS)
        if resolved:
            required_files.add(os.path.relpath(resolved, project_root))

    # \bibliography
    p_bibtex = re.compile(r"\\bibliography\s*\{([^}]+)\}")
    for m in p_bibtex.finditer(processed):
        for bib in m.group(1).split(","):
            bib = bib.strip()
            if not bib:
                continue
            resolved = resolve_path(base_dir, bib, BIB_EXTS)
            if resolved:
                required_files.add(os.path.relpath(resolved, project_root))

    # \lstinputlisting
    p_lst = re.compile(r"\\lstinputlisting(?:\[[^\]]*\])?\s*\{([^}]+)\}")
    for m in p_lst.finditer(processed):
        rel = m.group(1)
        resolved = resolve_path(base_dir, rel, None)
        if resolved:
            required_files.add(os.path.relpath(resolved, project_root))

    # \pgfplotstableread
    p_pgf = re.compile(r"\\pgfplotstableread(?:\[[^\]]*\])?\s*\{([^}]+)\}")
    for m in p_pgf.finditer(processed):
        rel = m.group(1)
        resolved = resolve_path(base_dir, rel, None)
        if resolved:
            required_files.add(os.path.relpath(resolved, project_root))


# ---------- Copying / writing ----------

def copy_non_tex_files(required_files, project_root, minimal_dir):
    r"""Copy all non-.tex required files into minimal/ preserving structure."""
    for rel in required_files:
        if rel.lower().endswith(".tex"):
            continue
        src = os.path.join(project_root, rel)
        if not os.path.exists(src):
            continue
        dst = os.path.join(minimal_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


def write_stripped_tex_files(required_files, project_root, minimal_dir):
    r"""
    For each required .tex file, write a version where:
        - \iffalse...\fi and \begin{comment}...\end{comment} blocks are removed
        - each line is truncated after the first unescaped % (keeping the %)
    into minimal/ with the SAME filename.
    """
    for rel in required_files:
        if not rel.lower().endswith(".tex"):
            continue
        src = os.path.join(project_root, rel)
        if not os.path.exists(src):
            continue
        stripped = strip_all_comments_for_output(read_text(src))
        dst = os.path.join(minimal_dir, rel)
        write_text(dst, stripped)


# ---------- Main ----------

def main():
    if len(sys.argv) != 2:
        print("Usage: python min_latex.py path/to/main.tex")
        sys.exit(1)

    main_tex = os.path.abspath(sys.argv[1])
    if not os.path.exists(main_tex):
        print(f"Error: {main_tex} does not exist.")
        sys.exit(1)

    project_root = os.path.dirname(main_tex)
    minimal_dir = os.path.join(project_root, "minimal")

    required_files = set()
    visited_tex = set()
    global_graphic_paths = []

    # Build dependency graph starting from main.tex
    find_dependencies(
        main_tex,
        project_root,
        required_files,
        visited_tex,
        global_graphic_paths,
    )

    # Recreate minimal/ directory
    if os.path.exists(minimal_dir):
        shutil.rmtree(minimal_dir)

    print("Creating minimal project in:", minimal_dir)

    # 1. Write .tex files with blocks removed and comments truncated
    write_stripped_tex_files(required_files, project_root, minimal_dir)

    # 2. Copy non-.tex files
    copy_non_tex_files(required_files, project_root, minimal_dir)

    # 3. Copy Makefile if present
    makefile_src = os.path.join(project_root, "Makefile")
    if os.path.exists(makefile_src):
        shutil.copy2(makefile_src, os.path.join(minimal_dir, "Makefile"))
        print("Copied Makefile.")

    print("\nRequired files (original paths):")
    for f in sorted(required_files):
        print(f)

    print("\nKnown graphic paths (absolute from \\graphicspath):")
    for gp in global_graphic_paths:
        print("  ", gp)

    print("\nMinimal project ready in:", minimal_dir)


if __name__ == "__main__":
    main()
