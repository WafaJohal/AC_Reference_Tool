#!/usr/bin/env python3
"""
Reference Author Frequency Tool
================================
Paste a numbered bibliography (ACM / IEEE style, e.g. lines starting with [1], [2] ...).
The tool parses the authors out of every reference, ranks people by how often they
appear, and shows the citations for whichever author you select — the most frequent
one is selected automatically.

You can also load a paper's PDF directly — the tool extracts the text, isolates the
References section, and analyses it.

Dependencies: Python 3 + Tkinter (bundled). PDF support uses PyMuPDF or pypdf if
either is installed (optional — plain text/paste always works).

Run:  python3 reference_author_tool.py
"""

import os
os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")  # hide macOS system-Tk deprecation notice

import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from collections import defaultdict


# --------------------------------------------------------------------------- #
#  PDF text extraction (optional dependency)
# --------------------------------------------------------------------------- #

def extract_pdf_text(path):
    """Extract all text from a PDF using PyMuPDF, falling back to pypdf.

    Raises RuntimeError with a friendly message if no backend is available or
    extraction fails.
    """
    # Preferred backend: PyMuPDF — fast, high quality.
    try:
        import pymupdf as fitz  # modern import name
    except ImportError:
        try:
            import fitz  # older PyMuPDF releases
        except ImportError:
            fitz = None

    if fitz is not None:
        try:
            parts = []
            with fitz.open(path) as doc:
                for page in doc:
                    parts.append(page.get_text("text"))
            return "\n".join(parts)
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"PyMuPDF could not read this PDF: {exc}")

    # Fallback backend: pypdf.
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError(
            "No PDF library found. Install one with:\n"
            "    pip3 install pymupdf\n"
            "or\n"
            "    pip3 install pypdf")

    try:
        reader = PdfReader(path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"pypdf could not read this PDF: {exc}")


def isolate_references(text):
    """Return just the bibliography portion of a full-paper text dump.

    Looks for the last 'References' / 'Bibliography' heading and returns
    everything after it. If none is found, returns the text unchanged so the
    numbered-marker parser can still try.
    """
    # Match a heading that sits on its own (allowing a number prefix like "7 References").
    pattern = re.compile(
        r'(?im)^\s*(?:\d+\.?\s+)?(references|bibliography|references cited|works cited)\s*$')
    matches = list(pattern.finditer(text))
    if matches:
        # Use the last such heading — earlier ones may be a section title in the ToC.
        tail = text[matches[-1].end():]
        # Trim a trailing appendix/acknowledgements section if it clearly follows.
        return tail
    # Fallback: if there's no heading but there are [n] markers, start at the first one.
    m = re.search(r'\[\s*1\s*\]', text)
    if m:
        return text[m.start():]
    return text


# --------------------------------------------------------------------------- #
#  Parsing
# --------------------------------------------------------------------------- #

def split_entries(text):
    """Split a blob of text into individual references keyed by their [n] number.

    Returns a list of (number, entry_text) tuples in order of appearance.
    Handles references that wrap across several lines.
    """
    # Find every "[n]" marker and slice the text between consecutive markers.
    markers = list(re.finditer(r'\[(\d+)\]', text))
    entries = []
    if markers:
        for i, m in enumerate(markers):
            num = int(m.group(1))
            start = m.end()
            end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
            chunk = text[start:end]
            entries.append((num, _clean(chunk)))
    else:
        # No [n] markers: treat each non-empty line as its own reference.
        for i, line in enumerate(l for l in text.splitlines() if l.strip()):
            entries.append((i + 1, _clean(line)))
    return entries


def _clean(chunk):
    """Collapse line-wrapping whitespace and repair hyphenated line breaks."""
    # Join words split across a line break by a hyphen: "co-\n  manipulation" -> "co-manipulation"
    chunk = re.sub(r'-\s*\n\s*', '-', chunk)
    # Any remaining whitespace (newlines, multiple spaces) -> single space.
    chunk = re.sub(r'\s+', ' ', chunk)
    return chunk.strip()


