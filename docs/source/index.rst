.. code-index documentation master file, created by
   sphinx-quickstart on Thu Jul 31 23:55:27 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

code-index documentation
========================

A repository-level source code indexer that utilizes tree-sitter to parse source code files
and creates an index of function and method definitions and references. It supports multiple
programming languages including Python, C, and C++.

Features
--------

* **Multi-language support**: Index Python, C, and C++ source code
* **Function and method tracking**: Find definitions and references for functions and methods
* **Flexible storage**: Support for in-memory, JSON, and SQLite storage backends
* **Query interface**: Search for symbols by name, regex patterns, or exact matches
* **Tree-sitter powered**: Uses tree-sitter for accurate syntax analysis

Quick Start
-----------

Check the project `README.md` for installation instructions.

Basic usage:

.. code-block:: python

   from code_index import CodeIndexer
   from code_index.language_processor import PythonProcessor
   from pathlib import Path

   # Create an indexer for Python code
   processor = PythonProcessor()
   indexer = CodeIndexer(processor)

   # Index a project
   project_path = Path("path/to/your/project")
   indexer.index_project(project_path)

   # Find all definitions of a function
   definitions = indexer.find_definitions("my_function")
   for defn in definitions:
       print(f"Found definition at {defn.file_path}:{defn.location.start_lineno}")

Contents
--------

.. toctree::
   :maxdepth: 2
   :caption: API Documentation:

   core_api
   language_processors
   index_system
   mcp
   utilities

.. toctree::
   :maxdepth: 1
   :caption: Examples:

   examples/basic_usage

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
