#!/usr/bin/env python3
"""Call Chain Retrieval Script

Given:
1. a directory path (on local filesystem)
2. a list of function names

Generate:
a call chain retrieval report in text. at least include
the source code of each function in the call chain.
if there are multiple possible definition of a function,
include all of them.

This script:
1. uses CodeIndexer to index the codebase (no cache)
2. for each function name, uses the index interface to find definition(s) and retrieve source code
3. writes the source code to text file (markdown format)
"""

import argparse
import time
from pathlib import Path
from typing import List, Set

from code_index.index import BaseIndex, CrossRefIndex
from code_index.indexer import CodeIndexer
from code_index.language_processor import language_processor_factory
from code_index.models import Definition
from code_index.utils.logger import logger


def setup_indexer(language: str) -> CodeIndexer:
    """Set up the CodeIndexer for the specified language.

    Args:
        language: Programming language (python, c, cpp)

    Returns:
        Configured CodeIndexer instance

    Raises:
        ValueError: If no language processor found for the language
    """
    processor = language_processor_factory(language)
    if processor is None:
        raise ValueError(f"No language processor found for: {language}")

    indexer = CodeIndexer(processor=processor, index=CrossRefIndex(), store_relative_paths=True)
    logger.info(f"Initialized indexer for language: {language}")
    return indexer


def index_directory(
    indexer: CodeIndexer, directory_path: Path, dirs: List[Path] | None = None
) -> None:
    """Index the entire directory.

    Args:
        indexer: CodeIndexer instance
        directory_path: Path to directory to index
        dirs: Optional list of subdirectories to include only. If None, index all.
    """
    start_time = time.time()
    indexer.index_project(directory_path, sub_directories=dirs)

    all_functions = indexer.get_all_functions()
    logger.info(f"Indexed {len(all_functions)} functions in {time.time() - start_time:.2f} seconds")


def find_function_definitions(index: BaseIndex, function_name: str) -> List[Definition]:
    """Find all definitions for a given function name.

    Args:
        index: Code index instance
        function_name: Name of function to find

    Returns:
        List of Definition objects
    """
    from code_index.index.code_query import FilterOption, QueryByName

    responses = index.handle_query(
        QueryByName(name=function_name, type_filter=FilterOption.FUNCTION)
    )
    assert len(responses) <= 1, "Expected at most one result for function name"
    definitions = []
    for response in responses:
        definitions.extend(response.info.definitions)
    logger.info(
        f"Found {len(responses)} entries and {len(definitions)} definitions for function: {function_name}"
    )
    return definitions


def get_source_code(
    directory_path: Path, definition: Definition, context_lines: int = 0, prefix: bool = False
) -> str:
    """Extract source code for a definition with optional context.

    Args:
        directory_path: Root directory path
        definition: Definition object containing location info
        context_lines: Number of context lines to include before and after
        prefix: Whether to add line number and marker prefixes

    Returns:
        Formatted source code with line numbers
    """
    file_path = directory_path / definition.location.file_path

    if not file_path.exists():
        return f"# File not found: {definition.location.file_path}"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        start_line = max(0, definition.location.start_lineno - 1 - context_lines)
        end_line = min(len(lines), definition.location.end_lineno + context_lines)

        source_lines = []
        for i in range(start_line, end_line):
            line_num = i + 1
            if not prefix:
                pref = ""
            else:
                marker = (
                    ">>> "
                    if definition.location.start_lineno
                    <= line_num
                    <= definition.location.end_lineno
                    else "    "
                )
                pref = f"{marker}{line_num:4d}: "
            source_lines.append(pref + lines[i].rstrip("\n"))

        return "\n".join(source_lines)

    except Exception as e:
        return f"# Error reading file {definition.location.file_path}: {e}"


