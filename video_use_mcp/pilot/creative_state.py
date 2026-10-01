"""Short creative edits serialize separately from long-running render work.

The deployed coordinator has one container. All interactive creative writers
share these locks so simultaneous style, script and timestamp edits preserve
each other. This is not a distributed lock for a multi-coordinator deployment.
"""

import inspect
import threading
from functools import wraps

# Bounded striped locks avoid keeping one lock per historical project forever.
_LOCKS = [threading.RLock() for _ in range(64)]


def creative_lock(project_id):
    return _LOCKS[hash(project_id) % len(_LOCKS)]


def creative_edit(function):
    signature = inspect.signature(function)

    @wraps(function)
    def serialized(*args, **kwargs):
        arguments = signature.bind(*args, **kwargs).arguments
        with creative_lock(arguments.get("project_id", "new")):
            return function(*args, **kwargs)

    return serialized
