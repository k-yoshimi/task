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

.PHONY: all html en ja clean linkcheck-en linkcheck-ja livehtml-en livehtml-ja help

all: html
html: en ja

en:
	$(SPHINXBUILD) -b html $(SPHINXOPTS) en $(BUILDDIR)/en

ja:
	$(SPHINXBUILD) -b html $(SPHINXOPTS) ja $(BUILDDIR)/ja

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
	@echo "Targets: html (default), en, ja, linkcheck-en, linkcheck-ja,"
	@echo "         livehtml-en, livehtml-ja, clean"
	@echo "Override SPHINXOPTS='' to tolerate warnings during local dev."
