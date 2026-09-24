# Reference Author Frequency Tool

A small Tkinter desktop app that reads a paper's references (pasted text, a `.txt`
file, or a **PDF**), ranks the authors by how many references they appear in, and —
for the selected author — lists their citations and the **years** those references
were published.

---

## Requirements

- **Python 3.9+** with **Tkinter** (Tkinter ships with the Python standard library
  — it is not a pip package).
- Python packages in [`requirements.txt`](requirements.txt): `pymupdf`, `pypdf`
  (only needed for PDF input; pasting/loading text works without them).

> **macOS note:** the system Python's Tk (8.5.9) has a bug where the window can
> appear all-white until resized. The app already works around this, but for the
> best result use a Python that bundles a modern Tk 8.6 (see Troubleshooting).

---

## Setup — create a virtual environment

From a terminal, in the project folder:

```bash
cd path/to/AC_Reference_Tool     # the folder containing this project

# 1. Create the virtual environment with Python 3.13 (bundles modern Tk 9.0)
/opt/homebrew/bin/python3.13 -m venv .venv

# 2. Activate it
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows (PowerShell/cmd)

# 3. Upgrade pip and install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

With the virtual environment activated:

```bash
python reference_author_tool.py
```

To leave the environment when you're done:

```bash
deactivate
```

---

## Usage

1. **Load PDF…** — pick a paper's PDF. The tool extracts the text, finds the
   *References* section, and analyses it automatically.
2. **Load text…** — load a `.txt` file of references, or just paste them into the
   box and click **Analyze**.
3. The left panel ranks authors by citation count; the most frequent is selected
   automatically. Use the **Find author** box above the list to filter it to names
   containing what you type (counts are unchanged — it just narrows the display).
4. The right panel shows the selected author's citations, led by their list of
   publication **years** and the year range.

### Filters

A filter row sits under the buttons; both narrow the reference set *before*
ranking, so only matching authors and citations are shown:

- **Years … to …** — keep only references whose year falls in the range. Leave one
  box empty for an open bound (e.g. `2022` to blank = 2022 onward). Undated
  references are excluded while a year filter is active.
- **Title contains** — keep only references whose title contains the keyword
  (case-insensitive). Useful for finding who publishes on a topic, e.g. `handover`.

Press **Enter** in any filter box or click **Apply filters**; **Reset** clears
them. The status line shows how many references matched (e.g. `18/141 refs`).

### Excluding papers and authors (self-citation handling)

Authors often cite themselves, which inflates the counts. You can remove items
from the tally:

- **Exclude a paper** — click the red **✕** next to any citation in the right
  panel. The whole reference leaves the pool, so its co-authors also stop getting
  credit for it.
- **Exclude an author** — click the **✕** in the first column of the ranking
  table. That person is dropped from the ranking (their co-authored papers still
  count towards everyone else).

Excluded items appear as chips in the **Excluded** bar; click a chip to restore
it, or **Clear all** to reset. Exclusions clear automatically when you analyse a
new set of references.

References are expected in numbered style (`[1]`, `[2]`, …), ACM/IEEE-like:

```
[1] Naoko Abe, Yue Hu, and Eiichi Yoshida. 2024. Human understanding of robot action. ...
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'tkinter'`
Your Python was built without Tk. Install a Python that includes it:

- **macOS (Homebrew):** `brew install python-tk@3.13`, then run with
  `/opt/homebrew/bin/python3.13`.
- **Or** install Python from [python.org](https://www.python.org/downloads/),
  which bundles Tk 8.6.
- **Ubuntu/Debian:** `sudo apt install python3-tk`.

### Window appears all white (macOS)
This is the old system-Tk 8.5.9 bug. The app auto-nudges the window to force a
redraw; if it persists, run under a Python with Tk 8.6 (see above). You can check
your Tk version with:

```bash
python -c "import tkinter; r=tkinter.Tk(); print(r.tk.call('info','patchlevel'))"
```

### PDF loads but no references are found
PDF text extraction of two-column papers can occasionally merge or mangle lines.
The extracted text stays editable in the box — fix any issues and click
**Analyze**, or the paper may use a non-`[n]` numbering style.