def extract_authors(entry_text):
    """Return a list of author names from one reference entry.

    Strategy: the author block is everything up to the first ". <year>." The year
    is a 4-digit number. Authors are separated by commas and the word "and".
    """
    # Grab everything before the first ". YYYY." (the publication year).
    m = re.match(r'(.*?)\.\s+(1[6-9]\d\d|20\d\d)\.', entry_text)
    author_block = m.group(1) if m else entry_text

    # Normalise separators: turn ", and " / " and " into a plain comma.
    author_block = re.sub(r',?\s+and\s+', ', ', author_block)

    authors = []
    for raw in author_block.split(','):
        name = raw.strip().strip('.').strip()
        if not name:
            continue
        # Drop "et al." and clearly non-name fragments.
        if re.fullmatch(r'et al\.?', name, flags=re.IGNORECASE):
            continue
        # A plausible author name contains at least one letter.
        if not re.search(r'[A-Za-z]', name):
            continue
        authors.append(_normalise_name(name))
    return authors


def _normalise_name(name):
    """Light normalisation so the same person collapses to one key."""
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def extract_year(entry_text):
    """Return the publication year of a reference as an int, or None.

    Uses the first '. YYYY.' (the year that follows the author block); falls back
    to the first standalone 4-digit year in a plausible range.
    """
    m = re.match(r'.*?\.\s+(1[6-9]\d\d|20\d\d)\.', entry_text)
    if m:
        return int(m.group(1))
    m = re.search(r'\b(1[6-9]\d\d|20\d\d)\b', entry_text)
    return int(m.group(1)) if m else None


def extract_title(entry_text):
    """Return the (approximate) title of a reference.

    In ACM/IEEE style the title is the sentence right after '. YEAR. '. It ends at
    the first sentence terminator ('. ', '? ', '! ') that precedes the venue.
    """
    m = re.match(r'.*?\.\s+(?:1[6-9]\d\d|20\d\d)\.\s+(.*)', entry_text)
    if not m:
        return ""
    region = m.group(1)
    cut = len(region)
    for term in (". ", "? ", "! "):
        i = region.find(term)
        if i != -1:
            cut = min(cut, i)
    return region[:cut].strip()


def parse_records(text):
    """Parse text into a list of reference records.

    Each record: {'num', 'year', 'title', 'authors' (deduped list), 'entry'}.
    """
    records = []
    for num, entry in split_entries(text):
        authors, seen = [], set()
        for author in extract_authors(entry):
            if author in seen:
                continue
            seen.add(author)
            authors.append(author)
        records.append({
            "num": num,
            "year": extract_year(entry),
            "title": extract_title(entry),
            "authors": authors,
            "entry": entry,
        })
    return records


def rank_records(records):
    """Build (ranking, author_to_refs) from a list of records.

    ranking:        list of (name, count) sorted by count desc, then name.
    author_to_refs: dict name -> list of (number, year, entry_text).
    """
    author_to_refs = defaultdict(list)
    for r in records:
        for author in r["authors"]:
            author_to_refs[author].append((r["num"], r["year"], r["entry"]))
    ranking = sorted(author_to_refs.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))
    ranking = [(name, len(refs)) for name, refs in ranking]
    return ranking, author_to_refs


def analyse(text):
    """Convenience wrapper: parse and rank in one call.

    Returns (ranking, author_to_refs, n_entries).
    """
    records = parse_records(text)
    ranking, author_to_refs = rank_records(records)
    return ranking, author_to_refs, len(records)


