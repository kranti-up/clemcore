import os
import logging
import logging.config
import yaml

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

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
with open(os.path.join(project_root, "logging.yaml")) as f:
    conf = yaml.safe_load(f)
    log_fn = conf["handlers"]["file_handler"]["filename"]
    log_fn = os.path.join(project_root, log_fn)
    conf["handlers"]["file_handler"]["filename"] = log_fn
    logging.config.dictConfig(conf)


def get_logger(name):
    return logging.getLogger(name)