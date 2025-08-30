from pathlib import Path
from typing import Optional

from tqdm import tqdm
from tree_sitter import Tree

from .index.base import BaseIndex, PersistStrategy
from .index.impl.simple_index import SimpleIndex
from .language_processor import LanguageProcessor, QueryContext
from .models import (
    Definition,
    Function,
    FunctionLikeInfo,
    Method,
    Reference,
    Symbol,
)
from .utils.logger import logger


class CodeIndexer:
    """A repository-level source code indexer for analyzing and indexing code symbols.

    This class provides functionality to parse source code files using tree-sitter
    and create an index of function and method definitions and references. It supports
    multiple programming languages through configurable language processors.

    The indexer can process individual files or entire project directories, extracting
    symbol information and storing it in a configurable index backend for later
    retrieval and analysis.
    """

    def __init__(
        self,
        processor: LanguageProcessor,
        index: BaseIndex | None = None,
        store_relative_paths: bool = True,
    ):
        """Initializes the CodeIndexer with the specified configuration.

        Args:
            processor: The language processor instance used to parse source code files.
                This processor defines which programming language(s) will be supported
                and how the parsing will be performed.
            index: The index backend for storing symbol information. If None, defaults
                to SimpleIndex. This allows for different storage strategies (in-memory,
                database, etc.).
            store_relative_paths: Whether to store file paths relative to the project
                root directory. If True (default), paths are stored relative to the
                project root. If False, absolute paths are used.

        Note:
            The processor's supported file extensions determine which files will be
            processed during indexing operations.

        Example:
            Here is a basic example of how to use the CodeIndexer to index a project, find definitions
            and references of a function, and persist the index to a JSON file.

            .. code-block:: python

                from pathlib import Path
                from code_index import CodeIndexer
                from code_index.language_processor import PythonProcessor
                from code_index.index.persist import SingleJsonFilePersistStrategy

                # Initialize the indexer with a Python language processor
                indexer = CodeIndexer(PythonProcessor())

                # Index a project directory
                indexer.index_project(Path("/path/to/project"))

                # Find definitions of a specific function
                definitions = indexer.find_definitions("my_function")
                for defn in definitions:
                    print(
                        f"Found definition at {defn.location.file_path}:{defn.location.start_lineno}"
                    )

                # Find references to a specific function
                references = indexer.find_references("my_function")
                for ref in references:
                    print(
                        f"Found reference at {ref.location.file_path}:{ref.location.start_lineno}"
                    )

                # Save the index to a JSON file
                indexer.dump_index(Path("index.json"), SingleJsonFilePersistStrategy())

        """
        logger.debug("Initializing CodeIndexer...")

        self._processor: LanguageProcessor = processor
        self._index: BaseIndex = index if index is not None else SimpleIndex()
        self._store_relative_paths: bool = store_relative_paths

    def __str__(self):
        """Returns a string representation of the CodeIndexer instance.

        Returns:
            A formatted string containing the processor, index, and configuration
            details of this CodeIndexer instance.
        """
        return (
            f"CodeIndexer(processor={self._processor.__str__()}, "
            f"index={self._index.__str__()}, "
            f"store_relative_paths={self._store_relative_paths})"
        )

    @property
    def processor(self) -> LanguageProcessor:
        """Gets the language processor used by this indexer.

        Returns:
            The LanguageProcessor instance configured for this indexer.
        """
        return self._processor

    @property
    def index(self):
        """Gets the index backend used by this indexer.

        Returns:
            The BaseIndex instance used for storing and retrieving symbol information.
        """
        return self._index

    def _process_definitions(
        self,
        tree: Tree,
        source_bytes: bytes,
        file_path: Path,
        processor: LanguageProcessor | None = None,
    ):
        """Processes and indexes all function and method definitions in a parsed AST.

        This method extracts function and method definitions from the abstract syntax
        tree and adds them to the index. It handles both standalone functions and
        class methods.

        Args:
            tree: The parsed abstract syntax tree from tree-sitter.
            source_bytes: The raw source code as bytes, used for extracting
                symbol text and position information.
            file_path: The path to the source file being processed.
            processor: Optional language processor to use. If None, uses the
                indexer's default processor.

        Note:
            This is an internal method that processes definition nodes identified
            by the language processor and adds them to the index storage.
        """
        if processor is None:
            processor = self._processor
        context = QueryContext(file_path=file_path, source_bytes=source_bytes)
        for node in processor.get_definition_nodes(tree.root_node):
            match processor.handle_definition(node, context):
                case (Function() | Method() as symbol, Definition() as def_):
                    self._index.add_definition(symbol, def_)
                case None:
                    pass

    def _process_references(
        self,
        tree: Tree,
        source_bytes: bytes,
        file_path: Path,
        processor: LanguageProcessor | None = None,
    ):
        """Processes and indexes all function and method references in a parsed AST.

        This method extracts function and method call sites from the abstract syntax
        tree and adds them to the index. It identifies where functions and methods
        are being invoked or referenced in the code.

        Args:
            tree: The parsed abstract syntax tree from tree-sitter.
            source_bytes: The raw source code as bytes, used for extracting
                reference text and position information.
            file_path: The path to the source file being processed.
            processor: Optional language processor to use. If None, uses the
                indexer's default processor.

        Note:
            This is an internal method that processes reference nodes identified
            by the language processor and adds them to the index storage.
        """
        if processor is None:
            processor = self._processor
        context = QueryContext(file_path=file_path, source_bytes=source_bytes)
        for node in processor.get_reference_nodes(tree.root_node):
            match processor.handle_reference(node, context):
                case (Function() | Method() as symbol, Reference() as ref):
                    self._index.add_reference(symbol, ref)
                case None:
                    pass

    def index_file(
        self, file_path: Path, project_path: Path, processor: Optional[LanguageProcessor] = None
    ):
        """Parses and indexes a single source code file.

        This method processes a single file, extracting function and method definitions
        and references. It will attempt to parse files even if their extension is not
        in the processor's supported extension list, logging a warning in such cases.

        Args:
            file_path: The path to the source file to be indexed. Must be a valid file.
            project_path: The root path of the project, used for calculating relative
                paths when store_relative_paths is True.
            processor: Optional language processor to use for this file. If None,
                uses the indexer's default processor.

        Note:
            If the file cannot be read due to I/O errors, the operation will be
            skipped with an error log. Non-file paths are also skipped with a warning.

        Example:
            .. code-block:: python

                indexer.index_file(Path("src/main.py"), Path("src/"))
        """
        if not file_path.is_file():
            logger.warning(f"Skipping non-file path: {file_path}")
            return
        if file_path.suffix not in self._processor.extensions:
            logger.warning(
                f"Unsupported file extension {file_path.suffix} for file {file_path}. Trying to parse anyway."
            )

        if processor is None:
            processor = self._processor

        parser = processor.parser
        lang_name = processor.name
        try:
            source_bytes = file_path.read_bytes()
            logger.debug(f"Indexing file: {file_path} as {lang_name}")
        except IOError as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return

        tree = parser.parse(source_bytes)

        if self._store_relative_paths:
            file_path = file_path.relative_to(project_path)

        self._process_definitions(tree, source_bytes, file_path, self._processor)
        self._process_references(tree, source_bytes, file_path, self._processor)

    def index_project(self, project_path: Path, sub_directories: list[Path] | None = None):
        """Recursively indexes all supported files in a project directory.

        This method walks through the entire project directory tree and indexes
        all files with extensions supported by the configured language processor.
        Only files matching the processor's supported extensions are processed.

        Args:
            project_path: The root directory path of the project to be indexed.
                All subdirectories will be recursively processed.
            sub_directories: Optional list of subdirectory paths (relative to the
                project root) to limit indexing to. If None, the entire project
                directory is processed.

        Note:
            Files with unsupported extensions are automatically skipped.
            The indexing progress is logged at info level with start and
            completion messages.

        Example:
            .. code-block:: python

                indexer.index_project(Path("/path/to/project"))
        """
        logger.info(f"Starting to index project at: {project_path}")
        files_to_index = []
        if sub_directories:
            for sub_dir in sub_directories:
                full_sub_dir = project_path / sub_dir
                if not full_sub_dir.is_dir():
                    if full_sub_dir.is_file():
                        # add the file to the list
                        files_to_index.append(full_sub_dir)
                files_to_index.extend(full_sub_dir.rglob("*"))
        else:
            files_to_index = list(project_path.rglob("*"))

        logger.info(f"Found {len(files_to_index)} files to index.")

        for file_path in tqdm(files_to_index):
            if not file_path.is_file():
                continue
            if file_path.suffix not in self._processor.extensions:
                continue
            self.index_file(file_path, project_path, self._processor)
        logger.info("Project indexing complete.")

    def find_definitions(self, name: str) -> list[Definition]:
        """Finds all definitions of functions or methods with the given name.

        Searches the index for all definition locations of functions or methods
        that match the specified name. This includes both standalone functions
        and class methods.

        Args:
            name: The name of the function or method to search for.

        Returns:
            A list of Definition objects containing location and context information
            for each found definition. Returns an empty list if no definitions are found.

        Example:
            .. code-block:: python

                definitions = indexer.find_definitions("calculate_total")
                for defn in definitions:
                    print(
                        f"Found definition at {defn.location.file_path}:{defn.location.start_lineno}"
                    )
                # Output: Found definition at src/utils.py:15

        """
        # 创建一个临时的Function对象来查找
        func = Function(name=name)
        return list(self._index.get_definitions(func))

    def find_references(self, name: str) -> list[Reference]:
        """Finds all references to functions or methods with the given name.

        Searches the index for all locations where functions or methods with the
        specified name are called or referenced. This includes function calls,
        method invocations, and other forms of symbol references.

        Args:
            name: The name of the function or method to search for.

        Returns:
            A list of PureReference objects containing location and context information
            for each found reference. Returns an empty list if no references are found.

        Example:
            .. code-block:: python

                references = indexer.find_references("calculate_total")
                for ref in references:
                    print(
                        f"Found reference at {ref.location.file_path}:{ref.location.start_lineno}"
                    )
                # Output: Found reference at src/main.py:42

        """
        # 创建一个临时的Function对象来查找
        func = Function(name=name)
        return list(self._index.get_references(func))

    def dump_index(self, output_path: Path, persist_strategy: PersistStrategy):
        """Persists the current index data to a file using the specified strategy.

        Saves all indexed symbol information to persistent storage. The format
        and structure of the saved data depends on the persistence strategy used.

        Args:
            output_path: The file path where the index data should be saved.
            persist_strategy: The persistence strategy that defines how the data
                should be serialized and stored (e.g., JSON, SQLite, etc.).

        Raises:
            IOError: If the file cannot be written due to permission or disk issues.

        Example:
            .. code-block:: python

                from code_index.index.persist import JSONPersistStrategy

                indexer.dump_index(Path("index.json"), JSONPersistStrategy())
        """
        self.index.persist_to(output_path, persist_strategy)

    def load_index(self, input_path: Path, persist_strategy: PersistStrategy):
        """Loads index data from a file using the specified strategy.

        Replaces the current index with data loaded from persistent storage.
        The format and structure of the loaded data depends on the persistence
        strategy used, which should match the strategy used when saving.

        Args:
            input_path: The file path from which to load the index data.
            persist_strategy: The persistence strategy that defines how the data
                should be deserialized and loaded (e.g., JSON, SQLite, etc.).

        Raises:
            IOError: If the file cannot be read due to permission or existence issues.
            ValueError: If the file format is invalid or incompatible.

        Note:
            This operation completely replaces the current index. Any unsaved
            indexing work will be lost.

        Example:
            .. code-block:: python

                from code_index.index.persist import JSONPersistStrategy

                indexer.load_index(Path("index.json"), JSONPersistStrategy())
        """
        self._index = self.index.__class__.load_from(input_path, persist_strategy)

    def get_function_info(self, func_like: Symbol) -> Optional[FunctionLikeInfo]:
        """Retrieves comprehensive information about a specific function or method.

        Gets detailed information about a function or method, including its
        definitions, references, and other metadata stored in the index.

        Args:
            func_like: A Symbol object (Function or Method) representing
                the symbol to retrieve information for.

        Returns:
            A FunctionLikeInfo object containing comprehensive information about
            the symbol, including all its definitions and references. Returns None
            if the symbol is not found in the index.

        Example:
            .. code-block:: python

                func = Function(name="calculate_total")
                info = indexer.get_function_info(func)
                if info:
                    print(f"Function has {len(info.definitions)} definitions")
                    print(f"Function has {len(info.references)} references")
        """
        return self._index.get_info(func_like)

    def get_all_functions(self) -> list[Symbol]:
        """Retrieves all functions and methods stored in the index.

        Returns a list of all Symbol objects (Functions and Methods) that
        have been indexed. This provides a complete overview of all symbols
        tracked by the indexer.

        Returns:
            A list of Symbol objects representing all indexed functions
            and methods. Returns an empty list if no symbols have been indexed.

        Example:
            .. code-block:: python

                all_functions = indexer.get_all_functions()
                print(f"Index contains {len(all_functions)} functions/methods")
                # Output: Index contains 42 functions/methods
                for func in all_functions:
                    print(f"- {func.name}")
                # Output:
                # - calculate_total
                # - process_data
        """
        return list(self._index.__iter__())

    def clear_index(self):
        """Clears all indexed data and resets the index to an empty state.

        Removes all definitions, references, and other symbol information from
        the index. This operation cannot be undone unless the index data has
        been previously saved using dump_index().

        Note:
            This creates a new instance of the same index class, ensuring a
            completely clean state while maintaining the same index configuration.

        Example:
            .. code-block:: python

                indexer.clear_index()
                print(f"Index now contains {len(indexer.get_all_functions())} functions")
                # Output: Index now contains 0 functions
        """
        # 重新创建一个新的索引实例
        self._index = self._index.__class__()
