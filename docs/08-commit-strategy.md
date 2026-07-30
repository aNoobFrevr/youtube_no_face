# Commit Strategy

Documentation and code changes should be grouped into coherent commits. For changes spanning several files, prefer Git data API tree commits so all related paths are applied atomically. When the connector only exposes the Contents API for a task, record that the result is a sequence of commits rather than claiming a single multi-file commit.
