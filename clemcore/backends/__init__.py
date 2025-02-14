import abc
import importlib
import inspect
import json
import os
from typing import Dict
import clemcore.utils.file_utils as file_utils
from clemcore.backends.model_registry import ModelSpec, ModelRegistry, Model, HumanModel, CustomResponseModel

__all_ = [
    "Model",
    "ModelSpec",
    "ModelRegistry",
    "HumanModel",
    "CustomResponseModel"
]


def load_credentials(backend, file_name="key.json") -> Dict:
    """Load login credentials and API keys from JSON file.
    Args:
        backend: Name of the backend/API provider to load key for.
        file_name: Name of the key file. Defaults to key.json in the clembench root directory.
    Returns:
        Dictionary with {backend: {api_key: key}}.
    """
    # todo:
    key_file = os.path.join(file_utils.project_root(), file_name)
    with open(key_file) as f:
        creds = json.load(f)
    assert backend in creds, f"No '{backend}' in {file_name}. See README."
    assert "api_key" in creds[backend], f"No 'api_key' in {file_name}. See README."
    return creds


class Backend(abc.ABC):
    """Abstract base class for clembench backends.
    All clembench backend classes must be child classes of this base class."""

    @abc.abstractmethod
    def get_model_for(self, model_spec: ModelSpec) -> Model:
        """Get a Model instance for the model specific by ModelSpec.
        Must be implemented by every clembench backend.
        Args:
            model_spec: A ModelSpec instance specifying the model to return a corresponding Model child class instance
                for the appropriate backend.
        Returns:
            A Model instance using the appropriate backend.
        """
        pass

    def __repr__(self):
        """Get a string representation of this Backend instance."""
        return str(self)

    def __str__(self):
        """Get a string name of the class of this Backend child class instance."""
        return f"{self.__class__.__name__}"


_backend_registry: Dict[str, Backend] = dict()  # we store references to the class constructor


def _load_model_for(model_spec: ModelSpec) -> Model:
    """Load a model backend class based on the passed ModelSpec.
    Registers backend if it is not already registered.
    Args:
        model_spec: The ModelSpec specifying the model to load the backend class for.
    Returns:
        The Model subclass for the model specified in the passed ModelSpec.
    """
    backend_name = model_spec.backend
    if backend_name not in _backend_registry:
        _register_backend(backend_name)
    backend_cls = _backend_registry[backend_name]
    return backend_cls.get_model_for(model_spec)


def _register_backend(backend_name: str):
    """Dynamically loads the Backend in the file with name <backend_name>_api.py into the _backend_registry.
    Raises an exception if no such file exists or the Backend class could not be found.
    Args:
        backend_name: The <backend_name> prefix of the <backend_name>_api.py file.
    Returns:
        The Backend subclass for the passed backend name.
    Raises:
        FileNotFoundError: Will be raised if no backend python file with the passed name can be found in the backends
            directory.
        LookupError: Will be raised if the backend python file with the passed name does not contain exactly one Backend
            subclass.
    """
    backends_root = os.path.join(file_utils.clemcore_root(), "backends")
    backend_module = f"{backend_name}_api"
    backend_path = os.path.join(backends_root, f"{backend_module}.py")
    if not os.path.isfile(backend_path):
        raise FileNotFoundError(f"The file '{backend_path}' does not exist. "
                                f"Create such a backend file or check the backend_name '{backend_name}'.")
    module = importlib.import_module(f"backends.{backend_module}")
    backend_subclasses = inspect.getmembers(module, predicate=is_backend)
    if len(backend_subclasses) == 0:
        raise LookupError(f"There is no Backend defined in {backend_module}. "
                          f"Create such a class and try again or check the backend_name '{backend_name}'.")
    if len(backend_subclasses) > 1:
        raise LookupError(f"There is more than one Backend defined in {backend_module}.")
    _, backend_cls = backend_subclasses[0]
    _backend_registry[backend_name] = backend_cls()
    return backend_cls


def is_backend(obj):
    """Check if an object is a Backend child class (instance).
    Args:
        obj: The object to be checked.
    Returns:
        True if the object is a Backend child class (instance); False otherwise.
    """
    if inspect.isclass(obj) and issubclass(obj, Backend):
        return True
    return False


class ContextExceededError(Exception):
    """Exception to be raised when the messages passed to a backend instance exceed the context limit of the model."""
    tokens_used: int = int()
    tokens_left: int = int()
    context_size: int = int()

    def __init__(self, info_str: str = "Context limit exceeded", tokens_used: int = 0,
                 tokens_left: int = 0, context_size: int = 0):
        """
        Args:
            info_str: String informing about context limit being exceeded. To optionally be modified with further
                information by the backend class eventually raising this error.
            tokens_used: The number of tokens used by the context that lead to this error being raised.
            tokens_left: The number of tokens left in the context limit. Will be negative if this error is raised,
                absolute value being the number of tokens that exceed the context limit.
            context_size: The size of the context/the context limit.
        """
        info = f"{info_str} {tokens_used}/{context_size}"
        super().__init__(info)
        self.tokens_used = tokens_used
        self.tokens_left = tokens_left
        self.context_size = context_size
