# Build the TASK library manual (English + Japanese).
#
# Usage:
#   make          # builds both trees into _build/{en,ja}
#   make en       # only English
#   make ja       # only Japanese
#   make clean
#   make linkcheck-en / linkcheck-ja
#   make livehtml-en  (requires `pip install sphinx-autobuild`)

SPHINXBUILD   ?= sphinx-build
BUILDDIR      ?= _build

# `-W --keep-going` is enforced by CI; for local dev, override with
#   make SPHINXOPTS=""
# to tolerate warnings. `-n` (nitpicky mode) is opt-in — many existing
# wrapper docstrings use unqualified :class: refs that would otherwise
# warn; when those are hardened, promote `-n` to the default.
SPHINXOPTS    ?= -W --keep-going

.PHONY: all html en ja pdf pdf-en pdf-ja clean linkcheck-en linkcheck-ja livehtml-en livehtml-ja help

all: html
html: en ja
pdf: pdf-en pdf-ja

en:
	$(SPHINXBUILD) -b html $(SPHINXOPTS) en $(BUILDDIR)/en

ja:
	$(SPHINXBUILD) -b html $(SPHINXOPTS) ja $(BUILDDIR)/ja

# PDF via xelatex (see conf_common.py:latex_elements for the preamble).
# We skip latexmk's orchestration and run xelatex → xdvipdfmx directly:
# latexmk's default "-pdf" pipeline expects pdflatex-style output; with
# xelatex it writes .xdv and latexmk sometimes flags that as failure.
# Three xelatex passes: (1) aux, (2) toc & longtable widths, (3) settle
# TOC page numbers that the longtable-driven repagination of pass 2 can
# invalidate. Autodoc-heavy Sphinx documents commonly need this third
# pass; the extra ~1s build cost is worth TOC correctness.
pdf-en:
	$(SPHINXBUILD) -b latex $(SPHINXOPTS) en $(BUILDDIR)/latex-en
	cd $(BUILDDIR)/latex-en && xelatex -no-pdf -interaction=nonstopmode task_manual.tex > /dev/null
	cd $(BUILDDIR)/latex-en && xelatex -no-pdf -interaction=nonstopmode task_manual.tex > /dev/null
	cd $(BUILDDIR)/latex-en && xelatex -no-pdf -interaction=nonstopmode task_manual.tex > /dev/null
	cd $(BUILDDIR)/latex-en && xdvipdfmx task_manual.xdv
	@echo "PDF ready: $(BUILDDIR)/latex-en/task_manual.pdf"

pdf-ja:
	$(SPHINXBUILD) -b latex $(SPHINXOPTS) ja $(BUILDDIR)/latex-ja
	cd $(BUILDDIR)/latex-ja && xelatex -no-pdf -interaction=nonstopmode task_manual.tex > /dev/null
	cd $(BUILDDIR)/latex-ja && xelatex -no-pdf -interaction=nonstopmode task_manual.tex > /dev/null
	cd $(BUILDDIR)/latex-ja && xelatex -no-pdf -interaction=nonstopmode task_manual.tex > /dev/null
	cd $(BUILDDIR)/latex-ja && xdvipdfmx task_manual.xdv
	@echo "PDF ready: $(BUILDDIR)/latex-ja/task_manual.pdf"

linkcheck-en:
	$(SPHINXBUILD) -b linkcheck $(SPHINXOPTS) en $(BUILDDIR)/linkcheck-en

linkcheck-ja:
	$(SPHINXBUILD) -b linkcheck $(SPHINXOPTS) ja $(BUILDDIR)/linkcheck-ja

livehtml-en:
	sphinx-autobuild -b html $(SPHINXOPTS) en $(BUILDDIR)/en

livehtml-ja:
	sphinx-autobuild -b html $(SPHINXOPTS) ja $(BUILDDIR)/ja

clean:
	rm -rf $(BUILDDIR)

help:
	@echo "Targets: html (default), en, ja,"
	@echo "         pdf, pdf-en, pdf-ja   (requires xelatex + CJK fonts)"
	@echo "         linkcheck-en, linkcheck-ja,"
	@echo "         livehtml-en, livehtml-ja, clean"
	@echo "Override SPHINXOPTS='' to tolerate warnings during local dev."
