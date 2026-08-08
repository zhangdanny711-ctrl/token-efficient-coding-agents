"""etlkit — a small batch data-pipeline toolkit.

Jobs are described by a JSON spec and executed as a fixed chain of
stages: extract -> validate -> transform -> load. Stages hand data to
each other through a plain-dict batch contract (see etlkit.contracts),
so every intermediate shape can be inspected, logged, and asserted on.

The toolkit is deliberately dependency-free: readers, writers, rule
checks, and the run log are all standard-library Python.
"""

__version__ = "1.4.2"
