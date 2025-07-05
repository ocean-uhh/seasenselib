"""
Unit tests to verify completeness of the readers module __all__ list.

This test ensures that:
1. All reader classes are properly included in __all__
2. All items in __all__ are actually importable
3. No reader files are missing from __all__
4. The abstract base class is properly handled
"""

import unittest
import inspect
import importlib
import glob
import re
from pathlib import Path

from ctd_tools import readers
from ctd_tools.readers.base import AbstractReader


class TestReadersCompleteness(unittest.TestCase):
    """Test suite to verify the completeness of the readers module."""

    def setUp(self):
        """Set up test fixtures."""
        self.readers_module = readers
        self.readers_dir = Path(readers.__file__).parent
        self.all_list = readers.__all__
        
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
            module_name = f"ctd_tools.readers.{file_name}"
            
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
        """Test that all classes in __all__ are properly imported from their respective modules."""
        for class_name in self.all_list:
            if class_name == 'AbstractReader':
                continue  # Skip the base class
                
            with self.subTest(class_name=class_name):
                # Check that the class exists in the module
                self.assertTrue(hasattr(self.readers_module, class_name),
                              f"Class '{class_name}' from __all__ not found in readers module")
                
                # Get the class and check its module
                reader_class = getattr(self.readers_module, class_name)
                expected_module = f"ctd_tools.readers.{self._class_name_to_file_name(class_name)}"
                
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
        # Create a sorted version for comparison
        sorted_all = sorted(self.all_list, key=str.lower)
        
        self.assertEqual(self.all_list, sorted_all,
                        f"__all__ list should be sorted alphabetically.\n"
                        f"Current: {self.all_list}\n"
                        f"Expected: {sorted_all}")
        
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
            module_name = f"ctd_tools.readers.{file_name}"
            
            try:
                # Import the individual reader module
                module = importlib.import_module(module_name)
                
                # Find all classes in this module that look like reader classes
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (inspect.isclass(attr) and 
                        attr.__module__ == module_name and  # Only classes defined in this module
                        attr is not AbstractReader):        # Exclude the base class itself
                        
                        # Check if this class inherits from AbstractReader
                        if not issubclass(attr, AbstractReader):
                            non_compliant_classes.append(f"{attr_name} in {file_name}.py")
                            
            except ImportError as e:
                self.fail(f"Could not import {module_name}: {e}")
        
        if non_compliant_classes:
            self.fail(f"Reader classes that don't inherit from AbstractReader: {', '.join(non_compliant_classes)}")
    
    def test_all_reader_classes_follow_naming_convention(self):
        """Test that all classes in reader files follow the naming convention of ending with 'Reader'."""
        # Get all Python reader files in the readers directory
        reader_files = glob.glob(str(self.readers_dir / "*_reader.py"))
        
        non_compliant_classes = []
        
        for file_path in reader_files:
            file_name = Path(file_path).stem  # Get filename without extension
            module_name = f"ctd_tools.readers.{file_name}"
            
            try:
                # Import the individual reader module
                module = importlib.import_module(module_name)
                
                # Find all classes defined in this module (excluding imported ones)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (inspect.isclass(attr) and 
                        attr.__module__ == module_name and  # Only classes defined in this module
                        attr is not AbstractReader):        # Exclude the base class itself
                        
                        # Check if class name ends with "Reader"
                        if not attr_name.endswith('Reader'):
                            non_compliant_classes.append(f"{attr_name} in {file_name}.py (should end with 'Reader')")
                            
            except ImportError as e:
                self.fail(f"Could not import {module_name}: {e}")
        
        if non_compliant_classes:
            self.fail(f"Classes that don't follow naming convention: {', '.join(non_compliant_classes)}")
    
    def test_file_extensions_are_unique(self):
        """Test that file extensions are unique across all reader classes."""
        # Collect file extensions from all reader classes
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
                             f"File extensions must be unique to avoid ambiguity.")
                
                extension_to_class[file_extension] = class_name
        
        # Ensure we found at least some extensions
        self.assertGreater(len(extension_to_class), 0, 
                          "At least one reader class should have a file extension")
    
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


if __name__ == '__main__':
    unittest.main()
