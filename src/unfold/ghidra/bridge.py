"""Ghidra bridge using PyGhidra for native Python access to the Ghidra API."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Global flag to track if PyGhidra/JVM has been started
_ghidra_started = False


def _ensure_ghidra_started():
    """Start PyGhidra/JVM if not already running."""
    global _ghidra_started
    if _ghidra_started:
        return

    import pyghidra

    if not pyghidra.started():
        from unfold.utils import find_ghidra_install

        install_dir = find_ghidra_install()
        os.environ.setdefault(
            "JAVA_HOME",
            "/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home",
        )
        logger.info("Starting PyGhidra with Ghidra at %s", install_dir)
        pyghidra.start(install_dir=install_dir)

    _ghidra_started = True


class GhidraBridge:
    """Direct Python bridge to Ghidra via PyGhidra."""

    def __init__(self, project_dir: Path | None = None):
        _ensure_ghidra_started()

        if project_dir is None:
            project_dir = Path.home() / ".unfold" / "projects"
        self.project_dir = Path(project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)

        # Cache: binary_path -> project_name
        self._project_names: dict[str, str] = {}

    def _get_project_name(self, binary_path: Path) -> str:
        key = str(binary_path.resolve())
        if key not in self._project_names:
            h = hashlib.md5(key.encode()).hexdigest()[:8]
            self._project_names[key] = f"{binary_path.stem}_{h}"
        return self._project_names[key]

    def _open_project(self, binary_path: Path):
        """Open or create a Ghidra project for the binary."""
        import pyghidra

        project_name = self._get_project_name(binary_path)
        project_location = self.project_dir / project_name
        project_location.mkdir(parents=True, exist_ok=True)

        return pyghidra.open_project(project_location, project_name, create=True)

    def _get_program(self, project, binary_path: Path):
        """Get program from project, importing if necessary."""
        import pyghidra

        program_name = binary_path.name
        try:
            program, consumer = pyghidra.consume_program(project, f"/{program_name}")
            return program, consumer
        except FileNotFoundError:
            # Need to import
            return self._import_binary(project, binary_path)

    def _import_binary(self, project, binary_path: Path):
        """Import a binary into the project."""
        from ghidra.app.util.importer import AutoImporter, MessageLog
        from ghidra.util.task import TaskMonitor
        from java.io import File as JFile  # type: ignore
        from java.lang import Object  # type: ignore

        consumer = Object()
        msg_log = MessageLog()
        j_file = JFile(str(binary_path))
        load_results = AutoImporter.importByUsingBestGuess(
            j_file,
            project,
            "/",
            consumer,
            msg_log,
            TaskMonitor.DUMMY,
        )
        if load_results is None:
            raise RuntimeError(f"Ghidra failed to import '{binary_path}'")

        # Get the primary loaded program
        primary = load_results.getPrimaryDomainObject()
        if primary is None:
            raise RuntimeError(f"No primary program from import of '{binary_path}'")

        load_results.save(TaskMonitor.DUMMY)
        return primary, consumer

    def _analyze_program(self, program):
        """Run Ghidra auto-analysis on the program."""
        import pyghidra

        from ghidra.program.util import GhidraProgramUtilities

        if GhidraProgramUtilities.shouldAskToAnalyze(program):
            logger.info("Running analysis on %s", program.getName())
            pyghidra.analyze(program)

    def analyze(self, binary_path: Path) -> dict:
        """Import and analyze a binary. Returns analysis summary."""
        binary_path = Path(binary_path).resolve()
        if not binary_path.exists():
            raise FileNotFoundError(f"Binary not found: {binary_path}")

        project = self._open_project(binary_path)
        try:
            program, consumer = self._get_program(project, binary_path)
            try:
                self._analyze_program(program)

                result = {
                    "name": str(program.getName()),
                    "language": str(program.getLanguage().getLanguageID()),
                    "compiler": str(program.getCompilerSpec().getCompilerSpecID()),
                    "image_base": f"0x{program.getImageBase().getOffset():x}",
                    "num_functions": program.getFunctionManager().getFunctionCount(),
                    "executable_format": str(program.getExecutableFormat()),
                }

                program.save("Analysis complete", None)
                return result
            finally:
                program.release(consumer)
        finally:
            project.close()

    def list_functions(self, binary_path: Path) -> list[dict]:
        """List all functions in the binary."""
        binary_path = Path(binary_path).resolve()
        project = self._open_project(binary_path)
        try:
            program, consumer = self._get_program(project, binary_path)
            try:
                self._analyze_program(program)
                fm = program.getFunctionManager()
                funcs = []
                for f in fm.getFunctions(True):
                    funcs.append(
                        {
                            "name": str(f.getName()),
                            "address": f"0x{f.getEntryPoint().getOffset():x}",
                            "size": f.getBody().getNumAddresses(),
                            "is_thunk": bool(f.isThunk()),
                            "is_external": bool(f.isExternal()),
                        }
                    )
                return funcs
            finally:
                program.release(consumer)
        finally:
            project.close()

    def decompile(self, binary_path: Path, function: str) -> dict:
        """Decompile a specific function by name or address."""
        binary_path = Path(binary_path).resolve()
        project = self._open_project(binary_path)
        try:
            program, consumer = self._get_program(project, binary_path)
            try:
                self._analyze_program(program)
                func = self._resolve_function(program, function)
                if func is None:
                    return {"error": f"Function not found: {function}"}

                from ghidra.app.decompiler import DecompInterface
                from ghidra.util.task import TaskMonitor

                decomp = DecompInterface()
                decomp.openProgram(program)
                try:
                    result = decomp.decompileFunction(func, 60, TaskMonitor.DUMMY)
                    decomp_func = result.getDecompiledFunction()
                    if decomp_func is not None:
                        code = str(decomp_func.getC())
                        return {
                            "name": str(func.getName()),
                            "address": f"0x{func.getEntryPoint().getOffset():x}",
                            "decompiled": code,
                            "signature": str(func.getSignature()),
                        }
                    else:
                        return {"error": f"Decompilation failed for {func.getName()}"}
                finally:
                    decomp.dispose()
            finally:
                program.release(consumer)
        finally:
            project.close()

    def get_xrefs_to(self, binary_path: Path, target: str) -> list[dict]:
        """Get cross-references TO a function/address."""
        binary_path = Path(binary_path).resolve()
        project = self._open_project(binary_path)
        try:
            program, consumer = self._get_program(project, binary_path)
            try:
                self._analyze_program(program)
                addr = self._resolve_address(program, target)
                if addr is None:
                    return [{"error": f"Could not resolve: {target}"}]

                ref_mgr = program.getReferenceManager()
                fm = program.getFunctionManager()
                refs = []
                for ref in ref_mgr.getReferencesTo(addr):
                    from_func = fm.getFunctionContaining(ref.getFromAddress())
                    refs.append(
                        {
                            "from_address": f"0x{ref.getFromAddress().getOffset():x}",
                            "from_function": str(from_func.getName())
                            if from_func
                            else None,
                            "type": str(ref.getReferenceType()),
                        }
                    )
                return refs
            finally:
                program.release(consumer)
        finally:
            project.close()

    def get_xrefs_from(self, binary_path: Path, target: str) -> list[dict]:
        """Get cross-references FROM a function/address."""
        binary_path = Path(binary_path).resolve()
        project = self._open_project(binary_path)
        try:
            program, consumer = self._get_program(project, binary_path)
            try:
                self._analyze_program(program)
                addr = self._resolve_address(program, target)
                if addr is None:
                    return [{"error": f"Could not resolve: {target}"}]

                ref_mgr = program.getReferenceManager()
                fm = program.getFunctionManager()
                refs = []
                for ref in ref_mgr.getReferencesFrom(addr):
                    to_func = fm.getFunctionContaining(ref.getToAddress())
                    refs.append(
                        {
                            "to_address": f"0x{ref.getToAddress().getOffset():x}",
                            "to_function": str(to_func.getName())
                            if to_func
                            else None,
                            "type": str(ref.getReferenceType()),
                        }
                    )
                return refs
            finally:
                program.release(consumer)
        finally:
            project.close()

    def get_strings(self, binary_path: Path) -> list[dict]:
        """Get all strings in the binary."""
        binary_path = Path(binary_path).resolve()
        project = self._open_project(binary_path)
        try:
            program, consumer = self._get_program(project, binary_path)
            try:
                self._analyze_program(program)
                # Iterate over all defined data looking for strings
                listing = program.getListing()
                mem = program.getMemory()
                strings = []
                data_iter = listing.getDefinedData(True)
                while data_iter.hasNext():
                    data = data_iter.next()
                    dt = data.getDataType()
                    if "string" in str(dt.getName()).lower():
                        val = data.getValue()
                        if val is not None:
                            strings.append(
                                {
                                    "address": f"0x{data.getAddress().getOffset():x}",
                                    "value": str(val),
                                    "length": len(str(val)),
                                }
                            )
                return strings
            finally:
                program.release(consumer)
        finally:
            project.close()

    def get_imports_exports(self, binary_path: Path) -> dict:
        """Get imported and exported symbols."""
        binary_path = Path(binary_path).resolve()
        project = self._open_project(binary_path)
        try:
            program, consumer = self._get_program(project, binary_path)
            try:
                self._analyze_program(program)
                sym_table = program.getSymbolTable()
                fm = program.getFunctionManager()

                imports = []
                for sym in sym_table.getExternalSymbols():
                    imports.append(
                        {
                            "name": str(sym.getName()),
                            "namespace": str(sym.getParentNamespace()),
                            "type": str(sym.getSymbolType()),
                        }
                    )

                exports = []
                for f in fm.getFunctions(True):
                    if not f.isExternal() and not f.isThunk():
                        sym = f.getSymbol()
                        if sym is not None and sym.isGlobal():
                            exports.append(
                                {
                                    "name": str(f.getName()),
                                    "address": f"0x{f.getEntryPoint().getOffset():x}",
                                }
                            )

                return {"imports": imports, "exports": exports}
            finally:
                program.release(consumer)
        finally:
            project.close()

    def rename_function(
        self, binary_path: Path, target: str, new_name: str
    ) -> dict:
        """Rename a function."""
        binary_path = Path(binary_path).resolve()
        project = self._open_project(binary_path)
        try:
            program, consumer = self._get_program(project, binary_path)
            try:
                self._analyze_program(program)
                func = self._resolve_function(program, target)
                if func is None:
                    return {"error": f"Function not found: {target}"}

                import pyghidra
                from ghidra.program.model.symbol import SourceType

                old_name = str(func.getName())
                with pyghidra.transaction(program, "Rename function"):
                    func.setName(new_name, SourceType.USER_DEFINED)

                program.save("Renamed function", None)
                return {
                    "old_name": old_name,
                    "new_name": new_name,
                    "address": f"0x{func.getEntryPoint().getOffset():x}",
                }
            finally:
                program.release(consumer)
        finally:
            project.close()

    def read_bytes(self, binary_path: Path, address: str, count: int) -> dict:
        """Read raw bytes at an address."""
        binary_path = Path(binary_path).resolve()
        project = self._open_project(binary_path)
        try:
            program, consumer = self._get_program(project, binary_path)
            try:
                addr = self._resolve_address(program, address)
                if addr is None:
                    return {"error": f"Invalid address: {address}"}

                mem = program.getMemory()
                data = []
                for i in range(count):
                    try:
                        b = mem.getByte(addr.add(i)) & 0xFF
                        data.append(b)
                    except Exception:
                        break

                hex_str = " ".join(f"{b:02x}" for b in data)
                ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
                return {
                    "address": f"0x{addr.getOffset():x}",
                    "count": len(data),
                    "hex": hex_str,
                    "ascii": ascii_str,
                }
            finally:
                program.release(consumer)
        finally:
            project.close()

    def _resolve_function(self, program, target: str):
        """Resolve a function by name or address."""
        fm = program.getFunctionManager()

        # Try by name first
        for f in fm.getFunctions(True):
            if str(f.getName()) == target:
                return f

        # Try by address
        addr = self._resolve_address(program, target)
        if addr is not None:
            return fm.getFunctionAt(addr)

        return None

    def _resolve_address(self, program, target: str):
        """Resolve an address string to a Ghidra Address object."""
        try:
            if target.startswith("0x"):
                addr_val = int(target, 16)
            else:
                addr_val = int(target)
            return (
                program.getAddressFactory()
                .getDefaultAddressSpace()
                .getAddress(addr_val)
            )
        except (ValueError, Exception):
            # Try as function name - return entry point
            fm = program.getFunctionManager()
            for f in fm.getFunctions(True):
                if str(f.getName()) == target:
                    return f.getEntryPoint()
            return None
