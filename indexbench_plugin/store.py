"""Where the database and the results log live: the temp folder, kept between runs
until Build index replaces the database."""

import os
import tempfile

DB_DIR = os.path.join(tempfile.gettempdir(), "megaexplorer-indexbench")
DB_PATH = os.path.join(DB_DIR, "index.sqlite")
LOG_PATH = os.path.join(DB_DIR, "results.log")
