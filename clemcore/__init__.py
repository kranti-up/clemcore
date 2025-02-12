import logging.config
import yaml
import importlib.resources as importlib_resources

import clemcore.backends as backends

BANNER = \
    r"""
      _                _                     _     
     | |              | |                   | |    
  ___| | ___ _ __ ___ | |__   ___ _ __   ___| |__  
 / __| |/ _ \ '_ ` _ \| '_ \ / _ \ '_ \ / __| '_ \ 
| (__| |  __/ | | | | | |_) |  __/ | | | (__| | | |
 \___|_|\___|_| |_| |_|_.__/ \___|_| |_|\___|_| |_|
"""  # doom font, thanks to http://patorjk.com/software/taag/

print(BANNER)


def load_logging_config():
    pkg_file_path = "utils/logging.yaml"
    with importlib_resources.files(__package__).joinpath(pkg_file_path).open("r") as f:
        return yaml.safe_load(f)


try:
    import logging

    logging.config.dictConfig(load_logging_config())
except Exception as e:
    print(f"Failed to load logging config: {e}")

# look for custom user-defined models before loading the base registry
backends.load_custom_model_registry()
backends.load_model_registry()
