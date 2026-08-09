"""
Unit tests to verify completeness of the readers module __all__ list.

This test ensures that:
1. All reader classes are properly included in __all__
2. All items in __all__ are actually importable
3. No reader files are missing from __all__
4. The abstract base class is properly handled
5. Autodiscovery finds all reader classes correctly
6. Format metadata matches what classes actually return
7. Developers add proper format metadata when adding new readers
"""

import dataclasses
import unittest
import inspect
import importlib
import glob
import re

from pathlib import Path
from seasenselib import readers
from seasenselib.readers.base import AbstractReader
from seasenselib.core.autodiscovery import ReaderDiscovery


class TestReadersCompleteness(unittest.TestCase):
    """Test suite to verify the completeness of the readers module and autodiscovery consistency."""

    def setUp(self):
        """Set up test fixtures."""
        self.readers_module = readers
        self.readers_dir = Path(readers.__file__).parent
        self.all_list = readers.__all__
        self.discovery = ReaderDiscovery()
        self.format_info = self.discovery.get_format_info()
        
        # Get plugin classes to exclude from certain tests
        self.plugin_classes = self.discovery.get_plugin_classes()
        
        # Get built-in classes only (for tests that shouldn't include plugins)
        all_classes = self.discovery.discover_classes()
        self.builtin_classes = {
            name: cls for name, cls in all_classes.items()
            if name not in self.plugin_classes
        }

    def test_all_list_exists(self):
        """Test that __all__ list exists and is not empty."""
        self.assertTrue(hasattr(self.readers_module, '__all__'))
        self.assertIsInstance(self.all_list, list)
        self.assertGreater(len(self.all_list), 0, "__all__ list should not be empty")

    def test_abstract_reader_in_all(self):
        """Test that AbstractReader is included in __all__."""
        self.assertIn('AbstractReader', self.all_list, 
                     "AbstractReader should be in __all__ list")

    def test_all_items_are_importable(self):
        """Test that all items in __all__ can be imported successfully."""
        for class_name in self.all_list:
            with self.subTest(class_name=class_name):
                # Test that the class exists in the module
                self.assertTrue(hasattr(self.readers_module, class_name),
                              f"Class '{class_name}' from __all__ not found in readers module")

                # Test that we can get the class
                reader_class = getattr(self.readers_module, class_name)
                self.assertTrue(inspect.isclass(reader_class),
                              f"'{class_name}' should be a class")

    def test_all_reader_classes_are_in_all_list(self):
        """Test that all concrete reader classes are included in __all__."""
        # Get all classes from the readers module that inherit from AbstractReader
        # but are not AbstractReader itself
        actual_reader_classes = []

        for attr_name in dir(self.readers_module):
            attr = getattr(self.readers_module, attr_name)
            if (inspect.isclass(attr) and 
                issubclass(attr, AbstractReader) and 
                attr is not AbstractReader):  # Exclude the base class itself
                actual_reader_classes.append(attr_name)

        # Check that each actual reader class is in __all__
        for class_name in actual_reader_classes:
            with self.subTest(class_name=class_name):
                self.assertIn(class_name, self.all_list,
                            f"Reader class '{class_name}' should be in __all__ list")

    def test_all_reader_files_have_classes_imported(self):
        """Test that all reader classes from individual files are imported and in __all__."""
        # Get all Python reader files in the readers directory
        reader_files = glob.glob(str(self.readers_dir / "*_reader.py"))

        missing_classes = []

        for file_path in reader_files:
            file_name = Path(file_path).stem  # Get filename without extension
            module_name = f"seasenselib.readers.{file_name}"

            try:
                # Import the individual reader module
                module = importlib.import_module(module_name)

                # Find all classes in this module that inherit from AbstractReader
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (inspect.isclass(attr) and 
                        issubclass(attr, AbstractReader) and 
                        attr is not AbstractReader and
                        attr.__module__ == module_name):  # Only classes defined in this module

                        # Check if this class is available in the main readers module
                        if not hasattr(self.readers_module, attr_name):
                            missing_classes.append(f"{attr_name} from {file_name}.py")
                        # Check if this class is in __all__
                        elif attr_name not in self.all_list:
                            missing_classes.append(f"{attr_name} (imported but not in __all__)")

            except ImportError as e:
                self.fail(f"Could not import {module_name}: {e}")

        if missing_classes:
            self.fail(f"Missing reader classes: {', '.join(missing_classes)}")

    def test_all_reader_classes_are_properly_imported(self):
        """Test that all built-in classes in __all__ are properly imported from their respective modules."""
        for class_name in self.all_list:
            if class_name == 'AbstractReader':
                continue  # Skip the base class

            with self.subTest(class_name=class_name):
                # Check that the class exists in the module
                self.assertTrue(hasattr(self.readers_module, class_name),
                              f"Class '{class_name}' from __all__ not found in readers module")

                # Get the class and check its module
                reader_class = getattr(self.readers_module, class_name)
                
                # Skip plugin classes - they come from external packages
                if class_name in self.plugin_classes:
                    continue
                
                expected_module = f"seasenselib.readers.{self._class_name_to_file_name(class_name)}"

                self.assertEqual(reader_class.__module__, expected_module,
                               f"Class '{class_name}' should be from module '{expected_module}', "
                               f"but is from '{reader_class.__module__}'")

    def _class_name_to_file_name(self, class_name):
        """Convert a class name to expected file name (PascalCase to snake_case)."""
        # Handle special cases
        if class_name == 'NetCdfReader':
            return 'netcdf_reader'

        # Convert PascalCase to snake_case
        snake_case = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', class_name)
        snake_case = re.sub('([a-z0-9])([A-Z])', r'\1_\2', snake_case).lower()
        return snake_case

    def test_all_concrete_readers_inherit_from_abstract_reader(self):
        """Test that all reader classes (except AbstractReader) inherit from AbstractReader."""
        for class_name in self.all_list:
            if class_name == 'AbstractReader':
                continue  # Skip the base class itself

            with self.subTest(class_name=class_name):
                reader_class = getattr(self.readers_module, class_name)
                self.assertTrue(issubclass(reader_class, AbstractReader),
                              f"'{class_name}' should inherit from AbstractReader")

    def test_no_extra_items_in_all(self):
        """Test that __all__ doesn't contain items that don't exist."""
        for class_name in self.all_list:
            with self.subTest(class_name=class_name):
                self.assertTrue(hasattr(self.readers_module, class_name),
                              f"Item '{class_name}' in __all__ does not exist in module")

    def test_all_readers_implement_required_methods(self):
        """Test that all reader classes implement the required abstract methods."""
        required_methods = ['format_name', 'format_key', 'file_extension']

        for class_name in self.all_list:
            if class_name == 'AbstractReader':
                continue  # Skip the abstract base class

            with self.subTest(class_name=class_name):
                reader_class = getattr(self.readers_module, class_name)

                for method_name in required_methods:
                    self.assertTrue(hasattr(reader_class, method_name),
                                  f"'{class_name}' should implement '{method_name}' method")

                    # Test that the method is callable
                    method = getattr(reader_class, method_name)
                    self.assertTrue(callable(method),
                                  f"'{class_name}.{method_name}' should be callable")

    def test_all_list_sorted_alphabetically(self):
        """Test that __all__ list is sorted alphabetically for better maintainability."""
        # Separate built-in and plugin classes
        builtin_names = [name for name in self.all_list if name not in self.plugin_classes]
        plugin_names = [name for name in self.all_list if name in self.plugin_classes]
        
        # Create expected order: built-ins first (sorted), then plugins (sorted)
        sorted_builtins = sorted(builtin_names, key=str.lower)
        sorted_plugins = sorted(plugin_names, key=str.lower)
        expected_order = sorted_builtins + sorted_plugins

        self.assertEqual(self.all_list, expected_order,
                        f"__all__ list should have built-in classes sorted alphabetically, "
                        f"followed by plugin classes sorted alphabetically.\n"
                        f"Current: {self.all_list}\n"
                        f"Expected: {expected_order}")

    def test_all_list_has_no_duplicates(self):
        """Test that __all__ list contains no duplicate entries."""
        self.assertEqual(len(self.all_list), len(set(self.all_list)),
                        f"__all__ list contains duplicates: {self.all_list}")

    def test_all_reader_classes_inherit_from_abstract_reader(self):
        """Test that all reader classes in reader files inherit from AbstractReader."""
        # Get all Python reader files in the readers directory
        reader_files = glob.glob(str(self.readers_dir / "*_reader.py"))

        non_compliant_classes = []

        for file_path in reader_files:
            file_name = Path(file_path).stem  # Get filename without extension
            module_name = f"seasenselib.readers.{file_name}"

            try:
                # Import the individual reader module
                module = importlib.import_module(module_name)

                # Find all classes in this module that look like reader classes
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (inspect.isclass(attr) and 
                        attr.__module__ == module_name and  # Only classes defined in this module
                        attr is not AbstractReader):        # Exclude the base class itself
                        if attr_name.startswith('_'):
                            continue  # Private helper classes are implementation details
                        if dataclasses.is_dataclass(attr):
                            continue  # Helper dataclasses are not reader implementations

                        # Check if this class inherits from AbstractReader
                        if not issubclass(attr, AbstractReader):
                            non_compliant_classes.append(f"{attr_name} in {file_name}.py")

            except ImportError as e:
                self.fail(f"Could not import {module_name}: {e}")

        if non_compliant_classes:
            self.fail(f"Reader classes that don't inherit from AbstractReader: " \
                      f"{', '.join(non_compliant_classes)}")

    def test_all_reader_classes_follow_naming_convention(self):
        """Test that all classes in reader files follow the naming 
        convention of ending with 'Reader'."""
        # Get all Python reader files in the readers directory
        reader_files = glob.glob(str(self.readers_dir / "*_reader.py"))

        non_compliant_classes = []

        for file_path in reader_files:
            file_name = Path(file_path).stem  # Get filename without extension
            module_name = f"seasenselib.readers.{file_name}"

            try:
                # Import the individual reader module
                module = importlib.import_module(module_name)

                # Find all classes defined in this module (excluding imported ones)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (inspect.isclass(attr) and 
                        attr.__module__ == module_name and  # Only classes defined in this module
                        attr is not AbstractReader):        # Exclude the base class itself
                        if attr_name.startswith('_'):
                            continue  # Private helper classes are implementation details
                        if dataclasses.is_dataclass(attr):
                            continue  # Helper dataclasses are not reader implementations

                        # Check if class name ends with "Reader"
                        if not attr_name.endswith('Reader'):
                            non_compliant_classes.append(
                                f"{attr_name} in {file_name}.py (should end with 'Reader')")

            except ImportError as e:
                self.fail(f"Could not import {module_name}: {e}")

        if non_compliant_classes:
            self.fail(f"Classes that don't follow naming convention: " \
                      f"{', '.join(non_compliant_classes)}")

    def test_file_extensions_are_unique(self):
        """Test that primary file extensions are unique across all reader classes."""
        # Collect primary file extensions from all reader classes
        extension_to_class = {}

        for class_name in self.all_list:
            if class_name == 'AbstractReader':
                continue  # Skip the abstract base class

            with self.subTest(class_name=class_name):
                reader_class = getattr(self.readers_module, class_name)

                # Get the file extension
                try:
                    file_extension = reader_class.file_extension()
                except Exception as e:
                    self.fail(f"Failed to get file_extension from {class_name}: {e}")

                # Skip None extensions (some readers might not have a specific extension)
                if file_extension is None:
                    continue

                # Normalize extension (ensure it starts with a dot, convert to lowercase)
                if not file_extension.startswith('.'):
                    file_extension = '.' + file_extension
                file_extension = file_extension.lower()

                # Check if this extension is already used by another class
                if file_extension in extension_to_class:
                    self.fail(f"File extension '{file_extension}' is used by both "
                             f"'{extension_to_class[file_extension]}' and '{class_name}'. "
                             f"Primary file extensions must be unique to avoid ambiguity.")

                extension_to_class[file_extension] = class_name

        # Ensure we found at least some extensions
        self.assertGreater(len(extension_to_class), 0, 
                          "At least one reader class should have a file extension")

    def test_auto_detect_file_extensions_are_unique(self):
        """Test that auto-detect extensions are unique across reader classes."""
        extension_to_class = {}

        for class_name in self.all_list:
            if class_name == 'AbstractReader':
                continue

            with self.subTest(class_name=class_name):
                reader_class = getattr(self.readers_module, class_name)

                try:
                    file_extensions = reader_class.file_extensions()
                except Exception as e:
                    self.fail(f"Failed to get file_extensions from {class_name}: {e}")

                for file_extension in file_extensions:
                    if file_extension is None:
                        continue

                    if not file_extension.startswith('.'):
                        file_extension = '.' + file_extension
                    file_extension = file_extension.lower()

                    if file_extension in extension_to_class:
                        self.fail(
                            f"File extension '{file_extension}' is used by both "
                            f"'{extension_to_class[file_extension]}' and '{class_name}'. "
                            f"Auto-detect file extensions must be unique to avoid ambiguity."
                        )

                    extension_to_class[file_extension] = class_name

    def test_format_keys_are_unique_and_valid(self):
        """Test that format keys are unique, not None, and follow kebab-case convention."""

        # Collect format keys from all reader classes
        key_to_class = {}

        # Regex pattern for valid kebab-case: lowercase letters, numbers, and hyphens
        # Must start and end with alphanumeric character, no consecutive hyphens
        kebab_case_pattern = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

        for class_name in self.all_list:
            if class_name == 'AbstractReader':
                continue  # Skip the abstract base class

            with self.subTest(class_name=class_name):
                reader_class = getattr(self.readers_module, class_name)

                # Get the format key
                try:
                    format_key = reader_class.format_key()
                except Exception as e:
                    self.fail(f"Failed to get format_key from {class_name}: {e}")

                # Check that format_key is not None
                self.assertIsNotNone(format_key, 
                        f"format_key for {class_name} should not be None")

                # Check that format_key is a string
                self.assertIsInstance(format_key, str,
                        f"format_key for {class_name} should be a string, got {type(format_key)}")

                # Check that format_key is not empty
                self.assertGreater(len(format_key.strip()), 0,
                        f"format_key for {class_name} should not be empty")

                # Check that format_key follows kebab-case convention
                self.assertTrue(kebab_case_pattern.match(format_key),
                        f"format_key '{format_key}' for {class_name} must be in kebab-case format "
                        f"(lowercase letters, numbers, and hyphens only, no consecutive hyphens, "
                        f"must start and end with alphanumeric character)")

                # Check if this format key is already used by another class
                if format_key in key_to_class:
                    self.fail(f"Format key '{format_key}' is used by both "
                             f"'{key_to_class[format_key]}' and '{class_name}'. "
                             f"Format keys must be unique to avoid ambiguity.")

                key_to_class[format_key] = class_name

        # Ensure we found at least some format keys
        self.assertGreater(len(key_to_class), 0, 
                          "At least one reader class should have a format key")

    # Autodiscovery-specific tests
    def test_autodiscovery_finds_readers(self):
        """Test that autodiscovery finds reader classes and returns format info."""
        self.assertIsInstance(self.format_info, list)
        self.assertGreater(len(self.format_info), 0, "Format info should not be empty")

    def test_format_info_entries_are_valid_dicts(self):
        """Test that all format info entries are valid dictionaries with required keys."""
        required_keys = {'key', 'name', 'class_name', 'extensions'}
        
        for i, entry in enumerate(self.format_info):
            with self.subTest(entry_index=i):
                self.assertIsInstance(entry, dict,
                                    f"Format info entry {i} should be a dict")
                
                # Check all required keys exist
                for key in required_keys:
                    self.assertIn(key, entry,
                                f"Format info entry {i} missing required key '{key}'")
                
                # Check required fields are not empty
                self.assertTrue(entry['key'].strip() if entry['key'] else False,
                              f"format key should not be empty in entry {i}")
                self.assertTrue(entry['name'].strip() if entry['name'] else False,
                              f"format name should not be empty in entry {i}")
                self.assertTrue(entry['class_name'].strip() if entry['class_name'] else False,
                              f"class_name should not be empty in entry {i}")

    def test_format_keys_are_unique(self):
        """Test that format keys in autodiscovery are unique."""
        format_keys = [entry['key'] for entry in self.format_info]
        duplicates = [key for key in set(format_keys) if format_keys.count(key) > 1]
        self.assertEqual([], duplicates, f"Duplicate format keys: {duplicates}")

    def test_format_keys_follow_kebab_case(self):
        """Test that all format keys follow kebab-case convention."""
        kebab_case_pattern = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
        
        for entry in self.format_info:
            with self.subTest(format_key=entry['key']):
                self.assertTrue(kebab_case_pattern.match(entry['key']),
                              f"format_key '{entry['key']}' for {entry['name']} "
                              f"must be in kebab-case format")

    def test_file_extensions_are_unique_when_present(self):
        """Test that autodiscovery file extensions are unique (when present)."""
        extensions = [
            ext
            for entry in self.format_info
            for ext in entry.get('extensions', [])
        ]
        normalized_extensions = [ext.lower() for ext in extensions if ext]
        duplicates = [ext for ext in set(normalized_extensions) if normalized_extensions.count(ext) > 1]
        self.assertEqual([], duplicates, f"Duplicate file extensions: {duplicates}")

    def test_all_discovered_classes_exist_as_files(self):
        """Test that every discovered built-in reader class has a corresponding file."""
        for entry in self.format_info:
            class_name = entry['class_name']
            
            # Skip plugin classes - they come from external packages
            if class_name in self.plugin_classes:
                continue
                
            with self.subTest(class_name=class_name):
                # Get reader class from module
                reader_class = getattr(self.readers_module, class_name)
                module_path = reader_class.__module__.replace('seasenselib.readers.', '')
                module_file = module_path + '.py'
                file_path = self.readers_dir / module_file
                
                self.assertTrue(file_path.exists(),
                              f"Module file {module_file} for {class_name} does not exist")

    def test_all_discovered_classes_are_importable(self):
        """Test that every discovered class can be imported and is a valid reader."""
        for entry in self.format_info:
            class_name = entry['class_name']
            with self.subTest(class_name=class_name):
                # Get reader class from module
                reader_class = getattr(self.readers_module, class_name)
                self.assertTrue(inspect.isclass(reader_class),
                              f"{class_name} should be a class")
                self.assertTrue(issubclass(reader_class, AbstractReader),
                              f"{class_name} should inherit from AbstractReader")

    def test_autodiscovery_completeness_vs_actual_files(self):
        """Test that autodiscovery includes all reader classes found in actual files."""
        # Get all Python reader files in the readers directory
        reader_files = glob.glob(str(self.readers_dir / "*_reader.py"))
        
        # Collect classes from autodiscovery
        discovered_classes = {entry['class_name'] for entry in self.format_info}
        
        # Find all reader classes in actual files
        missing_from_discovery = []

        for file_path in reader_files:
            file_name = Path(file_path).stem
            module_name = f"seasenselib.readers.{file_name}"

            try:
                module = importlib.import_module(module_name)
                
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (inspect.isclass(attr) and 
                        issubclass(attr, AbstractReader) and 
                        attr is not AbstractReader and
                        attr.__module__ == module_name):
                        
                        if attr_name not in discovered_classes:
                            missing_from_discovery.append(f"{attr_name} from {file_name}.py")

            except ImportError as e:
                self.fail(f"Could not import {module_name}: {e}")

        if missing_from_discovery:
            self.fail(f"Reader classes found in files but missing from autodiscovery: "
                     f"{', '.join(missing_from_discovery)}")

    def test_format_info_consistency_with_class_methods(self):
        """Test that format info matches what classes actually return."""
        for entry in self.format_info:
            class_name = entry['class_name']
            with self.subTest(class_name=class_name):
                # Get reader class from module
                reader_class = getattr(self.readers_module, class_name)
                
                # Test format_key consistency
                if hasattr(reader_class, 'format_key'):
                    actual_format_key = reader_class.format_key()
                    self.assertEqual(entry['key'], actual_format_key,
                                   f"Format info key '{entry['key']}' doesn't match "
                                   f"class method result '{actual_format_key}' for {class_name}")
                
                # Test format_name consistency
                if hasattr(reader_class, 'format_name'):
                    actual_format_name = reader_class.format_name()
                    self.assertEqual(entry['name'], actual_format_name,
                                   f"Format info name '{entry['name']}' doesn't match "
                                   f"class method result '{actual_format_name}' for {class_name}")
                
                # Test file_extension consistency
                if hasattr(reader_class, 'file_extension'):
                    actual_extension = reader_class.file_extension()
                    expected_extension = entry.get('extension')
                    self.assertEqual(expected_extension, actual_extension,
                                   f"Format info extension '{expected_extension}' doesn't match "
                                   f"class method result '{actual_extension}' for {class_name}")

                if hasattr(reader_class, 'file_extensions'):
                    actual_extensions = list(reader_class.file_extensions())
                    expected_extensions = entry.get('extensions')
                    self.assertEqual(expected_extensions, actual_extensions,
                                   f"Format info extensions '{expected_extensions}' don't match "
                                   f"class method result '{actual_extensions}' for {class_name}")

    def test_all_list_matches_autodiscovery(self):
        """Test that __all__ list matches autodiscovered class names plus AbstractReader."""
        discovered_classes = sorted([entry['class_name'] for entry in self.format_info])
        expected_all = sorted(['AbstractReader'] + discovered_classes)
        actual_all = sorted(self.all_list)
        
        self.assertEqual(expected_all, actual_all,
                        f"__all__ list doesn't match autodiscovery.\n"
                        f"Expected: {expected_all}\n"
                        f"Actual: {actual_all}")

    def test_no_orphaned_classes_in_all(self):
        """Test that no classes in __all__ are missing from autodiscovery (except AbstractReader)."""
        discovered_classes = {entry['class_name'] for entry in self.format_info}
        discovered_classes.add('AbstractReader')  # AbstractReader is expected
        
        orphaned_classes = [cls for cls in self.all_list if cls not in discovered_classes]
        self.assertEqual([], orphaned_classes,
                        f"Classes in __all__ but not discovered by autodiscovery: {orphaned_classes}")

    def test_no_unused_discovery_entries(self):
        """Test that all discovered classes are in __all__."""
        unused_entries = [entry['class_name'] for entry in self.format_info
                         if entry['class_name'] not in self.all_list]
        self.assertEqual([], unused_entries,
                        f"Discovered classes not used in __all__: {unused_entries}")

if __name__ == '__main__':
    unittest.main()