# --------------------------------------------------------------------------- #
#  GUI
# --------------------------------------------------------------------------- #

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Reference Author Frequency Tool")
        self.geometry("1080x720")
        self.minsize(820, 560)

        self.author_to_refs = {}
        self.records = []

        self._build_ui()

        # Work around the macOS system-Tk 8.5.9 blank-window bug: the window can
        # render all-white until it is resized. Force a redraw by nudging the
        # geometry once the event loop starts, and bring the window to the front.
        self.after(50, self._force_redraw)

    def _force_redraw(self):
        try:
            self.update_idletasks()
            self.lift()
            self.focus_force()
            geo = self.geometry()  # e.g. "1080x720+100+80"
            size, _, pos = geo.partition("+")
            w, h = (int(v) for v in size.split("x"))
            rest = "+" + pos if pos else ""
            self.geometry(f"{w + 1}x{h + 1}{rest}")
            self.update_idletasks()
            self.geometry(f"{w}x{h}{rest}")
        except Exception:
            pass

    # ---- layout ---------------------------------------------------------- #
    def _build_ui(self):
        pad = dict(padx=8, pady=6)

        # Top: input area + controls
        top = ttk.Frame(self)
        top.pack(fill="x", **pad)

        ttk.Label(top, text="Paste your references below (lines starting with [1], [2], …):",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w")

        self.input_text = tk.Text(self, height=10, wrap="word", font=("TkFixedFont", 10),
                                  undo=True)
        self.input_text.pack(fill="both", expand=False, padx=8)

        btns = ttk.Frame(self)
        btns.pack(fill="x", **pad)
        ttk.Button(btns, text="Analyze", command=self.on_analyze).pack(side="left")
        ttk.Button(btns, text="Load PDF…", command=self.on_load_pdf).pack(side="left", padx=6)
        ttk.Button(btns, text="Load text…", command=self.on_load).pack(side="left")
        ttk.Button(btns, text="Clear", command=self.on_clear).pack(side="left", padx=6)
        self.status = ttk.Label(btns, text="")
        self.status.pack(side="left", padx=12)

        # Filter row: year range + title keyword
        filt = ttk.Frame(self)
        filt.pack(fill="x", padx=8, pady=(0, 6))

        ttk.Label(filt, text="Years:").pack(side="left")
        self.year_from = ttk.Entry(filt, width=6)
        self.year_from.pack(side="left", padx=(4, 2))
        ttk.Label(filt, text="to").pack(side="left")
        self.year_to = ttk.Entry(filt, width=6)
        self.year_to.pack(side="left", padx=(2, 12))

        ttk.Label(filt, text="Title contains:").pack(side="left")
        self.keyword = ttk.Entry(filt, width=24)
        self.keyword.pack(side="left", padx=(4, 8))

        ttk.Button(filt, text="Apply filters", command=self._apply_filters).pack(side="left")
        ttk.Button(filt, text="Reset", command=self._reset_filters).pack(side="left", padx=6)

        # Apply on Enter from any filter field.
        for widget in (self.year_from, self.year_to, self.keyword):
            widget.bind("<Return>", lambda _e: self._apply_filters())

        # Bottom: split pane — ranking on left, citations on right
        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Left: ranking
        left = ttk.Frame(panes)
        ttk.Label(left, text="Authors by frequency", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        cols = ("count", "name")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("count", text="#")
        self.tree.heading("name", text="Author")
        self.tree.column("count", width=50, anchor="center", stretch=False)
        self.tree.column("name", width=240, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        tsb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        tsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=tsb.set)
        self.tree.bind("<<TreeviewSelect>>", self.on_select_author)
        panes.add(left, weight=1)

        # Right: citations for selected author
        right = ttk.Frame(panes)
        self.detail_label = ttk.Label(right, text="Citations", font=("TkDefaultFont", 11, "bold"))
        self.detail_label.pack(anchor="w")
        self.detail = tk.Text(right, wrap="word", font=("TkDefaultFont", 11), state="disabled")
        self.detail.pack(side="left", fill="both", expand=True)
        dsb = ttk.Scrollbar(right, orient="vertical", command=self.detail.yview)
        dsb.pack(side="right", fill="y")
        self.detail.configure(yscrollcommand=dsb.set)
        panes.add(right, weight=2)

    # ---- actions --------------------------------------------------------- #
    def on_load(self):
        path = filedialog.askopenfilename(
            title="Open a references file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError as exc:
            messagebox.showerror("Could not open file", str(exc))
            return
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", content)
        self.on_analyze()

    def on_load_pdf(self):
        path = filedialog.askopenfilename(
            title="Open a paper PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if not path:
            return
        self.status.config(text="Extracting PDF…")
        self.update_idletasks()
        try:
            full_text = extract_pdf_text(path)
        except RuntimeError as exc:
            self.status.config(text="")
            messagebox.showerror("Could not read PDF", str(exc))
            return

        refs_text = isolate_references(full_text)
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", refs_text)
        if not re.search(r'\[\s*\d+\s*\]', refs_text):
            messagebox.showwarning(
                "No numbered references found",
                "The extracted text doesn't seem to contain [1], [2] … style "
                "references. I've loaded the extracted text anyway — you can edit it "
                "and click Analyze, or the numbering style may differ.")
        self.on_analyze()

    def on_clear(self):
        self.input_text.delete("1.0", "end")
        self.records = []
        self.author_to_refs = {}
        self.tree.delete(*self.tree.get_children())
        self._set_detail("")
        self.status.config(text="")

    def on_analyze(self):
        text = self.input_text.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Nothing to analyze", "Paste some references first.")
            return
        # Parse once; filtering re-uses these records without re-parsing.
        self.records = parse_records(text)
        self._apply_filters()

    def _reset_filters(self):
        self.year_from.delete(0, "end")
        self.year_to.delete(0, "end")
        self.keyword.delete(0, "end")
        self._apply_filters()

    def _read_year(self, entry):
        val = entry.get().strip()
        if not val:
            return None
        m = re.search(r'\d{4}', val)
        return int(m.group(0)) if m else None

    def _apply_filters(self):
        if not self.records:
            return
        y_from = self._read_year(self.year_from)
        y_to = self._read_year(self.year_to)
        if y_from and y_to and y_from > y_to:
            y_from, y_to = y_to, y_from  # tolerate swapped bounds
        kw = self.keyword.get().strip().lower()
        year_active = y_from is not None or y_to is not None

        filtered = []
        for r in self.records:
            if kw and kw not in r["title"].lower():
                continue
            if year_active:
                if r["year"] is None:
                    continue  # can't place an undated ref in a year range
                if y_from is not None and r["year"] < y_from:
                    continue
                if y_to is not None and r["year"] > y_to:
                    continue
            filtered.append(r)

        ranking, author_to_refs = rank_records(filtered)
        self.author_to_refs = author_to_refs

        self.tree.delete(*self.tree.get_children())
        for name, count in ranking:
            self.tree.insert("", "end", iid=name, values=(count, name))

        # Build a short description of the active filters.
        bits = []
        if year_active:
            lo = y_from if y_from is not None else "…"
            hi = y_to if y_to is not None else "…"
            bits.append(f"years {lo}–{hi}")
        if kw:
            bits.append(f"title~“{kw}”")
        filt_desc = f" [filtered: {', '.join(bits)}]" if bits else ""

        if ranking:
            top_name, top_count = ranking[0]
            self.status.config(
                text=f"{len(filtered)}/{len(self.records)} refs · "
                     f"{len(ranking)} authors · top: {top_name} ({top_count}){filt_desc}")
            self.tree.selection_set(top_name)
            self.tree.focus(top_name)
            self.tree.see(top_name)
            self._show_author(top_name)
        else:
            self.status.config(
                text=f"0/{len(self.records)} refs match{filt_desc} · no authors")
            self.detail_label.config(text="Citations")
            self._set_detail("")

    def on_select_author(self, _event):
        sel = self.tree.selection()
        if sel:
            self._show_author(sel[0])

    def _show_author(self, name):
        refs = self.author_to_refs.get(name, [])
        self.detail_label.config(text=f"{name} — {len(refs)} citation(s)")

        # Summary line: sorted list of years (with counts when a year repeats).
        years = [y for _, y, _ in refs if y is not None]
        header_lines = []
        if years:
            year_counts = {}
            for y in years:
                year_counts[y] = year_counts.get(y, 0) + 1
            parts = []
            for y in sorted(year_counts):
                parts.append(f"{y}" if year_counts[y] == 1 else f"{y} (×{year_counts[y]})")
            span = f"{min(years)}–{max(years)}" if min(years) != max(years) else f"{min(years)}"
            header_lines.append(f"Years: {', '.join(parts)}")
            header_lines.append(f"Range: {span}   ·   {len(years)} dated / {len(refs)} total")
            header_lines.append("")

        body_lines = []
        for num, year, entry in refs:
            yr = year if year is not None else "n.d."
            body_lines.append(f"[{num}] ({yr}) {entry}")

        self._set_detail("\n".join(header_lines) + "\n\n".join(body_lines))

    def _set_detail(self, text):
        self.detail.config(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.config(state="disabled")


if __name__ == "__main__":
    App().mainloop()
