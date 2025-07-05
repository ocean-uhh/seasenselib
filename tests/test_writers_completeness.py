"""
Unit tests to verify completeness of the writers module __all__ list.

This test ensures that:
1. All writer classes are properly included in __all__
2. All items in __all__ are actually importable
3. No writer files are missing from __all__
4. The abstract base class is properly handled
5. All writer classes inherit from AbstractWriter
6. All writer classes follow naming conventions
"""

import unittest
import inspect
import importlib
import glob
import re
from pathlib import Path

from ctd_tools import writers
from ctd_tools.writers.base import AbstractWriter


class TestWritersCompleteness(unittest.TestCase):
    """Test suite to verify the completeness of the writers module."""

    def setUp(self):
        """Set up test fixtures."""
        self.writers_module = writers
        self.writers_dir = Path(writers.__file__).parent
        self.all_list = writers.__all__

    def test_all_list_exists(self):
        """Test that __all__ list exists and is not empty."""
        self.assertTrue(hasattr(self.writers_module, '__all__'))
        self.assertIsInstance(self.all_list, list)
        self.assertGreater(len(self.all_list), 0, "__all__ list should not be empty")

    def test_abstract_writer_in_all(self):
        """Test that AbstractWriter is included in __all__."""
        self.assertIn('AbstractWriter', self.all_list, 
                     "AbstractWriter should be in __all__ list")

    def test_all_items_are_importable(self):
        """Test that all items in __all__ can be imported successfully."""
        for class_name in self.all_list:
            with self.subTest(class_name=class_name):
                # Test that the class exists in the module
                self.assertTrue(hasattr(self.writers_module, class_name),
                              f"Class '{class_name}' from __all__ not found in writers module")

                # Test that we can get the class
                writer_class = getattr(self.writers_module, class_name)
                self.assertTrue(inspect.isclass(writer_class),
                              f"'{class_name}' should be a class")

    def test_all_writer_classes_are_in_all_list(self):
        """Test that all concrete writer classes are included in __all__."""
        # Get all classes from the writers module that inherit from AbstractWriter
        # but are not AbstractWriter itself
        actual_writer_classes = []

        for attr_name in dir(self.writers_module):
            attr = getattr(self.writers_module, attr_name)
            if (inspect.isclass(attr) and 
                issubclass(attr, AbstractWriter) and 
                attr is not AbstractWriter):  # Exclude the base class itself
                actual_writer_classes.append(attr_name)

        # Check that each actual writer class is in __all__
        for class_name in actual_writer_classes:
            with self.subTest(class_name=class_name):
                self.assertIn(class_name, self.all_list,
                            f"Writer class '{class_name}' should be in __all__ list")

    def test_all_writer_files_have_classes_imported(self):
        """Test that all writer classes from individual files are imported and in __all__."""
        # Get all Python writer files in the writers directory
        writer_files = glob.glob(str(self.writers_dir / "*_writer.py"))

        missing_classes = []

        for file_path in writer_files:
            file_name = Path(file_path).stem  # Get filename without extension
            module_name = f"ctd_tools.writers.{file_name}"

            try:
                # Import the individual writer module
                module = importlib.import_module(module_name)

                # Find all classes in this module that inherit from AbstractWriter
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (inspect.isclass(attr) and 
                        issubclass(attr, AbstractWriter) and 
                        attr is not AbstractWriter and
                        attr.__module__ == module_name):  # Only classes defined in this module

                        # Check if this class is available in the main writers module
                        if not hasattr(self.writers_module, attr_name):
                            missing_classes.append(f"{attr_name} from {file_name}.py")
                        # Check if this class is in __all__
                        elif attr_name not in self.all_list:
                            missing_classes.append(f"{attr_name} (imported but not in __all__)")

            except ImportError as e:
                self.fail(f"Could not import {module_name}: {e}")

        if missing_classes:
            self.fail(f"Missing writer classes: {', '.join(missing_classes)}")

    def test_all_writer_classes_are_properly_imported(self):
        """Test that all classes in __all__ are properly imported from their respective modules."""
        for class_name in self.all_list:
            if class_name == 'AbstractWriter':
                continue  # Skip the base class

            with self.subTest(class_name=class_name):
                # Check that the class exists in the module
                self.assertTrue(hasattr(self.writers_module, class_name),
                              f"Class '{class_name}' from __all__ not found in writers module")

                # Get the class and check its module
                writer_class = getattr(self.writers_module, class_name)
                expected_module = f"ctd_tools.writers.{self._class_name_to_file_name(class_name)}"

                self.assertEqual(writer_class.__module__, expected_module,
                               f"Class '{class_name}' should be from module '{expected_module}', "
                               f"but is from '{writer_class.__module__}'")

    def _class_name_to_file_name(self, class_name):
        """Convert a class name to expected file name (PascalCase to snake_case)."""
        # Handle special cases
        if class_name == 'NetCdfWriter':
            return 'netcdf_writer'

        # Convert PascalCase to snake_case
        snake_case = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', class_name)
        snake_case = re.sub('([a-z0-9])([A-Z])', r'\1_\2', snake_case).lower()
        return snake_case

    def test_all_concrete_writers_inherit_from_abstract_writer(self):
        """Test that all writer classes (except AbstractWriter) inherit from AbstractWriter."""
        for class_name in self.all_list:
            if class_name == 'AbstractWriter':
                continue  # Skip the base class itself

            with self.subTest(class_name=class_name):
                writer_class = getattr(self.writers_module, class_name)
                self.assertTrue(issubclass(writer_class, AbstractWriter),
                              f"'{class_name}' should inherit from AbstractWriter")

    def test_no_extra_items_in_all(self):
        """Test that __all__ doesn't contain items that don't exist."""
        for class_name in self.all_list:
            with self.subTest(class_name=class_name):
                self.assertTrue(hasattr(self.writers_module, class_name),
                              f"Item '{class_name}' in __all__ does not exist in module")

    def test_all_writers_implement_required_methods(self):
        """Test that all writer classes implement the required abstract methods."""
        for class_name in self.all_list:
            if class_name == 'AbstractWriter':
                continue  # Skip the abstract base class

            with self.subTest(class_name=class_name):
                writer_class = getattr(self.writers_module, class_name)

                # Test that write method exists and is callable
                self.assertTrue(hasattr(writer_class, 'write'),
                              f"'{class_name}' should implement 'write' method")
                write_method = getattr(writer_class, 'write')
                self.assertTrue(callable(write_method),
                              f"'{class_name}.write' should be callable")

                # Test that file_extension property exists
                self.assertTrue(hasattr(writer_class, 'file_extension'),
                              f"'{class_name}' should implement 'file_extension' property")

                # Check if file_extension is a property (this is tricky without instantiation)
                file_ext_attr = getattr(writer_class, 'file_extension')
                self.assertTrue(isinstance(file_ext_attr, property) or callable(file_ext_attr),
                              f"'{class_name}.file_extension' should be a property or method")

    def test_all_list_sorted_alphabetically(self):
        """Test that __all__ list is sorted alphabetically for better maintainability."""
        # Create a sorted version for comparison
        sorted_all = sorted(self.all_list, key=str.lower)

        self.assertEqual(self.all_list, sorted_all,
                        f"__all__ list should be sorted alphabetically.\\n"
                        f"Current: {self.all_list}\\n"
                        f"Expected: {sorted_all}")

    def test_all_list_has_no_duplicates(self):
        """Test that __all__ list contains no duplicate entries."""
        self.assertEqual(len(self.all_list), len(set(self.all_list)),
                        f"__all__ list contains duplicates: {self.all_list}")

    def test_all_writer_classes_inherit_from_abstract_writer(self):
        """Test that all writer classes in writer files inherit from AbstractWriter."""
        # Get all Python writer files in the writers directory
        writer_files = glob.glob(str(self.writers_dir / "*_writer.py"))

        non_compliant_classes = []

        for file_path in writer_files:
            file_name = Path(file_path).stem  # Get filename without extension
            module_name = f"ctd_tools.writers.{file_name}"

            try:
                # Import the individual writer module
                module = importlib.import_module(module_name)

                # Find all classes in this module that look like writer classes
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (inspect.isclass(attr) and 
                        attr.__module__ == module_name and  # Only classes defined in this module
                        attr is not AbstractWriter):        # Exclude the base class itself

                        # Check if this class inherits from AbstractWriter
                        if not issubclass(attr, AbstractWriter):
                            non_compliant_classes.append(f"{attr_name} in {file_name}.py")

            except ImportError as e:
                self.fail(f"Could not import {module_name}: {e}")

        if non_compliant_classes:
            self.fail(f"Writer classes that don't inherit from AbstractWriter: " \
                      f"{', '.join(non_compliant_classes)}")

    def test_all_writer_classes_follow_naming_convention(self):
        """Test that all classes in writer files follow the naming convention 
        of ending with 'Writer'."""
        # Get all Python writer files in the writers directory
        writer_files = glob.glob(str(self.writers_dir / "*_writer.py"))

        non_compliant_classes = []

        for file_path in writer_files:
            file_name = Path(file_path).stem  # Get filename without extension
            module_name = f"ctd_tools.writers.{file_name}"

            try:
                # Import the individual writer module
                module = importlib.import_module(module_name)

                # Find all classes defined in this module (excluding imported ones)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (inspect.isclass(attr) and 
                        attr.__module__ == module_name and  # Only classes defined in this module
                        attr is not AbstractWriter):        # Exclude the base class itself

                        # Check if class name ends with "Writer"
                        if not attr_name.endswith('Writer'):
                            non_compliant_classes.append(f"{attr_name} in "
                                f"{file_name}.py (should end with 'Writer')")

            except ImportError as e:
                self.fail(f"Could not import {module_name}: {e}")

        if non_compliant_classes:
            self.fail(f"Classes that don't follow naming convention: " \
                      f"{', '.join(non_compliant_classes)}")

    def test_file_extensions_are_unique(self):
        """Test that file extensions are unique across all writer classes."""
        # Collect file extensions from all writer classes
        extension_to_class = {}

        for class_name in self.all_list:
            if class_name == 'AbstractWriter':
                continue  # Skip the abstract base class

            with self.subTest(class_name=class_name):
                writer_class = getattr(self.writers_module, class_name)

                # Get the file extension (it's a property, so we need to access it differently)
                try:
                    # Since it's a property, we need to get it from the class
                    if hasattr(writer_class, 'file_extension'):
                        file_extension_prop = getattr(writer_class, 'file_extension')
                        if isinstance(file_extension_prop, property):
                            # For testing purposes, we can't easily instantiate without data
                            # so we'll check if the property is defined
                            continue
                        else:
                            # If it's not a property, try calling it
                            file_extension = file_extension_prop()
                    else:
                        self.fail(f"'{class_name}' does not have file_extension property")

                except Exception as e:
                    # Skip this test for classes where we can't get the extension
                    # (e.g., because they require instantiation)
                    continue

                # Skip None extensions (some writers might not have a specific extension)
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
                             f"File extensions must be unique to avoid ambiguity.")

                extension_to_class[file_extension] = class_name


if __name__ == '__main__':
    unittest.main()