def write_report_header(
    file_handle,
    directory_path: Path,
    language: str,
    function_names: List[str],
    note: str | None = None,
) -> None:
    """Write the report header to the output file.

    Args:
        file_handle: Open file handle to write to
        directory_path: Directory that was analyzed
        language: Programming language
        function_names: List of function names analyzed
        note: Optional note to include in the report
    """
    file_handle.write("# Call Chain Source Code Retrieval\n\n")
    file_handle.write(f"- **Repo**: `{directory_path.name}`\n")
    file_handle.write(f"- **Language**: {language}\n")
    file_handle.write(f"- **Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    if note:
        file_handle.write(f"**Note**: {note}\n\n")
    file_handle.write("## Retrieved Functions\n\n")
    for func in function_names:
        file_handle.write(f"- `{func}`\n")
    file_handle.write("\n---\n\n")


def write_function_report(
    file_handle,
    function_name: str,
    definitions: List[Definition],
    directory_path: Path,
    indexer: CodeIndexer,
    language: str,
    prefix: bool = False,
) -> None:
    """Write the report section for a single function.

    Args:
        file_handle: Open file handle to write to
        function_name: Name of the function
        definitions: List of definitions found
        directory_path: Root directory path
        indexer: CodeIndexer instance for finding references
        language: Programming language for code formatting
        prefix: Whether to add line number and marker prefixes
    """
    file_handle.write(f"## Function: `{function_name}`\n\n")

    if not definitions:
        file_handle.write(f"**No definitions found for function `{function_name}`**\n\n")
        return

    file_handle.write(f"**Found {len(definitions)} definition(s)**\n\n")

    for i, definition in enumerate(definitions, 1):
        file_handle.write(f"- **File**: `{definition.location.file_path}`\n")
        file_handle.write(
            f"- **Line range**: {definition.location.start_lineno}-{definition.location.end_lineno}\n"
        )

        file_handle.write("\nDocstring:\n")
        if definition.doc:
            file_handle.write(f"```\n{definition.doc}\n```\n\n")
        else:
            file_handle.write("_No docstring available_\n\n")

        source_code = get_source_code(directory_path, definition, prefix=prefix)
        file_handle.write(f"```\n{source_code}\n```\n\n")


def generate_call_chain_report(
    directory_path: Path,
    function_names: List[str],
    language: str,
    output_file: Path,
    dirs: List[Path] | None = None,
    note: str | None = None,
) -> None:
    """Generate call chain report for the specified functions.

    Args:
        directory_path: Path to directory to analyze
        function_names: List of function names to analyze
        language: Programming language
        output_file: Output file path for the report
        dirs: Optional list of subdirectories to include only. If None, index all.
        note: Optional note to include in the report
    """
    # Setup indexer
    indexer = setup_indexer(language)

    # Index the directory
    logger.info("Indexing directory...")
    index_directory(indexer, directory_path, dirs)

    # Generate report
    logger.info(f"Generating report for functions: {', '.join(function_names)}")

    processed_functions: Set[str] = set()

    with open(output_file, "w", encoding="utf-8") as f:
        write_report_header(f, directory_path, language, function_names, note)

        for function_name in function_names:
            if function_name in processed_functions:
                continue

            definitions = find_function_definitions(indexer.index, function_name)
            write_function_report(f, function_name, definitions, directory_path, indexer, language)

            processed_functions.add(function_name)
            f.write("---\n\n")

    logger.info(f"Call chain report written to: {output_file}")


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Retrieve call chains for specified functions from a directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze Python functions
  python call_chain_retrieval.py /path/to/code --functions main setup_app

  # Analyze C functions with custom output
  python call_chain_retrieval.py /path/to/code --language c --functions malloc free --output my_report.md

  # Multiple functions
  python call_chain_retrieval.py /path/to/code --functions func1 func2 func3
        """,
    )

    parser.add_argument("directory_path", type=Path, help="Path to the directory to analyze")

    parser.add_argument(
        "--dirs",
        "-d",
        nargs="+",
        type=Path,
        default=None,
        help="Optional list of subdirectories to include only (default: include all subdirectories of the repo)",
    )

    parser.add_argument(
        "--functions", "-f", nargs="+", required=True, help="List of function names to analyze"
    )

    parser.add_argument(
        "--language",
        "-l",
        type=str,
        default="python",
        choices=["python", "c", "cpp"],
        help="Programming language of the code (default: python)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output file path (default: call_chain_report_<timestamp>.md)",
    )

    return parser.parse_args()


def validate_arguments(args: argparse.Namespace) -> bool:
    """Validate command line arguments.

    Args:
        args: Parsed arguments

    Returns:
        True if valid, False otherwise
    """
    # Validate directory path
    if not args.directory_path.exists():
        logger.error(f"Directory path does not exist: {args.directory_path}")
        return False

    if not args.directory_path.is_dir():
        logger.error(f"Path is not a directory: {args.directory_path}")
        return False

    # Set default output file if not specified
    if args.output is None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        args.output = Path(f"call_chain_report_{timestamp}.md")

    return True


def main() -> int:
    """Main function with CLI interface.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Parse and validate arguments
    args = parse_arguments()

    if not validate_arguments(args):
        return 1

    try:
        logger.info("Starting call chain retrieval process...")
        logger.info(f"Analyzing directory: {args.directory_path}")

        # Generate the report
        generate_call_chain_report(
            directory_path=args.directory_path,
            function_names=args.functions,
            language=args.language,
            output_file=args.output,
        )

        logger.info("✅ Call chain retrieval completed successfully!")
        logger.info(f"Report saved to: {args.output}")

        return 0

    except Exception as e:
        logger.error(f"❌ Error during call chain retrieval: {e}")
        return 1


def join_files(output_file: Path, input_files: List[Path]):
    with open(output_file, "w", encoding="utf-8") as outfile:
        for fname in input_files:
            with open(fname, "r", encoding="utf-8") as infile:
                outfile.write(infile.read())
                outfile.write("\n\n---\n\n")
    logger.info(f"Joined files into: {output_file}")


if __name__ == "__main__":
    exit(main())
